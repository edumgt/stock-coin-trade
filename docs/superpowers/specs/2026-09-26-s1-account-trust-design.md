# S1 계정·신뢰 기반 — 설계

- 작성: 2026-09-26, PM 에이전트(Claude Code)
- 상위 계획: 서비스 고도화 프로그램. 선행 작업은 T0-1 검증 스킬(`2026-09-26-t0-verification-loop-design.md`)
- 검토: Security Architect(Agency-Agents, 독립 검토) — "수정 후 승인". 지적 사항은 PM이 코드에서 다시 확인했고 모두 사실이었다. 이 판은 그 지적을 반영했다(맨 끝 "보안 검토 반영" 참고).
- 상태: 노아 승인(2026-09-26)

## 쉬운 요약 (노아용)

실제 사람들이 가입하는 서비스가 되려면 회원 관리를 은행 앱에 가까운 수준으로 올려야 합니다. 바뀌는 것은 여섯 가지입니다.

1. **로그아웃하면 서버에서도 즉시 끊깁니다.** 지금은 로그아웃해도, 누가 로그인 정보(쿠키)를 복사해 가면 7일 동안 쓸 수 있습니다. "모든 기기에서 로그아웃" 버튼도 생깁니다.
2. **가입하면 메일로 인증을 마쳐야 로그인됩니다. 비밀번호를 잊으면 메일로 재설정합니다.** 로그인하지 않아도 둘러보기와 백테스트는 그대로 쓸 수 있습니다.
3. **비밀번호는 미국 표준(NIST)에 따라 15자 이상입니다.** 흔한 비밀번호는 거절하지만 특수문자는 강요하지 않습니다. 긴 문장형을 권합니다.
4. **개인정보 처리방침과 동의 화면을 만듭니다.** 실명 대신 닉네임을 받습니다. 탈퇴하면 그 사람의 데이터를 즉시 지우고, 빠뜨린 게 있으면 자동 테스트가 잡습니다.
5. **로그인·가입 화면에서 외부 스크립트를 없앱니다.** 지금 이 화면들은 외부 서버의 스크립트를 불러옵니다. 그 서버가 해킹되면 비밀번호가 새어 나갈 수 있습니다.
6. **공개 사이트의 가입은 메일 발송이 준비될 때까지 자동으로 닫혀 있습니다.** 지금 실제 가입자는 0명이라 잃는 것은 없습니다.

노아님이 하실 일:
- 처리방침 초안의 법률 확인(초안은 에이전트가 쓰고 법무 검토 에이전트가 먼저 봅니다)
- 도메인 구매(출시 2주 전)
- 확인됨(2026-09-26): **"메일 인증 전에는 로그인 불가"**(2번). 남의 이메일로 계정을 선점하는 문제와 미인증 계정 처리 로직이 함께 사라집니다.

## 목표와 범위

- **목표**: 공개 서비스로 열어도 되는 수준의 계정 수명주기. 기준은 NIST SP 800-63B-4 비밀번호 요구(§3.1.1.2, 2026-09-26 PM이 원문 확인)와 OWASP ASVS 기본 수준의 세션 요구(원문 미대조)이며, 한국 개인정보 처리 관행을 따른다.
- **범위 밖**: 소셜 로그인, 2단계 인증, 이메일 주소 변경, CAPTCHA, 기능별 사용 한도(S3), SES 실제 연결과 도메인(S5), 사이트 전체의 CSS 빌드 전환(S4. 단, 인증 화면만은 이번에 처리한다).

## 현재 상태 (2026-09-26 코드 확인)

- **세션**: Flask 서명 쿠키만 쓰고 서버 저장이 없다.
  - 7일, `HttpOnly`, `SameSite=Lax`.
  - public이어도 `Secure`를 강제하지 않는다(`settings.py:170`). compose 기본값만 true다.
- **로그인 사용자 확인**: `session.get("member_id")`가 62곳(17개 파일)에 흩어져 있다.
  - API 키 경로(`openapi.py:65`)는 `g.member_id`를 쓴다.
- **비밀번호**
  - `bcrypt` 직접 사용(`members.py:31`). 정책은 "비어 있지 않음"뿐이다.
  - bcrypt는 72바이트를 넘는 부분을 잘라서 검증한다.
  - `create-admin` 최소 길이는 12자다(`bootstrap.py:58`).
