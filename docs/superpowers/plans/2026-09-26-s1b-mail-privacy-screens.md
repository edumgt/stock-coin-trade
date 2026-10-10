# S1b 메일 인증·재설정·탈퇴·인증 화면 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 공개 가입을 열어도 되는 계정 수명주기를 완성한다: 메일 인증 뒤에만 로그인, 가입 여부를 드러내지 않는 가입·재설정, 비밀번호 변경, 즉시 탈퇴, 개인정보 처리방침, 제3자 스크립트 없는 인증 화면과 강제 CSP.

**Architecture:**
- 메일은 `mailer.py` 하나가 맡는다. 고정 템플릿, 단일 수신자, 요청 밖 스레드 발송, 공유 limiter 저장소로 발송 상한.
- 1회용 토큰은 `member_tokens.py`(해시만 저장, 원자적 사용)가 맡는다.
- 새 API(인증·재전송·재설정·변경·탈퇴)는 새 블루프린트 `member_account.py`에 둔다. 가입·로그인은 `members.py`를 고친다.
- 탈퇴는 `member_delete.py`, 정기 정리(7일 미인증·로그 90일)는 `retention.py`, 활동일 기록은 `member_sessions.py`에 더한다.
- 인증 화면 7개는 `auth.css`·`auth-pages.js`·`auth-token.js`만 쓰고, nginx가 그 경로에만 CSP를 강제한다.

**Tech Stack:** Flask, SQLAlchemy 2.0 Core(text), MariaDB 11.4, smtplib, Flask-Limiter 4.1.1(`limits`), Mailpit v1.31.2, nginx 1.31.6, pytest, 검증 스킬 `verify-stockdesk`.

**Spec:** `docs/superpowers/specs/2026-09-26-s1-account-trust-design.md` §③(가입·인증·재설정·변경)·§④·§⑤·위협 모델·검증. 선행: S1a(`docs/evidence/s1-account-core-2026-09-26.md`).

## Global Constraints

- **인증 전 로그인 불가**: 메일 인증을 쓰는 배포(public 전부, 또는 local에서 `SMTP_HOST`가 있을 때)에서 `email_verified_at`이 없으면 잘못된 비밀번호와 **같은 401**. 메일이 없는 local(교실 실습)은 예전처럼 가입 즉시 인증·로그인.
- **공개 가입**: `SIGNUP_ENABLED=true`와 메일 설정이 모두 있어야 열린다(S1a Codex H1). S1b를 배포해도 SSM에 값을 넣지 않으므로 공개 가입은 닫힌 채다. 여는 것은 S5 관문(도메인·SES·노아 법률 확인) 뒤다.
- **가입 응답**: 메일 인증 모드에서는 새 주소·기존 주소·예약/관리자 주소·함정 필드 모두 `202 {"status": "check_email"}`, 모든 경로 bcrypt 1회, 메일은 스레드. 입력 형식 오류(닉네임·이메일·비밀번호 정책·동의)는 DB를 보기 전 400.
- **토큰**: 인증 24시간·재설정 30분, 새로 발급하면 같은 목적의 이전 토큰 삭제, DB에는 SHA-256만, 링크는 `{PUBLIC_BASE_URL}/member/verify.html#t=…`·`/member/reset.html#t=…`, 사용은 `UPDATE … WHERE used_at IS NULL AND expires_at > now` 영향 1행일 때만.
- **메일**: 제목·본문 고정, 사용자 입력 없음, `to_addrs=[주소 하나]`, `ssl.create_default_context()`로 STARTTLS(public 필수), 실패는 응답에 드러내지 않고 로그에는 요청 ID·종류·오류 이름만.
- **발송 상한**(limiter 켜진 배포): 전역 하루 200통, 수신 주소별 합산 시간당 3통·하루 10통.
- **제한**: 재전송·재설정 요청은 IP당 시간당 10회, 토큰 사용(인증·재설정)은 IP당 시간당 20회, 비밀번호 변경·탈퇴는 회원당 시간당 10회.
- **탈퇴**: 한 트랜잭션. 삭제 14개 표, `member_id` NULL 3개 표(`system_error_log`, `api_usage_log`, `ai_usage`), `ai_invite`는 NULL+폐기, 마지막에 `member`.
- **인증 화면**: 제3자 스크립트·스타일 0개, 인라인 `<script>`·`<style>`·`style=""` 0개, CSP `default-src 'self'; script-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'self'; form-action 'self'`를 nginx가 강제.
- **로그 보관**: DB 로그 90일(worker). CloudWatch 로그 그룹 `/stockdesk/app`은 이미 30일(2026-09-26 조회)이라 처리방침에는 30일로 적고 인프라는 바꾸지 않는다.
- **코드 규칙**: 한국어 docstring·JSDoc(@param/@returns), 새 의존성 없음, 사용자 입력 출력은 `textContent`만.
- **검증**: 단위 `docker run --rm -v "$PWD":/repo -w /repo sct-test:dev python -m pytest -q -m "not integration"`, 통합 `scripts/verify/stack.sh itest`, 앱 F1, 커밋 전 `ruff check .`·`ruff format --check tests/unit tests/integration tests/conftest.py`.
- **PR 단위**: PR D(Task 1~4, 계획 문서 포함) → PR E(Task 5~7) → PR F(Task 8~10, 교차 검토·배포). 각 PR은 CI 3개 통과 뒤 머지. 공개 배포는 PR F 뒤 한 번.

## Review Focus

1. 메일 서버가 죽어 있어도 가입·재설정 요청은 202를 즉시 돌려줘야 한다(스레드 예외가 요청을 깨뜨리지 않음). → Task 1 `test_send_failure_is_swallowed_and_logged_without_address`.
2. 재설정에서 약한 새 비밀번호를 넣으면 토큰이 소모되지 않아 같은 링크로 다시 시도할 수 있어야 한다. → Task 3 `test_weak_password_does_not_burn_the_reset_token`.
3. 같은 인증 토큰을 두 요청이 동시에 쓰면 하나만 성공해야 한다. → Task 2 `test_a_token_can_be_used_once_even_concurrently`.
4. 나중에 새로 생긴 `member_id` 표가 탈퇴 경로에 없으면 CI가 실패해야 한다. → Task 5 `test_every_member_id_table_is_handled_by_the_delete_path`.
5. 인증 화면을 `.html` 없이(`/member/login`) 열어도 CSP가 붙어야 한다. → Task 8 Step 6(curl 헤더 확인).

---

### Task 1: 메일 설정·Mailpit·`mailer.py` (PR D)

**Files:**
- Modify: `python-stock-backend/settings.py`, `compose.portfolio.yml`, `compose.public.yml`, `tests/unit/test_settings.py`
- Create: `python-stock-backend/mailer.py`, `tests/unit/test_mailer.py`

**Interfaces:**
- Produces(`Settings`): `smtp_port: int = 587`, `smtp_user: str = ""`, `smtp_password: str = ""`(repr 제외), `smtp_from: str = ""`, `smtp_starttls: bool = True`, 속성 `email_verification -> bool`(`is_public or bool(smtp_host)`).
- Produces(`app.config`): `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM`, `SMTP_STARTTLS`, `EMAIL_VERIFICATION`.
- Produces(`mailer`): `TEMPLATES`, `valid_address(address: str) -> bool`, `build(kind, to_addr, token, *, sender, base_url) -> EmailMessage`, `send(msg, config: dict) -> None`, `queue(kind: str, to_addr: str, token: str | None = None) -> None`. `kind`는 `"verify"`·`"exists"`·`"reset"`.

- [ ] **Step 1: 실패하는 설정 테스트** — `tests/unit/test_settings.py` 끝에 추가하고, `test_flask_config_keeps_the_original_session_settings`의 기대 dict에 `"SMTP_HOST": "", "SMTP_PORT": 587, "SMTP_USER": "", "SMTP_PASSWORD": "", "SMTP_FROM": "", "SMTP_STARTTLS": True, "EMAIL_VERIFICATION": False`를 더한다.

```python
def test_email_verification_is_on_for_public_and_for_local_with_mail():
    assert Settings.from_env({}).email_verification is False
    local_mail = {"SMTP_HOST": "mailpit", "SMTP_PORT": "1025", "SMTP_STARTTLS": "false",
                  "SMTP_FROM": "no-reply@stockdesk.local", "PUBLIC_BASE_URL": "http://127.0.0.1:3334"}
    settings = Settings.from_env(local_mail)
    assert settings.email_verification is True and settings.smtp_port == 1025 and settings.smtp_starttls is False
    assert Settings.from_env(PUBLIC_OK).email_verification is True


def test_local_mail_needs_a_base_url_for_links():
    with pytest.raises(SettingsError, match="PUBLIC_BASE_URL"):
        Settings.from_env({"SMTP_HOST": "mailpit", "SMTP_FROM": "no-reply@stockdesk.local"})


def test_public_mail_requires_starttls_and_a_sender():
    mail = {**PUBLIC_OK, "SMTP_HOST": "smtp.example.test", "PUBLIC_BASE_URL": "https://desk.example.test"}
    with pytest.raises(SettingsError, match="SMTP_STARTTLS"):
        Settings.from_env({**mail, "SMTP_FROM": "no-reply@example.test", "SMTP_STARTTLS": "false"})
    with pytest.raises(SettingsError, match="SMTP_FROM"):
        Settings.from_env(mail)
    assert Settings.from_env({**mail, "SMTP_FROM": "no-reply@example.test"}).smtp_starttls is True


def test_smtp_password_is_kept_out_of_the_settings_repr():
    settings = Settings.from_env({"SMTP_HOST": "mailpit", "SMTP_PASSWORD": "smtp-secret-value",
                                  "SMTP_FROM": "a@b.test", "PUBLIC_BASE_URL": "http://127.0.0.1:3334"})
    assert "smtp-secret-value" not in repr(settings)
```

- [ ] **Step 2: 실패하는 메일 테스트** `tests/unit/test_mailer.py`

```python
"""메일: 단일 수신자, 고정 템플릿, 프래그먼트 링크, 발송 실패 숨김, 발송 상한."""

import logging
import ssl
from types import SimpleNamespace

import pytest

import mailer
from app import create_app
from settings import Settings

CONFIG = {"SMTP_HOST": "mailpit", "SMTP_PORT": 1025, "SMTP_USER": "", "SMTP_PASSWORD": "", "SMTP_STARTTLS": False}


@pytest.mark.parametrize(
    "address",
    ["a@x.test,b@y.test", "a@x.test b@y.test", "<a@x.test>", "a@x.test\nBcc: c@z.test", "no-at-sign", "a@@x.test",
     "x" * 250 + "@x.test"],
)
def test_only_a_single_plain_address_is_accepted(address):
    assert mailer.valid_address(address) is False
    with pytest.raises(ValueError):
        mailer.build("verify", address, "tok", sender="no-reply@x.test", base_url="https://desk.example.test")


def test_links_use_the_configured_base_and_a_fragment_token():
    msg = mailer.build("reset", "user@example.test", "abc123", sender="no-reply@x.test", base_url="https://desk.example.test")
    body = msg.get_content()
    assert "https://desk.example.test/member/reset.html#t=abc123" in body
    assert "?t=" not in body and msg["To"] == "user@example.test"


def test_templates_take_no_user_text():
    # build에는 닉네임 같은 사용자 입력을 넘길 인자가 없다. 제목·본문은 코드에 고정돼 있다.
    for kind in ("verify", "exists", "reset"):
        msg = mailer.build(kind, "user@example.test", "tok", sender="no-reply@x.test", base_url="https://d.test")
        assert msg["Subject"] == mailer.TEMPLATES[kind][0]


def test_send_uses_one_recipient_and_verified_tls(monkeypatch):
    calls = {}

    class FakeSMTP:
        def __init__(self, host, port, timeout):
            calls["target"] = (host, port)

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def starttls(self, context):
            calls["verify_mode"] = context.verify_mode

        def login(self, user, password):
            calls["login"] = user

        def send_message(self, msg, to_addrs):
            calls["to_addrs"] = to_addrs

    monkeypatch.setattr(mailer.smtplib, "SMTP", FakeSMTP)
    msg = mailer.build("verify", "user@example.test", "tok", sender="no-reply@x.test", base_url="https://d.test")
    mailer.send(msg, {**CONFIG, "SMTP_STARTTLS": True, "SMTP_USER": "u", "SMTP_PASSWORD": "p"})
    assert calls["to_addrs"] == ["user@example.test"] and calls["verify_mode"] == ssl.CERT_REQUIRED


class _Inline:
    """threading.Thread 대용: start()에서 바로 실행한다."""

    def __init__(self, target, daemon):
        self.target = target

    def start(self):
        self.target()


def _mail_app(ratelimit_enabled=False):
    application = create_app(Settings(
        profile="local", secret_key="k" * 40, session_cookie_secure=False, ratelimit_enabled=ratelimit_enabled,
        smtp_host="mailpit", smtp_port=1025, smtp_starttls=False, smtp_from="no-reply@stockdesk.local",
        public_base_url="http://127.0.0.1:3334"))
    application.config.update(TESTING=True)
    return application


def test_send_failure_is_swallowed_and_logged_without_address(monkeypatch, caplog):
    # threading 모듈 전체가 아니라 mailer가 보는 이름만 바꾼다(limiter 저장소도 스레드를 쓴다).
    monkeypatch.setattr(mailer, "threading", SimpleNamespace(Thread=_Inline))

    def broken(msg, config):
        raise ConnectionRefusedError("mail server down")

    monkeypatch.setattr(mailer, "send", broken)
    with _mail_app().test_request_context("/"), caplog.at_level(logging.WARNING, logger="mailer"):
        mailer.queue("verify", "secret-person@example.test", "tok-value")
    assert "ConnectionRefusedError" in caplog.text
    assert "secret-person" not in caplog.text and "tok-value" not in caplog.text


def test_per_address_cap_counts_every_kind(monkeypatch):
    # threading 모듈 전체가 아니라 mailer가 보는 이름만 바꾼다(limiter 저장소도 스레드를 쓴다).
    monkeypatch.setattr(mailer, "threading", SimpleNamespace(Thread=_Inline))
    sent = []
    monkeypatch.setattr(mailer, "send", lambda msg, config: sent.append(msg["To"]))
    with _mail_app(ratelimit_enabled=True).test_request_context("/"):
        for kind in ("verify", "exists", "reset", "verify"):
            mailer.queue(kind, "capped@example.test", "tok")
        mailer.queue("verify", "other@example.test", "tok")
    assert sent == ["capped@example.test"] * 3 + ["other@example.test"]
```

