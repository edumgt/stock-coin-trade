# S1b 계정 수명주기 검증 기록 (2026-09-26)

메일 인증·비밀번호 재설정과 변경·탈퇴·정기 정리·개인정보 처리방침·인증 화면(CSP)을 구현하고 확인한 기록이다.
- 설계: `docs/superpowers/specs/2026-09-26-s1-account-trust-design.md` §③·④·⑤
- 계획: `docs/superpowers/plans/2026-09-26-s1b-mail-privacy-screens.md`
- 앞 단계: `docs/evidence/s1-account-core-2026-09-26.md`

증거 폴더(`.verify-artifacts/`)는 git에 올리지 않는다. 아래 경로는 PM 로컬 기준이다.

## 1. PR별 결과

| PR | 내용 | 단위 | 통합(`stack.sh itest`) | 검증 스킬 | CI |
|---|---|---|---|---|---|
| #29 D | mailer·Mailpit·메일 인증·가입 여부 비노출·재설정·변경·오류 보고기 | 454 passed | 79 passed | F1 PASS 22단계(실제 Mailpit 메일) | 3개 통과, 머지 |
| #30 E | 탈퇴·삭제 누락 스캔·활동일·정기 정리·처리방침 초안 | 455 passed | 84 passed | F1·F2 PASS | 3개 통과, 머지 |
| F | 인증 화면·CSP 강제·F1 탈퇴까지·법률/보안 검토 반영 | 456 passed | 87 passed | F1 PASS 26단계, F2 PASS | — |

## 2. 검증 스킬 F1 (26단계, `20260926T104807Z-7a54-F1`)

- **흐름**: 가입 202 → 인증 전 로그인 401 → 메일 토큰 인증 200 → 같은 토큰 400 → 로그인·복사 쿠키 거부·모든 기기 로그아웃 → 재설정 메일 → 새 비밀번호, 옛 비밀번호 401 → 비밀번호 변경 → 틀린 비밀번호 탈퇴 400 → 탈퇴 200 → `member_id` 표 19개 모두 0행.
- **증거의 비밀 값**: 토큰·비밀번호는 `***`로만 남았다.
- **가림 누락 1건**: `current` 키는 가려지지 않았다. 증거 키를 `current_password`로 바꿨고, 가려지지 않은 로컬 증거 폴더 하나는 지웠다.

## 3. 인증 화면 (쿠키 없는 Playwright)

**CSP 헤더**
- 강제 적용: `/member/login`, `/member/login.html`, `/member/register.html`, `/member/verify.html`, `/member/reset-request.html`, `/member/reset.html`, `/member/account.html`, `/privacy.html`, `/privacy` 9개 주소 모두 200이고 `Content-Security-Policy: default-src 'self'…`가 붙는다.
- 그대로 둔 곳: `/index.html`은 강제 CSP 없이 보고 전용을 유지한다.

**외부 요청**
- 가입·재설정·처리방침 화면의 요청은 모두 `127.0.0.1:3334`(같은 출처)였다.
- 콘솔 경고·오류는 0건이다. Chrome VERBOSE 제안(비밀번호 폼에 사용자 이름 칸 권장)만 있었다.

**동작 확인**

| 확인 | 결과 |
|---|---|
| 토큰 제거 | `reset.html#t=abc`를 열면 주소창이 `reset.html`이 되고, 토큰은 메모리에만 남는다 |
| 로그인하지 않고 `account.html` 열기 | `/member/login.html`로 이동 |
| 화면 주행 | 가입(동의 체크) → 안내 문구 → Mailpit 링크 → "이메일 인증 완료" 버튼 → 로그인 → 계정 설정에서 탈퇴 → DB `member` 0행 |
| 메일 검사기 방어(H1 수정 뒤) | 링크만 열면 `email_verified_at` 미설정(0), 버튼을 누르면 1 |
| 첫 화면 하단 | `개인정보 처리방침` 링크가 보인다 |

**캡처**
- `20260926T102948Z-bdfd-F1/`(register·privacy·verified·deleted)와 `20260926T104242Z-e484-F1/register.png`(동의 문구 개정 뒤)는 **H1 수정(8d2a715) 전 화면**이다.
- 현재 코드의 인증 화면은 `20260926T105225Z-63ff-F1/verify-confirm-button.png`(버튼 단계)다.
- 같은 폴더의 `verify-network.txt`에 네트워크 기록을 남겼다. 요청 8개가 모두 `127.0.0.1:3334`이고, 열기만 했을 때 인증 POST는 없다.

## 4. 응답 시간 (가입 여부가 드러나는지, 검증 스택 M1 Pro, 각 10회)

| 경우 | 상태 | 중앙값 | 최소~최대 |
|---|---|---|---|
| 가입: 새 주소 | 202 | 258ms | 254~279ms |
| 가입: 이미 있는 주소 | 202 | 254ms | 251~257ms |
| 가입: 예약 주소 | 202 | 268ms | 248~352ms |
| 인증 메일 재전송: 있는 주소 | 202 | 24ms | 14~33ms |
| 인증 메일 재전송: 없는 주소 | 202 | 19ms | 12~40ms |