- **가입 여부 노출**
  - 중복 이메일은 "이미 존재" 응답으로 드러난다.
  - 공개 관리자 주소도 다른 400 응답을 받는다(`members.py:451-453`).
  - 없는 계정은 bcrypt를 수행하지 않는다.
- **로그**
  - 서버 오류 로그는 쿼리를 포함한 경로(`app.py:234`)와 IP(`app.py:237`)를 저장한다.
  - 클라이언트 오류 보고기는 `location.href` 전체를 보낸다(`common.js:11` → `error_analysis.py:119`). 브라우저 정보(User-Agent)도 저장한다.
  - 마스킹 정규식(`error_analysis.py:19`)은 `t=` 같은 토큰 파라미터를 가리지 못한다.
  - nginx 접근 로그는 AWS CloudWatch로 간다(`compose.aws.yml`, 보존 기간 미확인).
- **화면**
  - 로그인·가입 화면이 버전 고정·무결성 해시 없는 `https://cdn.tailwindcss.com`을 불러온다(`member/login.html:16`).
  - CSP는 보고 전용이다(`docker/nginx-security-headers.conf:9`).
- **회원 소유 테이블**
  - 삭제 대상(FK):
    - `hold_crypto`, `crypto_order`, `stock_position`, `stock_order`
    - `kis_practice_account`, `kis_practice_position`, `kis_practice_order`
    - `hts_watch_memo`, `alternative_position`, `alternative_order`, `api_key`
  - NULL 허용 표: `system_error_log`, `api_usage_log`, `ai_invite`
  - `ai_usage`는 NOT NULL이고, 월 AI 예산 집계에 쓰인다.
- **공개 데모 회원**: 20명 모두 `@system-bot.local` 봇이다. 실제 가입자 0명(운영 DB 조회 2026-09-26).

## 설계

### ① 과도기: 공개 가입을 구조로 닫기 (첫 PR)
- `SIGNUP_ENABLED`의 기본값
  - local: true
  - public: **`SMTP_HOST`와 `PUBLIC_BASE_URL`이 모두 설정된 경우에만** true가 될 수 있다. 메일을 보낼 수 없으면 인증이 불가능하므로 가입도 열 수 없다.
- 가입이 닫혀 있으면
  - `POST /api/member/register`가 403 `SIGNUP_CLOSED`를 반환한다.
  - `/api/member/me`가 `signupOpen: false`를 싣는다.
  - 가입 화면은 "공개 베타 준비 중"을 보여 준다.
- public 기동 검사를 추가한다(`Settings.from_env`의 기존 `problems` 목록). 아래 조건을 어기면 기동을 거부한다.
  - `SESSION_COOKIE_SECURE`는 반드시 true
  - 가입이 열리면 `PUBLIC_BASE_URL`이 `https://`로 시작

### ② 세션: MariaDB 세션 표 (기존 호출부는 그대로 둔다)

새 표를 만든다.

```sql
member_session (
  token_hash CHAR(64) PRIMARY KEY,   -- 원본 토큰의 SHA-256
  member_id BIGINT NOT NULL,         -- FK member
  created_at DATETIME NOT NULL,
  last_seen_at DATETIME NOT NULL,
  KEY (member_id)
)
```

- **발급**(로그인, 비밀번호 변경 후 현재 요청)
  - `session.clear()`로 세션 고정을 막는다.
  - `secrets.token_urlsafe(32)`로 토큰을 만들고 행을 넣는다.
  - 서명 쿠키에 `member_id`와 `sid`(원본 토큰)를 **함께** 둔다. `csrf_token`은 새로 만든다.
- **확인**: `before_request` 훅 하나. `app.py`의 기존 훅보다 앞에 등록한다.
  - 쿠키에 `member_id`가 있으면 `sid`의 해시로 행을 찾는다.
  - 행이 없거나, 만료됐거나, `member_id`가 다르거나, **DB 조회가 실패하면**(fail closed) `session.clear()`한다.
  - 기존 62곳의 `session.get("member_id")`는 이 훅을 통과한 값만 보게 되므로 **코드를 옮기지 않는다.** `g.member_id` 이름도 쓰지 않아 API 키 경로와 섞이지 않는다.
  - `sid`가 없는 옛 쿠키는 자동으로 무효가 된다. `SECRET_KEY`를 교체할 필요가 없다.
