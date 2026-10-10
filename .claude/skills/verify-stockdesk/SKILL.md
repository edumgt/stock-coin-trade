---
name: verify-stockdesk
description: stock-coin-trade 앱(Flask + nginx + MariaDB + PostgreSQL)을 전용 검증 스택 stockdesk-verify(127.0.0.1:3334)에 띄우고, 기능 지도대로 주행해 증거를 남기고, 자기가 띄운 것만 정리한다. "고쳤다·동작한다·통과했다"를 말하기 전에, PR 전 검증, 워커 결과 재검증에 쓴다.
---

# verify-stockdesk

이 스킬은 앱이 실제로 동작하는지 증거로 보이는 절차다. 빌드나 단위 테스트 통과는 동작의 증거가 아니다.

## 규칙

- 검증은 `stockdesk-verify` 프로젝트(포트 3334)에서만 한다. 로컬 스택 `stock-portfolio-local`(3333)은 PM 소유라 조작하지 않는다.
- 자기가 띄우지 않은 인스턴스는 주행하지 않는다. doctor가 확인한다.
- 화면 확인은 쿠키 없는 Playwright로 한다. Ego는 노아의 로그인 세션을 쓰므로 검증 주행에 쓰지 않는다.
- 증거가 없으면 "통과"라고 쓰지 않는다. 보고에는 명령, 종료 코드, 증거 경로를 붙인다.
- 검증 중에는 이 체크아웃과 `.verify-artifacts` 밖에 쓰지 않는다(graphify save-result, vault·메모리 기록 금지).

## Launch

`scripts/verify/stack.sh up`
- 첫 실행 때 `.env.verify`(권한 600)를 만든다. 값은 출력하지 않는다.
- 이미지를 빌드하고 frontend·backend·init·DB를 띄운다. worker는 띄우지 않는다.
- 셸 환경변수는 스택에 넘기지 않는다. 앱 설정은 `.env.verify` 값만 쓴다(`JEV_ENABLED` 같은 과금 변수가 새지 않는다).
- 스택은 한 번에 한 체크아웃만 쓴다. 다른 체크아웃이 쓰는 중이면 종료 코드 2로 멈춘다. 띄운 체크아웃은 compose가 컨테이너에 붙이는 `com.docker.compose.project.working_dir` 라벨로 확인한다.
- 준비되면 `up: ok`를 출력한다. 첫 빌드는 몇 분 걸린다.

## Doctor

`scripts/verify/stack.sh doctor`
- 이 체크아웃이 띄운 스택인지(working_dir 라벨), 포트 3334의 주인이 이 프로젝트 컨테이너인지, `/health`, init 종료 코드 0, 프로필 `local`, 판정 모델 꺼짐을 확인한다.
- `ok`가 아니면(종료 코드 2) 주행하지 않고 원인을 보고한다.

## Drive

`.claude/skills/verify-stockdesk/features/README.md`(저장소 기준 경로, 숨김 폴더라 `rg --files`에 안 잡힌다)에서 기능을 고르고, 그 파일의 "주행" 절을 따른다.
- API 흐름은 `python3 scripts/verify/f<번호>_*.py`로 증명한다. 종료 코드는 0 통과, 1 실패, 2 전제 불충족이다.
- 통합 테스트(`stack.sh itest`)는 코드 수준 보조 증거다. HTTP 주행 스크립트를 대신하지 않는다.
- 화면은 Playwright로 연다. 선택자는 접근성 이름, `id`, `data-*`를 쓰고 좌표는 쓰지 않는다.

## Evidence

- 스크립트가 `.verify-artifacts/<UTC시각>-<무작위4자>-<기능ID>/transcript.json`을 쓴다. 쿠키, 토큰, 비밀번호, csrf는 `***`로 가린다. 실패 메시지 같은 문장 속의 값도 가린다.
- 예상 밖 오류(응답 형식이 다름 등)도 판정 FAIL과 함께 증거를 남긴다.
- 화면 캡처와 화면에서 읽은 값(Playwright `evaluate` 결과 등)은 같은 폴더에 파일로 저장한다. 도구 결과가 실행 기록에 남지 않으므로, 파일이 없으면 그 화면은 "미검증"으로 보고한다.
- 보고에는 판정과 이 경로를 쓴다.

## Cleanup

`scripts/verify/stack.sh down`
- 자기가 띄운 스택만 `down -v`한다. 다른 체크아웃이 띄운 스택이면 거부(종료 코드 2), `.env.verify`가 없으면 실패(1)다. 익명 볼륨 수가 up 때보다 늘어도 실패(1)다.
- 증거 폴더는 지우지 않는다.
- 프로세스를 이름으로 죽이지 않는다.

## 함정

- 샌드박스 안의 에이전트(예: Codex `workspace-write`)는 `~/.docker/buildx`에 쓸 수 없어 `up`이 실패할 수 있다. 그때는 `mkdir -p /private/tmp/stockdesk-verify-buildx-$UID && BUILDX_CONFIG=/private/tmp/stockdesk-verify-buildx-$UID scripts/verify/stack.sh up`으로 올린다.
- 검증 스택에는 Mailpit이 있어 가입에 메일 인증이 필요하다. 메일은 `common.mail_link(주소, 경로)`로 읽는다(UI 포트는 `docker port`로 찾는 임의 포트).
- 브라우저를 띄울 수 없는 환경이면 화면 확인은 "미검증"으로 보고한다. API 스크립트의 판정은 그대로 유효하지만, 화면까지 "통과"라고 쓰지 않는다.

## Helpers

| 명령 | 역할 |
|---|---|
| `scripts/verify/stack.sh up\|doctor\|down` | 스택 수명주기 |
| `scripts/verify/stack.sh itest [pytest 인자]` | 검증 스택 DB로 통합 테스트(`-m integration`) |
| `python3 scripts/verify/f1_accounts.py` | F1 회원 |
| `common.mail_link(to, path)` | 검증 스택 Mailpit에서 링크 찾기 |
| `python3 scripts/verify/f2_backtest.py` | F2 백테스트 영수증 |
| `python3 scripts/verify/f5_disclosures.py` | F5 공시 고지·관심 종목(예시 행을 넣고 지운다) |
| `scripts/verify/common.py` | 공용 도구(직접 실행하지 않음) |

구조와 형식은 cursor/plugins pstack(MIT)의 create-verification-skill을 참고해 새로 썼다.