- 가입은 모든 경로가 bcrypt를 한 번씩 돌려 범위가 겹친다.
- 재전송·재설정 요청은 토큰 발급과 상한 확인을 스레드로 옮긴 뒤 범위가 겹친다. 남은 차이는 수 ms이며, 받아들였다(아래 6절 L7).

## 5. 테스트가 진짜로 잡는지 (돌연변이 확인)

| 일부러 넣은 결함 | 잡은 테스트 |
|---|---|
| 탈퇴 삭제 목록에서 `api_key`를 뺌 | `test_deleting_an_account_leaves_no_row_with_its_id_anywhere`, `test_every_member_id_table_is_handled_by_the_delete_path` 둘 다 실패 |

## 6. 교차 검토

**Codex·Grok·Gemini**: 모두 사용 한도나 인증 문제로 실행하지 못했다.
- Codex는 2026-10-01까지 한도에 걸렸다.
- Grok은 무료 한도에 걸렸다.
- Gemini는 인증이 설정되지 않았다.

그래서 다른 모델 계열은 **OpenCode Go 구독의 `gpt-6-luna`**(읽기 전용 plan 에이전트)로 검토했다. 작업 폴더는 검토 전후에 변하지 않았다.

**검토 범위**
- 두 검토자 모두 `c9e39fa..90a8730`(PR D·E·F 전체, 계획 문서 제외)을 봤다.
- 지적을 고친 7a42479·8d2a715는 다른 검토자가 다시 보지 않았다. Reality Checker가 diff를 직접 읽어 새 결함이 없다고 판정했다(9절).

**ecc:security-reviewer**: high 이상 0건. 단위·통합·F1을 직접 돌렸다.

| 출처 | 심각도 | 지적 | 판정·조치 | 확인 |
|---|---|---|---|---|
| OpenCode | high | H1 메일 보안 검사기가 인증 링크를 열면 자동 인증된다. 남의 주소로 가입한 공격자가 계정을 선점할 수 있다 | 타당. 사람이 버튼을 눌러야 토큰을 쓴다 | 브라우저: 열기만 하면 0, 누르면 1 |
| OpenCode | high | H2 비밀번호 변경·CLI 재설정 뒤에도 API 키가 살아 있다 | 타당. 같은 트랜잭션에서 모두 끈다 | `test_password_change_also_disables_api_keys`, create-admin 테스트에 단언 추가 |
| OpenCode | medium | M3 public이 http 기준 주소로 재설정 링크를 보낼 수 있다 | 타당. 메일을 켜면 https가 아니면 기동하지 않는다 | `test_public_mail_links_must_use_https_even_while_signup_is_closed` |
| OpenCode | medium | M4 상한에 걸린 요청도 토큰을 바꿔 사용자가 인증·복구를 못 할 수 있다 | 타당. 상한 확인 뒤 스레드에서 발급한다 | `test_a_capped_resend_keeps_the_last_token_valid` |
| OpenCode | medium | M5 상한의 test→hit 경합 | 타당. 원자적 hit만 쓴다(거절 쪽으로 보수적) | 단위 `test_per_address_cap_counts_every_kind` |
| OpenCode | medium | M6 정리 작업이 경계에서 인증한 계정을 지울 수 있다 | 타당. 삭제 트랜잭션에서 행을 잠그고 다시 확인한다. 인증 API는 지워진 계정이면 400 | `test_an_account_verified_after_selection_is_not_deleted` |
| OpenCode | low | L7 경로별 동기 작업 차이로 응답 시간 차이가 생긴다 | 완화(토큰·상한을 스레드로) 뒤 실측했다. 남은 수 ms 차이는 수용 | 4절 |
| ecc | low | 익명 요청이 변경·탈퇴 제한 버킷 하나를 나눠 쓴다 | 타당. 로그인하지 않았으면 IP 키 | 단위·통합 통과 |
| ecc | 정보 | 재전송이 공개 관리자 주소를 건너뛰지 않는다 | 타당. 재설정과 같은 규칙으로 건너뛴다 | 통합 통과 |
| ecc | 정보 | 인증 화면에 강제 CSP와 보고 전용 CSP가 함께 붙는다 | `report-uri`가 없어 영향이 없다. 수용 | — |

## 7. 법률 검토 (Legal Compliance Checker, 개인정보보호위원회 작성지침 2025.4. 대조)

결론은 "초안은 아직 공개 불가"였다. 필수 항목이 빠졌고, 사실과 다른 문장이 있었다.