- [ ] **Step 3: 실패 확인** — `docker run --rm -v "$PWD":/repo -w /repo sct-test:dev python -m pytest -q tests/unit/test_settings.py tests/unit/test_mailer.py` → 새 테스트 FAIL(`email_verification` 없음, `mailer` 없음).

- [ ] **Step 4: `settings.py` 구현**
  - `from dataclasses import dataclass, field`로 import를 바꾸고 필드를 더한다(`public_base_url` 아래):

```python
    smtp_port: int = 587
    smtp_user: str = ""
    # 비밀 값이라 repr에 넣지 않는다.
    smtp_password: str = field(default="", repr=False)
    # 보내는 주소. 메일을 쓰면 반드시 정한다.
    smtp_from: str = ""
    # public은 STARTTLS를 끌 수 없다(인증서 검증은 mailer가 기본 SSL 컨텍스트로 한다).
    smtp_starttls: bool = True

    @property
    def email_verification(self) -> bool:
        """메일 인증을 마쳐야 로그인하는 배포인지. public은 항상, local은 SMTP_HOST가 있을 때.

        @returns 메일 인증 사용 여부
        """
        return self.is_public or bool(self.smtp_host)
```

  - `from_env`의 `smtp_host`·`public_base_url` 줄 아래:

```python
        try:
            smtp_port = int(env.get("SMTP_PORT") or "587")
        except ValueError:
            raise SettingsError("SMTP_PORT must be an integer.") from None
        smtp_from = (env.get("SMTP_FROM") or "").strip()
        smtp_starttls = (env.get("SMTP_STARTTLS") or "true").strip().lower() == "true"
        if smtp_host and not public_base_url:
            raise SettingsError("SMTP_HOST needs PUBLIC_BASE_URL for the links in mail.")
        if smtp_host and not smtp_from:
            raise SettingsError("SMTP_HOST needs SMTP_FROM.")
```

  - public `problems`에 `if smtp_host and not smtp_starttls: problems.append("SMTP_STARTTLS must stay on")`.
  - `cls(...)`에 `smtp_port=smtp_port, smtp_user=(env.get("SMTP_USER") or "").strip(), smtp_password=env.get("SMTP_PASSWORD") or "", smtp_from=smtp_from, smtp_starttls=smtp_starttls,`.
  - `flask_config`에 `"SMTP_HOST": self.smtp_host, "SMTP_PORT": self.smtp_port, "SMTP_USER": self.smtp_user, "SMTP_PASSWORD": self.smtp_password, "SMTP_FROM": self.smtp_from, "SMTP_STARTTLS": self.smtp_starttls, "EMAIL_VERIFICATION": self.email_verification,`.

- [ ] **Step 5: `mailer.py` 구현**

```python
"""회원 메일(인증·가입 안내·재설정). 표준 라이브러리 smtplib만 쓴다(설계: S1 스펙 ⑤).

- 제목·본문은 코드에 고정한 템플릿이고 닉네임 같은 사용자 입력을 넣지 않는다(피싱 문구 주입 차단).
- 링크는 PUBLIC_BASE_URL로만 만들고 토큰은 프래그먼트(#t=)에 둔다(서버·접근 로그·Referer에 남지 않게).
- 발송은 요청 밖 스레드에서 하고 실패는 응답에 드러내지 않는다. 로그에는 요청 ID·종류·오류 이름만 남긴다.
"""

from __future__ import annotations

import hashlib
import logging
import re
import smtplib
import ssl
import threading
from email.message import EmailMessage

from flask import current_app
from limits import parse

from errors import request_id
from extensions import limiter

log = logging.getLogger("mailer")

GLOBAL_DAILY = parse("200/day")
PER_ADDRESS = (parse("3/hour"), parse("10/day"))
MAX_ADDRESS_LENGTH = 254
# 주소 하나만: 공백·쉼표·세미콜론·꺾쇠·줄바꿈·두 번째 @가 없어야 한다.
_SINGLE_ADDRESS = re.compile(r"[^\s,;<>@]+@[^\s,;<>@]+\.[^\s,;<>@]+")
TEMPLATES = {
    "verify": (
        "[Noah Trading Desk] 이메일 주소를 확인해 주세요",
        "아래 링크를 열면 가입이 끝납니다. 링크는 24시간 동안 한 번만 쓸 수 있습니다.\n\n{link}\n\n"
        "가입한 적이 없다면 이 메일을 무시하세요.",
    ),
    "exists": (
        "[Noah Trading Desk] 이미 가입된 주소입니다",
        "이 주소로 가입 요청이 있었지만 이미 가입된 주소입니다. 비밀번호가 기억나지 않으면 아래에서 재설정하세요.\n\n"
        "{link}\n\n요청한 적이 없다면 이 메일을 무시하세요.",
    ),
    "reset": (
        "[Noah Trading Desk] 비밀번호 재설정",
        "아래 링크에서 새 비밀번호를 정하세요. 링크는 30분 동안 한 번만 쓸 수 있습니다.\n\n{link}\n\n"
        "요청한 적이 없다면 이 메일을 무시하세요. 비밀번호는 바뀌지 않습니다.",
    ),
}
PATHS = {
    "verify": "/member/verify.html#t={token}",
    "exists": "/member/reset-request.html",
    "reset": "/member/reset.html#t={token}",
}


def valid_address(address: str) -> bool:
    """주소 하나짜리 이메일인지.

    @param address 받는 주소
    @returns 발송해도 되는 단일 주소면 True
    """
    return len(address) <= MAX_ADDRESS_LENGTH and bool(_SINGLE_ADDRESS.fullmatch(address))


def build(kind: str, to_addr: str, token: str | None, *, sender: str, base_url: str) -> EmailMessage:
    """고정 템플릿으로 메일을 만든다.

    @param kind "verify"·"exists"·"reset"
    @param to_addr 받는 주소(단일)
    @param token 링크에 넣을 1회용 토큰(없으면 빈 값)
    @param sender 보내는 주소(SMTP_FROM)
    @param base_url 링크 기준 주소(PUBLIC_BASE_URL)
    @returns 보낼 메시지
    """
    if not valid_address(to_addr):
        raise ValueError("mail recipient must be a single address")
    subject, body = TEMPLATES[kind]
    msg = EmailMessage()
    msg["Subject"], msg["From"], msg["To"] = subject, sender, to_addr
    msg.set_content(body.format(link=base_url + PATHS[kind].format(token=token or "")))
    return msg


def send(msg: EmailMessage, config: dict) -> None:
    """SMTP로 한 통 보낸다. 받는 주소는 msg["To"] 하나로 고정한다.

    @param msg build가 만든 메시지
    @param config SMTP_HOST·SMTP_PORT·SMTP_USER·SMTP_PASSWORD·SMTP_STARTTLS
    """
    with smtplib.SMTP(config["SMTP_HOST"], config["SMTP_PORT"], timeout=15) as smtp:
        if config["SMTP_STARTTLS"]:
            smtp.starttls(context=ssl.create_default_context())
        if config["SMTP_USER"]:
            smtp.login(config["SMTP_USER"], config["SMTP_PASSWORD"])
        smtp.send_message(msg, to_addrs=[msg["To"]])


def _within_caps(address: str) -> bool:
    """전역 하루·수신 주소별 상한 안이면 한 통을 센다. limiter가 꺼진 배포(local)는 세지 않는다.

    @param address 받는 주소
    @returns 보내도 되면 True
    """
    if not limiter.enabled:
        return True
    strategy = limiter.limiter  # public은 Redis 공유 저장소
    key = hashlib.sha256(address.lower().encode("utf-8")).hexdigest()
    checks = [(GLOBAL_DAILY, ("mail", "all")), *((limit, ("mail", key)) for limit in PER_ADDRESS)]
    if not all(strategy.test(limit, *keys) for limit, keys in checks):
        return False
    for limit, keys in checks:
        strategy.hit(limit, *keys)
    return True


def queue(kind: str, to_addr: str, token: str | None = None) -> None:
    """메일을 백그라운드로 보낸다. 메일 미설정·잘못된 주소·상한 초과면 조용히 건너뛴다.

    @param kind "verify"·"exists"·"reset"
    @param to_addr 받는 주소
    @param token 링크 토큰
    """
    config = current_app.config
    if not config.get("SMTP_HOST") or not valid_address(to_addr):
        return
    rid = request_id()
    if not _within_caps(to_addr):
        log.warning("mail cap reached request_id=%s kind=%s", rid, kind)
        return
    msg = build(kind, to_addr, token, sender=config["SMTP_FROM"], base_url=config["PUBLIC_BASE_URL"])
    snapshot = {key: config[key] for key in ("SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASSWORD", "SMTP_STARTTLS")}

    def run() -> None:
        try:
            send(msg, snapshot)
        except Exception as exc:  # noqa: BLE001 - 발송 실패는 요청에 드러내지 않는다
            log.warning("mail send failed request_id=%s kind=%s error=%s", rid, kind, type(exc).__name__)

    threading.Thread(target=run, daemon=True).start()
```

- [ ] **Step 6: Mailpit과 compose**
  - `compose.portfolio.yml`의 `x-portfolio-backend-environment`에 추가:

```yaml
  # 로컬·검증 스택의 메일은 Mailpit이 받는다(밖으로 나가지 않음). 켜져 있으면 가입에 메일 인증이 필요하다.
  SMTP_HOST: mailpit
  SMTP_PORT: "1025"
  SMTP_STARTTLS: "false"
  SMTP_FROM: no-reply@stockdesk.local
  PUBLIC_BASE_URL: http://127.0.0.1:${FRONTEND_PORT:-3333}
```

  - `services:`에 추가(PM 스택 3333과 검증 스택 3334가 함께 떠도 충돌하지 않게 UI 포트는 호스트가 고른다):

```yaml
  mailpit:
    image: axllent/mailpit:v1.31.2
    networks:
      - internal
    # 웹 UI·API(8025)만 127.0.0.1의 임의 포트로 연다. 실제 포트는 `docker port <컨테이너> 8025/tcp`.
    ports:
      - "127.0.0.1::8025"
    restart: unless-stopped
```

  - `python-backend.depends_on`에 `mailpit: {condition: service_started}`를 더한다.
  - `compose.public.yml`의 공개 환경 목록에 `SMTP_PORT: ${SMTP_PORT:-587}`, `SMTP_USER: ${SMTP_USER:-}`, `SMTP_PASSWORD: ${SMTP_PASSWORD:-}`, `SMTP_FROM: ${SMTP_FROM:-}`, `SMTP_STARTTLS: ${SMTP_STARTTLS:-true}`를 더한다(값은 S5에서 SSM으로).

- [ ] **Step 7: 통과 확인** — 단위 전체, `ruff check .`. CI의 Compose 검사와 같은 placeholder 환경변수(`.github/workflows/ci.yml` "Validate Compose files" 값)로 `docker compose -f docker-compose.yml -f compose.portfolio.yml --profile local-db config --quiet`와 공개 조합(`-f compose.public.yml -f compose.edge.yml -f compose.aws.yml`, 값은 `ECR_REGISTRY=example.invalid IMAGE_TAG=ci AWS_REGION=x LOG_GROUP=x SITE_ADDRESS=x ADMIN_EMAIL=x@y.z`)이 통과하는지 확인한다.

- [ ] **Step 8: Commit** — `feat: 메일 발송(mailer)·Mailpit·메일 설정을 추가한다`

---

### Task 2: 회원 열·인증 토큰·열거 없는 가입·인증 전 로그인 거부 (PR D)

**Files:**
- Create: `python-stock-backend/member_tokens.py`, `python-stock-backend/member_account.py`, `tests/integration/test_member_verification.py`, `tests/unit/test_account_rules.py`
- Modify: `python-stock-backend/models.py`(Member 열 4개), `members.py`(열 이전·가입·로그인), `accounts.py`(닉네임·이메일 규칙, 처리방침 버전), `bootstrap.py`(토큰 표, 관리자 인증 표시), `demo_seed.py`(인증 표시), `app.py`(블루프린트), `database/db.sql`, `database/SCHEMA.md`, `tests/unit/snapshots/routes_*.txt`, `tests/unit/test_security_controls.py`

**Interfaces:**
- Produces(`accounts`): `PRIVACY_VERSION = "2026-09-26"`, `normalize_nickname(value) -> str`, `nickname_problem(name: str) -> str | None`, `email_problem(email: str) -> str | None`
- Produces(`member_tokens`): `LIFETIME`, `token_hash`, `ensure_token_table() -> None`, `issue(member_id: int, purpose: str) -> str`, `consume(conn, token: str, purpose: str) -> int | None`(호출자가 `commit`·`rollback`)
- Produces(`member_account.account_bp`): `POST /api/member/verify {token}` → 200 `{"verified": true}` | 400 `INVALID_TOKEN`; `POST /api/member/verify/resend {email}` → 202 `{"status": "accepted"}`
- Produces(`members.register`): 메일 인증 모드 202 `{"status": "check_email"}`, 메일 없는 local은 기존 200+세션

- [ ] **Step 1: 실패하는 규칙 단위 테스트** `tests/unit/test_account_rules.py`

```python
"""닉네임(사칭 방지)과 이메일(단일 주소) 입력 규칙."""

import pytest

from accounts import email_problem, nickname_problem, normalize_nickname


@pytest.mark.parametrize("name", ["주식왕", "ab", "노아 Trader 01", "가" * 20])
def test_ordinary_nicknames_pass(name):
    assert nickname_problem(normalize_nickname(name)) is None


@pytest.mark.parametrize("name", ["a", "가" * 21, "adm‮nimda", "no​ah", "tab\tname", "  "])
def test_short_long_and_invisible_or_control_characters_are_refused(name):
    assert nickname_problem(normalize_nickname(name)) is not None


def test_fullwidth_nickname_is_normalized():
    assert normalize_nickname("ｎｏａｈ") == "noah"


@pytest.mark.parametrize("email", ["a@x.test,b@y.test", "a b@x.test", "<a@x.test>", "a@x.test\n", "x" * 250 + "@x.test", "nope"])
def test_email_must_be_one_plain_address(email):
    assert email_problem(email) is not None


def test_plain_email_passes():
    assert email_problem("user.name+tag@example.test") is None
```

