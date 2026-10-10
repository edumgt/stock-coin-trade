# AWS 공개 데모 배포 — 2026-09-25

- 포트폴리오 계획 Phase 6의 실행 기록이다. 준비 단계는 [AWS 공개 데모 준비](aws-demo-prep-2026-09-25.md)에 있다.
- 주소: <https://43-201-225-127.sslip.io>
  - 도메인이 없어 sslip.io 호스트명을 쓴다. 이 이름은 탄력적 IP `43.201.225.127`로 풀린다.
  - 도메인을 사면 GitHub `production` 환경의 `SITE_ADDRESS`만 바꾸고 다시 배포한다.
- 구성: [ADR-0003](../adr/0003-aws-demo-topology.md) 그대로(스택 `stockdesk`, 서울)

## 선택과 근거

| 항목 | 값 | 근거 |
|---|---|---|
| 인스턴스 | t3.small | 서울 온디맨드 $0.026/h(가격 API, 2026-09-25). EBS 50 GiB($0.0912/GB-월)와 공인 IPv4를 더해 월 약 $28. 배포 후 메모리 사용 0.68 GiB, 스왑 0 |
| 예산 | 월 35 USD | 실제 80%·예상 100%에서 메일. 예전 절차서 예시(t3.medium + 30 USD)는 월 약 46 USD라 매달 경보가 울렸다 |
| EC2·S3 | 스택 전용 | 원본 쪽 EC2·S3와 분리. 템플릿의 수명 주기 규칙(`old-versions`)이 버킷 전체에 걸리고, IAM이 버킷 ARN 단위라 공유하면 서로 영향을 준다 |
| AI 리서치 | 꺼짐 | SSM에 AI 파라미터를 넣지 않았다. 켤 때는 [배포 절차](../deploy/aws.md) 2절의 AI 항목을 넣고 다시 배포한다 |

## 순서

1. SSM Parameter Store에 SecureString 8개를 넣었다(`/stock-coin-trade/prod/`). 값은 `openssl rand -hex`로 만들어 바로 넣고 출력하지 않았다.
2. 변경 세트를 먼저 만들고 확인한 뒤 실행했다. 리소스 22개, 모두 Add, `CREATE_COMPLETE`.
3. GitHub `production` 환경과 변수 6개(스택 출력값 + `SITE_ADDRESS`)를 넣었다.
4. Deploy 워크플로를 실행했다. 첫 두 번의 시도는 아래 결함 때문에 실패했다.

## 실제 환경에서만 드러난 결함

| 결함 | 증상 | 수정 |
|---|---|---|
| XFS 라벨 길이 | user data가 `mkfs.xfs -L stockdesk-data`에서 멈췄다("label (maximum 12 characters)"). 그 뒤의 데이터 볼륨 마운트·Compose 설치·스왑이 건너뛰어졌다 | 라벨을 `stockdesk`로 줄였다(PR #11). 스택 업데이트 뒤 `cloud-init clean` + 재부팅으로 user data를 처음부터 다시 실행해 확인했다 |
| OIDC subject 형식 | `configure-aws-credentials`가 `Not authorized to perform sts:AssumeRoleWithWebIdentity`. 저장소가 `use_immutable_subject=true`라 sub가 `repo:Noah-TaeHwan@153077902/stock-coin-trade@1372388177:environment:production` 형식이었다 | `GitHubRepository` 기본값을 불변 형식으로 바꾸고 패턴이 `@ID`를 받게 했다(PR #12). GitHub 설정은 되돌리지 않았다. 불변 형식은 저장소 이름 변경·재생성으로 신뢰가 넘어가는 것을 막는다 |

준비 단계에서 미검증이던 "Nitro NVMe 시리얼 = 볼륨 ID"는 실제로 맞았다(`nvme1n1` 시리얼 `vol0b7267f1456efaffc`).

## 확인 결과 (배포 run 36139356670 이후)

- 워크플로: OIDC 인증, 이미지 빌드·푸시, 릴리스 업로드, SSM으로 `deploy.sh` 실행, HTTPS 스모크 테스트가 모두 success
- 보안 그룹 인바운드: 80/tcp, 443/tcp, 443/udp만. IMDSv2 필수, SSM Online
- `curl https://…/health` → 200. 인증서 발급자 Let's Encrypt(YE1), 만료 2026-12-24(Caddy가 자동 갱신). `http://` → 308로 https 이동
- 화면 `/`, `/member/login.html`, `/quant.html`, `/arbitrage.html`, `/research-agent.html`, `/hts.html` → 모두 200
- `/api/quant/sources` → `profile: public`, 사용 소스는 `synthetic`, `synthetic_sql`뿐
- `/api/agent/status` → `enabled: false`
- 같은 입력으로 백테스트 POST 두 번 → 201(새 영수증 저장) 다음 200(같은 영수증 재사용), 소스 `synthetic_sql`
- CloudWatch 로그 그룹 `/stockdesk/app`에 컨테이너 8개의 스트림이 생겼다
- Budgets `stockdesk-monthly` 35 USD, 알림 ACTUAL 80%·FORECASTED 100%
- 호스트 메모리: 전체 1.9 GiB 중 사용 0.68 GiB, 스왑 사용 0

## 하지 않은 것

- 관리자 계정 생성(`create-admin`): 비밀번호를 사람이 직접 넣어야 해서 Noah가 Session Manager로 실행한다([배포 절차](../deploy/aws.md) 5절)
- 자동 롤백을 운영 환경에서 일부러 일으켜 보는 것. 로컬 실측은 준비 단계에서 했다
- 실제 청구 금액 확인: 월 비용은 단가로 계산한 추정치다. 첫 청구서에서 확인한다
- DB 백업·복구 리허설(준비 단계와 같음)
