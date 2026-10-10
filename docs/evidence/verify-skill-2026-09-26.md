# 검증 스킬 verify-stockdesk 실행 증거 (2026-09-26)

T0-1 검증 스킬과 T0-3 상시 지시를 만든 뒤, 스킬이 약속한 대로 동작하는지 확인한 기록이다. 설계는 `docs/superpowers/specs/2026-09-26-t0-verification-loop-design.md`, 구현 계획은 `docs/superpowers/plans/2026-09-26-t0-verify-stockdesk.md`에 있다. 증거 폴더(`.verify-artifacts/`)는 git에 올리지 않으므로, 아래 경로는 PM 로컬 기준이다.

## 1. 처음부터 끝까지 한 번에 (PM, Claude)

| 명령 | 종료 코드 | 결과 |
|---|---|---|
| `scripts/verify/stack.sh up` | 0 | `up: ok project=stockdesk-verify port=3334` |
| `scripts/verify/stack.sh doctor` | 0 | `doctor: ok profile=local jev=false port=3334` |
| `python3 scripts/verify/f1_accounts.py` | 0 | `F1: PASS`, 증거 `20260926T021213Z-03ea-F1/transcript.json`(8단계, `member` 행 1) |
| `python3 scripts/verify/f2_backtest.py` | 0 | `F2: PASS`, 증거 `20260926T021214Z-5437-F2/transcript.json` |
| `scripts/verify/stack.sh down` | 0 | `down: ok 익명 볼륨 1→1`, 남은 `stockdesk-verify` 컨테이너 0개 |

정리 후에도 두 증거 폴더는 남아 있었다.

## 2. 안전 장치 확인 (계획 Review Focus)

| 확인 | 방법 | 결과 |
|---|---|---|
| 남의 인스턴스 주행 거부 | 3334에 `python3 -m http.server`를 띄우고 doctor | `frontend 컨테이너가 없습니다`, 종료 코드 2 |
| 과금 변수 차단 | 셸에 `JEV_ENABLED=true`, 가짜 `TYPESAFE_API_KEY`를 둔 채 up | 컨테이너 안 `JEV_ENABLED=false`, 키는 빈 값 |
| 기준 없이 정리 | `pre-dangling.txt`를 치우고 down | `기준 없음(up 기록 없음)`, 종료 코드 0 |
| 증거의 비밀 가림 | F1 transcript 검사 | 비밀번호 `***` 2곳, 원본 비밀번호 0건, csrf `***` 3곳 |
| 연속 실행 | F1 2회 연속, 동시에 2회 | 모두 PASS, 동시 실행도 증거 폴더가 따로 생김 |
| PM 로컬 스택 보호 | `stock-portfolio-local` 컨테이너 목록 전후 비교 | 변화 없음 |

## 3. 구현 중 발견하고 고친 결함

- **bash 변수 뒤 비ASCII 문자**: `"$before→$after"`에서 bash가 `→`의 첫 바이트까지 변수 이름으로 읽어 `unbound variable`로 멈췄다. `${before}→${after}`로 고쳤다.
- **가짜 전제 충족**: nginx가 모르는 경로에도 `index.html`을 200으로 준다. 그래서 `/health` 200만으로는 백엔드 응답인지 알 수 없었다. F1은 본문 `{"status": "ok"}`까지 확인한다.
- **증거 덮어쓰기**: 같은 초에 실행하면 증거 폴더 이름이 겹쳐 앞 증거가 사라졌다. 폴더 이름에 무작위 네 글자를 붙였다. 단위 테스트는 RED→GREEN으로 확인했다.
- **스킬이 git에 안 올라감**: `.gitignore`의 `.claude/`가 레포 스킬을 막고 있었다. `.claude/*`와 `!.claude/skills/`로 바꿨다.

## 4. 다른 모델의 독립 재현 (Codex, 교차 모델 검증 겸 스킬 평가)

Codex CLI 0.157.0(`workspace-write` 샌드박스, 네트워크 허용)에 평범한 요청 한 줄을 줬다. "평가"라는 말과 스킬 경로는 알려 주지 않았다: "백테스트 계산 영수증 기능이 실제로 제대로 도는지 확인해 줘. 레포에 정해진 확인 절차가 있으면 그대로 따르고…".

| 항목 | Codex 보고 | PM 재확인 |
|---|---|---|
| 절차 발견 | `AGENTS.md`에서 스킬을 찾아 따름 | 실행 기록상 `SKILL.md`, `features/README.md`, `F2-backtest.md`, `standing-orders.md`, `stack.sh`, `f2_backtest.py`를 읽음 |
| F2 판정 | API 통과(201 → 200, 같은 영수증, 조회 200과 `metrics`) | 증거 `20260926T021533Z-3e51-F2/transcript.json`이 PASS. 영수증 `a73bec97…`가 PM 실행과 같다(새로 띄운 스택에서도 같은 입력이면 같은 영수증) |
| 화면 확인 | 브라우저 실행 권한 문제로 "미검증"이라고 보고, 전체 판정은 PARTIAL | 자기보고 그대로가 맞다. PASS로 부풀리지 않았다 |
| 정리 | down 완료, 파일 수정 없음 | 익명 볼륨 1→1, `git status` 변화 없음, 검증 컨테이너 0개 |
| 막힌 곳 | 첫 `up`이 `~/.docker/buildx` 쓰기로 실패해 `BUILDX_CONFIG`를 임시 폴더로 바꿔 통과 | `SKILL.md` "함정" 절에 우회 방법과 "브라우저 없으면 화면은 미검증"을 추가 |