- **만료**: 유휴 7일 또는 발급 30일.
  - `last_seen_at`은 1시간이 지났을 때만 갱신한다.
  - 활동일 기록(④)도 이 갱신 분기 안에서만 한다. 매 요청마다 DB에 쓰지 않기 위해서다.
  - 만료 행은 worker가 매일 03:00 KST에 정리한다(`scheduler.py` CronTrigger 패턴).
- **종료**
  - 로그아웃: 해당 행 삭제.
  - "모든 기기 로그아웃": 그 회원의 행 전부 삭제.
  - 비밀번호 변경: 전부 삭제한 뒤 현재 요청에 새로 발급.
  - 비밀번호 재설정·탈퇴·관리자 CLI 재설정: 전부 삭제.

### ③ 가입·인증·비밀번호

**비밀번호 정책** (NIST SP 800-63B-4 §3.1.1.2)
- 입력은 **NFKC로 정규화**한 뒤 길이를 세고 해시한다. 한글 입력 방식 차이를 막기 위해서다.
- 최소 **15자**(단일 인증 SHALL), 최대 **64자** 허용. 조합 규칙은 요구하지 않는다.
- **차단 목록과 전체 일치 비교**(SHALL)
  - 더 큰 공개 유출 목록에서 15자 이상만 추려 동봉한다. 라이선스를 확인하고 출처를 적는다.
  - 다음 경우도 거절한다: 이메일 앞부분이나 닉네임이나 서비스 이름을 포함한 경우, 같은 글자만 반복한 경우.
- **잘라서 검증하지 않는다**(SHALL).
  - 새 형식: `"s2$" + bcrypt(base64(sha256(NFKC(password))))`.
  - 옛 형식(`$2b$…`)은 그대로 검증하고, 로그인에 성공하면 새 형식으로 다시 저장한다.
  - `bootstrap.create_admin`도 같은 헬퍼와 정책(15자, 차단 목록)을 쓴다. 기존 12자 기준은 삭제한다.
- 이 정책은 새로 정하는 비밀번호(가입, 변경, 재설정, 관리자 생성)에만 적용한다.

**가입** (`POST /api/member/register`, 응답은 언제나 `202 {"status": "check_email"}`)
- **입력 필드**
  - 닉네임(기존 `username` 열, 2~20자). NFKC로 정규화하고, 제어문자·방향 전환 문자·폭 0 문자는 거절한다. 공개 랭킹에서 다른 사람을 사칭하지 못하게 하기 위해서다.
  - 이메일. **주소 하나만** 받고 254자 이하여야 한다. 쉼표·공백·`<>`·줄바꿈은 거절한다.
  - 비밀번호.
  - 필수 동의 두 개: 만 14세 이상, 개인정보 수집·이용.
- **가입 여부를 드러내지 않는다.** 모든 경로가 bcrypt를 1회 수행하고, 메일은 요청 처리 밖(백그라운드 스레드)에서 보낸다. 응답 시간으로 구분되지 않게 하기 위해서다.

  | 경우 | 처리 |
  |---|---|
  | 새 주소 | 계정 생성 + 인증 메일 |
  | 기존 주소 | 생성 없음 + "이미 가입된 주소" 안내 메일 |
  | 예약 도메인·공개 관리자 주소 | 아무것도 하지 않음 |
  | 함정 필드가 채워짐 | 아무것도 하지 않음 |

- `member`에 열을 추가한다(멱등 ALTER, `members.py:128` 패턴).
  - `email_verified_at DATETIME NULL`
  - `created_at DATETIME NULL DEFAULT CURRENT_TIMESTAMP`
  - `consent_version VARCHAR(20) NULL`
  - `consented_at DATETIME NULL`
  - 기존 비예약 계정은 이전할 때 `email_verified_at = NOW()`로 채운다.
- **메일 인증을 마쳐야 로그인할 수 있다**(노아 확인 2026-09-26).
  - 인증하지 않은 계정의 로그인은 잘못된 비밀번호와 같은 오류 문구로 거절한다.
  - 인증 메일 재전송은 로그인 화면의 "인증 메일 다시 받기"에서 한다.
  - 7일 동안 인증하지 않은 계정은 worker가 삭제한다(④의 삭제 경로 재사용).

**인증·재설정 토큰**

```sql
member_token (
  token_hash CHAR(64) PRIMARY KEY,
  member_id BIGINT NOT NULL,           -- FK member
  purpose ENUM('verify','reset') NOT NULL,
  expires_at DATETIME NOT NULL,
  used_at DATETIME NULL,
  KEY (member_id, purpose)
)
```