- [ ] **Step 2: 실패하는 통합 테스트** `tests/integration/test_member_verification.py`

```python
"""메일 인증 모드: 열거 없는 가입, 인증 전 로그인 거부, 1회용 토큰, 재전송."""

import threading
import uuid

import pytest
from sqlalchemy import text

import bootstrap
import db
import mailer
import member_tokens
import passwords
from app import create_app
from settings import Settings

pytestmark = pytest.mark.integration
PASSWORD = "long-enough-passphrase-for-tests"
MAIL_SETTINGS = dict(
    profile="local", secret_key="k" * 40, session_cookie_secure=False, smtp_host="mailpit", smtp_port=1025,
    smtp_starttls=False, smtp_from="no-reply@stockdesk.local", public_base_url="http://127.0.0.1:3334",
)


@pytest.fixture(scope="module", autouse=True)
def tables():
    bootstrap.create_tables()


@pytest.fixture
def outbox(monkeypatch):
    sent = []
    monkeypatch.setattr(mailer, "queue", lambda kind, to, token=None: sent.append((kind, to, token)))
    return sent


def _client(**overrides):
    application = create_app(Settings(**{**MAIL_SETTINGS, **overrides}))
    application.config.update(TESTING=True)
    return application.test_client()


def _signup(client, email, **extra):
    return client.post("/api/member/register", json={
        "username": "인증", "email": email, "password": PASSWORD, "password2": PASSWORD,
        "agreeAge": True, "agreePrivacy": True, **extra})


def _cleanup(email):
    with db.engine.begin() as conn:
        member_id = conn.execute(text("SELECT member_id FROM member WHERE email = :e"), {"e": email}).scalar()
        if member_id:
            for table in ("member_token", "member_session", "api_key", "system_error_log", "member"):
                conn.execute(text(f"DELETE FROM {table} WHERE member_id = :id"), {"id": member_id})


@pytest.fixture
def email():
    address = f"verify-{uuid.uuid4().hex[:10]}@example.test"
    yield address
    _cleanup(address)


def test_signup_needs_both_consents(email, outbox):
    response = _signup(_client(), email, agreePrivacy=False)
    assert response.status_code == 400 and response.get_json()["field"] == "consent"


def test_every_signup_path_answers_the_same_and_hashes_once(email, outbox, monkeypatch):
    calls = []
    real = passwords.hash_password
    monkeypatch.setattr(passwords, "hash_password", lambda pw: calls.append(1) or real(pw))
    client = _client()
    fresh = _signup(client, email)
    again = _signup(client, email)
    reserved = _signup(client, f"x-{uuid.uuid4().hex[:6]}@system-bot.local")
    trap = _signup(client, f"trap-{uuid.uuid4().hex[:6]}@example.test", website="http://spam.test")
    answers = {(r.status_code, r.get_data(as_text=True)) for r in (fresh, again, reserved, trap)}
    assert answers == {(202, fresh.get_data(as_text=True))} and fresh.get_json() == {"status": "check_email"}
    assert len(calls) == 4
    assert [kind for kind, _, _ in outbox] == ["verify", "exists"] and {to for _, to, _ in outbox} == {email}


def test_login_is_refused_until_the_email_is_verified(email, outbox):
    client = _client()
    _signup(client, email)
    refused = client.post("/api/member/login", json={"email": email, "password": PASSWORD})
    wrong = client.post("/api/member/login", json={"email": email, "password": PASSWORD + "x"})
    assert refused.status_code == wrong.status_code == 401 and refused.get_json() == wrong.get_json()
    assert client.post("/api/member/verify", json={"token": outbox[0][2]}).status_code == 200
    assert client.post("/api/member/login", json={"email": email, "password": PASSWORD}).status_code == 200


def test_a_token_can_be_used_once_even_concurrently(email, outbox):
    _signup(_client(), email)
    token = outbox[0][2]
    results = []

    def use():
        with db.engine.connect() as conn:
            results.append(member_tokens.consume(conn, token, "verify"))
            conn.commit()

    threads = [threading.Thread(target=use) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert sum(result is not None for result in results) == 1
    assert _client().post("/api/member/verify", json={"token": token}).status_code == 400


def test_a_new_token_replaces_the_old_one_and_only_hashes_are_stored(email, outbox):
    client = _client()
    _signup(client, email)
    first = outbox[0][2]
    assert client.post("/api/member/verify/resend", json={"email": email}).status_code == 202
    second = outbox[1][2]
    with db.engine.connect() as conn:
        stored = conn.execute(text(
            "SELECT token_hash FROM member_token t JOIN member m USING (member_id) WHERE m.email = :e"),
            {"e": email}).scalars().all()
    assert stored == [member_tokens.token_hash(second)]
    assert client.post("/api/member/verify", json={"token": first}).status_code == 400
    assert client.post("/api/member/verify", json={"token": second}).status_code == 200


def test_resend_answers_the_same_for_unknown_addresses(outbox):
    response = _client().post("/api/member/verify/resend", json={"email": f"nobody-{uuid.uuid4().hex[:6]}@example.test"})
    assert response.status_code == 202 and outbox == []


def test_expired_verification_tokens_are_refused(email, outbox):
    _signup(_client(), email)
    token = outbox[0][2]
    with db.engine.begin() as conn:
        conn.execute(text("UPDATE member_token SET expires_at = expires_at - INTERVAL 25 HOUR WHERE token_hash = :h"),
                     {"h": member_tokens.token_hash(token)})
    assert _client().post("/api/member/verify", json={"token": token}).status_code == 400
```

- [ ] **Step 3: 실패 확인** — 단위: 규칙 테스트 FAIL(import 오류). 통합: `scripts/verify/stack.sh up && scripts/verify/stack.sh itest tests/integration/test_member_verification.py` → FAIL(202 아님, 토큰 표 없음).

- [ ] **Step 4: `accounts.py` 규칙**(파일 머리 import에 `import unicodedata`)

```python
PRIVACY_VERSION = "2026-09-26"
NICKNAME_MIN, NICKNAME_MAX = 2, 20


def normalize_nickname(value: object) -> str:
    """닉네임을 NFKC로 정규화하고 앞뒤 공백을 지운다.

    @param value 입력 값
    @returns 정규화한 닉네임
    """
    return unicodedata.normalize("NFKC", str(value or "")).strip()


def nickname_problem(name: str) -> str | None:
    """닉네임 규칙 위반 메시지(2~20자, 제어·방향 전환·폭 0 문자 금지). 통과면 None.

    @param name 정규화한 닉네임
    @returns 위반 메시지 또는 None
    """
    if not NICKNAME_MIN <= len(name) <= NICKNAME_MAX:
        return f"닉네임은 {NICKNAME_MIN}~{NICKNAME_MAX}자로 정해 주세요."
    if any(unicodedata.category(ch) in ("Cc", "Cf") for ch in name):
        return "닉네임에 보이지 않는 문자나 제어 문자를 쓸 수 없습니다."
    return None


def email_problem(email: str) -> str | None:
    """이메일 입력 규칙 위반 메시지(주소 하나, 254자 이하). 통과면 None.

    @param email 입력 이메일(앞뒤 공백 제거 뒤)
    @returns 위반 메시지 또는 None
    """
    import mailer  # mailer가 extensions·errors를 불러오므로 accounts 로딩 순서를 바꾸지 않게 안에서 부른다

    return None if mailer.valid_address(email) else "올바른 이메일 주소 하나를 입력해 주세요."
```

- [ ] **Step 5: `member_tokens.py`**

```python
"""메일 인증·비밀번호 재설정용 1회용 토큰(설계: S1 스펙 ③). DB에는 SHA-256만 둔다."""

from __future__ import annotations

import secrets
from datetime import timedelta

from sqlalchemy import text

from db import engine
from member_sessions import _now, token_hash

LIFETIME = {"verify": timedelta(hours=24), "reset": timedelta(minutes=30)}

TOKEN_TABLE = """CREATE TABLE IF NOT EXISTS member_token (
  token_hash CHAR(64) NOT NULL,
  member_id BIGINT(20) NOT NULL,
  purpose ENUM('verify','reset') NOT NULL,
  expires_at DATETIME NOT NULL COMMENT 'UTC',
  used_at DATETIME NULL COMMENT 'UTC',
  PRIMARY KEY (token_hash),
  KEY idx_member_token_member (member_id, purpose),
  CONSTRAINT fk_member_token_member FOREIGN KEY (member_id) REFERENCES member (member_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci"""

__all__ = ["LIFETIME", "consume", "ensure_token_table", "issue", "token_hash"]


def ensure_token_table() -> None:
    """member_token 표를 만든다(멱등)."""
    with engine.begin() as conn:
        conn.execute(text(TOKEN_TABLE))


def issue(member_id: int, purpose: str) -> str:
    """새 토큰을 발급하고 같은 목적의 이전 토큰을 지운다.

    @param member_id 회원 ID
    @param purpose "verify" 또는 "reset"
    @returns 메일 링크에 넣을 원본 토큰(저장하지 않음)
    """
    token = secrets.token_urlsafe(32)
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM member_token WHERE member_id = :m AND purpose = :p"), {"m": member_id, "p": purpose})
        conn.execute(
            text("INSERT INTO member_token (token_hash, member_id, purpose, expires_at) VALUES (:h, :m, :p, :exp)"),
            {"h": token_hash(token), "m": member_id, "p": purpose, "exp": _now() + LIFETIME[purpose]},
        )
    return token


def consume(conn, token: str, purpose: str) -> int | None:
    """토큰을 원자적으로 사용 처리한다. 커밋·롤백은 호출자가 한다(뒤이은 검사가 실패하면 롤백해 토큰을 되살린다).

    @param conn 트랜잭션 중인 연결
    @param token 원본 토큰
    @param purpose "verify" 또는 "reset"
    @returns 회원 ID, 없거나 만료·사용된 토큰이면 None
    """
    if not token:
        return None
    digest, now = token_hash(token), _now()
    used = conn.execute(
        text("UPDATE member_token SET used_at = :now WHERE token_hash = :h AND purpose = :p "
             "AND used_at IS NULL AND expires_at > :now"),
        {"now": now, "h": digest, "p": purpose},
    ).rowcount
    if used != 1:
        return None
    return conn.execute(text("SELECT member_id FROM member_token WHERE token_hash = :h"), {"h": digest}).scalar()
```

- [ ] **Step 6: 회원 열 이전·모델·seed**
  - `models.Member`에 열을 더한다(`DateTime`, `func` import): `email_verified_at = Column(DateTime)`, `created_at = Column(DateTime, server_default=func.now())`, `consent_version = Column(String(20))`, `consented_at = Column(DateTime)`.
  - `members.py`에 추가하고 `ensure_member_tables()` 끝(`ensure_unique_member_email()` 다음)에서 `ensure_member_columns()`를 부른다:

```python
MEMBER_COLUMNS = {
    "email_verified_at": "DATETIME NULL",
    "created_at": "DATETIME NULL DEFAULT CURRENT_TIMESTAMP",
    "consent_version": "VARCHAR(20) NULL",
    "consented_at": "DATETIME NULL",
}


def ensure_member_columns() -> None:
    """메일 인증·동의 기록 열을 더한다(멱등). 이 열이 생기기 전 계정은 인증된 것으로 본다."""
    with engine.begin() as conn:
        present = set(conn.execute(text(
            "SELECT COLUMN_NAME FROM information_schema.COLUMNS WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'member'"
        )).scalars())
        for name, ddl in MEMBER_COLUMNS.items():
            if name not in present:
                conn.execute(text(f"ALTER TABLE member ADD COLUMN {name} {ddl}"))
        if "email_verified_at" not in present:
            conn.execute(text("UPDATE member SET email_verified_at = NOW()"))
```

  - `database/db.sql`의 `member` DDL에 같은 4개 열을 넣고(`email_verified_at datetime DEFAULT NULL`, `created_at datetime DEFAULT current_timestamp()`, `consent_version varchar(20) DEFAULT NULL`, `consented_at datetime DEFAULT NULL`), `member_session` 뒤에 `member_token` DDL을 넣는다. `SCHEMA.md`에 `member_token` 절과 `member` 새 열 설명(인증·동의)을 더한다.
  - `bootstrap.create_tables()`: `ensure_session_table()` 다음 줄 `ensure_token_table()`(`from member_tokens import ensure_token_table`).
  - `bootstrap.create_admin`: 새로 만들 때 `Member(..., email_verified_at=func.now())`, 재설정 때 `member.email_verified_at = member.email_verified_at or func.now()`(`from sqlalchemy import func, text`).
  - `demo_seed.py`의 `Member(`(약 175행)에 `email_verified_at=now,`를 더한다(Mailpit이 있는 로컬 스택에서도 데모 계정이 로그인되게).

- [ ] **Step 7: 가입·로그인**
  - `members.py` import: `import mailer`, `import member_tokens`, `from accounts import PRIVACY_VERSION, can_sign_in, email_problem, is_reserved_email, nickname_problem, normalize_nickname`, `from sqlalchemy import func, text`.
  - `register()` 전체를 다음으로 바꾼다.