**에이전트가 고친 것**
- 서버 접속 기록 범위(모든 요청·30일), 백업 최대 35일, 공개 랭킹, 세션·토큰·외부 API 이력, 쿠키와 외부 배포망, 파기 절차, 권리 행사, 보호책임자 절, 구제 기관, 변경 고지를 적었다.
- **명령 바 입력의 국외 이전(미국 외부 판정 서비스)**을 적었다. 공개 서버의 `jev-enabled`가 켜져 있음을 SSM에서 값 대조로 확인했다(값은 출력하지 않음).
- 가입 동의 문구에 목적·항목·보유 기간·거부권과 불이익을 적었다.
- 탈퇴 안내에 백업·로그 보관을 밝혔다.
- 탈퇴하면 AI 초대 코드 이름표도 지운다(코드 수정, 통합 테스트 단언).
- 모든 화면 하단과 로그인 화면에 처리방침 링크를 두었다.

**남긴 것**: `[확정 전]`으로 표시하고 노아 결정으로 남겼다(8절).

## 8. 노아 결정·할 일

공개 가입을 열기 전 관문(S5)이다. 지금은 공개 가입이 닫혀 있다.

1. 개인정보 보호책임자(운영자) 성명과 공개 연락 이메일
2. 처리방침 시행일
3. 처리 근거 방식
   - 가: 필수 동의를 유지한다(현재 화면).
   - 나: 계약 이행으로 처리하고 "처리방침 확인" 체크로 바꾼다.
4. 투자자 랭킹을 모두 공개로 둘지, 원하는 사람만 참여하게 할지
5. **공개 명령 바(판정 모델)**
   - 켜 둘지 결정한다. 켜 두려면 국외 이전 고지와 동의 방식이 필요하다.
   - 이전받는 외부 판정 서비스 사업자의 법인명·연락처·입력 보관 기간을 확인한다.
6. AWS 계약 법인명(처리 위탁 수탁자)
7. 최종 법률 확인: 만 14세 자기 신고 방식, 명령 바 국외 이전 근거 등
8. S5: 도메인, SES 메일 연결(연결 뒤 처리방침에 수탁자 추가), `SIGNUP_ENABLED=true`

## 8-1. 공개 배포 확인 (배포 실행 36237461424, `6b00cfe`)

배포 전에 `scripts/ec2/backup-db.sh`로 운영 DB를 S3에 백업했다(35일 보관). 배포 뒤 SSM으로 서버 안에서 확인했다.

| 확인 | 결과 |
|---|---|
| `/health` | 200 |
| `GET /api/member/me` | `signupOpen: false`, `profile: public` |
| `POST /api/member/register` | 403 |
| 강제 CSP | `/member/login`·`/member/login.html`·`/member/verify.html`·`/privacy.html`·`/privacy` 모두 200+헤더, `/index.html`은 없음 |
| 백테스트 회귀(F2와 같은 요청) | 200 |
| DB 이전 | `member` 새 열 4개, `member_session`·`member_token`·`member_activity_day` 표, `ai_usage.member_id` NULL 허용, 기존 회원 21명 모두 인증 표시(미인증 0) |
| bcrypt(t3.small, 컨테이너 안 10회) | 해시 중앙값 290ms(287~304), 검증 중앙값 294ms(288~416) |

- **bcrypt**: 중앙값은 스펙 기준 300ms 안이지만 여유가 작다. 요청 처리까지 더하면 로그인 응답은 300ms를 조금 넘을 수 있다. 사용자가 느끼는 지연은 크지 않아 비용(12)은 유지한다. 가입을 연 뒤 실제 응답 시간을 재서 다시 판단한다.
- **명령 바**: 호출하면 외부 과금 API를 부르므로 화면 응답 200만 확인하고 호출은 하지 않았다.

## 9. Reality Checker 판정

**PR F 머지·배포 가능(READY)**

- 직접 재현한 결과: 단위 456 passed, 통합 87 passed, F1 26단계 PASS, CSP·외부 요청 0건, H1 버튼 흐름.
- 돌린 스택이 HEAD와 같은지 해시로 확인했다.

**배포 조건**
1. 공개 서버 컨테이너에서 bcrypt 소요 시간을 실측한다(계정 불필요, 기준 300ms).
2. `/member/api-keys.html`을 잔여 위험으로 기록한다.

**공개 가입 열기(S5)**: 아직 준비되지 않음(NEEDS WORK). 8절 노아 결정과 t3.small 실측이 남아 있다.

**설계와 달라진 점**
- 세션 DB 조회 실패 확인은 설계의 통합 테스트 대신 단위 테스트(`test_session_store_failure_logs_the_visitor_out`, 엔진을 가짜로 바꿈)로 했다.

## 10. 남은 기술 항목

- **`/member/api-keys.html`**: 강제 CSP가 없고 버전을 고정하지 않은 Tailwind CDN을 불러온다.
  - 설계의 인증 화면 목록 밖이지만, 새로 만든 API 키가 보이는 화면이다.
  - S4 화면 작업 때 인증 화면과 같은 방식(자체 CSS·강제 CSP)으로 바꾼다.

- **공개 서버 로그인 소요 시간**: 가입이 열린 뒤 S5에서 잰다. 지금은 미검증이다.
- **Chrome VERBOSE 제안**: 비밀번호 폼에 숨은 사용자 이름 칸을 두라는 제안이다. 비밀번호 관리자 편의 기능이라 S4 화면 작업 때 반영한다.
