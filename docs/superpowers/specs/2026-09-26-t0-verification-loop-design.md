# T0 검증 루프와 가드레일 — 설계

- 작성: 2026-09-26, PM 에이전트(Claude Code)
- 상위 계획: 서비스 고도화 프로그램(T0 → S1 → S3 → S4 → S5, S2 병행)
- 상태: 노아 승인(2026-09-26)

## 쉬운 요약 (노아용)

에이전트가 일을 마쳤다고 할 때 그 말을 믿을 근거가 필요합니다. 오늘 작업자 에이전트들이 세 번 실수했습니다.
- 테스트용 저장 공간을 두 번 치우지 않았습니다.
- 다른 작업 공간과 공유되는 임시 보관함을 잘못 썼습니다.
- 치웠다고 보고했는데 실제로는 남아 있었습니다.

세 실수 모두 "앱을 띄우고, 눌러 보고, 증거를 남기고, 자기가 띄운 것만 치우는" 절차가 문서로 정해져 있지 않아서 생겼습니다.

T0는 이 절차를 **누구나(어떤 에이전트든) 같은 방식으로 실행할 수 있는 도구**로 만듭니다. 또 사람이 매번 말로 지적하던 규칙 몇 가지를 **자동 검사**로 바꿉니다. 참고한 것은 Cursor 엔지니어 Lauren Tan의 강연과 공개 도구 pstack(MIT 라이선스)입니다. 핵심은 "신뢰는 검증에서 나온다", "말로 한 규칙은 자동 검사로 바꿔라"입니다.

노아님이 하실 일은 없습니다. 결과는 PR의 증거로 확인하시면 됩니다.

## 배경과 근거

- 강연(재업로드 `youtube.com/watch?v=ONeM6YDmvqA`, 자막 기준)
  - 7:48 검증 스킬이 가장 중요하다: 에이전트가 앱을 실제로 실행하고 증거를 남겨야 한다
  - 12:14 기능 지도: 각 기능에 어떻게 도달하고 무엇이 동작의 증거인지
  - 45:25 강제 층위: 아키텍처·CI가 문서 규칙보다 강하다
  - 49:50 사람이 리뷰 코멘트로 불변식을 지키면 코드 냄새다
- pstack: `github.com/cursor/plugins` 커밋 `ecc249f1e306fc64ddf83c7bed16cacf7c2239db`의 `pstack/`
  - 참고 문서: `skills/create-verification-skill/SKILL.md`, `references/feature-map-example/`, `skills/show-me-your-work/SKILL.md`, `skills/principle-encode-lessons-in-structure/SKILL.md`
  - 구조와 형식만 참고하고 문서는 새로 쓴다. 옮겨 쓴 부분이 생기면 해당 파일에 MIT 고지와 출처를 단다.
- pstack을 통째로 설치하지 않는 이유: Cursor 전용 기능(`/loop`, cloud agent, Bugbot, Task `environment`)을 전제한다. 이미 쓰는 도구 층(Superpowers, ECC, Ponytail, Agency-Agents, Orca)과 역할이 겹친다.

## T0-1 검증 스킬 `verify-stockdesk`

### 파일

| 경로 | 역할 |
|---|---|
| `.claude/skills/verify-stockdesk/SKILL.md` | 에이전트용 절차: Launch·Doctor·Drive·Evidence·Cleanup·Helpers |
| `.claude/skills/verify-stockdesk/features/README.md` | 기능 지도 색인, 공통 전제·주행 관례·증거 규칙 |
| `.claude/skills/verify-stockdesk/features/F1-accounts.md`, `F2-backtest.md` | 기능별 지도(네 절 고정). 아래 표의 F3~F5는 해당 기능을 고칠 때 추가 |
| `compose.verify.yml` | 검증 전용 덧씌움: 포트 3334, Mailpit 서비스 |
| `scripts/verify/stack.sh` | `up` · `doctor` · `down` 하위 명령 하나 |
| `scripts/verify/f1_accounts.py` 등 | 기능별 주행 스크립트(표준 라이브러리 `urllib`만) |
| `AGENTS.md`(레포 루트, 새로 만듦) | 다른 도구가 스킬과 상시 지시를 찾는 입구, 몇 줄 |
| `.gitignore` | `.verify-artifacts/` 추가 |

### 격리 원칙
- 검증은 **전용 compose 프로젝트 `stockdesk-verify`**에서만 한다.
  - 명령 형태: `docker compose -p stockdesk-verify --env-file .env.verify -f docker-compose.yml -f compose.portfolio.yml -f compose.verify.yml --profile local-db ...`
  - 볼륨 이름은 프로젝트 이름이 앞에 붙으므로 노아·PM의 로컬 스택(`stock-portfolio-local`, 3333)과 섞이지 않는다.
- `.env.verify`는 첫 `up` 때 무작위 값으로 만든다(권한 600, gitignore됨, 값은 출력하지 않음). 브로커·클라우드 키는 넣지 않는다.
- 자기가 띄우지 않은 인스턴스는 조작하지 않는다. Doctor가 컨테이너의 프로젝트 라벨이 `stockdesk-verify`인지 확인한다.

