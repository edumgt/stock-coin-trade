# 공용 데모 로그인 — 2026-09-27

공개 반영 후 실제 계정 생성·로그인 결과는 [운영 반영 기록](public-demo-release-2026-09-27.md)에 있다. 아래는 그에 앞서 수행한 로컬 검증이다.

## 요청과 상태

사용자가 로그인·회원가입 화면에 공개 데모 계정을 안내하고 실제 체험할 수 있도록 요청했다. 지정 정보는 `test@test.com` / `test1234`이며 공개 안내용이다.

**아래는 운영 반영 전 완료한 로컬 구현·검증 기록이다.** 기준은 `fb86eea`, 작업 위치는 `/Users/noah/portfolios/stock-coin-trade-mobile-recovery`, 검증 브랜치는 `fix/mobile-recovery`다. 검증은 커밋 전 후보에서 수행했다. 사용자가 이후 커밋·PR·병합·배포·운영 데모 생성까지 승인했으며, 운영 실행 결과는 실제 완료 후 별도로 추가한다. 앞선 모바일 수정·메일 확인 복원은 [별도 기록](mobile-recovery-2026-09-27.md)을 따른다.

## 변경

- `flask --app app create-demo`가 일반 회원인 공용 데모를 생성한다. 같은 데모는 `unchanged`, 기존 일반 계정이나 관리자 주소와 충돌하면 오류로 끝나며 덮어쓰지 않는다.
- `Member.is_demo`는 기본값 false다. 기존 `ensure_member_tables`의 멱등 컬럼 추가 절차로 `TINYINT(1) NOT NULL DEFAULT 0`을 추가한다. 이메일 문자열만으로 기존 회원을 데모로 바꾸지 않는다.
- 지정된 8자 비밀번호는 운영자용 데모 생성 경로에서만 해시한다. 일반 신규 비밀번호 정책은 15자 그대로다.
- 데모의 비밀번호 변경·재설정·탈퇴·전체 로그아웃·API 키·OpenAPI·KIS 접근을 서버에서 제한한다. 현재 세션 로그아웃과 모의 체험은 허용한다. 관리자 주소 설정이 바뀌어도 데모는 관리자 권한을 얻지 않는다.
- 데모 주소의 신규 가입은 예약 처리한다. 같은 주소의 기존 일반 회원의 복구 기능은 `is_demo` 표식이 없으면 유지한다.
- `/api/member/me?demo=1`의 `demoReady`가 true일 때만 로그인·가입 화면에 안내한다. 기존 폼 제출을 사용하는 데모 버튼을 제공하고, 모의 거래·메모가 방문자끼리 공유됨을 알린다.
- 가입이 닫혔으면 가입 폼과 일반 비밀번호 안내를 숨기고 데모 안내를 보여 준다. 열린 가입은 기존 흐름을 유지한다.
- 공개 nginx에서 차단한 `/trade/order.html`로 보내던 로그인 성공 경로를 수정했다. 명확한 local 프로필만 기존 경로로 가며 public·프로필 조회 실패는 `/trade/stock.html`로 간다.

## 실제 검증

명령의 cwd는 위 worktree이며, 아래 증거는 `.verify-artifacts/` 아래에 보존했다.