- **수명**: 인증 24시간, 재설정 30분. 새로 발급하면 같은 목적의 이전 토큰은 무효가 된다.
- **링크는 프래그먼트로 만든다**: `{PUBLIC_BASE_URL}/member/verify.html#t=…`, `…/member/reset.html#t=…`.
  - 프래그먼트는 서버, 접근 로그, Referer로 전달되지 않는다.
  - 화면은 `<head>`의 첫 스크립트(자체 호스팅 파일)가 토큰을 읽어 메모리에 두고, `history.replaceState`로 주소창에서 지운다.
  - 토큰은 POST 본문으로만 서버에 보낸다.
- **1회용은 원자적으로 처리한다.**
  - `UPDATE member_token SET used_at=NOW() WHERE token_hash=? AND used_at IS NULL AND expires_at>NOW()`를 실행한다.
  - 영향받은 행이 1일 때만 진행한다.
- 재설정에 성공하면 `email_verified_at`도 채운다(메일을 받았다는 증명이므로).
- 링크 도메인은 **`PUBLIC_BASE_URL` 설정으로만** 만든다. 요청의 `Host` 헤더는 쓰지 않는다.

**로그인** (`POST /api/member/login`)
- 없는 계정이어도 미리 만든 더미 해시로 bcrypt를 1회 수행한다. 오류 문구는 하나다.
- **제한**
  - IP: 기존 분당 10회를 유지한다. IPv6는 /64 단위로 센다.
  - 이메일 키: **실패(401)만** 센다(Flask-Limiter `deduct_when`), 시간당 30회. 남이 5번 틀려서 계정을 잠그는 공격을 막는다.

**인증 메일 재전송** (`POST /api/member/verify/resend`): 항상 `202`로 응답한다. 제한은 아래 "메일 발송 상한"을 따른다.

**비밀번호 재설정**
- `POST /api/member/password/reset-request`: 항상 `202`로 응답한다. 공개 관리자 주소는 메일로 재설정하지 않는다(CLI로만).
- `POST /api/member/password/reset`: 원자적 토큰 사용 → 정책 검사 → 저장. 이어서 다음을 처리한다.
  - **모든 세션 삭제**
  - **그 회원의 Open API 키 전부 비활성화**. 세션을 훔친 사람이 만들어 둔 키가 살아남지 않게 하기 위해서다.
  - 자동 로그인은 하지 않는다.

**비밀번호 변경** (`POST /api/member/password/change`)
- 현재 비밀번호를 확인한 뒤 정책을 검사한다.
- 다른 세션은 삭제하고, 현재 세션은 새로 발급한다.
- 회원 단위로 시간당 10회 제한한다. 세션을 훔친 사람이 현재 비밀번호를 대입해 보는 것을 막기 위해서다.

### ④ 개인정보·탈퇴·측정

**처리방침** (`/privacy.html`, 버전 문자열을 `consent_version`에 기록)
- 에이전트가 초안을 쓰고, Legal Compliance Checker가 검토하고, **노아가 법률 확인**한다.
- **수집 항목**: 이메일, 닉네임, 비밀번호 해시, 동의 기록, 활동일, 모의투자 기록, 오류 로그의 IP와 브라우저 정보.
- **보관**: 탈퇴 즉시 파기. 로그는 90일이다.
  - DB 로그는 worker가 삭제한다.
  - CloudWatch 로그 그룹은 보존 기간 90일로 설정하고, 이것을 배포 체크리스트에 넣는다.
- **처리위탁·국외 이전**: AWS 서울 리전, SES(S5). S3에서 쓸 Anthropic·외부 판정 서비스(미국)는 해당 기능을 켜기 전에 문구를 반영한다.
- 가입 화면에 요약과 전문 링크를 둔다. 선택 동의는 두지 않는다(마케팅 메일 없음).

**탈퇴** (`POST /api/member/delete`)
- 현재 비밀번호를 받는다. 회원 단위로 시간당 10회 제한한다.
- 한 트랜잭션 안에서 처리한다.
  - 삭제: FK 목록 11개, `member_session`, `member_token`, `member_activity_day`.
  - `member_id`를 NULL로:
    - `ai_invite`: 폐기 처리도 함께 한다.
    - `ai_usage`: 월 예산 집계를 보존하기 위해서다. NULL 허용으로 바꾸는 멱등 ALTER가 필요하다.
    - `system_error_log`, `api_usage_log`
  - 마지막으로 `member`를 삭제하고 세션을 비운다.