## 5. 화면 확인 (PM, 쿠키 없는 Playwright)

`http://127.0.0.1:3334/quant.html`에서 "MA 20/50 실행 후 결과 저장"을 누르고 결과 영역을 캡처했다(`20260926T021818Z-61e9-F2/quant.png`). 지표 표와 함께 "계산 영수증 a73bec976237 · 같은 입력의 기존 실행"이 보였다. API 증거의 영수증과 일치한다.

## 한계

- 증거 폴더는 로컬 전용이라 PR에서 직접 열어 볼 수 없다. 이 문서의 표가 그 요약이다.
- 시세는 합성·교육용 샘플이다. 확인한 것은 영수증의 동일성과 흐름이지 수익률 값이 아니다.

## 6. 최종 교차 리뷰 반영 (Codex 읽기 전용 리뷰)

Codex가 중요 5건, 사소 2건을 찾았다. 중요 5건은 먼저 재현(RED)한 뒤 고치고 통과(GREEN)를 확인했다.

| 지적 | 재현 | 수정 | 확인 |
|---|---|---|---|
| 실패 메시지에 응답 본문이 들어가 csrf 값이 증거에 남음 | 단위 테스트 | 문장 속 "키: 값"의 값도 가림 | `test_run_keeps_failure_evidence_free_of_secrets` 등 통과 |
| 예상 밖 예외(HTML 응답의 `.get`)는 증거 없이 중단됨 | 단위 테스트 | 모든 예외를 FAIL로 기록 | `test_run_turns_unexpected_errors_into_recorded_failures` 통과 |
| 셸 변수가 검증 스택으로 샘 | 셸 `FRONTEND_PORT=9999`로 up하니 9999에 뜸 | `env -i`로 셸 환경을 비우고 docker 연결 변수만 넘김, doctor가 판정 모델·프로필을 판정 | 변수 4개를 넣고 up해도 3334·`jev=false`로 정상 |
| down이 남의 스택까지 지우고, env 파일이 없으면 성공 처리 | 코드 확인 | 소유 기록(`owner`), 남의 스택은 거부(2), env 파일 없으면 실패(1) | 소유 기록을 바꾸자 doctor·down·up 모두 2, 컨테이너 4개 유지. env 파일을 치우자 down 1 |
| 가드 우회(주석 속 `-v`, 이중 공백, `["innerHTML"]`, `Column( Float`) | 반례 테스트 | 주석 제거 후 판정, 공백·괄호 형태 허용 | 반례 테스트 통과, 기준값 변화 없음 |

- 같은 재현 중에 `"$PORT가"`에서 bash가 한글까지 변수 이름으로 읽는 버그가 **두 번째로** 나왔다. 같은 교정을 두 번 했으므로 CI 가드 G7로 옮겼다.
- 사소 2건은 보류했다: `.claude/skills/` 전체 추적(프로젝트 스킬 폴더라 의도된 범위), F2가 모든 404를 데이터 부족으로 분류하는 문제.
- 리뷰 중 다른 도구가 `.agents/skills/verify-stockdesk`에 스킬 사본을 만들었다. 두 벌이 어긋나지 않게 원본을 가리키는 심링크로 바꿨다.

## 7. 최종 리뷰 반영 (Claude 리뷰어, 수정 전 커밋 `ecf899a` 기준)

Codex 지적과 겹치는 항목은 6절에서 이미 고쳤다. 새로 나온 것만 처리했다.

| 지적 | 재현 | 수정 | 확인 |
|---|---|---|---|
| 치명: CI의 `ruff format --check`가 실패해 main 보호 아래서 머지 불가 | CI와 같은 명령으로 실패 재현 | `ruff format` 적용. 계획 Task 7에 이 단계가 빠져 있었다 | 같은 명령이 "28 files already formatted" |
| 중요: `VERIFY_BASE_URL`을 3333으로 바꾸면 PM 로컬 DB에 쓸 수 있음 | 단위 테스트 | 호스트·포트가 `127.0.0.1:3334`가 아니면 주행 전에 UNMET | 테스트 통과, 실제로 3333을 주면 종료 코드 2이고 요청 0건 |
| 개선: 소유 기록 파일 대신 compose `working_dir` 라벨 | 리뷰용 작업 폴더(다른 체크아웃)에서 실제로 스택을 띄움 | 라벨로 소유를 판정해 상태 파일을 없앰 | 이 체크아웃의 doctor·down·up이 모두 2, 컨테이너 유지. 띄운 쪽에서 정리한 뒤 전 과정 통과 |

보류한 사소 항목(다음에 해당 파일을 고칠 때 처리)은 다음과 같다.
- doctor 일부 조회 실패 시 메시지 없이 종료 코드 1로 끝남
- F2의 404 세분화
- `outerHTML`·`insertAdjacentHTML`(각 2곳)을 G1 범위에 넣기(S4의 XSS 정리와 함께)
- 증거 폴더가 실행 위치 기준
- `.claude/skills/` 추적 범위