```python
CHECK_EMAIL = {"status": "check_email"}


@member_bp.post("/register")
@limiter.limit("5 per hour")
def register():
    if not current_app.config.get("SIGNUP_ENABLED", True):
        return jsonify({"error": "SIGNUP_CLOSED", "message": "공개 베타 준비 중이라 가입을 잠시 닫았습니다."}), 403
    body = request.get_json(silent=True) or {}
    username = normalize_nickname(body.get("username"))
    email = str(body.get("email") or "").strip()
    password = body.get("password") or ""
    password2 = body.get("password2") or ""

    problem = nickname_problem(username)
    if problem:
        return jsonify({"field": "username", "error": problem}), 400
    problem = email_problem(email)
    if problem:
        return jsonify({"field": "email", "error": problem}), 400
    if not password:
        return jsonify({"field": "password", "error": "비밀번호를 입력해주세요."}), 400
    if password != password2:
        return jsonify({"field": "password2", "error": "패스워드가 일치하지 않습니다."}), 400
    public = current_app.config["APP_PROFILE"] == "public"
    silent = is_reserved_email(email) or (public and email.lower() == admin_email())
    if not current_app.config.get("EMAIL_VERIFICATION"):
        return _register_without_mail(username, email, password, silent)

    if not (body.get("agreeAge") is True and body.get("agreePrivacy") is True):
        return jsonify({"field": "consent", "error": "필수 동의 항목을 확인해 주세요."}), 400
    weak = passwords.problem(password, email=email, nickname=username)
    if weak:
        return jsonify({"field": "password", "error": weak}), 400
    # 여기부터는 모든 경우가 같은 응답이다. bcrypt도 경우마다 한 번씩 돌려 응답 시간을 맞춘다.
    hashed = passwords.hash_password(password)
    if silent or body.get("website"):
        return jsonify(CHECK_EMAIL), 202
    created_id = existing_email = None
    with session_scope() as db:
        existing = db.query(Member).filter(Member.email == email).first()
        if existing:
            existing_email = existing.email
        else:
            member = Member(username=username, email=email, password=hashed, asset=INITIAL_ASSET,
                            consent_version=PRIVACY_VERSION, consented_at=func.now())
            db.add(member)
            try:
                db.flush()
                created_id = member.member_id
            except IntegrityError:
                db.rollback()
                existing_email = email
    if created_id:
        mailer.queue("verify", email, member_tokens.issue(created_id, "verify"))
    elif existing_email:
        mailer.queue("exists", existing_email)
    return jsonify(CHECK_EMAIL), 202


def _register_without_mail(username: str, email: str, password: str, reserved: bool):
    """메일이 없는 로컬 실습: 예전처럼 바로 만들고 인증된 계정으로 로그인한다.

    @param username 닉네임
    @param email 이메일
    @param password 비밀번호
    @param reserved 예약·관리자 주소 여부
    @returns Flask 응답
    """
    if reserved:
        return jsonify({"field": "email", "error": "사용할 수 없는 이메일입니다."}), 400
    weak = passwords.problem(password, email=email, nickname=username)
    if weak:
        return jsonify({"field": "password", "error": weak}), 400
    with session_scope() as db:
        if db.query(Member).filter(Member.email == email).first():
            return jsonify({"field": "email", "error": "이미 존재하는 회원입니다."}), 400
        member = Member(username=username, email=email, password=passwords.hash_password(password),
                        asset=INITIAL_ASSET, email_verified_at=func.now())
        db.add(member)
        try:
            db.flush()
        except IntegrityError:
            db.rollback()
            return jsonify({"field": "email", "error": "이미 존재하는 회원입니다."}), 400
        member_id = member.member_id
    member_sessions.start(member_id)
    return jsonify({"username": username})
```

  - `login()`의 판정 줄을 바꾼다:

```python
        # 메일 인증을 쓰는 배포는 인증 전 계정을 잘못된 비밀번호와 똑같이 거절한다(남의 주소 선점 방지).
        verified = member is not None and (
            member.email_verified_at is not None or not current_app.config.get("EMAIL_VERIFICATION"))
        if not (member and matched and verified and can_sign_in(member.email, current_app.config["APP_PROFILE"])):
```

- [ ] **Step 8: `member_account.py`(인증·재전송)** — `app.py`에서 `member_bp` 등록 옆에 `from member_account import account_bp`와 `app.register_blueprint(account_bp)`를 더한다(기존 등록 줄 모양대로).

```python
"""메일 인증·재설정·비밀번호 변경·탈퇴 API(설계: S1 스펙 ③·④). 가입·로그인은 members.py."""

from __future__ import annotations

from flask import Blueprint, jsonify, request
from sqlalchemy import text

import mailer
import member_tokens
from accounts import is_reserved_email
from db import engine
from extensions import limiter

account_bp = Blueprint("member_account", __name__, url_prefix="/api/member")
ACCEPTED = {"status": "accepted"}
INVALID_TOKEN = {"error": "INVALID_TOKEN", "message": "링크가 만료되었거나 이미 사용되었습니다. 다시 요청해 주세요."}


def _email_from_body() -> str:
    """요청 본문의 이메일(앞뒤 공백 제거).

    @returns 이메일 문자열
    """
    return str((request.get_json(silent=True) or {}).get("email") or "").strip()


def _find_member(email: str):
    """이메일로 회원을 찾는다. 형식이 틀리거나 예약 주소면 찾지 않는다.

    @param email 이메일
    @returns member_id·email·email_verified_at 매핑 또는 None
    """
    if not mailer.valid_address(email) or is_reserved_email(email):
        return None
    with engine.connect() as conn:
        return conn.execute(text("SELECT member_id, email, email_verified_at FROM member WHERE email = :e"),
                            {"e": email}).mappings().first()


@account_bp.post("/verify")
@limiter.limit("20 per hour")
def verify_email():
    """메일 링크의 토큰으로 이메일 인증을 마친다."""
    token = str((request.get_json(silent=True) or {}).get("token") or "")
    with engine.connect() as conn:
        member_id = member_tokens.consume(conn, token, "verify")
        if member_id is None:
            conn.rollback()
            return jsonify(INVALID_TOKEN), 400
        conn.execute(text("UPDATE member SET email_verified_at = COALESCE(email_verified_at, NOW()) WHERE member_id = :m"),
                     {"m": member_id})
        conn.commit()
    return jsonify({"verified": True})


@account_bp.post("/verify/resend")
@limiter.limit("10 per hour")
def resend_verification():
    """인증 메일을 다시 보낸다. 주소가 있든 없든, 이미 인증했든 같은 202로 답한다."""
    row = _find_member(_email_from_body())
    if row and row["email_verified_at"] is None:
        mailer.queue("verify", row["email"], member_tokens.issue(row["member_id"], "verify"))
    return jsonify(ACCEPTED), 202
```

- [ ] **Step 9: 기존 테스트 정리**
  - 라우트 스냅샷 두 파일에 `POST /api/member/verify member_account.verify_email`, `POST /api/member/verify/resend member_account.resend_verification`를 정렬 위치에 넣는다(`pytest tests/unit/test_app_factory.py tests/unit/test_public_profile.py` 실패 diff로 위치 확인).
  - `tests/unit/test_security_controls.py::test_public_admin_address_cannot_register`를 `test_public_admin_address_gets_the_same_answer_as_any_signup`으로 바꾼다. 본문은 `{"username": "관리", "email": "Owner@Example.com", "password": "quiet river finds the sea", "password2": "quiet river finds the sea", "agreeAge": True, "agreePrivacy": True}`, `mock.patch.object(members, "session_scope")`를 건 채 요청하고 `status_code == 202`, `get_json() == {"status": "check_email"}`, `session_scope.assert_not_called()`를 단언한다.
  - 통합 테스트의 닉네임이 1자인 가입 호출(`grep -n '"username": "' tests/`로 찾기: `"k"`, `"x"`, `"d"` 등)을 2자 이상으로 바꾼다.

- [ ] **Step 10: 통과 확인** — 단위 전체, `scripts/verify/stack.sh itest` 전체.

- [ ] **Step 11: Commit** — `feat: 메일 인증을 마쳐야 로그인하고 가입은 가입 여부를 드러내지 않는다`

---

### Task 3: 비밀번호 재설정·변경 (PR D)

**Files:**
- Modify: `python-stock-backend/member_account.py`, 라우트 스냅샷 2개
- Test: `tests/integration/test_member_verification.py`(추가)

**Interfaces:**
- Consumes: `member_tokens.issue/consume`, `mailer.queue`, `passwords.problem/hash_password/verify`, `member_sessions.start`, `authz.admin_email`
- Produces: `POST /api/member/password/reset-request {email}` → 202; `POST /api/member/password/reset {token, password, password2}` → 200 `{"success": true}` | 400; `POST /api/member/password/change {current, password, password2}` → 200 | 400 | 401

- [ ] **Step 1: 실패하는 통합 테스트**(파일 끝에 추가)

```python
NEW_PASSWORD = "another long passphrase here"


def _verified_client(email, outbox):
    client = _client()
    _signup(client, email)
    client.post("/api/member/verify", json={"token": outbox[-1][2]})
    assert client.post("/api/member/login", json={"email": email, "password": PASSWORD}).status_code == 200
    return client


def test_reset_ends_sessions_disables_api_keys_and_does_not_log_in(email, outbox):
    phone = _verified_client(email, outbox)
    assert phone.post("/api/member/api-keys", json={"label": "k1"}).status_code == 200
    assert _client().post("/api/member/password/reset-request", json={"email": email}).status_code == 202
    kind, to, token = outbox[-1]
    assert (kind, to) == ("reset", email)
    browser = _client()
    done = browser.post("/api/member/password/reset", json={"token": token, "password": NEW_PASSWORD, "password2": NEW_PASSWORD})
    assert done.status_code == 200
    assert browser.get("/api/member/me").get_json()["loggedIn"] is False
    assert phone.get("/api/member/me").get_json()["loggedIn"] is False
    with db.engine.connect() as conn:
        active = conn.execute(text(
            "SELECT COUNT(*) FROM api_key k JOIN member m USING (member_id) WHERE m.email = :e AND k.is_active = 1"),
            {"e": email}).scalar()
    assert active == 0
    assert _client().post("/api/member/login", json={"email": email, "password": PASSWORD}).status_code == 401
    assert _client().post("/api/member/login", json={"email": email, "password": NEW_PASSWORD}).status_code == 200


def test_weak_password_does_not_burn_the_reset_token(email, outbox):
    _verified_client(email, outbox)
    _client().post("/api/member/password/reset-request", json={"email": email})
    token = outbox[-1][2]
    weak = _client().post("/api/member/password/reset", json={"token": token, "password": "short", "password2": "short"})
    assert weak.status_code == 400 and weak.get_json()["field"] == "password"
    ok = _client().post("/api/member/password/reset", json={"token": token, "password": NEW_PASSWORD, "password2": NEW_PASSWORD})
    assert ok.status_code == 200


def test_reset_request_answers_the_same_for_unknown_addresses(outbox):
    response = _client().post("/api/member/password/reset-request",
                              json={"email": f"nobody-{uuid.uuid4().hex[:6]}@example.test"})
    assert response.status_code == 202 and outbox == []


def test_reset_also_verifies_the_email(email, outbox):
    client = _client()
    _signup(client, email)
    client.post("/api/member/password/reset-request", json={"email": email})
    token = outbox[-1][2]
    client.post("/api/member/password/reset", json={"token": token, "password": NEW_PASSWORD, "password2": NEW_PASSWORD})
    assert client.post("/api/member/login", json={"email": email, "password": NEW_PASSWORD}).status_code == 200


def test_change_keeps_this_session_and_ends_the_others(email, outbox):
    laptop = _verified_client(email, outbox)
    phone = _client()
    phone.post("/api/member/login", json={"email": email, "password": PASSWORD})
    wrong = laptop.post("/api/member/password/change",
                        json={"current": "nope-nope-nope", "password": NEW_PASSWORD, "password2": NEW_PASSWORD})
    assert wrong.status_code == 400 and wrong.get_json()["field"] == "current"
    ok = laptop.post("/api/member/password/change",
                     json={"current": PASSWORD, "password": NEW_PASSWORD, "password2": NEW_PASSWORD})
    assert ok.status_code == 200
    assert laptop.get("/api/member/me").get_json()["loggedIn"] is True
    assert phone.get("/api/member/me").get_json()["loggedIn"] is False
```

- [ ] **Step 2: 실패 확인** — `scripts/verify/stack.sh itest tests/integration/test_member_verification.py` → 새 테스트 404로 FAIL.

- [ ] **Step 3: 구현** — `member_account.py` import를 `from flask import Blueprint, current_app, jsonify, request, session`로 넓히고 `import member_sessions`, `import passwords`, `from authz import admin_email`를 더한 뒤 추가한다.

```python
def _member_key() -> str:
    """회원 단위 제한 키(세션은 before_request 훅이 이미 검증했다).

    @returns "member:<id>"
    """
    return f"member:{session.get('member_id')}"


@account_bp.post("/password/reset-request")
@limiter.limit("10 per hour")
def request_password_reset():
    """재설정 메일을 보낸다. 항상 202. 공개 배포의 관리자 주소는 메일로 재설정하지 않는다(CLI만)."""
    email = _email_from_body()
    public_admin = current_app.config["APP_PROFILE"] == "public" and email.lower() == admin_email()
    row = None if public_admin else _find_member(email)
    if row:
        mailer.queue("reset", row["email"], member_tokens.issue(row["member_id"], "reset"))
    return jsonify(ACCEPTED), 202


@account_bp.post("/password/reset")
@limiter.limit("20 per hour")
def reset_password():
    """토큰으로 새 비밀번호를 정한다. 모든 세션을 끝내고 API 키를 끄며, 자동 로그인하지 않는다."""
    body = request.get_json(silent=True) or {}
    token, password, password2 = str(body.get("token") or ""), body.get("password") or "", body.get("password2") or ""
    if not password or password != password2:
        return jsonify({"field": "password2", "error": "비밀번호가 일치하지 않습니다."}), 400
    with engine.connect() as conn:
        member_id = member_tokens.consume(conn, token, "reset")
        if member_id is None:
            conn.rollback()
            return jsonify(INVALID_TOKEN), 400
        row = conn.execute(text("SELECT email, username FROM member WHERE member_id = :m"), {"m": member_id}).mappings().first()
        weak = passwords.problem(password, email=row["email"], nickname=row["username"] or "")
        if weak:
            conn.rollback()  # 토큰을 되살려 같은 링크로 다시 시도하게 한다
            return jsonify({"field": "password", "error": weak}), 400
        conn.execute(text("UPDATE member SET password = :p, email_verified_at = COALESCE(email_verified_at, NOW()) "
                          "WHERE member_id = :m"), {"p": passwords.hash_password(password), "m": member_id})
        conn.execute(text("DELETE FROM member_session WHERE member_id = :m"), {"m": member_id})
        conn.execute(text("UPDATE api_key SET is_active = 0 WHERE member_id = :m"), {"m": member_id})
        conn.commit()
    session.clear()
    return jsonify({"success": True})


@account_bp.post("/password/change")
@limiter.limit("10 per hour", key_func=_member_key)
def change_password():
    """현재 비밀번호를 확인하고 바꾼다. 다른 기기 세션은 끝내고 이 기기는 새 세션을 받는다."""
    member_id = session.get("member_id")
    if not member_id:
        return jsonify({"error": "UNAUTHORIZED", "message": "로그인이 필요합니다."}), 401
    body = request.get_json(silent=True) or {}
    current, password, password2 = body.get("current") or "", body.get("password") or "", body.get("password2") or ""
    if not password or password != password2:
        return jsonify({"field": "password2", "error": "비밀번호가 일치하지 않습니다."}), 400
    with engine.connect() as conn:
        row = conn.execute(text("SELECT email, username, password FROM member WHERE member_id = :m"),
                           {"m": member_id}).mappings().first()
        if not row or not passwords.verify(current, row["password"]):
            return jsonify({"field": "current", "error": "현재 비밀번호가 맞지 않습니다."}), 400
        weak = passwords.problem(password, email=row["email"], nickname=row["username"] or "")
        if weak:
            return jsonify({"field": "password", "error": weak}), 400
        conn.execute(text("UPDATE member SET password = :p WHERE member_id = :m"),
                     {"p": passwords.hash_password(password), "m": member_id})
        conn.execute(text("DELETE FROM member_session WHERE member_id = :m"), {"m": member_id})
        conn.commit()
    member_sessions.start(member_id)
    return jsonify({"success": True})
```