### SKILL.md 절
- **Launch**: `scripts/verify/stack.sh up`
  - 실행 전 `docker volume ls -qf dangling=true | wc -l` 값을 `.verify-artifacts/<run>/pre-dangling.txt`에 기록한다.
  - `up -d --build --wait`로 띄우고, `/health` 200이 나오면 준비 완료로 본다.
- **Doctor**: `scripts/verify/stack.sh doctor`
  - 포트 3334의 응답자가 `stockdesk-verify` 프로젝트 컨테이너인지 확인한다.
  - `/health` 200, `/api/member/me`의 `profile` 값, `init` 컨테이너 종료 코드 0을 확인한다.
  - 하나라도 실패하면 주행하지 않는다.
- **Drive**:
  - 기능 지도의 주행 절을 따른다.
  - API 흐름은 `scripts/verify/f*.py`로 증명한다. 재실행할 수 있고, 판정은 기대값을 문자 그대로 비교한다.
  - 화면은 쿠키 없는 Playwright로 연다(Claude는 Playwright MCP). Ego는 노아의 로그인 세션을 쓰므로 검증 주행에 쓰지 않는다.
  - 선택자는 접근성 이름·`id`·`data-*`를 쓰고 좌표는 쓰지 않는다.
- **Evidence**: `.verify-artifacts/<UTC시각>-<기능ID>/`에 저장한다.
  - 요청·응답 기록(JSON, 쿠키·토큰 값 가림), 화면 캡처, 필요한 경우 DB 조회 결과(행 수)
  - 증거 없는 "통과"는 통과가 아니다.
- **Cleanup**: `scripts/verify/stack.sh down`
  - `stockdesk-verify` 프로젝트만 `down -v --remove-orphans`한다.
  - 이후 dangling 볼륨 수가 실행 전과 같은지 비교하고, 다르면 실패로 보고한다.
  - 다른 프로젝트의 볼륨은 지우지 않는다. 증거 폴더는 남긴다.
- **Helpers**: 스크립트마다 사용법 한 줄과 종료 코드(0 통과, 1 실패, 2 전제 불충족)를 적는다.

### 기능 지도 (지금은 F1·F2만, F3~F5는 그 기능을 다음에 고칠 때 추가)
각 파일은 다음 네 절을 이 순서로 가진다.
- `하위 기능`
- `사용자 경로`
- `주행(전제 조건 포함)`: 사용자 행동, 정확한 명령, 관찰되는 결과를 한 줄씩
- `함정`

| ID | 기능 | 증거의 핵심 | 알려진 함정 |
|---|---|---|---|
| F1 | 회원: 가입·로그인·`/me`·로그아웃 (S1이 인증·재설정·탈퇴로 확장) | 응답 코드와 본문, `member` 행 수 | public 프로필은 가입이 닫혀 있음(S1-①) |
| F2 | 퀀트 백테스트와 계산 영수증(`/quant.html`) | `receiptId`가 같은 입력에서 같은 값, 지표 필드 존재 | 합성 데이터 기준 |
| F3 | 명령 바(6자리 코드, 명령어, 자연어) | 이동 URL | 판정 모델 꺼짐이면 도움말로 떨어짐(정상) |
| F4 | 김프 매트릭스와 공지 경고(`/arbitrage.html`) | `notices`·`noticeStatus` 필드 | 외부 거래소 네트워크 의존 → 실패는 "전제 불충족"으로 보고 |
| F5 | 공시 화면(`/events.html`, `DISC`) | `/api/disclosures` 응답 형태 | DART 키 없으면 빈 목록(정상) |

### 완료 판정
- 스킬 지시만 따라 `up → doctor → F1 주행 → 증거 → down`을 한 번에 통과한다.
- 정리 후 증거 폴더가 남아 있고, dangling 볼륨 수가 변하지 않는다.
- Evidence Collector(Agency-Agents)가 스킬만 읽고 F2를 독립적으로 한 번 주행해 같은 판정을 낸다(작성자와 검증자 분리).

## T0-2 CI 가드 (S1의 PR들과 함께 들어감)

- 파일: `tests/policy/test_guards.py` 하나와 기준값 `tests/policy/guard_baseline.json`.
- 방식은 **래칫**이다. 규칙별로 "파일 → 허용 개수"를 동결하고, 개수가 늘면 실패한다. 줄면 기준값을 낮추라는 메시지로 실패한다. 줄어든 상태를 고정하기 위해서다.
- 첫 규칙 묶음(사고가 났거나 보안 경계인 것만):

| 규칙 | 찾는 패턴 | 현재 | 목표 |
|---|---|---|---|
| G1 안전하지 않은 HTML 삽입 | `frontend/`의 `innerHTML =`·`+=` | 216곳/24파일 | 새 대입 금지. 줄이는 작업은 S4에서 |
| G3 금액·수량 Float | `Column(Float` | 7개 | 신규 금지 |
| G4 대화·이력성 주석 | `*.py`·`*.js`의 주석 안에 있는 `노아가`, `Noah said`, `이번 PR`, `리뷰에서 지적` 류(문서 파일은 대상 아님) | 먼저 측정. 0건이면 규칙을 만들지 않는다 | 실제로 생기면 추가 |
| G5 외부 HTTP timeout 누락 | `ruff check --select S113 --output-format json`의 파일별 개수(자체 AST 계수기 없음) | 측정 후 동결 | 줄여 감 |