- **삭제 누락 방지 장치**
  - MariaDB 통합 테스트가 `information_schema.columns`에서 `member_id` 열을 가진 모든 표를 찾는다.
  - 탈퇴한 테스트 회원의 id를 가진 행이 전 표에서 0인지 확인한다.
  - 표가 늘어도 삭제 경로에 넣지 않으면 CI가 실패한다.

**사용 측정**

```sql
member_activity_day (member_id BIGINT NOT NULL, day DATE NOT NULL, PRIMARY KEY (member_id, day))
```

- ②의 1시간 갱신 분기에서 KST 날짜로 `INSERT IGNORE`한다. IP·기기·페이지 정보는 저장하지 않는다.
- 집계 CLI(`usage-report`)는 **실제 가입자가 생긴 뒤** 만든다. 기록은 나중에 소급할 수 없으므로 지금 시작한다.

### ⑤ 메일·남용 방지·화면

**메일** (`python-stock-backend/mailer.py`, 표준 라이브러리 `smtplib`·`email.message.EmailMessage`)
- 설정: `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM`, `SMTP_STARTTLS`, `PUBLIC_BASE_URL`.
- **TLS**: `starttls(context=ssl.create_default_context())`로 인증서를 검증한다. public에서는 STARTTLS를 필수로 한다.
- **발송**: `send_message(msg, to_addrs=[검증된 주소 하나])`.
- **내용**
  - 제목과 본문은 코드에 고정된 템플릿이다. **닉네임 등 사용자 입력은 메일에 넣지 않는다**(피싱 문구 주입 차단).
  - 링크는 `PUBLIC_BASE_URL`로만 만든다.
- **실패 처리**
  - 발송 실패는 응답에 드러내지 않는다.
  - 로그에는 요청 ID와 오류 종류만 남기고, 이메일 주소와 토큰은 남기지 않는다.
- **메일 발송 상한**(공유 limiter)
  - 전역 하루 상한: 기본 200통. 1단계 예산에 맞춘 값이다.
  - 수신 주소별 합산: 가입·재전송·재설정을 합쳐 시간당 3통, 하루 10통.
  - IP·IPv6 /64별 가입: 시간당 5회(기존 유지).
- **로컬·검증 환경**: Mailpit 컨테이너(이미지 태그 고정, T0-1 `compose.verify.yml`와 `compose.portfolio.yml`).
- **public**: S5에서 도메인을 산 뒤 SES SMTP를 연결한다.

**클라이언트 오류 보고기** (`frontend/js/common.js:11`)
- `url`에 `location.origin + location.pathname`만 담는다. 쿼리와 프래그먼트는 보내지 않는다.

**인증 화면**
- 대상: `member/register.html`, `login.html`, `verify.html`, `reset-request.html`, `reset.html`, `account.html`, `/privacy.html`.
- **제3자 스크립트 0개**
  - Tailwind CDN을 빼고, 기존 `frontend/css/style.css`에 손으로 쓴 `auth.css` 하나를 더해 스타일을 입힌다. 빌드 도구는 들이지 않는다(사이트 전체의 CSS 빌드 전환은 S4).
  - 인라인 스크립트는 파일로 분리한다.
- **CSP 강제**: nginx `location /member/`와 `/privacy.html`에 `Content-Security-Policy: default-src 'self'; script-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'self'; form-action 'self'`를 **강제**한다. 보고 전용이 아니다. 기존 보안 헤더 include는 유지한다.
- **스타일**: 기존 다크 터미널 스타일을 따른다. 사용자 입력은 `escapeHtml`로 출력한다.
- **화면별 내용**
  - 가입: 규칙 안내("문장처럼 길게 — 예: 봄비 오는 날 공시를 읽는다"), 동의, 함정 필드, 닫힘 안내.
  - 로그인: "비밀번호 찾기", "인증 메일 다시 받기".
  - 계정 설정: 비밀번호 변경, 모든 기기 로그아웃, 탈퇴(현재 비밀번호 확인).

## 위협 모델