- [ ] **Step 4: 라우트 스냅샷에 세 경로 추가, 통과 확인**(단위 전체, itest 전체).
- [ ] **Step 5: Commit** — `feat: 메일로 비밀번호를 재설정하고 로그인한 채 비밀번호를 바꾼다`

---

### Task 4: 오류 보고기·F1 메일 흐름·PR D

**Files:**
- Modify: `frontend/js/common.js`(오류 보고 URL), `scripts/verify/common.py`(Mailpit 조회), `scripts/verify/f1_accounts.py`, `.claude/skills/verify-stockdesk/features/F1-accounts.md`, `.claude/skills/verify-stockdesk/SKILL.md`

- [ ] **Step 1: 오류 보고기** — `common.js`의 `JSON.stringify({ ...payload, url: location.href })`를 `JSON.stringify({ ...payload, url: location.origin + location.pathname })`로 바꾸고, 위 주석에 "주소의 쿼리·프래그먼트(메일 링크 토큰)는 보내지 않는다"를 더한다.

- [ ] **Step 2: Mailpit 조회 도구**(`scripts/verify/common.py`, `import urllib.parse` 추가)

```python
def mail_link(to: str, path: str, wait: float = 15.0) -> str:
    """검증 스택 Mailpit에서 to에게 온 가장 최근 메일의 링크(path를 포함)를 찾는다.

    @param to 받는 주소
    @param path 링크 경로 앞부분(예: "/member/verify.html#t=")
    @param wait 메일을 기다릴 최대 초
    @returns 링크 전체 문자열
    """
    container = subprocess.run(
        ["docker", "ps", "-q", "--filter", f"label=com.docker.compose.project={PROJECT}",
         "--filter", "label=com.docker.compose.service=mailpit"],
        check=True, capture_output=True, text=True,
    ).stdout.strip()
    if not container:
        raise RuntimeError("검증 스택에 Mailpit이 없습니다")
    port = subprocess.run(["docker", "port", container, "8025/tcp"], check=True, capture_output=True,
                          text=True).stdout.split(":")[-1].strip()
    api = f"http://127.0.0.1:{port}/api/v1"
    pattern = re.compile(r"https?://\S+" + re.escape(path) + r"\S*")
    deadline = time.monotonic() + wait
    while time.monotonic() < deadline:
        query = urllib.parse.quote(f'to:"{to}"')
        with urllib.request.urlopen(f"{api}/search?query={query}", timeout=10) as response:
            messages = json.loads(response.read()).get("messages") or []
        for message in messages:  # 최신 순
            with urllib.request.urlopen(f"{api}/message/{message['ID']}", timeout=10) as response:
                match = pattern.search(json.loads(response.read()).get("Text", ""))
            if match:
                return match.group(0)
        time.sleep(0.5)
    raise AssertionError(f"{wait}초 안에 {path} 링크 메일이 오지 않음")
```

  (증거에는 링크를 넣지 않는다. 토큰을 쓴 단계는 입력에 `{"token": "***"}`로 기록한다.)

- [ ] **Step 3: F1 재작성** — `steps()`를 다음 순서로 바꾼다(괄호는 `rec.add` 단계 이름).
  1. health(기존)
  2. 짧은 비밀번호 400(`register-short-password`, 본문에 `agreeAge`·`agreePrivacy`)
  3. 가입 202 `check_email`(`register`)
  4. 인증 전 로그인 401(`login-before-verify`)
  5. `mail_link(email, "/member/verify.html#t=")`에서 `#t=` 뒤를 토큰으로 → `POST /api/member/verify` 200(`verify`), 같은 토큰 다시 400(`verify-reuse`)
  6. 로그인 200 → `/me` True(`login`, `me-after-login`)
  7. 복사 쿠키 거부·로그아웃·재로그인·두 번째 기기·모든 기기 로그아웃(기존 단계 유지)
  8. 재설정 요청 202(`reset-request`) → `mail_link(email, "/member/reset.html#t=")` → `POST /api/member/password/reset` 200(`reset`) → 옛 비밀번호 로그인 401(`login-old-password`) → 새 비밀번호 로그인 200(`login-new-password`)
  9. 비밀번호 변경 200(`password-change`) → `/me` True(`me-after-change`)
  10. DB 회원 행 1(기존)
  - 비밀번호는 `"verify-" + secrets.token_hex(8)`, 재설정 비밀번호 `"verify-new-" + secrets.token_hex(8)`, 변경 비밀번호 `"verify-changed-" + secrets.token_hex(8)`.
- [ ] **Step 4: 문서** — F1 지도에 `f1-verify`·`f1-reset`·`f1-change`를 더하고 사용자 경로·API 목록을 갱신한다. SKILL.md 함정 절에 "검증 스택은 Mailpit이 있어 메일 인증 모드다. 가입만으로는 로그인되지 않는다. 메일은 `common.mail_link`로 읽는다"를 더하고, Helpers 표에 `common.mail_link`를 적는다.
- [ ] **Step 5: 확인** — `scripts/verify/stack.sh up`(Mailpit 포함 재빌드) → `doctor` → `python3 scripts/verify/f1_accounts.py` PASS, `f2_backtest.py` PASS. `docker ps --filter label=com.docker.compose.project=stockdesk-verify`에 mailpit이 있고 PM 스택(3333) 컨테이너 목록은 전후가 같다.
- [ ] **Step 6: Commit** — `feat: 오류 보고에서 주소의 토큰을 빼고 F1이 메일 인증·재설정까지 돈다`
- [ ] **Step 7: PR D** — 계획 문서를 함께 올린다. CI 3개 통과 → 머지. 공개 배포는 PR F 뒤 한 번에 한다.

---

### Task 5: 탈퇴와 삭제 누락 스캔 (PR E)

**Files:**
- Create: `python-stock-backend/member_delete.py`, `tests/integration/test_member_delete.py`
- Modify: `member_account.py`(탈퇴 API), `member_sessions.py`(활동일 표 DDL만), `bootstrap.py`(`ensure_deletable`), 라우트 스냅샷 2개, `database/SCHEMA.md`(`ai_usage.member_id` NULL 허용 이유)

**Interfaces:**
- Produces(`member_delete`): `DELETE_TABLES: tuple[str, ...]`, `NULLIFY_TABLES: tuple[str, ...]`, `ensure_deletable() -> None`, `delete_member(member_id: int) -> None`
- Produces(`member_sessions`): `ACTIVITY_TABLE`(이 Task에서 표만 만든다. 기록은 Task 6)
- Produces: `POST /api/member/delete {password}` → 200 `{"success": true}` | 400 | 401

- [ ] **Step 1: 실패하는 통합 테스트** `tests/integration/test_member_delete.py`

```python
"""탈퇴: 한 트랜잭션 삭제, member_id를 가진 모든 표 0행(information_schema 스캔), AI 비용 합계 보존."""

import uuid

import pytest
from sqlalchemy import text

import bootstrap
import db
import member_delete
from app import create_app
from settings import Settings

pytestmark = pytest.mark.integration
PASSWORD = "long-enough-passphrase-for-tests"


@pytest.fixture(scope="module", autouse=True)
def tables():
    bootstrap.create_tables()


def _client():
    application = create_app(Settings(profile="local", secret_key="k" * 40, session_cookie_secure=False))
    application.config.update(TESTING=True)
    return application.test_client()


def _member_tables(conn):
    return conn.execute(text(
        "SELECT TABLE_NAME FROM information_schema.COLUMNS WHERE TABLE_SCHEMA = DATABASE() "
        "AND COLUMN_NAME = 'member_id' AND TABLE_NAME <> 'member'")).scalars().all()


def test_deleting_an_account_leaves_no_row_with_its_id_anywhere():
    email = f"bye-{uuid.uuid4().hex[:10]}@example.test"
    client = _client()
    assert client.post("/api/member/register", json={"username": "탈퇴", "email": email, "password": PASSWORD,
                                                      "password2": PASSWORD}).status_code == 200
    assert client.post("/api/member/api-keys", json={"label": "k"}).status_code == 200
    with db.engine.begin() as conn:
        member_id = conn.execute(text("SELECT member_id FROM member WHERE email = :e"), {"e": email}).scalar()
        conn.execute(text("INSERT INTO hts_watch_memo (member_id, symbol, memo) VALUES (:m, '005930', 'memo')"), {"m": member_id})
        conn.execute(text("INSERT INTO system_error_log (source, message, member_id) VALUES ('SERVER', 'x', :m)"), {"m": member_id})
        invite = conn.execute(text(
            "INSERT INTO ai_invite (code_hash, label, member_id, expires_at, max_requests, max_tokens) "
            "VALUES (:h, 'bye', :m, NOW() + INTERVAL 1 DAY, 1, 1) RETURNING invite_id"),
            {"h": uuid.uuid4().hex * 2, "m": member_id}).scalar()
        conn.execute(text("INSERT INTO ai_usage (member_id, invite_id, model, status, cost_usd, question_chars) "
                          "VALUES (:m, :i, 'claude-opus-5-5', 'ok', 1.25, 10)"), {"m": member_id, "i": invite})
    assert client.post("/api/member/delete", json={"password": "not-the-password"}).status_code == 400
    assert client.post("/api/member/delete", json={"password": PASSWORD}).status_code == 200
    assert client.get("/api/member/me").get_json()["loggedIn"] is False
    with db.engine.connect() as conn:
        leftovers = {table: conn.execute(text(f"SELECT COUNT(*) FROM {table} WHERE member_id = :m"),
                                         {"m": member_id}).scalar() for table in _member_tables(conn)}
        gone = conn.execute(text("SELECT COUNT(*) FROM member WHERE member_id = :m"), {"m": member_id}).scalar()
        kept = conn.execute(text("SELECT SUM(cost_usd) FROM ai_usage WHERE invite_id = :i"), {"i": invite}).scalar()
        revoked = conn.execute(text("SELECT revoked_at IS NOT NULL FROM ai_invite WHERE invite_id = :i"), {"i": invite}).scalar()
        conn.execute(text("DELETE FROM ai_usage WHERE invite_id = :i"), {"i": invite})
        conn.execute(text("DELETE FROM ai_invite WHERE invite_id = :i"), {"i": invite})
        conn.commit()
    assert leftovers == {table: 0 for table in leftovers} and gone == 0
    assert float(kept) == 1.25 and revoked == 1


def test_every_member_id_table_is_handled_by_the_delete_path():
    with db.engine.connect() as conn:
        found = set(_member_tables(conn))
    handled = set(member_delete.DELETE_TABLES) | set(member_delete.NULLIFY_TABLES) | {"ai_invite"}
    assert found - handled == set(), f"탈퇴 경로에 없는 member_id 표: {sorted(found - handled)}"
```

(`INSERT … RETURNING`은 MariaDB 10.5부터 된다. 11.4에서 동작한다.)

- [ ] **Step 2: 실패 확인** — itest → import 오류·404로 FAIL.

- [ ] **Step 3: 활동일 표 DDL**(`member_sessions.py`; 기록 로직은 Task 6)

```python
# 로그인한 회원이 활동한 날(KST)만 하루 1행. IP·기기·페이지는 남기지 않는다(스펙 ④ 측정).
ACTIVITY_TABLE = """CREATE TABLE IF NOT EXISTS member_activity_day (
  member_id BIGINT(20) NOT NULL,
  day DATE NOT NULL,
  PRIMARY KEY (member_id, day),
  CONSTRAINT fk_member_activity_member FOREIGN KEY (member_id) REFERENCES member (member_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci"""
```

  `ensure_session_table()`이 `SESSION_TABLE` 다음에 `ACTIVITY_TABLE`도 실행하게 하고 docstring을 "세션·활동일 표를 만든다(멱등)."로 바꾼다.

- [ ] **Step 4: `member_delete.py`**