- 규칙 ID는 G1, G3, G4, G5다. G2(세션 직접 접근 금지)는 S1 보안 검토 반영으로 삭제했다. 세션 확인 훅이 쿠키의 `member_id`를 검증하므로 기존 62곳을 옮길 필요가 없다.
- 한국어 JSDoc·docstring 필수 규칙은 그대로 둔다. 강연의 "주석 전면 금지"는 들이지 않고, 근본 문제인 대화·이력성 주석만 막는다(G4).
- 구현 결과(2026-09-26, 노아 요청으로 S1에서 T0 PR로 당김): G1(219곳/25파일)·G3(7개/1파일)은 래칫으로 동결했다. G4는 측정 결과 0건이라 규칙을 만들지 않았다. G5도 0건이라 자체 계수기 대신 ruff `S113`을 켰다. 상시 지시 1번(익명 볼륨)은 G6(`docker rm`은 `-v`와 함께)으로 옮겼다.
- 새 규칙은 **같은 교정을 두 번 하게 됐을 때** 추가한다(`docs/agents/standing-orders.md`에서 승격).

## T0-3 상시 지시와 결정 로그

- `docs/agents/standing-orders.md`: 번호를 붙여 한 줄에 제약 하나. 처음 넣을 내용은 다음과 같다.
  1. 컨테이너 테스트는 `docker run --rm`, 컨테이너 삭제는 `docker rm -v`. 익명 볼륨을 남기지 않는다.
  2. worktree 사이에서 `git stash`를 쓰지 않는다(공유된다). 임시 보관은 커밋이나 패치 파일로 한다.
  3. Mac에서 파이썬 테스트는 `sct-test:dev` 컨테이너로 돌린다(`.venv` 네이티브 import 멈춤).
  4. 키·토큰·비밀 값을 출력하지 않는다. 확인은 길이·형식·일치 여부만 한다.
  5. 로컬 스택 `stock-portfolio-local`은 PM 소유다. 검증은 `stockdesk-verify`(T0-1)에서 한다.
  6. main에 직접 커밋·푸시하지 않는다. `<type>/<short>` 브랜치와 PR을 쓴다.
  7. "잔여 0", "통과" 같은 보고에는 실행한 명령과 출력 경로를 붙인다.
- Orca 워커 브리프는 이 파일을 **그대로 붙인다**.
- 워커 보고에는 `decisions.tsv`를 요구한다. 열은 `ts phase decision why evidence result`이며 한 결정에 한 행이다. 커밋하지 않고 보고에 첨부한다.
- 노아의 전역 스킬(orca-pm-loop 브리프 템플릿)에 반영하는 일은 vault 스킬 정본 절차가 따로 있으므로 이 레포 범위 밖이다. 필요하면 후속 작업으로 둔다.

## T0-4 교차 모델 검증 (S1 완료 판정에 포함)

- S1의 각 PR diff를 **Codex CLI가 읽기 전용**으로 보안 검토한다. 실패하면 Grok을 쓴다.
  - 검토 기준: 인증·세션·토큰·열거·메일 헤더 주입·삭제 누락·로그 유출
  - 도구 로그인 상태는 실행 때 확인한다. 설치는 확인했다: `codex`, `grok`, `opencode`
- 지적 사항은 PM이 분류한다(수정 / 반증 첨부 후 기각). 결과는 `docs/evidence/`에 남긴다.
- 여기에 `ecc:security-reviewer`와 Reality Checker 최종 판정을 더한다. 검증자는 작성자와 다른 모델 계열을 원칙으로 한다.

## T0-5 스킬 평가 (S1 뒤, 별도 결정)

- 대상은 `verify-stockdesk` 하나다.
- "평가 중"이라는 사실을 숨긴 자연스러운 과제를 서로 다른 모델 두 개에게 주고, 다른 계열의 채점자가 판정한다.
- 이번 PR에는 넣지 않는다.

## 범위 밖

pstack 설치, 클라우드 에이전트·자동 머지, 대규모 코드 구조 재작성(S4에서 "먼저 빼기"로 다룸), 전역 스킬 수정.

## 검증

- T0-1: 위 완료 판정 세 가지. 증거는 `docs/evidence/verify-skill-<날짜>.md`에 요약한다.
- T0-2:
  - main에서 가드 테스트가 통과한다.
  - G1 위반 한 줄을 추가한 임시 커밋에서 실패하는 것을 확인하고 되돌린다.
  - 기준값 파일이 실제 개수와 일치한다.
- T0-3: 다음 Orca 브리프에 파일이 그대로 붙었는지 PM이 확인한다.
- CI: 기존 lint·unit·통합 작업이 초록.