| 위협 | 대응 |
|---|---|
| 세션 쿠키 탈취 후 재사용 | 서버 세션 표, 로그아웃 즉시 삭제, 유휴 7일·절대 30일, `HttpOnly`·`SameSite=Lax`, public `Secure` 기동 강제 |
| 세션 고정 | 발급 때 `session.clear()` 후 새 토큰 |
| 세션 저장소 장애 | 조회 실패 시 로그아웃 처리(fail closed) |
| 크리덴셜 스터핑·무차별 대입 | IP 제한(IPv6 /64), 이메일 키 실패 전용 제한, 15자, 차단 목록 |
| 계정 잠금 공격 | 이메일 키 제한은 실패만 세고 시간당 30회로 둔다 |
| 가입 여부 열거 | 모든 경로 동일한 202, bcrypt 1회, 메일 비동기, 예약·관리자 주소도 동일 응답 |
| 토큰 유출(로그·Referer·오류 보고·CDN) | 프래그먼트 링크, 오류 보고기가 경로만 전송, 인증 화면 제3자 JS 0개와 CSP 강제, DB에는 해시만, 원자적 1회용, 짧은 수명 |
| 재설정 링크 도메인 변조(Host 헤더) | `PUBLIC_BASE_URL`만 사용, public에서 필수 |
| 메일 수신자·헤더 주입, TLS 미검증 | 단일 주소 검증, `to_addrs` 고정, 고정 템플릿, 사용자 입력 없음, 기본 SSL 컨텍스트 |
| 메일 폭탄(임의 주소로 대량 발송) | 전역 하루 상한, 수신 주소별 합산 상한, IP·/64 제한 |
| 계정 선점(남의 주소로 가입) | 인증 전 로그인 불가, 7일 미인증 삭제 |
| 세션 탈취 후 영속화(API 키) | 재설정 시 Open API 키 전부 비활성화 |
| 현재 비밀번호 대입(변경·탈퇴 API) | 회원 단위 시간당 10회 |
| 관리자 계정 | `create-admin` 15자·차단 목록, CLI 재설정 시 세션 삭제, 메일 재설정 제외 |
| 닉네임 사칭(랭킹) | NFKC, 제어·방향·폭 0 문자 거절 |
| CSRF | 기존 전역 출처 검사(`security.py`)가 새 POST 경로에도 적용 |
| 탈퇴 후 잔존 데이터 | 트랜잭션 삭제와 `information_schema` 스캔 테스트 |
| 긴 입력으로 CPU 소모 | 최대 64자, 앞단 SHA-256으로 bcrypt 입력 길이 고정 |

## 구현 순서 (PR 단위, 각각 T0-1 검증 스킬로 증명)

1. **가입 닫기와 public 기동 검사**(①). T0-2 가드 G1·G3·G4·G5와 기준값을 함께 넣는다.
2. **세션 표와 확인 훅**(②). 기존 호출부는 수정하지 않는다.
3. **비밀번호 정책·해시 형식·로그인 강화**(③ 앞부분), `create-admin` 정책 통일.
4. **메일 기반 흐름**: `mailer.py`와 Mailpit, 토큰 표, 인증·재전송·재설정·변경, 열거 방지, 메일 상한, 오류 보고기 수정.
5. **개인정보·탈퇴**: 처리방침·동의·닉네임 규칙, 탈퇴와 스캔 테스트, 활동일 기록, 로그 90일 정리.
6. **인증 화면 정리**: 자체 CSS, CSP 강제, 검증 스킬 F1 확장, 교차 모델 보안 검토(T0-4), 공개 배포.

## 검증

- **단위 테스트**
  - 토큰: 해시, 만료, 원자적 1회용(동시 사용 2건 중 1건만 성공).
  - 비밀번호 정책: 14자 거절, 15자 허용, 차단 목록 일치 거절, 이메일 앞부분 포함 거절, 65자 거절, 한글 30자 허용, NFKC 동등 입력이 같은 해시로 검증되는지.
  - 해시 형식 이전: 옛 형식으로 로그인하면 새 형식으로 저장.
  - 열거 방지: 새 주소·기존 주소·관리자 주소·함정 필드의 응답 코드와 본문이 같고, 네 경우 모두 bcrypt가 1회 호출되는지.
  - 메일: 쉼표 여러 주소 거절, `to_addrs` 단일, 제목과 본문에 사용자 입력 없음.
  - 설정: public에서 `SESSION_COOKIE_SECURE=false`면 기동 거부, 가입이 열리는데 `PUBLIC_BASE_URL`이 없으면 기동 거부.