```python
"""회원 탈퇴: 회원과 소유 데이터를 한 트랜잭션으로 지운다(설계: S1 스펙 ④).

삭제 목록에 없는 member_id 표가 생기면 tests/integration/test_member_delete.py가 실패한다.
"""

from __future__ import annotations

from sqlalchemy import text

from db import engine

# 자식 표부터 지운다(모의 KIS 주문·포지션 → 계좌).
DELETE_TABLES = (
    "hold_crypto", "crypto_order", "stock_order", "stock_position",
    "kis_practice_order", "kis_practice_position", "kis_practice_account",
    "hts_watch_memo", "alternative_order", "alternative_position", "api_key",
    "member_session", "member_token", "member_activity_day",
)
# 기록은 남기되 누구의 것인지 끊는다. ai_usage는 월 AI 예산 합계를 지키려고 남긴다. 로그는 90일 뒤 지워진다.
NULLIFY_TABLES = ("system_error_log", "api_usage_log", "ai_usage")


def ensure_deletable() -> None:
    """ai_usage.member_id를 NULL 허용으로 바꾼다(멱등). 탈퇴해도 비용 행을 남기기 위해서다."""
    with engine.begin() as conn:
        nullable = conn.execute(text(
            "SELECT IS_NULLABLE FROM information_schema.COLUMNS WHERE TABLE_SCHEMA = DATABASE() "
            "AND TABLE_NAME = 'ai_usage' AND COLUMN_NAME = 'member_id'")).scalar()
        if nullable == "NO":
            conn.execute(text("ALTER TABLE ai_usage MODIFY member_id BIGINT(20) NULL"))


def delete_member(member_id: int) -> None:
    """회원과 소유 데이터를 지운다. 초대 코드는 연결을 끊고 폐기한다.

    @param member_id 탈퇴할 회원 ID
    """
    params = {"m": member_id}
    with engine.begin() as conn:
        for table in DELETE_TABLES:
            conn.execute(text(f"DELETE FROM {table} WHERE member_id = :m"), params)
        conn.execute(text("UPDATE ai_invite SET member_id = NULL, revoked_at = COALESCE(revoked_at, NOW()) "
                          "WHERE member_id = :m"), params)
        for table in NULLIFY_TABLES:
            conn.execute(text(f"UPDATE {table} SET member_id = NULL WHERE member_id = :m"), params)
        conn.execute(text("DELETE FROM member WHERE member_id = :m"), params)
```

- [ ] **Step 5: 탈퇴 API**(`member_account.py`, `import member_delete`)

```python
@account_bp.post("/delete")
@limiter.limit("10 per hour", key_func=_member_key)
def delete_account():
    """현재 비밀번호를 확인하고 회원과 소유 데이터를 즉시 지운다."""
    member_id = session.get("member_id")
    if not member_id:
        return jsonify({"error": "UNAUTHORIZED", "message": "로그인이 필요합니다."}), 401
    password = (request.get_json(silent=True) or {}).get("password") or ""
    with engine.connect() as conn:
        stored = conn.execute(text("SELECT password FROM member WHERE member_id = :m"), {"m": member_id}).scalar()
    if not passwords.verify(password, stored):
        return jsonify({"field": "password", "error": "비밀번호가 맞지 않습니다."}), 400
    member_delete.delete_member(member_id)
    session.clear()
    return jsonify({"success": True})
```

  - `bootstrap.create_tables()` 끝(`ensure_ai_tables()` 뒤)에 `ensure_deletable()`(`from member_delete import ensure_deletable`).
  - 통합 테스트 도우미 5곳(`test_member_accounts.py`, `test_stock_order_race.py`, `test_deskmcp_end_to_end.py`, `test_member_sessions.py`, `test_member_verification.py`)의 수동 삭제 루프를 `member_delete.delete_member(member_id)` 한 줄로 바꾼다(삭제 목록을 한 곳에만 둔다).

- [ ] **Step 6: 통과 확인** — 라우트 스냅샷에 `POST /api/member/delete member_account.delete_account`, 단위 전체, itest 전체. `DELETE_TABLES`에서 `"api_key"`를 잠시 빼면 두 테스트가 실패하는지 한 번 확인하고 되돌린다.
- [ ] **Step 7: Commit** — `feat: 비밀번호를 확인하고 회원과 소유 데이터를 즉시 지운다`

---

### Task 6: 활동일 기록·7일 미인증·로그 90일 정리 (PR E)

**Files:**
- Create: `python-stock-backend/retention.py`, `tests/integration/test_retention.py`
- Modify: `member_sessions.py`(활동일 기록), `scheduler.py`, `tests/unit/test_scheduler_worker.py`, `tests/unit/test_price_sources.py`, `database/db.sql`, `database/SCHEMA.md`

**Interfaces:**
- Produces(`member_sessions`): `_record_activity(conn, member_id: int) -> None`
- Produces(`retention`): `UNVERIFIED_DAYS = 7`, `LOG_DAYS = 90`, `purge_unverified_members() -> int`, `purge_old_logs() -> int`

- [ ] **Step 1: 실패하는 통합 테스트** `tests/integration/test_retention.py`

```python
"""활동일 하루 1행, 7일 미인증 계정 삭제(새 가입 흐름만), 90일 지난 로그 삭제."""

import uuid

import pytest
from sqlalchemy import text

import bootstrap
import db
import member_delete
import retention
from app import create_app
from settings import Settings

pytestmark = pytest.mark.integration
PASSWORD = "long-enough-passphrase-for-tests"


@pytest.fixture(scope="module", autouse=True)
def tables():
    bootstrap.create_tables()


def _insert_member(conn, email, verified, consent, age_days):
    conn.execute(text(
        "INSERT INTO member (username, email, password, asset, email_verified_at, consent_version, created_at) "
        "VALUES ('정리', :e, 'x', 0, IF(:v, NOW(), NULL), :c, NOW() - INTERVAL :d DAY)"),
        {"e": email, "v": verified, "c": consent, "d": age_days})
    return conn.execute(text("SELECT member_id FROM member WHERE email = :e"), {"e": email}).scalar()


def test_only_stale_unverified_signups_are_removed():
    tag = uuid.uuid4().hex[:8]
    with db.engine.begin() as conn:
        stale = _insert_member(conn, f"stale-{tag}@example.test", False, "2026-09-26", 8)
        fresh = _insert_member(conn, f"fresh-{tag}@example.test", False, "2026-09-26", 1)
        legacy = _insert_member(conn, f"legacy-{tag}@example.test", False, None, 30)
        verified = _insert_member(conn, f"ok-{tag}@example.test", True, "2026-09-26", 30)
    assert retention.purge_unverified_members() >= 1
    with db.engine.connect() as conn:
        left = set(conn.execute(text("SELECT member_id FROM member WHERE member_id IN (:a, :b, :c, :d)"),
                                {"a": stale, "b": fresh, "c": legacy, "d": verified}).scalars())
    for member_id in left:
        member_delete.delete_member(member_id)
    assert left == {fresh, legacy, verified}


def test_logs_older_than_90_days_are_removed():
    marker = f"retention-{uuid.uuid4().hex[:8]}"
    with db.engine.begin() as conn:
        conn.execute(text("INSERT INTO system_error_log (source, message, occurred_at) VALUES "
                          "('SERVER', :m, NOW() - INTERVAL 91 DAY), ('SERVER', :m, NOW() - INTERVAL 89 DAY)"), {"m": marker})
    retention.purge_old_logs()
    with db.engine.begin() as conn:
        left = conn.execute(text("SELECT COUNT(*) FROM system_error_log WHERE message = :m"), {"m": marker}).scalar()
        conn.execute(text("DELETE FROM system_error_log WHERE message = :m"), {"m": marker})
    assert left == 1


def test_a_logged_in_day_is_recorded_once_without_device_data():
    email = f"active-{uuid.uuid4().hex[:8]}@example.test"
    application = create_app(Settings(profile="local", secret_key="k" * 40, session_cookie_secure=False))
    application.config.update(TESTING=True)
    client = application.test_client()
    client.post("/api/member/register", json={"username": "활동", "email": email, "password": PASSWORD, "password2": PASSWORD})
    client.post("/api/member/login", json={"email": email, "password": PASSWORD})
    with db.engine.connect() as conn:
        member_id = conn.execute(text("SELECT member_id FROM member WHERE email = :e"), {"e": email}).scalar()
        rows = conn.execute(text("SELECT COUNT(*) FROM member_activity_day WHERE member_id = :m"), {"m": member_id}).scalar()
        columns = set(conn.execute(text("SELECT COLUMN_NAME FROM information_schema.COLUMNS WHERE TABLE_SCHEMA = DATABASE() "
                                        "AND TABLE_NAME = 'member_activity_day'")).scalars())
    member_delete.delete_member(member_id)
    assert rows == 1 and columns == {"member_id", "day"}
```

- [ ] **Step 2: 실패 확인** — itest → `retention` 없음 FAIL.

- [ ] **Step 3: 활동일 기록**(`member_sessions.py`, `from zoneinfo import ZoneInfo`)

```python
KST = ZoneInfo("Asia/Seoul")


def _record_activity(conn, member_id: int) -> None:
    """오늘(KST) 활동을 한 번만 기록한다.

    @param conn 트랜잭션 중인 연결
    @param member_id 회원 ID
    """
    conn.execute(text("INSERT IGNORE INTO member_activity_day (member_id, day) VALUES (:m, :d)"),
                 {"m": member_id, "d": datetime.now(KST).date()})
```

  `start()`의 INSERT 다음 줄과 `validate()`의 TOUCH 갱신 다음 줄에서 `_record_activity(conn, member_id)`를 부른다.

- [ ] **Step 4: `retention.py`**

```python
"""정기 정리: 7일 미인증 가입, 90일 지난 로그(설계: S1 스펙 ③·④). worker가 매일 실행한다.

시각 비교는 DB의 NOW()로 한다(열 기본값이 DB 시각이라 파이썬 시각과 섞지 않는다).
"""

from __future__ import annotations

from sqlalchemy import text

from db import engine
from member_delete import delete_member

UNVERIFIED_DAYS = 7
LOG_DAYS = 90


def purge_unverified_members() -> int:
    """새 가입 흐름(동의 기록 있음)으로 만든 뒤 7일 안에 인증하지 않은 계정을 지운다.

    @returns 지운 계정 수
    """
    with engine.connect() as conn:
        ids = conn.execute(text(
            "SELECT member_id FROM member WHERE email_verified_at IS NULL AND consent_version IS NOT NULL "
            f"AND created_at < NOW() - INTERVAL {UNVERIFIED_DAYS} DAY")).scalars().all()
    for member_id in ids:
        delete_member(member_id)
    return len(ids)


def purge_old_logs() -> int:
    """90일 지난 오류·외부 API 사용 로그를 지운다.

    @returns 지운 행 수
    """
    with engine.begin() as conn:
        errors = conn.execute(text(f"DELETE FROM system_error_log WHERE occurred_at < NOW() - INTERVAL {LOG_DAYS} DAY")).rowcount
        usage = conn.execute(text(f"DELETE FROM api_usage_log WHERE called_at < NOW() - INTERVAL {LOG_DAYS} DAY")).rowcount
    return errors + usage
```

- [ ] **Step 5: worker 등록**(`scheduler.py`, `purge_expired` 등록 아래)

```python
    from retention import purge_old_logs, purge_unverified_members

    scheduler.add_job(purge_unverified_members, CronTrigger(hour=3, minute=10, timezone="Asia/Seoul"), id="member_unverified_purge")
    scheduler.add_job(purge_old_logs, CronTrigger(hour=3, minute=20, timezone="Asia/Seoul"), id="log_retention")
```

  - `test_scheduler_worker.py` 기대 집합·정렬 목록과 `test_price_sources.py`의 `names`(`["run_bot_trading_round", "purge_expired", "purge_unverified_members", "purge_old_logs"]`)를 갱신하고, 두 작업의 시·분(3:10, 3:20)을 단언한다.
  - `db.sql`에 `member_activity_day` DDL, `SCHEMA.md`에 활동일 절(하루 1행, IP·기기 없음)과 보관 규칙(미인증 7일, 로그 90일)을 더한다.

- [ ] **Step 6: 통과 확인·Commit** — 단위·itest 전체. `feat: 활동일을 하루 한 줄만 남기고 미인증 계정과 오래된 로그를 정리한다`

---

### Task 7: 개인정보 처리방침·PR E

**Files:**
- Create: `frontend/privacy.html`(Task 8의 공용 머리·`auth.css`로 작성. Task 8보다 먼저 하면 `auth.css`는 Task 8 Step 3을 이때 만든다)
- Test: `tests/unit/test_account_rules.py`(한 줄 추가)

- [ ] **Step 1: 초안 작성** — 머리는 Task 8 Step 4의 공용 머리(`data-page="privacy"`, `auth-card wide`), 본문은 `<section class="doc">` 안에 `<h2>`·`<p>`·`<ul>`로 아래 내용을 쓴다. 맨 위에 "버전 2026-09-26(초안). 가입을 열기 전에 법률 확인을 거쳐 확정합니다."
  1. 수집 항목: 이메일, 닉네임, 비밀번호 해시(원문은 저장하지 않음), 필수 동의 기록(버전·시각), 로그인한 날짜(하루 한 줄), 모의투자 기록(주문·보유·메모·API 키 해시), 오류 기록의 IP 주소와 브라우저 정보.
  2. 목적: 회원 식별과 로그인, 메일 인증·비밀번호 재설정, 모의투자 기능 제공, 오류 진단과 남용 방지, 서비스 이용 통계(주간 이용자 수처럼 개인을 드러내지 않는 집계).
  3. 보관 기간: 탈퇴하면 즉시 파기. 7일 안에 메일 인증을 마치지 않은 가입은 자동 삭제. 오류·외부 API 사용 기록은 90일 뒤 삭제(탈퇴 때 회원과의 연결을 먼저 끊음). 서버 로그(AWS CloudWatch)는 30일 보관.
  4. 처리위탁·국외 이전: Amazon Web Services(서울 리전)에 서버와 데이터 보관. 메일 발송 서비스는 연결할 때 이 문서에 적는다. 해외 AI 서비스(Anthropic 등, 미국)는 해당 기능을 켜기 전에 이 문서를 고치고 다시 동의를 받는다.
  5. 이용자 권리: 계정 설정 화면에서 비밀번호 변경·모든 기기 로그아웃·즉시 탈퇴. 그 밖의 열람·정정 요청은 문의 주소로.
  6. 만 14세 미만은 가입할 수 없다.
  7. 안전성 확보 조치: 비밀번호 해시 저장(bcrypt), 로그인 세션 서버 확인, 전송 구간 암호화(HTTPS), 관리자 접근 제한.
  8. 문의: "문의 주소는 확정 때 적습니다."(운영자 공개 주소는 **노아 결정 항목**)
  9. 투자 조언 아님: 이 서비스는 계산과 출처를 보여 주는 도구이며 투자 권유나 조언을 하지 않는다.
