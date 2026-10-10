# 모바일 점검 중단 복구 — 2026-09-27

후속 승인으로 PR #46을 병합·배포했고, [운영 반영 기록](public-demo-release-2026-09-27.md)에 공개 모바일 재확인 결과를 남겼다. 아래의 승인 범위·로컬 상태는 각 검증 당시 기록이다.

## 승인과 기준 상태

- 사용자 요청: Claude Code 중단 지점 확인 후 “이어서 해봐. 그리고 기록 기억 제대로 해줘.”
- 원본 Claude 세션: `fdeeed87-4614-4ac7-a306-1a30acd0ace7`. Orca `c52f3ea3`는 사용자가 제공한 연결 ID이며 이번 조사에서 앱 메타데이터로 독립 확인하지 않았다.
- 현재 Codex 세션: `01a0e1ca-1353-7c13-bce2-f29f8c360330`.
- 기준: `fb86eea9ae502db532c3e3ef8267716234ebfa12`(PR #45), 원본 체크아웃은 clean `main`.
- 수정 위치: `/Users/noah/portfolios/stock-coin-trade-mobile-recovery`, 브랜치 `fix/mobile-recovery`.
- 승인 범위: 모바일 문제 재현·수정·검증과 기록. commit/push/PR/merge/배포는 이번 요청으로 수행하지 않는다.

## 복원한 중단 지점

원본 로그: `/Users/noah/.claude/projects/-Users-noah-portfolios-stock-coin-trade/fdeeed87-4614-4ac7-a306-1a30acd0ace7.jsonl`.

| KST | 상태 | 원본 근거 |
|---|---|---|
| 15:43~15:44 | SiteDownAlarm 시험 ALARM 및 자동 OK 전환, SNS action 성공. Gmail 두 메일 모두 `INBOX` | JSONL 35426·35435행 |
| 15:45 | 구독 confirmed=1, pending=0, 경보 두 개 OK 기록 | JSONL 35453행 |
| 15:46 | 메일 시험 완료를 사용자에게 보고 | JSONL 35554행 |
| 16:05:37 | 모바일 워커 `a94797ea8e5ba870d` 결과 반환 | JSONL 35560행 |
| 16:05:38 | 메인 Claude 사용량 제한. 모바일 결과의 리더 검토·수정·최종 보고 미실행 | JSONL 35568행 |

메일은 당시 실행을 입증한 역사 기록이다. 이번 작업에서 메일 시험이나 AWS 설정 변경을 반복하지 않는다.

## 이어서 수행할 범위

1. 기존 모바일 증거의 768px→809px 확대(index/quant), 390px 분석 제목 겹침을 현재 기준 소스에서 재현하고 원인을 확인한다.
2. 관련 CSS를 최소 수정하고 실제 작은 조작 버튼·글자의 치수를 재확인한다.
3. 전용 `stockdesk-verify` 스택에서 360·390·768·1280px 화면과 로그인 후 보유·이력·계정 페이지를 주행한다.
4. 작성자와 별도 리뷰, 리더 재검증, 스택 정리 및 메모리 인계를 남긴다.

기존 증거: `/Users/noah/portfolios/stock-coin-trade/.verify-artifacts/20260927-mobile-audit/`. 이 폴더는 읽기 전용으로 보존한다. 새 증거는 이 worktree의 `.verify-artifacts/mobile-recovery/`에 둔다.

## 검증과 최종 상태

모바일 레이아웃 수정은 로컬 검증과 독립 리뷰를 완료했다. 공개 서버에는 반영하지 않았다. 아래 미검증 항목을 전체 앱 통과로 바꾸지 않는다.

- 수정 대상: `frontend/css/style.css`, `frontend/css/analysis.css`, `frontend/css/quant-lab.css`, `frontend/trade/stock.html`.
- 헤더가 줄바꿈되지 않아 768px 레이아웃이 확대됐다. 로컬 비로그인 프로필에서는 기존 공개 측정 809px와 달리 835px 이상으로 재현됐다. 정적 자원 로드 후 901px 경계의 추가 넘침도 확인해 줄바꿈 범위를 1023px까지 조정했다.
- 분석 화면은 모바일 그리드가 sidebar 행을 1px로 줄였다. 내용 높이를 유지하고, 좁은 화면에서는 기존 sidebar 스크롤을 35dvh 안에서 사용해 목차와 본문을 함께 볼 수 있도록 했다.
- 실제 작은 헤더·퀀트·주식 조작 영역을 확대했다. 검색창은 테두리 안쪽 높이까지 44px가 되도록 외곽을 46px로 잡았다.
- 독립 소스 리뷰에서 발견한 긴 분석 메뉴와 768px 조작 크기 누락을 반영했다. 마지막 소스 검토는 새 차단 오류 없음이며, 실행 검증과 구분한다.
- 리더 실행: `docker run --rm -v "$PWD":/repo -w /repo sct-test:dev python -m pytest -q -m 'not integration' tests/policy` → 종료 코드 0, 14 passed. 증거: `.verify-artifacts/mobile-recovery/policy-check.log`.

### 최종 실행 증거

모든 명령의 작업 디렉터리는 이 문서의 수정 worktree다. 최종 소스 4파일의 diff SHA-256은 `efb33b8ea570a94a6827ca8bca05ba9ea4552f1ca54f2283da7b3a60f687bdaf`이며, 파일별 해시는 `.verify-artifacts/mobile-recovery/source-state.json`에 있다. 리더가 로컬 서버 응답 해시와 대조해 4파일 모두 일치함을 확인했다(`leader-served-hashes.json`).

| 실행 | 결과 | 증거 (`.verify-artifacts/mobile-recovery/` 아래) |
|---|---|---|
| `scripts/verify/stack.sh doctor` | exit 0, local, 판정 모델 false, 포트 3334 | `receipt.json` 및 리더 도구 응답 |
| `node .verify-artifacts/mobile-recovery/mobile-layout-check.cjs after-v3 360,390,768,900,901,1022,1023,1024,1280` | exit 0, 63조합. 문서폭 일치·제목 겹침 0·주요 터치 높이 충족. 페이지 스크립트 오류 0 | `after-v3/summary.json` 및 PNG |
| `node .verify-artifacts/mobile-recovery/mobile-layout-check.cjs leader-check 390,1023,1024` | 리더 직접 exit 0, 21조합 PASS | `leader-check.log`, `leader-check/` |
| `node .verify-artifacts/mobile-recovery/mobile-auth-check.cjs auth-after-v3` | exit 0. 가입→Mailpit 인증→로그인→보유·거래이력·계정 화면(360/390/768), 로그인 헤더 경계 1022/1023/1024, 임시 계정 탈퇴 | `auth-after-v3/results.json` 및 PNG |
| 주식 컨트롤 개별 측정·그룹별 첫 버튼 클릭 | 기간 5·MA 4·보이는 비율 7·하위 탭 5·관심 탭 2: 390/768에서 높이 44px 이상 | `stock-inventory-v2/result.json` |
| 위 정책 검사 명령 최종 소스 재실행 | exit 0, 14 passed | `policy-final.log` |
| `scripts/verify/stack.sh down` | exit 0, 익명 볼륨 1→1, 검증 프로젝트 컨테이너·볼륨 0 | `cleanup.log`, `receipt.json` |

Node는 기존 설치된 Playwright를 사용했다. 모듈 탐색이 필요한 셸에서는 `NODE_PATH=/Users/noah/.local/lib/node_modules`를 붙인다. 새 의존성은 추가하지 않았다. 재실행 전 `stack.sh up`과 `doctor`가 필요하다.

리더는 최종 390px 분석·주식 및 768px 메인 스크린샷도 직접 확인했다. 분석 목차는 내부 스크롤로 끝 항목까지 포커스 이동 가능하며, 첫 본문 제목도 초기 화면에 보인다.

### 남은 한계

- 물타기 모달의 비율 버튼 4개는 같은 CSS가 적용되지만, 현재 샘플 데이터에서는 모달이 열리지 않아 실제 조작은 미검증이다.
- 로그인한 보유 화면은 경로·제목·너비를 확인했지만 자산 차트 렌더링은 확인하지 못했다. 별도 비로그인 진단에서 Highcharts CDN 403을 관측했으나 인증 세션의 원인으로 확정할 수 없다. 거래이력은 0건 상태로 검증했다.
- 작은 단축키·종목 코드·STEP 배지는 유지했다. 모든 텍스트를 확대하는 디자인 변경이나 전체 기능 검증은 수행하지 않았다.
- 소스 리뷰 영수증: `review-receipt.json`, `review-decisions.tsv`. 워커 실제 역할·모델·effort 및 라우팅 기록: `../mobile-recovery-routing/spawned.json`. 모델 라우팅의 낮은 확신 뒤 명시적 리더 예외 배정을 사용했으며 라우팅 선택 성공으로 보고하지 않는다.

## 검증 해석

- `before/`는 수정 전 원본으로 보존한다. 초기 검사 스크립트는 분석 h1 선택자를 잘못 잡았으므로 `headingOverlap:null`은 정상이라는 뜻이 아니다. sidebar 1px와 실제 h1/h2 좌표가 별도 재현 근거다.
- `after/`, `after-v2/`는 중간 후보의 증거이며 최종 통과 기록으로 사용하지 않는다.
- 닫힌 메뉴·의도한 내부 스크롤·작은 장식 배지를 전부 같은 결함으로 세지 않는다. 실제 조작 요소는 존재 개수·치수·클릭 가능 여부를 확인한다.
- 이 검증은 전용 로컬 스택이다. 공개 프로필·실계정·실거래·운영 데이터 검증으로 확대하지 않는다.

## 이어지는 요청

같은 세션에서 사용자가 로그인·회원가입 안내에 공용 데모 계정을 제공하고 실제 로그인할 수 있도록 요청했다. 이 추가 작업은 위 모바일 완료 기록과 구분해 진행한다. 일반 비밀번호 정책을 완화하거나 기존 관리자 계정을 데모로 노출하지 않는다. 공용 계정의 변경·삭제·키 발급 경로를 먼저 확인한 뒤 구현·검증한다.