- **MariaDB 통합 테스트**
  - 로그아웃 뒤 같은 쿠키로 `/api/member/me`를 호출하면 `loggedIn: false`.
  - 쿠키의 `member_id`를 다른 값으로 조작하면 무효.
  - 세션 DB 조회를 실패시키면 로그아웃 처리.
  - 비밀번호 변경 뒤 다른 세션은 무효, 현재 세션은 유지.
  - 재설정 뒤 모든 세션 무효, API 키 비활성.
  - 미인증 계정은 로그인 불가.
  - 탈퇴 뒤 `member_id` 스캔 0행, `ai_usage` 비용 합계 보존.
  - 7일 미인증 정리.
- **검증 스킬 F1(T0-1)**
  - 전 흐름: 가입 → Mailpit API로 링크(프래그먼트) 추출 → 인증 → 로그인 → 재설정 → 모든 기기 로그아웃 → 탈퇴 → DB 0행.
  - 증거: 스크립트 기록과, 쿠키 없는 Playwright로 캡처한 화면.
  - 브라우저 네트워크 기록에서 인증 화면이 외부 도메인 요청을 하지 않는지 확인한다.
- **성능**: 공개 서버(t3.small)에서 로그인 1회의 bcrypt 소요 시간을 실측한다(비용 12). 300ms를 넘으면 비용 조정을 검토한다.
- **보안**: PR마다 Codex 교차 검토와 `ecc:security-reviewer`에서 높음 이상 0건. 마지막에 Reality Checker 판정.
- **배포 후**
  - 공개 서버에서 `signupOpen: false`와 가입 403을 확인한다.
  - 인증 화면 응답에 CSP 헤더가 붙는지 확인한다.
  - `/health` 200과 기존 공개 기능(백테스트, 명령 바)을 회귀 확인한다.
  - CloudWatch 보존 90일 설정을 확인한다.

## 보안 검토 반영 (2026-09-26)

Security Architect 판정은 "수정 후 승인"이다. PM이 인용된 file:line 9곳을 직접 열어 모두 사실임을 확인했다.

| 지적 | 반영 |
|---|---|
| 높음: `?t=` 토큰이 nginx 로그·오류 보고기(`location.href`)·CDN 스크립트에 노출 | 프래그먼트 링크, 오류 보고기는 경로만 전송, `<head>` 첫 스크립트로 제거 |
| 높음: 인증 화면의 버전 고정 없는 제3자 스크립트, CSP 보고 전용 | 인증 화면에서 제3자 JS 0개, CSP 강제 |
| 높음: 링크 도메인 미정(Host 헤더 변조) | `PUBLIC_BASE_URL` 필수 |
| 중간: 수신자 검증·TLS 검증 없음, 닉네임 주입 | 단일 주소 검증, `to_addrs`, 기본 SSL 컨텍스트, 메일에 사용자 입력 없음 |
| 중간: 관리자 주소 열거, 응답 시간 차이 | 모든 경로 동일 응답, bcrypt 1회, 메일 비동기 |
| 중간: 이메일 키 제한이 계정 잠금에 악용 | 실패만 세고 시간당 30회 |
| 중간: API 키가 재설정 뒤에도 살아남음 | 재설정 시 비활성화 |
| 중간: 차단 목록이 15자 하한과 겹쳐 효과 없음 | 15자 이상 목록, 맥락 단어 거절, NFKC |
| 중간: 처리방침 수집 항목(User-Agent)·CloudWatch 보존 누락 | 추가 |
| 낮음: 1회용 토큰 경쟁 조건 | 원자적 UPDATE |
| 빠진 위협: 메일 폭탄, 관리자, 현재 비밀번호 대입, Secure 미강제, fail closed, 닉네임 사칭 | 모두 위협 모델과 설계에 추가 |
| 과한 설계: 62곳 이전과 가드 G2 | **채택**: 쿠키에 `member_id`와 `sid`를 함께 두고 훅이 검증한다. 이전과 G2를 삭제한다 |
| 과한 설계: 인증 전 로그인 허용 | **채택(노아 확인)**: 인증 전 로그인 불가 |
| 과한 설계: 메일의 닉네임 | **채택**: 넣지 않음 |
| 과한 설계: `usage-report` 즉시 구현 | **채택**: 기록만 먼저 하고 집계는 가입자가 생긴 뒤 |

검토자는 네트워크를 쓰지 않았으므로, 표준 인용은 검토자 기준으로 "미검증"이다. NIST §3.1.1.2 수치는 PM이 원문으로 확인했다.