- [ ] **Step 2: 검토 위임** — Legal Compliance Checker 1명에게 초안과 스펙 ④를 주고, 한국 개인정보 보호법 기준으로 빠진 필수 기재사항, 국외 이전 고지 방식, 만 14세 확인 방법, 고칠 문구를 표로 받는다. 금지: 파일 수정. PM이 반영하고, **노아 법률 확인**과 문의 주소는 증거 문서의 "노아 항목"과 S5 관문 목록에 남긴다.
- [ ] **Step 3: 버전 고정 테스트**(`tests/unit/test_account_rules.py` 끝)

```python
def test_privacy_page_shows_the_version_recorded_at_signup():
    from pathlib import Path

    from accounts import PRIVACY_VERSION

    page = Path(__file__).resolve().parents[2] / "frontend" / "privacy.html"
    assert f"버전 {PRIVACY_VERSION}" in page.read_text(encoding="utf-8")
```

- [ ] **Step 4: Commit·PR E** — `docs: 개인정보 처리방침 초안을 올리고 동의 버전과 맞춘다`. PR E(Task 5~7) → CI → 머지.

---

### Task 8: 인증 화면·CSP 강제 (PR F)

**Files:**
- Create: `frontend/css/auth.css`, `frontend/js/auth-pages.js`, `frontend/js/auth-token.js`, `frontend/member/verify.html`, `frontend/member/reset-request.html`, `frontend/member/reset.html`, `frontend/member/account.html`
- Modify(전면 교체): `frontend/member/login.html`, `frontend/member/register.html`
- Modify: `frontend/privacy.html`(머리 구조 확인), `docker/nginx.conf`, `docker/nginx.public.conf`, `tests/policy/guard_baseline.json`(innerHTML 줄면 갱신)

**Interfaces:**
- Consumes: Task 2·3·5의 API 경로와 응답(`202 check_email`, `INVALID_TOKEN`, `field`)
- Produces: `body[data-page]` 값 `login|register|verify|reset-request|reset|account|privacy`, 요소 id `form`·`message`·`submit`·`toLogin`·`resend`·`change`·`everywhere`·`remove`

- [ ] **Step 1: `auth-token.js`**(토큰 화면 `<head>`의 첫 스크립트)

```js
// 메일 링크의 토큰(#t=)을 읽어 메모리에만 두고 주소창에서 지운다.
// 프래그먼트는 서버로 가지 않지만, 주소창·방문 기록·화면 공유에 남지 않게 바로 지운다.
(() => {
  const token = new URLSearchParams(location.hash.slice(1)).get('t');
  window.__authToken = token || '';
  if (location.hash) history.replaceState(null, '', location.pathname);
})();
```

- [ ] **Step 2: `auth-pages.js`**

```js
'use strict';
// 인증 화면 공용 스크립트. 외부·인라인 스크립트 없이 CSP 'self'로 동작한다. 사용자 입력은 textContent로만 출력한다.
const AUTH_API = window.APP_CONFIG?.apiBase ?? '';

/**
 * JSON POST를 보내고 상태와 본문을 돌려준다.
 * @param {string} path API 경로
 * @param {object} body 요청 본문
 * @returns {Promise<{status: number, data: object}>} 상태 코드와 JSON 본문(없으면 {})
 */
async function postJson(path, body) {
  const res = await fetch(AUTH_API + path, {
    method: 'POST', credentials: 'include',
    headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
  });
  let data = {};
  try { data = await res.json(); } catch (_) { /* 본문 없음 */ }
  return { status: res.status, data };
}

/**
 * 현재 로그인 상태를 가져온다.
 * @returns {Promise<object>} /api/member/me 응답(실패하면 {})
 */
async function currentMember() {
  try {
    const res = await fetch(AUTH_API + '/api/member/me', { credentials: 'include' });
    return await res.json();
  } catch (_) { return {}; }
}

/**
 * 안내 문구를 보여 준다.
 * @param {string} text 문구
 * @param {'error'|'ok'} kind 종류(색)
 * @returns {void}
 */
function say(text, kind = 'error') {
  const el = document.getElementById('message');
  el.textContent = text;
  el.dataset.kind = kind;
  el.hidden = false;
}

/**
 * 입력 값을 읽는다.
 * @param {string} id 요소 id
 * @returns {string} 값
 */
const valueOf = id => document.getElementById(id).value;

/**
 * 체크 상자 상태를 읽는다.
 * @param {string} id 요소 id
 * @returns {boolean} 체크 여부
 */
const isChecked = id => document.getElementById(id).checked;

/**
 * 서버 오류 본문에서 보여 줄 문구를 고른다.
 * @param {number} status HTTP 상태
 * @param {object} data 응답 본문
 * @param {string} fallback 기본 문구
 * @returns {string} 문구
 */
function errorText(status, data, fallback) {
  if (status === 429) return '시도가 너무 많습니다. 잠시 후 다시 시도해 주세요.';
  return data.message || data.error || fallback;
}

/**
 * 폼 제출을 가로채 handler를 실행하고, 실행 중에는 제출 버튼을 잠근다.
 * @param {string} formId 폼 id
 * @param {() => Promise<void>} handler 제출 처리
 * @returns {void}
 */
function onSubmit(formId, handler) {
  const form = document.getElementById(formId);
  form.addEventListener('submit', async event => {
    event.preventDefault();
    const button = form.querySelector('button[type=submit]');
    button.disabled = true;
    document.getElementById('message').hidden = true;
    try { await handler(); } catch (_) { say('서버에 연결할 수 없습니다. 잠시 후 다시 시도해 주세요.'); }
    finally { button.disabled = false; }
  });
}

const PAGES = {
  login() {
    onSubmit('form', async () => {
      const { status, data } = await postJson('/api/member/login', { email: valueOf('email'), password: valueOf('password') });
      if (status === 200) { location.href = '/trade/order.html'; return; }
      say(errorText(status, data, '로그인에 실패했습니다.'));
    });
  },

  async register() {
    const me = await currentMember();
    if (me.signupOpen === false) {
      say('공개 베타 준비 중이라 지금은 가입을 받지 않습니다.');
      document.getElementById('submit').disabled = true;
      return;
    }
    onSubmit('form', async () => {
      const { status, data } = await postJson('/api/member/register', {
        username: valueOf('username'), email: valueOf('email'), password: valueOf('password'),
        password2: valueOf('password2'), agreeAge: isChecked('agreeAge'), agreePrivacy: isChecked('agreePrivacy'),
        website: valueOf('website'),
      });
      if (status === 202) {
        document.getElementById('form').hidden = true;
        say('확인 메일을 보냈습니다. 메일의 링크를 열면 가입이 끝납니다. 메일이 없으면 스팸함을 확인해 주세요.', 'ok');
        return;
      }
      if (status === 200) { location.href = '/trade/order.html'; return; }
      say(errorText(status, data, '가입에 실패했습니다.'));
    });
  },

  async verify() {
    const resend = document.getElementById('resend');
    onSubmit('resend', async () => {
      await postJson('/api/member/verify/resend', { email: valueOf('email') });
      say('가입했지만 아직 인증하지 않은 주소라면 인증 메일을 다시 보냈습니다.', 'ok');
    });
    if (!window.__authToken) { resend.hidden = false; return; }
    const { status, data } = await postJson('/api/member/verify', { token: window.__authToken });
    if (status === 200) {
      say('이메일 인증이 끝났습니다. 이제 로그인할 수 있습니다.', 'ok');
      document.getElementById('toLogin').hidden = false;
      return;
    }
    say(errorText(status, data, '인증하지 못했습니다.'));
    resend.hidden = false;
  },

  'reset-request'() {
    onSubmit('form', async () => {
      await postJson('/api/member/password/reset-request', { email: valueOf('email') });
      document.getElementById('form').hidden = true;
      say('가입된 주소라면 재설정 메일을 보냈습니다. 링크는 30분 동안 쓸 수 있습니다.', 'ok');
    });
  },

  reset() {
    if (!window.__authToken) {
      document.getElementById('form').hidden = true;
      say('재설정 링크가 없습니다. 비밀번호 찾기에서 메일을 다시 받아 주세요.');
      return;
    }
    onSubmit('form', async () => {
      const { status, data } = await postJson('/api/member/password/reset', {
        token: window.__authToken, password: valueOf('password'), password2: valueOf('password2'),
      });
      if (status === 200) {
        document.getElementById('form').hidden = true;
        say('비밀번호를 바꿨습니다. 모든 기기에서 로그아웃되었으니 새 비밀번호로 로그인해 주세요.', 'ok');
        document.getElementById('toLogin').hidden = false;
        return;
      }
      say(errorText(status, data, '비밀번호를 바꾸지 못했습니다.'));
    });
  },

  async account() {
    const me = await currentMember();
    if (!me.loggedIn) { location.href = '/member/login.html'; return; }
    document.getElementById('who').textContent = me.username || '';
    onSubmit('change', async () => {
      const { status, data } = await postJson('/api/member/password/change', {
        current: valueOf('current'), password: valueOf('password'), password2: valueOf('password2'),
      });
      if (status === 200) {
        document.getElementById('change').reset();
        say('비밀번호를 바꿨습니다. 다른 기기는 로그아웃되었습니다.', 'ok');
        return;
      }
      say(errorText(status, data, '비밀번호를 바꾸지 못했습니다.'));
    });
    onSubmit('everywhere', async () => {
      await postJson('/api/member/logout-all', {});
      location.href = '/member/login.html';
    });
    onSubmit('remove', async () => {
      if (!isChecked('confirmDelete')) { say('탈퇴하면 모든 기록이 즉시 지워집니다. 확인란을 체크해 주세요.'); return; }
      const { status, data } = await postJson('/api/member/delete', { password: valueOf('deletePassword') });
      if (status === 200) { location.href = '/index.html'; return; }
      say(errorText(status, data, '탈퇴하지 못했습니다.'));
    });
  },

  privacy() {},
};

PAGES[document.body.dataset.page]?.();
```

- [ ] **Step 3: `auth.css`** — 로그인 화면의 인라인 `@font-face` 5개를 옮기고, 인증 화면이 쓰는 클래스만 정의한다(Tailwind 유틸리티 대체). 먼저 `grep -nE -- '--(up|down|down-bg|muted|accent|radius|border|fg):' frontend/css/style.css`로 변수 이름을 확인하고, 없는 이름은 있는 것으로 바꾼다.

```css
/* 인증 화면 전용 스타일(외부 자원 없음, CSP 'self'). 사이트 공통 변수는 style.css에서 온다. */
@font-face { font-family: 'Pretendard'; font-weight: 400; font-display: swap; src: url('/fonts/Pretendard-Regular.woff2') format('woff2'); }
@font-face { font-family: 'Pretendard'; font-weight: 600; font-display: swap; src: url('/fonts/Pretendard-SemiBold.woff2') format('woff2'); }
@font-face { font-family: 'Pretendard'; font-weight: 700; font-display: swap; src: url('/fonts/Pretendard-Bold.woff2') format('woff2'); }
@font-face { font-family: 'Pretendard'; font-weight: 800; font-display: swap; src: url('/fonts/Pretendard-ExtraBold.woff2') format('woff2'); }
@font-face { font-family: 'Pretendard'; font-weight: 900; font-display: swap; src: url('/fonts/Pretendard-Black.woff2') format('woff2'); }

[hidden] { display: none !important; }
.auth-page { font-family: 'Pretendard', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; color: var(--fg); }
.auth-logo { text-decoration: none; margin-bottom: 1.5rem; }
.auth-tagline { margin: -1rem 0 2rem; text-align: center; font-size: 14px; color: var(--muted); }
.auth-card.wide { max-width: 560px; }
.auth-title { margin: 0 0 .25rem; text-align: center; font-size: 20px; font-weight: 900; }
.auth-sub { margin: 0 0 1.75rem; text-align: center; font-size: 14px; color: var(--muted); }
.auth-field { margin-bottom: 1rem; }
.auth-label { display: block; margin-bottom: .4rem; font-size: 12px; font-weight: 700; letter-spacing: .07em;
  text-transform: uppercase; color: var(--muted); }
.auth-hint { margin-top: .35rem; font-size: 12px; color: var(--muted); }
.auth-check { display: flex; gap: .5rem; align-items: flex-start; margin: .5rem 0; font-size: 14px; }
.auth-check a { color: var(--accent); }
.auth-submit { width: 100%; margin-top: .75rem; }
.auth-submit:disabled { opacity: .5; cursor: not-allowed; }
.auth-message { margin: 0 0 1rem; padding: .75rem 1rem; border-radius: var(--radius); font-size: 14px;
  background: var(--down-bg); border: 1px solid rgba(255, 77, 77, .35); color: var(--down); }
.auth-message[data-kind="ok"] { background: rgba(0, 200, 120, .08); border-color: rgba(0, 200, 120, .35); color: var(--up); }
.auth-links { margin-top: 1.25rem; text-align: center; font-size: 13px; color: var(--muted); }
.auth-links a { color: var(--accent); text-decoration: none; }
.auth-section { margin-top: 1.75rem; padding-top: 1.25rem; border-top: 1px solid var(--border); }
.auth-section h2 { margin: 0 0 .75rem; font-size: 15px; font-weight: 800; }
.auth-danger { border-color: var(--down) !important; color: var(--down) !important; background: transparent !important; }
/* 봇만 채우는 함정 칸: 화면 밖으로 뺀다(display:none이면 일부 봇이 건너뛴다). */
.auth-hp { position: absolute; left: -10000px; width: 1px; height: 1px; overflow: hidden; }
.doc { max-width: 760px; line-height: 1.7; font-size: 15px; }
.doc h2 { margin: 1.5rem 0 .5rem; font-size: 17px; }
.doc ul { padding-left: 1.2rem; }
```

- [ ] **Step 4: 화면 7개** — 모두 같은 머리를 쓰고, 토큰 화면(verify·reset)은 `<script src="/js/auth-token.js?v=20260926"></script>`를 `<head>`의 `<meta charset>` 바로 다음, **첫 스크립트**로 둔다.