| 검사 | 결과 | 증거 |
|---|---|---|
| `docker run --rm -v "$PWD":/repo -w /repo sct-test:dev python -m pytest -q -m 'not integration'` | exit 0, **520 passed, 1 skipped, 91 deselected, 4 subtests passed** | `demo-implementation/full-unit-final.log` |
| 새 데모 테스트 형식 정리 후 재실행 | exit 0, 13 passed | `demo-implementation/demo-after-format.log` |
| `ruff check .`, CI 범위 `ruff format --check`, `node --check frontend/js/auth-pages.js`, `git diff --check` | 모두 exit 0 | `demo-implementation/ruff-final.log`, `format-final.log`, 리더 도구 응답 |
| 전용 스택 기동·doctor | local / 판정 모델 false / 3334, exit 0 | `public-demo/receipt.json` |
| 데모 생성 전 API·화면 | demoReady false, 390/768/1024 안내 숨김 | `public-demo/before/`, `20260927T083010Z-fb47-demo-before/transcript.json` |
| 실제 검증 DB에서 `flask --app app create-demo` 2회 | exit 0, created → unchanged | `public-demo/receipt.json` |
| 데모 로그인·보호 API | 유효 쿠키·CSRF로 DEMO_ACCOUNT 403 확인. isDemo true, isAdmin false, canUseKisAccount false. 현재 세션 로그아웃 200 | `public-demo/20260927T083146Z-7cee-demo-after/transcript.json` |
| 데모 안내·버튼 주행 | 390/768/1024 폭 정상, 실제 로그인 200. 리더도 별도 실행 exit 0 | `public-demo/after-final/`, `leader-after.log`, `leader-after/` |
| 일반 회원 F1 | 기존 가입·메일 인증·복구·변경·탈퇴 등 26단계 PASS | `public-demo/f1/20260927T083318Z-623e-F1/transcript.json` |
| 데모 복구/인증 메일 요청 | generic 202, 전용 Mailpit 수신 0→0 | `public-demo/mail-result.json` |
| 로컬 스택에서 가입 닫힘 설정 | signupOpen false, 가입 POST 403, 폼 숨김·데모 안내 노출, 390px 정상. 이후 정상 구성 복원 | `public-demo/signup-off/` |
| public/unknown/프로필 조회 실패 프런트 분기 | 실제 로그인 후 stock 경로 200 | `public-demo/public-landing-fixture/results.json` |
| 최종 소스와 서버 대조 | 프런트 응답·백엔드 이미지 13파일 해시 일치 | `public-demo/final-source-state.json` |

public 착지 검사는 **브라우저의 profile 메타데이터만 모사**했고, 서버는 검증 스킬이 요구하는 local 프로필이다. 실제 public 백엔드·nginx 기동이나 운영 배포 증거로 확대하지 않는다. OpenAPI의 기존 데모 API 키 거부는 단위 테스트 증거이며 실제 DB 키 생성으로 확인하지 않았다.

전체 검사 중 기존 KIS 단위 테스트 4개가 새 권한 조회로 DB 연결을 시도했다. 일반 회원 테스트 상태를 명시하고 데모 차단·네트워크 미호출 검사를 추가해 교정했다. 원래 단언은 유지했고, 최초 실패 로그 `demo-implementation/full-unit.log`도 보존했다. 네트워크 전용 Upbit 검사 1개와 integration 표시 91개는 위 단위 실행에 포함되지 않는다.

## 검토와 운영 경계

- 별도 `noah-reviewer`가 주소 선점·기존 회원 복구·관리자 승격·계정 인수·KIS/API 키 경로·DB 세션 사용·최종 UI·테스트 단언을 검토했다. 확인된 지적을 반영했고 최종 신규 차단 오류는 없었다. 리뷰 자체는 실행 증거와 구분한다.
- demoReady는 생성 CLI가 보장한 표식·인증·identity를 확인한다. 매 조회마다 bcrypt 검사를 하지 않는다. 운영자가 DB나 공개 암호 상수를 직접 바꾼 경우에는 생성 명령과 실제 로그인을 다시 확인해야 한다.
- 모의 거래와 메모는 공용으로 공유된다. 방문자별 데이터 분리나 주기적 초기화는 구현하지 않았다.
- 원래 모바일 기록의 미검증(보유 차트, 닫힌 물타기 모달)은 이 변경으로 완료 처리하지 않는다.
- 검증 스택은 `stack.sh down` exit 0으로 정리했다. 관련 컨테이너·프로젝트 볼륨은 0개, 익명 볼륨은 1→1이다. `public-demo/stack-down.log`와 `receipt.json`에 원본이 있다. 운영 DB·MCP·전역 설정·공개 사이트는 변경하지 않았다.

## 공개 반영 시 필요한 순서

1. 검증된 변경을 PR로 통합하고 기존 배포 절차로 반영한다. 새 컬럼은 기존 init-db 절차가 추가한다.
2. 새 백엔드에서 `flask --app app create-demo`를 실행한다. 기존 계정 충돌 오류가 있으면 그 계정을 변경하지 않고 중단한다.
3. 운영 `/api/member/me?demo=1`과 실제 로그인·가입 안내·데모 버튼·착지·권한을 다시 확인한다. 이 단계 전에는 공개 사용 가능으로 보고하지 않는다.