```html
<!doctype html>
<html lang="ko">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta name="referrer" content="no-referrer">
  <title>{제목} — Noah Trading Desk</title>
  <link rel="icon" type="image/svg+xml" href="/img/favicon.svg">
  <link rel="stylesheet" href="/css/style.css?v=20260925-terminal">
  <link rel="stylesheet" href="/css/auth.css?v=20260926">
</head>
<body data-page="{page}">
<main class="auth-page">
  <a class="auth-logo" href="/index.html">Noah Trading Desk</a>
  <p class="auth-tagline">데이터로 판단하는 투자자를 위한 도구 · 투자 조언이 아닙니다</p>
  <section class="auth-card">
    <h1 class="auth-title">{제목}</h1>
    <p class="auth-message" id="message" hidden></p>
    {본문}
  </section>
</main>
<script src="/js/config.js"></script>
<script src="/js/auth-pages.js?v=20260926"></script>
</body>
</html>
```

  화면별 `{제목}`·`{page}`·`{본문}`:
  - `login.html`(로그인, `login`):

```html
    <p class="auth-sub">이메일과 비밀번호를 입력해 주세요.</p>
    <form id="form" novalidate>
      <div class="auth-field"><label class="auth-label" for="email">이메일</label>
        <input class="dark-input" id="email" type="email" autocomplete="email" required></div>
      <div class="auth-field"><label class="auth-label" for="password">비밀번호</label>
        <input class="dark-input" id="password" type="password" autocomplete="current-password" required></div>
      <button class="btn-gold auth-submit" id="submit" type="submit">로그인</button>
    </form>
    <p class="auth-links"><a href="/member/reset-request.html">비밀번호 찾기</a> · <a href="/member/verify.html">인증 메일 다시 받기</a> · <a href="/member/register.html">가입</a></p>
```

  - `register.html`(가입, `register`):

```html
    <p class="auth-sub">비밀번호는 15자 이상, 문장처럼 길게 정하세요. 예: 봄비 오는 날 공시를 읽는다</p>
    <form id="form" novalidate>
      <div class="auth-field"><label class="auth-label" for="username">닉네임</label>
        <input class="dark-input" id="username" autocomplete="nickname" maxlength="20" required>
        <p class="auth-hint">2~20자. 실명을 쓰지 않아도 됩니다. 랭킹에 보입니다.</p></div>
      <div class="auth-field"><label class="auth-label" for="email">이메일</label>
        <input class="dark-input" id="email" type="email" autocomplete="email" required></div>
      <div class="auth-field"><label class="auth-label" for="password">비밀번호</label>
        <input class="dark-input" id="password" type="password" autocomplete="new-password" minlength="15" required></div>
      <div class="auth-field"><label class="auth-label" for="password2">비밀번호 확인</label>
        <input class="dark-input" id="password2" type="password" autocomplete="new-password" required></div>
      <div class="auth-hp" aria-hidden="true"><label for="website">웹사이트</label>
        <input id="website" tabindex="-1" autocomplete="off"></div>
      <label class="auth-check"><input type="checkbox" id="agreeAge"> 만 14세 이상입니다. (필수)</label>
      <label class="auth-check"><input type="checkbox" id="agreePrivacy">
        <span>개인정보 수집·이용에 동의합니다. 이메일·닉네임·동의 기록·활동일을 모으고, 탈퇴하면 즉시 지웁니다.
        <a href="/privacy.html" target="_blank" rel="noopener">전문 보기</a> (필수)</span></label>
      <button class="btn-gold auth-submit" id="submit" type="submit">가입하기</button>
    </form>
    <p class="auth-links">이미 계정이 있나요? <a href="/member/login.html">로그인</a></p>
```

  - `verify.html`(이메일 인증, `verify`, 토큰 스크립트):

```html
    <p class="auth-links" id="toLogin" hidden><a href="/member/login.html">로그인하러 가기</a></p>
    <form id="resend" hidden novalidate>
      <p class="auth-sub">가입한 이메일을 넣으면 인증 메일을 다시 보냅니다.</p>
      <div class="auth-field"><label class="auth-label" for="email">이메일</label>
        <input class="dark-input" id="email" type="email" autocomplete="email" required></div>
      <button class="btn-gold auth-submit" type="submit">인증 메일 다시 받기</button>
    </form>
```

  - `reset-request.html`(비밀번호 찾기, `reset-request`):

```html
    <p class="auth-sub">가입한 이메일로 재설정 링크를 보냅니다.</p>
    <form id="form" novalidate>
      <div class="auth-field"><label class="auth-label" for="email">이메일</label>
        <input class="dark-input" id="email" type="email" autocomplete="email" required></div>
      <button class="btn-gold auth-submit" id="submit" type="submit">재설정 메일 받기</button>
    </form>
    <p class="auth-links"><a href="/member/login.html">로그인</a></p>
```

  - `reset.html`(새 비밀번호, `reset`, 토큰 스크립트):

```html
    <p class="auth-sub">15자 이상, 문장처럼 길게 정하세요.</p>
    <form id="form" novalidate>
      <div class="auth-field"><label class="auth-label" for="password">새 비밀번호</label>
        <input class="dark-input" id="password" type="password" autocomplete="new-password" minlength="15" required></div>
      <div class="auth-field"><label class="auth-label" for="password2">새 비밀번호 확인</label>
        <input class="dark-input" id="password2" type="password" autocomplete="new-password" required></div>
      <button class="btn-gold auth-submit" id="submit" type="submit">비밀번호 바꾸기</button>
    </form>
    <p class="auth-links" id="toLogin" hidden><a href="/member/login.html">로그인하러 가기</a></p>
```

  - `account.html`(계정 설정, `account`, `<section class="auth-card wide">`):

```html
    <p class="auth-sub"><span id="who"></span> 님의 계정</p>
    <form id="change" novalidate>
      <h2 class="auth-title">비밀번호 변경</h2>
      <div class="auth-field"><label class="auth-label" for="current">현재 비밀번호</label>
        <input class="dark-input" id="current" type="password" autocomplete="current-password" required></div>
      <div class="auth-field"><label class="auth-label" for="password">새 비밀번호</label>
        <input class="dark-input" id="password" type="password" autocomplete="new-password" minlength="15" required></div>
      <div class="auth-field"><label class="auth-label" for="password2">새 비밀번호 확인</label>
        <input class="dark-input" id="password2" type="password" autocomplete="new-password" required></div>
      <button class="btn-gold auth-submit" type="submit">비밀번호 바꾸기</button>
    </form>
    <form id="everywhere" class="auth-section" novalidate>
      <h2>모든 기기에서 로그아웃</h2>
      <p class="auth-hint">이 기기를 포함해 로그인된 모든 곳에서 로그아웃합니다.</p>
      <button class="btn-gold auth-submit" type="submit">모든 기기 로그아웃</button>
    </form>
    <form id="remove" class="auth-section" novalidate>
      <h2>탈퇴</h2>
      <p class="auth-hint">계정과 모의투자 기록·메모·API 키가 즉시 지워지고 되돌릴 수 없습니다.</p>
      <div class="auth-field"><label class="auth-label" for="deletePassword">현재 비밀번호</label>
        <input class="dark-input" id="deletePassword" type="password" autocomplete="current-password" required></div>
      <label class="auth-check"><input type="checkbox" id="confirmDelete"> 모든 기록이 지워지는 것을 이해했습니다.</label>
      <button class="btn-gold auth-submit auth-danger" type="submit">탈퇴하기</button>
    </form>
```

  - `privacy.html`(개인정보 처리방침, `privacy`, `auth-card wide`, 본문은 Task 7).
  - 확인: `grep -nE '<script>|<style|style="|https?://' frontend/member/{login,register,verify,reset-request,reset,account}.html frontend/privacy.html` 결과가 0줄이어야 한다(외부 URL·인라인 스크립트·인라인 스타일 0).

- [ ] **Step 5: nginx CSP**(`docker/nginx.conf`와 `docker/nginx.public.conf`의 `location /` **앞**)

```nginx
    # 인증 화면: 제3자·인라인 스크립트 없이 CSP를 강제한다(S1 스펙 ⑤). 확장자를 생략한 주소도 같은 헤더를 받는다.
    location ~ ^/(member/(login|register|verify|reset-request|reset|account)|privacy)(\.html)?$ {
        include /etc/nginx/snippets/security-headers.conf;
        add_header Content-Security-Policy "default-src 'self'; script-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'self'; form-action 'self'" always;
        add_header Cache-Control "no-cache" always;
        try_files $uri $uri.html =404;
    }
```

- [ ] **Step 6: 확인** — `scripts/verify/stack.sh up`(프론트 재빌드) 뒤:

```bash
for p in /member/login /member/login.html /member/register.html /member/verify.html /member/reset-request.html /member/reset.html /member/account.html /privacy.html /privacy; do
  printf '%s ' "$p"; curl -s -o /dev/null -D - "http://127.0.0.1:3334$p" | grep -ci '^content-security-policy: default-src'; done
curl -s -o /dev/null -D - http://127.0.0.1:3334/index.html | grep -ci '^content-security-policy: default-src'
```

  기대: 인증 화면 9줄 모두 `1`, index는 `0`(다른 화면은 보고 전용 유지). `pytest tests/policy` 통과(옛 login/register의 innerHTML이 사라져 개수가 줄면 `guard_baseline.json`을 갱신).

- [ ] **Step 7: Commit** — `feat: 인증 화면을 외부 스크립트 없이 다시 만들고 CSP를 강제한다`

---

### Task 9: F1 전 흐름·화면 증거 (PR F)

**Files:**
- Modify: `scripts/verify/f1_accounts.py`, `.claude/skills/verify-stockdesk/features/F1-accounts.md`

- [ ] **Step 1: F1 끝에 탈퇴와 스캔** — Task 4 흐름의 "DB 회원 행 1" 뒤에:
  1. `member_id = common.mariadb_scalar(f"SELECT member_id FROM member WHERE email = '{email}'")`
  2. 틀린 비밀번호 탈퇴 400(`delete-wrong-password`) → 맞는 비밀번호 탈퇴 200(`delete`) → `/me` False(`me-after-delete`)
  3. `common.mariadb_scalar("SELECT GROUP_CONCAT(TABLE_NAME) FROM information_schema.COLUMNS WHERE TABLE_SCHEMA = 'mockinv' AND COLUMN_NAME = 'member_id'")`를 쉼표로 나눠 표마다 `SELECT COUNT(*) FROM {표} WHERE member_id = {member_id}`가 `0`인지 확인(`db-scan-after-delete`, 표별 결과 dict를 증거로)
- [ ] **Step 2: 화면 확인(쿠키 없는 Playwright, MCP `mcp__playwright__*`)**
  - `http://127.0.0.1:3334/member/register.html`·`login.html`·`verify.html`·`reset.html#t=abc`·`account.html`·`/privacy.html`을 연다.
  - 화면마다 `browser_network_requests`에서 `127.0.0.1:3334` 밖 요청 0건, `browser_console_messages`에 `Refused to`(CSP 위반) 0건.
  - `reset.html#t=abc`를 연 뒤 `browser_evaluate`로 `location.href`에 `#t=`가 없는지 확인.
  - `account.html`은 로그인하지 않았으면 `/member/login.html`로 이동하는지 확인.
  - 캡처: F1 증거 폴더에 `register.png`, `login.png`, `privacy.png`.
- [ ] **Step 3: 화면 주행 한 번** — Playwright로 가입(동의 체크) → 안내 문구 → `common.mail_link`로 받은 인증 링크를 브라우저로 열어 "인증이 끝났습니다" → 로그인 → `account.html`에서 탈퇴. 캡처 `verified.png`, `deleted.png`.
- [ ] **Step 4: 전체 실행** — `up && doctor && f1 && f2 && down`, 익명 볼륨 수 불변.
- [ ] **Step 5: Commit** — `feat: F1이 가입부터 탈퇴와 DB 스캔까지 돈다`

---

### Task 10: 교차 검토·증거·PR F·배포

- [ ] **Step 1: 교차 모델 보안 검토(T0-4)** — PR D·E·F 전체 diff(main 대비, 계획 문서 제외)를 두 검토자에게 읽기 전용으로 맡긴다.
  - Codex: `codex exec -s read-only`, 스펙 위협 모델 표 기준, 심각도·file:line·실패 시나리오·수정안.
  - `ecc:security-reviewer`: 같은 범위. 브리프에 금지(파일 수정·외부 네트워크·패키지 내려받기)와 요구 증거를 적는다.
  - high 이상은 재현 테스트부터 쓰고 고친다. medium 이하는 판정(수정·수용)과 이유를 증거에 적는다.
- [ ] **Step 2: Reality Checker** — 스펙 "검증" 절 항목별 증거 위치(테스트 이름·F1 단계·캡처)를 표로 만들어 판정을 받는다. "보완 필요"면 고치고 다시 받는다.
- [ ] **Step 3: 증거 문서** `docs/evidence/s1-account-lifecycle-2026-09-26.md` — PR별 테스트 수, F1 단계 목록, CSP 헤더 표, 화면 캡처 경로, 외부 요청 0건, 교차 검토 표, Reality Checker 판정, 노아 항목(처리방침 법률 확인·문의 주소, S5의 도메인·SES·가입 열기).
- [ ] **Step 4: PR F → CI → 머지 → 공개 배포** — 배포 뒤 SSM으로 서버 안에서 확인:
  - `/health` 200, `/api/member/me`에 `signupOpen: false`, 가입 403
  - `/member/login`·`/privacy.html` 응답에 `Content-Security-Policy: default-src 'self'` 헤더
  - `member` 새 열 4개, `member_token`·`member_activity_day` 표, `ai_usage.member_id` NULL 허용
  - 기존 계정(관리자가 있으면)의 `email_verified_at`이 채워졌는지(COUNT만, 주소는 출력하지 않음)
  - F2와 같은 백테스트 요청 200, 명령 바 화면 200(회귀)
  - 공개 서버 로그인 소요 시간은 가입이 열리는 S5에서 잰다(지금은 미검증으로 기록)
- [ ] **Step 5: 기록** — vault 프로젝트 페이지와 하네스 메모리(S1 완료, 공개 가입은 S5 관문 뒤)를 갱신한다.
