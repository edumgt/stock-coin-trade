# T0 검증 스킬 `verify-stockdesk`와 상시 지시 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 어떤 에이전트든 같은 절차로 앱을 격리된 스택에 띄우고, 기능을 주행하고, 증거를 남기고, 자기가 띄운 것만 치우게 만든다(T0-1). 반복된 교정은 상시 지시 문서로 모은다(T0-3).

**Architecture:**
- 기존 compose 파일(`docker-compose.yml` + `compose.portfolio.yml`)을 전용 프로젝트 이름 `stockdesk-verify`, 포트 3334, 전용 env 파일로 다시 쓴다. 새 compose 파일은 만들지 않는다.
- `scripts/verify/stack.sh`가 up·doctor·down을 맡는다. 기능별 파이썬 스크립트가 HTTP로 주행하고, 증거는 `.verify-artifacts/`에 남긴다.
- 에이전트용 절차는 `.claude/skills/verify-stockdesk/SKILL.md`와 기능 지도에 둔다.

**Tech Stack:** bash, Docker Compose v2.24+, Python 3.11 표준 라이브러리(`urllib`, `http.cookiejar`, `json`, `subprocess`), pytest.

**Spec:** `docs/superpowers/specs/2026-09-26-t0-verification-loop-design.md` (T0-1, T0-3). T0-2 가드는 S1 계획의 첫 PR에서 다룬다.

## Global Constraints

- **격리**: compose 프로젝트 이름은 `stockdesk-verify`, 프런트 포트는 `127.0.0.1:3334`, env 파일은 `.env.verify`(권한 600, 기존 `.gitignore`의 `.env.*`로 제외됨)다.
- **금지 대상**: `stock-portfolio-local` 프로젝트(노아/PM 소유, 3333)의 컨테이너·볼륨은 조회 외에는 건드리지 않는다.
- **외부 호출 차단**: 검증 스택에는 `JEV_ENABLED`, `TYPESAFE_API_KEY`, `JEV_MONTHLY_BUDGET_USD`, `DART_API_KEY`를 넘기지 않는다(셸 환경에서 제거). worker 서비스는 띄우지 않는다(`up ... frontend`).
- **의존성**: 스크립트는 표준 라이브러리만 쓴다. 새 의존성은 없다.
- **증거**: `.verify-artifacts/<UTC시각>-<기능ID>/transcript.json`. 쿠키, 토큰, 비밀번호, csrf 값은 `***`로 가린다. 정리할 때 지우지 않는다.
- **종료 코드**: 0 통과, 1 실패, 2 전제 불충족.
- **주석과 문서**: 한국어 docstring·주석. 대화·이력성 주석("노아가 말했다" 류)은 쓰지 않는다.
- **Mac에서 파이썬 테스트**: `docker run --rm -v "$PWD":/repo -w /repo sct-test:dev python -m pytest …`
- **스펙과 다른 점**
  - Mailpit과 `compose.verify.yml`은 메일 기능을 만드는 S1의 네 번째 PR에서 추가한다(지금은 쓰는 곳이 없다).
  - `pre-dangling.txt`는 실행별 폴더가 아니라 `.verify-artifacts/pre-dangling.txt` 하나로 둔다(up과 down이 같은 기준을 읽도록).

## Review Focus

1. 포트 3334를 다른 프로세스가 쓰고 있으면, doctor가 "우리 컨테이너가 아님"을 알아내고 종료 코드 2로 멈춰야 한다. 남의 인스턴스를 주행하면 안 된다. → Task 3의 doctor가 `docker port`로 게시 포트 소유를 확인한다.
2. PM 셸에 `JEV_ENABLED=true`가 export돼 있어도 검증 스택으로 새면 안 된다(과금). → Task 3의 `compose()`가 `env -u`로 제거하고, Step 5에서 확인한다.
3. `up` 기록 없이 `down`을 실행해도 죽지 않고 정리한 뒤 "기준 없음"을 보고해야 한다. → Task 3 Step 6.
4. 증거 파일에 세션 쿠키·csrf·비밀번호가 평문으로 남으면 안 된다. → Task 2 단위 테스트.
5. F1을 연달아 두 번 돌려도 이메일이 겹쳐 실패하면 안 된다. → Task 2 `unique_email` 테스트와 Task 4 Step 5(2회 실행).

---

### Task 1: 에이전트 입구 문서와 상시 지시 (T0-3)

**Files:**
- Create: `docs/agents/standing-orders.md`
- Create: `AGENTS.md`
- Create: `CLAUDE.md`
- Modify: `.gitignore`(끝에 한 줄)

**Interfaces:**
- Produces: `docs/agents/standing-orders.md`. 이후 모든 Orca 브리프에 그대로 붙인다. `AGENTS.md`는 다른 도구의 입구, `CLAUDE.md`는 Claude Code가 `AGENTS.md`를 읽게 하는 한 줄이다.

- [ ] **Step 1: 상시 지시 파일 작성**

`docs/agents/standing-orders.md`:

```markdown
# 상시 지시 (stock-coin-trade)

에이전트 작업 전에 읽고 따른다. Orca 워커 브리프에는 이 파일을 그대로 붙인다. 같은 교정을 두 번 하게 되면 여기에 한 줄을 추가하고, 가능하면 CI 가드(`tests/policy/`)로 옮긴다.

1. 컨테이너 테스트는 `docker run --rm`, 컨테이너 삭제는 `docker rm -v`로 한다. 익명 볼륨을 남기지 않는다.
2. worktree 사이에서 `git stash`를 쓰지 않는다(모든 worktree가 공유한다). 임시 보관은 커밋이나 패치 파일로 한다.
3. Mac에서 파이썬 테스트는 `sct-test:dev` 컨테이너로 돌린다: `docker run --rm -v "$PWD":/repo -w /repo sct-test:dev python -m pytest -q -m "not integration"`.
4. 키·토큰·비밀 값을 출력하지 않는다. 확인은 길이·형식·일치 여부로만 한다.
5. 로컬 스택 `stock-portfolio-local`(포트 3333)은 PM 소유다. 검증은 `.claude/skills/verify-stockdesk`의 `stockdesk-verify` 스택에서 한다.
6. main에 직접 커밋·푸시하지 않는다. `<type>/<short>` 브랜치와 PR을 쓴다. `gh`는 `-R Noah-TaeHwan/stock-coin-trade`를 붙인다.
7. "통과", "잔여 0" 같은 보고에는 실행한 명령과 출력(또는 증거 경로)을 붙인다. 자기보고는 증거가 아니다.
8. 워커 보고에는 `decisions.tsv`(열: `ts phase decision why evidence result`, 한 결정에 한 행)를 첨부한다. 커밋하지 않는다.
```

- [ ] **Step 2: `AGENTS.md`와 `CLAUDE.md` 작성**

`AGENTS.md`:

```markdown
# 에이전트 안내

- 상시 지시: `docs/agents/standing-orders.md`를 먼저 읽는다.
- 앱 검증: `.claude/skills/verify-stockdesk/SKILL.md`. 동작한다는 주장은 이 절차의 증거로 한다.
- 설계는 `docs/superpowers/specs/`, 구현 계획은 `docs/superpowers/plans/`, 검증 기록은 `docs/evidence/`에 있다.
```

`CLAUDE.md`:

```markdown
@AGENTS.md
```

- [ ] **Step 3: `.gitignore`에 증거 폴더 추가**

`.gitignore` 끝에 추가:

```
.verify-artifacts/
```

- [ ] **Step 4: 확인**

Run: `git check-ignore -v .verify-artifacts/x .env.verify`
Expected: 두 경로 모두 무시 규칙과 함께 출력된다(`.verify-artifacts/`, `.env.*`).

- [ ] **Step 5: Commit**

```bash
git add docs/agents/standing-orders.md AGENTS.md CLAUDE.md .gitignore
git commit -m "docs: 에이전트 상시 지시와 입구 문서를 추가한다"
```

---

### Task 2: 검증 공용 모듈 `scripts/verify/common.py`

**Files:**
- Create: `scripts/verify/common.py`
- Test: `tests/unit/test_verify_common.py`

**Interfaces:**
- Produces(이후 태스크가 쓰는 이름):
  - `PASS=0`, `FAIL=1`, `UNMET=2`, `PROJECT="stockdesk-verify"`, `BASE_URL`(기본 `http://127.0.0.1:3334`)
  - `redact(value) -> 사본`
  - `unique_email(prefix: str = "verify") -> str`
  - `class Recorder(feature_id: str, root: Path = ARTIFACTS)`: `.add(step: str, request: dict, status: int, body)`, `.finish(verdict: str) -> Path`, `.dir: Path`
  - `class Client(base: str = BASE_URL)`: `.call(method: str, path: str, body: dict | None = None) -> tuple[int, object]`
  - `mariadb_scalar(sql: str) -> str`
  - `run(feature_id: str, steps: Callable[[Client, Recorder], None]) -> int`

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/unit/test_verify_common.py`:

```python
"""검증 공용 모듈(scripts/verify/common.py)의 비밀 가림·이메일 생성·증거 기록을 확인한다."""

import importlib.util
import json
import re
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "verify_common", Path(__file__).resolve().parents[2] / "scripts" / "verify" / "common.py"
)
common = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(common)


def test_redact_masks_secret_keys_at_any_depth():
    body = {"csrfToken": "abc", "profile": "local", "nested": [{"password": "p", "username": "u"}], "Set-Cookie": "s=1"}
    assert common.redact(body) == {
        "csrfToken": "***", "profile": "local", "nested": [{"password": "***", "username": "u"}], "Set-Cookie": "***",
    }


def test_redact_leaves_non_dict_values_alone():
    assert common.redact("plain") == "plain"
    assert common.redact([1, 2]) == [1, 2]


def test_unique_email_is_safe_and_distinct():
    first, second = common.unique_email(), common.unique_email()
    assert first != second
    assert re.fullmatch(r"verify-\d+-[0-9a-f]{6}@example\.test", first)


def test_recorder_writes_redacted_transcript(tmp_path):
    rec = common.Recorder("F9", root=tmp_path)
    rec.add("login", {"email": "a@example.test", "password": "secret-pw"}, 200, {"username": "u", "csrfToken": "t"})
    path = rec.finish("PASS")
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["verdict"] == "PASS"
    assert data["steps"][0]["request"]["password"] == "***"
    assert data["steps"][0]["body"]["csrfToken"] == "***"
    assert "secret-pw" not in path.read_text(encoding="utf-8")
    assert path.parent.name.endswith("-F9")
```

- [ ] **Step 2: 실패 확인**

Run: `docker run --rm -v "$PWD":/repo -w /repo sct-test:dev python -m pytest -q tests/unit/test_verify_common.py`
Expected: FAIL. `scripts/verify/common.py`가 없어 `FileNotFoundError`가 난다.

- [ ] **Step 3: 구현**

`scripts/verify/common.py`:

```python
"""검증 스크립트 공용 도구: HTTP 호출, 증거 기록(비밀 가림), DB 조회, 종료 코드.

표준 라이브러리만 쓴다. 대상은 전용 스택 stockdesk-verify(기본 http://127.0.0.1:3334)다.
"""

from __future__ import annotations

import http.cookiejar
import json
import os
import re
import secrets
import subprocess
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path

PASS, FAIL, UNMET = 0, 1, 2
PROJECT = "stockdesk-verify"
BASE_URL = os.environ.get("VERIFY_BASE_URL", "http://127.0.0.1:3334")
ARTIFACTS = Path(os.environ.get("VERIFY_ARTIFACTS", ".verify-artifacts"))
_SECRET_KEY = re.compile(r"(?i)(token|password|secret|cookie|sid|csrf)")


def redact(value):
    """dict·list 안에서 비밀로 보이는 키의 값을 '***'로 바꾼 사본을 돌려준다.

    @param value 요청·응답 본문(dict, list, 스칼라)
    @returns 비밀 값을 가린 사본
    """
    if isinstance(value, dict):
        return {key: ("***" if _SECRET_KEY.search(str(key)) else redact(item)) for key, item in value.items()}
    if isinstance(value, list):
        return [redact(item) for item in value]
    return value


def unique_email(prefix: str = "verify") -> str:
    """실행마다 겹치지 않는 예약 도메인(.test) 이메일을 만든다.

    @param prefix 주소 앞부분
    @returns 예: verify-1790000000-a1b2c3@example.test
    """
    return f"{prefix}-{int(time.time())}-{secrets.token_hex(3)}@example.test"


class Recorder:
    """한 기능 주행의 요청·응답을 증거 폴더의 transcript.json으로 남긴다."""

    def __init__(self, feature_id: str, root: Path = ARTIFACTS):
        """@param feature_id 기능 ID(F1 등) @param root 증거 최상위 폴더"""
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        self.dir = Path(root) / f"{stamp}-{feature_id}"
        self.dir.mkdir(parents=True, exist_ok=True)
        self.steps: list[dict] = []

    def add(self, step: str, request: dict, status: int, body) -> None:
        """한 단계를 기록한다. @param step 단계 이름 @param request 보낸 값 @param status HTTP 상태 @param body 응답 본문"""
        self.steps.append({"step": step, "request": redact(request), "status": status, "body": redact(body)})

    def finish(self, verdict: str) -> Path:
        """판정과 함께 파일로 쓴다. @param verdict PASS·FAIL·UNMET @returns transcript.json 경로"""
        path = self.dir / "transcript.json"
        path.write_text(json.dumps({"verdict": verdict, "steps": self.steps}, ensure_ascii=False, indent=2),
                        encoding="utf-8")
        return path


def _json(raw: bytes):
    """응답 바이트를 JSON으로, 실패하면 앞부분 문자열로 돌려준다."""
    try:
        return json.loads(raw.decode("utf-8") or "null")
    except ValueError:
        return raw[:200].decode("utf-8", "replace")


class Client:
    """쿠키를 유지하는 최소 HTTP 클라이언트."""

    def __init__(self, base: str = BASE_URL):
        """@param base 대상 기본 URL"""
        self.base = base
        self._opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))

    def call(self, method: str, path: str, body: dict | None = None) -> tuple[int, object]:
        """요청을 보내고 (상태, JSON 본문)을 돌려준다. @param method HTTP 메서드 @param path 경로 @param body JSON 본문"""
        data = json.dumps(body).encode("utf-8") if body is not None else None
        request = urllib.request.Request(self.base + path, data=data, method=method,
                                         headers={"Content-Type": "application/json"})
        try:
            with self._opener.open(request, timeout=30) as response:
                return response.status, _json(response.read())
        except urllib.error.HTTPError as exc:
            return exc.code, _json(exc.read())


def mariadb_scalar(sql: str) -> str:
    """검증 스택 MariaDB에서 한 값을 조회한다. 비밀번호는 컨테이너 환경변수로만 쓴다.

    @param sql 우리가 만든 값만 넣은 SELECT 문(외부 입력 금지)
    @returns 첫 행 첫 열 문자열
    """
    container = subprocess.run(
        ["docker", "ps", "-q", "--filter", f"label=com.docker.compose.project={PROJECT}",
         "--filter", "label=com.docker.compose.service=mariadb"],
        check=True, capture_output=True, text=True,
    ).stdout.strip()
    if not container:
        raise RuntimeError(f"{PROJECT} mariadb 컨테이너가 없습니다")
    script = 'MYSQL_PWD="$MARIADB_PASSWORD" mariadb -u"$MARIADB_USER" mockinv -N -e "$0"'
    return subprocess.run(["docker", "exec", container, "sh", "-c", script, sql],
                          check=True, capture_output=True, text=True).stdout.strip()


def run(feature_id: str, steps: Callable[[Client, Recorder], None]) -> int:
    """기능 주행을 실행하고 판정·증거 경로를 출력한다.

    @param feature_id 기능 ID
    @param steps (client, recorder)를 받아 실패 시 AssertionError, 전제 불충족 시 ConnectionError를 낸다
    @returns 종료 코드(PASS·FAIL·UNMET)
    """
    recorder, client = Recorder(feature_id), Client()
    try:
        steps(client, recorder)
        verdict, code = "PASS", PASS
    except AssertionError as exc:
        recorder.add("assertion", {}, 0, str(exc))
        verdict, code = "FAIL", FAIL
    except (ConnectionError, urllib.error.URLError, RuntimeError) as exc:
        recorder.add("precondition", {}, 0, str(exc))
        verdict, code = "UNMET", UNMET
    path = recorder.finish(verdict)
    print(f"{feature_id}: {verdict} evidence={path}")
    return code
```

- [ ] **Step 4: 통과 확인**

Run: `docker run --rm -v "$PWD":/repo -w /repo sct-test:dev python -m pytest -q tests/unit/test_verify_common.py`
Expected: `4 passed`

- [ ] **Step 5: 린트**

Run: `docker run --rm -v "$PWD":/repo -w /repo sct-test:dev ruff check scripts/verify tests/unit/test_verify_common.py`
Expected: `All checks passed!`

- [ ] **Step 6: Commit**

```bash
git add scripts/verify/common.py tests/unit/test_verify_common.py
git commit -m "feat: 검증 스크립트 공용 모듈(증거 기록·비밀 가림)을 추가한다"
```

---

### Task 3: 스택 관리 `scripts/verify/stack.sh` (Launch·Doctor·Cleanup)

**Files:**
- Create: `scripts/verify/stack.sh`(실행 권한)

**Interfaces:**
- Consumes: `docker-compose.yml`, `compose.portfolio.yml`(변경 없음). `PORTFOLIO_LOCAL.md`의 env 생성 방식을 그대로 쓴다.
- Produces: `scripts/verify/stack.sh up|doctor|down`(종료 코드 0·1·2), `.env.verify`, `.verify-artifacts/pre-dangling.txt`.

- [ ] **Step 1: 스크립트 작성**

`scripts/verify/stack.sh`:

```bash
#!/usr/bin/env bash
# 검증 전용 스택(stockdesk-verify, 127.0.0.1:3334)을 올리고·점검하고·내린다.
# 사용법: scripts/verify/stack.sh up|doctor|down   종료 코드: 0 통과, 1 실패, 2 전제 불충족
set -euo pipefail
cd "$(dirname "$0")/../.."

PROJECT=stockdesk-verify
PORT=3334
ENV_FILE=.env.verify
ART=.verify-artifacts

# 과금·외부 호출 변수는 셸에 있어도 검증 스택으로 넘기지 않는다.
compose() {
  env -u JEV_ENABLED -u TYPESAFE_API_KEY -u JEV_MONTHLY_BUDGET_USD -u DART_API_KEY \
    docker compose -p "$PROJECT" --env-file "$ENV_FILE" \
    -f docker-compose.yml -f compose.portfolio.yml --profile local-db "$@"
}

dangling() { docker volume ls -qf dangling=true | wc -l | tr -d ' '; }

# 처음 한 번 무작위 값으로 .env.verify를 만든다(권한 600, 값은 출력하지 않음).
make_env() {
  [ -f "$ENV_FILE" ] && return 0
  python3 - "$ENV_FILE" "$PORT" <<'PY'
import os
import secrets
import sys

path, port = sys.argv[1], sys.argv[2]
values = {
    "FRONTEND_PORT": port, "MARIADB_USER": "mockinv",
    "MARIADB_PASSWORD": secrets.token_hex(24), "MARIADB_ROOT_PASSWORD": secrets.token_hex(24),
    "QUANT_DB_NAME": "quant_research", "QUANT_DB_USER": "quant", "QUANT_DB_PASSWORD": secrets.token_hex(24),
    "SECRET_KEY": secrets.token_hex(32),
}
fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
with os.fdopen(fd, "w") as out:
    out.writelines(f"{key}={value}\n" for key, value in values.items())
PY
}

service_id() {
  docker ps -aq --filter "label=com.docker.compose.project=$PROJECT" --filter "label=com.docker.compose.service=$1"
}

case "${1:-}" in
  up)
    mkdir -p "$ART"
    dangling > "$ART/pre-dangling.txt"
    make_env
    # worker는 외부 시세 사이트를 부르는 주기 작업이라 띄우지 않는다. frontend가 backend·init·DB를 끌어온다.
    compose up -d --build --wait frontend
    echo "up: ok project=$PROJECT port=$PORT"
    ;;
  doctor)
    frontend=$(docker ps -q --filter "label=com.docker.compose.project=$PROJECT" --filter "label=com.docker.compose.service=frontend")
    [ -n "$frontend" ] || { echo "doctor: $PROJECT frontend 컨테이너가 없습니다"; exit 2; }
    published=$(docker port "$frontend" 80/tcp | head -1)
    [ "$published" = "127.0.0.1:$PORT" ] || { echo "doctor: 포트 $PORT가 이 프로젝트 것이 아닙니다($published)"; exit 2; }
    curl -fsS "http://127.0.0.1:$PORT/health" >/dev/null || { echo "doctor: /health 실패"; exit 2; }
    init=$(service_id init)
    code=$(docker inspect -f '{{.State.ExitCode}}' "$init")
    [ "$code" = 0 ] || { echo "doctor: init 종료 코드 $code"; exit 2; }
    profile=$(curl -fsS "http://127.0.0.1:$PORT/api/member/me" | python3 -c 'import json,sys; print(json.load(sys.stdin)["profile"])')
    jev=$(docker exec "$(service_id python-backend)" sh -c 'echo "${JEV_ENABLED:-unset}"')
    echo "doctor: ok profile=$profile jev=$jev port=$PORT"
    ;;
  down)
    if [ -f "$ENV_FILE" ]; then compose down -v --remove-orphans; else echo "down: $ENV_FILE 없음, compose 정리 생략"; fi
    after=$(dangling)
    if [ -f "$ART/pre-dangling.txt" ]; then
      before=$(cat "$ART/pre-dangling.txt")
      [ "$after" -le "$before" ] || { echo "down: 익명 볼륨이 늘었습니다 $before→$after"; exit 1; }
      echo "down: ok 익명 볼륨 $before→$after"
    else
      echo "down: 기준 없음(up 기록 없음), 현재 익명 볼륨 $after"
    fi
    ;;
  *)
    echo "사용법: $0 up|doctor|down"; exit 2 ;;
esac
```

Run: `chmod +x scripts/verify/stack.sh && bash -n scripts/verify/stack.sh`
Expected: 출력 없음(문법 정상).

- [ ] **Step 2: 첫 실행(up)**

Run: `scripts/verify/stack.sh up`
Expected: 마지막 줄 `up: ok project=stockdesk-verify port=3334`. `stat -f %Lp .env.verify`가 `600`.

- [ ] **Step 3: 점검(doctor)**

Run: `scripts/verify/stack.sh doctor`
Expected: `doctor: ok profile=local jev=false port=3334`

- [ ] **Step 4: 남의 스택 보호 확인**

Run: `docker ps --filter label=com.docker.compose.project=stock-portfolio-local --format '{{.Names}} {{.Status}}'`
Expected: 3333 로컬 스택의 목록과 상태가 Step 2 전과 같다(재시작·재생성 없음).

- [ ] **Step 5: 과금 변수 차단 확인 (Review Focus 2)**

Run: `JEV_ENABLED=true scripts/verify/stack.sh up && scripts/verify/stack.sh doctor`
Expected: `jev=false`. 셸의 `JEV_ENABLED=true`가 `env -u`로 제거되어 compose 기본값 false가 쓰인다.

- [ ] **Step 6: 정리(down)와 기준 없음 경로 (Review Focus 3)**

Run: `scripts/verify/stack.sh down`
Expected: `down: ok 익명 볼륨 N→M`(M ≤ N). `docker ps -a --filter label=com.docker.compose.project=stockdesk-verify -q`는 빈 출력.
Run: `mv .verify-artifacts/pre-dangling.txt .verify-artifacts/pre.bak && scripts/verify/stack.sh down; echo "exit=$?"; mv .verify-artifacts/pre.bak .verify-artifacts/pre-dangling.txt`
Expected: `down: 기준 없음(up 기록 없음), 현재 익명 볼륨 M`, `exit=0`.

- [ ] **Step 7: 포트 소유 확인 (Review Focus 1)**

Run: `python3 -m http.server 3334 --bind 127.0.0.1 >/dev/null 2>&1 & srv=$!; sleep 1; scripts/verify/stack.sh doctor; echo "exit=$?"; kill $srv`
Expected: `doctor: stockdesk-verify frontend 컨테이너가 없습니다`, `exit=2`.

- [ ] **Step 8: Commit**

```bash
git add scripts/verify/stack.sh
git commit -m "feat: 검증 전용 스택 관리 스크립트(up·doctor·down)를 추가한다"
```

---

### Task 4: F1 회원 주행 스크립트와 기능 지도

**Files:**
- Create: `scripts/verify/f1_accounts.py`
- Create: `.claude/skills/verify-stockdesk/features/F1-accounts.md`

**Interfaces:**
- Consumes: `common.run`, `common.Client.call`, `common.Recorder.add`, `common.unique_email`, `common.mariadb_scalar`
- Produces: `python3 scripts/verify/f1_accounts.py`(종료 코드). S1 계획이 인증·재설정·탈퇴 단계를 여기에 더한다.
- 현재 API(2026-09-26, `members.py`)
  - `POST /api/member/register {username,email,password,password2}` → 200 `{"username"}`
  - `POST /api/member/login {email,password}` → 200 `{"username","asset"}`
  - `POST /api/member/logout` → 200 `{"success": true}`
  - `GET /api/member/me` → `{"loggedIn": bool, ...}`

- [ ] **Step 1: 주행 스크립트 작성**

`scripts/verify/f1_accounts.py`:

```python
"""F1 회원 주행: 가입 → /me → 로그아웃 → /me → 로그인 → /me, DB에 회원 행 1개.

사용법: python3 scripts/verify/f1_accounts.py (먼저 scripts/verify/stack.sh up·doctor)
"""

import secrets
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402


def steps(client: common.Client, rec: common.Recorder) -> None:
    """F1 단계를 순서대로 실행하고 기대값과 다르면 AssertionError를 낸다."""
    status, body = client.call("GET", "/health")
    rec.add("health", {}, status, body)
    if status != 200:
        raise ConnectionError(f"/health {status}")

    email, password = common.unique_email(), "verify-" + secrets.token_hex(8)
    status, body = client.call("POST", "/api/member/register",
                               {"username": "검증", "email": email, "password": password, "password2": password})
    rec.add("register", {"username": "검증", "email": email, "password": password}, status, body)
    assert status == 200 and body.get("username") == "검증", f"가입 기대 200/검증, 실제 {status}/{body}"

    status, body = client.call("GET", "/api/member/me")
    rec.add("me-after-register", {}, status, body)
    assert body.get("loggedIn") is True, f"가입 뒤 loggedIn 기대 True, 실제 {body}"

    status, body = client.call("POST", "/api/member/logout")
    rec.add("logout", {}, status, body)
    assert status == 200 and body.get("success") is True, f"로그아웃 기대 200/True, 실제 {status}/{body}"

    status, body = client.call("GET", "/api/member/me")
    rec.add("me-after-logout", {}, status, body)
    assert body.get("loggedIn") is False, f"로그아웃 뒤 loggedIn 기대 False, 실제 {body}"

    status, body = client.call("POST", "/api/member/login", {"email": email, "password": password})
    rec.add("login", {"email": email, "password": password}, status, body)
    assert status == 200 and body.get("username") == "검증", f"로그인 기대 200/검증, 실제 {status}/{body}"

    status, body = client.call("GET", "/api/member/me")
    rec.add("me-after-login", {}, status, body)
    assert body.get("loggedIn") is True, f"로그인 뒤 loggedIn 기대 True, 실제 {body}"

    rows = common.mariadb_scalar(f"SELECT COUNT(*) FROM member WHERE email = '{email}'")
    rec.add("db-member-rows", {"email": email}, 0, {"rows": rows})
    assert rows == "1", f"member 행 기대 1, 실제 {rows}"


if __name__ == "__main__":
    sys.exit(common.run("F1", steps))
```

`email`에는 `unique_email()`이 만든 `[a-z0-9-]@example.test` 형식만 들어가므로 SQL에 외부 입력이 섞이지 않는다.

- [ ] **Step 2: 스택을 올린 상태에서 실행**

Run: `scripts/verify/stack.sh up && scripts/verify/stack.sh doctor && python3 scripts/verify/f1_accounts.py; echo "exit=$?"`
Expected: `F1: PASS evidence=.verify-artifacts/<시각>-F1/transcript.json`, `exit=0`.

- [ ] **Step 3: 증거 확인 (Review Focus 4)**

Run: `f=$(ls -t .verify-artifacts/*-F1/transcript.json | head -1); python3 -c "import json,sys; d=json.load(open(sys.argv[1])); print(d['verdict'], [s['step'] for s in d['steps']])" "$f"; grep -c '"password": "\*\*\*"' "$f"; grep -c 'verify-[0-9a-f]\{16\}' "$f"`
Expected: `PASS [...]`, `2` 이상(가림 적용), `0`(원본 비밀번호 없음).

- [ ] **Step 4: 전제 불충족을 잡는지 확인**

Run: `VERIFY_BASE_URL=http://127.0.0.1:3334/nope python3 scripts/verify/f1_accounts.py; echo "exit=$?"`
Expected: `F1: UNMET …`, `exit=2`(`/health`가 200이 아니므로).

- [ ] **Step 5: 두 번 연속 실행 (Review Focus 5)**

Run: `python3 scripts/verify/f1_accounts.py && python3 scripts/verify/f1_accounts.py; echo "exit=$?"`
Expected: 두 번 모두 `PASS`, `exit=0`.

- [ ] **Step 6: 기능 지도 작성**

`.claude/skills/verify-stockdesk/features/F1-accounts.md`:

```markdown
# F1 회원

사용자가 가입하고, 로그인 상태를 확인하고, 로그아웃과 재로그인을 한다. S1 계정·신뢰 기반 작업이 인증 메일·재설정·모든 기기 로그아웃·탈퇴를 이 지도에 더한다.

## 하위 기능

- `f1-register`: 가입하면 곧바로 로그인 상태가 된다(S1 뒤에는 "인증 메일 발송"으로 바뀐다).
- `f1-me`: `/api/member/me`가 로그인 여부와 프로필을 알려 준다.
- `f1-logout`: 로그아웃하면 `loggedIn: false`.
- `f1-login`: 같은 이메일·비밀번호로 다시 로그인한다.

## 사용자 경로

- 화면: `/member/register.html`, `/member/login.html`, 상단 메뉴의 로그아웃.
- API: `POST /api/member/register`, `POST /api/member/login`, `POST /api/member/logout`, `GET /api/member/me`.

## 주행

전제 조건: `scripts/verify/stack.sh doctor`가 `ok`, 프로필 `local`.

- **전체 흐름.** 가입부터 재로그인까지 한 번에 돈다. `python3 scripts/verify/f1_accounts.py`를 실행한다. `F1: PASS`와 증거 경로가 출력되고, `member` 행이 1개다.
- **화면 확인.** 쿠키 없는 Playwright로 `http://127.0.0.1:3334/member/login.html`을 연다. 이메일과 비밀번호 칸이 있고 로그인 버튼이 보인다. 캡처는 같은 증거 폴더에 `login.png`로 저장한다.

## 함정

- public 프로필은 S1 이후 가입이 닫혀 있다(`signupOpen: false`, 가입 403). 검증 스택은 local이다.
- 이메일은 실행마다 새로 만든다(`@example.test`). 고정 주소를 쓰면 두 번째 실행에서 "이미 존재"로 실패한다.
- 로그인 제한(IP당 분당 10회)은 local 프로필에서 꺼져 있다. public에서 반복하면 429가 난다.
```

- [ ] **Step 7: Commit**

```bash
git add scripts/verify/f1_accounts.py .claude/skills/verify-stockdesk/features/F1-accounts.md
git commit -m "feat: F1 회원 주행 스크립트와 기능 지도를 추가한다"
```

---

### Task 5: F2 백테스트 영수증 주행 스크립트와 기능 지도

**Files:**
- Create: `scripts/verify/f2_backtest.py`
- Create: `.claude/skills/verify-stockdesk/features/F2-backtest.md`

**Interfaces:**
- Consumes: `common.run`, `common.Client.call`, `common.Recorder.add`
- 현재 API(`quant.py:311,358`)
  - `POST /api/quant/backtests {symbol,strategy,feeRate,slippage,fast,slow}` → 새 실행이면 201, 같은 입력이면 200, 본문에 `receiptId`(64자리 16진수)
  - 데이터가 부족하면 404
  - `GET /api/quant/backtests/<receiptId>` → 200, `receiptId`·`metrics`

- [ ] **Step 1: 주행 스크립트 작성**

`scripts/verify/f2_backtest.py`:

```python
"""F2 백테스트 영수증 주행: 같은 입력을 두 번 실행하면 같은 receiptId, 조회로 다시 읽힌다.

사용법: python3 scripts/verify/f2_backtest.py (먼저 scripts/verify/stack.sh up·doctor)
"""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402

REQUEST = {"symbol": "005930", "strategy": "ma2050", "feeRate": 0.00015, "slippage": 0.0005, "fast": 20, "slow": 50}


def steps(client: common.Client, rec: common.Recorder) -> None:
    """F2 단계를 실행하고 기대값과 다르면 AssertionError를 낸다."""
    status, first = client.call("POST", "/api/quant/backtests", REQUEST)
    rec.add("backtest-1", REQUEST, status, {"receiptId": first.get("receiptId") if isinstance(first, dict) else first})
    if status == 404:
        raise ConnectionError(f"시세 데이터 부족: {first}")
    assert status in (200, 201), f"첫 실행 기대 200/201, 실제 {status}/{first}"
    receipt = first.get("receiptId", "")
    assert re.fullmatch(r"[0-9a-f]{64}", receipt), f"receiptId 형식 오류: {receipt!r}"

    status, second = client.call("POST", "/api/quant/backtests", REQUEST)
    rec.add("backtest-2", REQUEST, status, {"receiptId": second.get("receiptId")})
    assert status == 200 and second.get("receiptId") == receipt, (
        f"같은 입력 기대 200/같은 영수증, 실제 {status}/{second.get('receiptId')}")

    status, stored = client.call("GET", f"/api/quant/backtests/{receipt}")
    rec.add("stored", {"receiptId": receipt}, status,
            {"receiptId": stored.get("receiptId"), "hasMetrics": "metrics" in stored})
    assert status == 200 and stored.get("receiptId") == receipt and "metrics" in stored, f"조회 실패 {status}/{stored}"


if __name__ == "__main__":
    sys.exit(common.run("F2", steps))
```

- [ ] **Step 2: 실행**

Run: `python3 scripts/verify/f2_backtest.py; echo "exit=$?"`
Expected: `F2: PASS evidence=…-F2/transcript.json`, `exit=0`. 첫 호출은 처음이면 201, 이전 실행을 재사용하면 200이다(둘 다 통과).

- [ ] **Step 3: 기능 지도 작성**

`.claude/skills/verify-stockdesk/features/F2-backtest.md`:

```markdown
# F2 퀀트 백테스트와 계산 영수증

사용자가 종목과 전략으로 백테스트를 돌린다. 같은 입력이면 같은 계산 영수증(receiptId)이 나오고, 영수증으로 결과를 다시 읽는다.

## 하위 기능

- `f2-run`: 첫 실행은 201(새 실행)이고, 본문에 64자리 16진수 `receiptId`가 있다.
- `f2-idempotent`: 같은 입력의 재실행은 200이고 같은 `receiptId`다.
- `f2-lookup`: `GET /api/quant/backtests/<receiptId>`로 지표(`metrics`)를 다시 읽는다.

## 사용자 경로

- 화면: `/quant.html`의 종목 입력칸(`data-symbol`)과 기본 실행 버튼(MA 20/50).
- API: `POST /api/quant/backtests`, `GET /api/quant/backtests/<receiptId>`.

## 주행

전제 조건: `scripts/verify/stack.sh doctor`가 `ok`. 로컬 샘플 시세에 005930이 있다.

- **영수증 재현.** 같은 입력으로 두 번 실행하고 조회한다. `python3 scripts/verify/f2_backtest.py`를 실행한다. `F2: PASS`가 출력되고, 두 실행의 `receiptId`가 같다.
- **화면 확인.** 쿠키 없는 Playwright로 `http://127.0.0.1:3334/quant.html`을 열고 기본 실행을 누른다. 결과 영역에 수익률·MDD와 "전략 #"이 나온다. 캡처는 증거 폴더에 `quant.png`로 저장한다.

## 함정

- 시세는 합성·교육용 샘플이다. 수익률 값 자체를 기대값으로 삼지 말고, 영수증의 동일성과 필드 존재를 본다.
- 비용 파라미터를 바꾸면 영수증이 바뀐다(`feeRate` 0.00015는 1.5bp로 반올림된다, `quant.py:163`).
- 404는 데이터 부족이다. 실패가 아니라 전제 불충족(종료 코드 2)으로 보고한다.
```

- [ ] **Step 4: Commit**

```bash
git add scripts/verify/f2_backtest.py .claude/skills/verify-stockdesk/features/F2-backtest.md
git commit -m "feat: F2 백테스트 영수증 주행 스크립트와 기능 지도를 추가한다"
```

---

### Task 6: `SKILL.md`, 지도 색인, 처음부터 끝까지 증명

**Files:**
- Create: `.claude/skills/verify-stockdesk/SKILL.md`
- Create: `.claude/skills/verify-stockdesk/features/README.md`
- Create: `docs/evidence/verify-skill-2026-09-26.md`

**Interfaces:**
- Consumes: Task 3~5의 명령 전부.
- Produces: 다른 에이전트가 이 파일만 읽고 검증을 수행할 수 있는 스킬.

- [ ] **Step 1: `SKILL.md` 작성**

```markdown
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

## Launch

`scripts/verify/stack.sh up`
- 첫 실행 때 `.env.verify`(권한 600)를 만든다. 값은 출력하지 않는다.
- 이미지를 빌드하고 frontend·backend·init·DB를 띄운다. worker는 띄우지 않는다.
- 준비되면 `up: ok`를 출력한다.

## Doctor

`scripts/verify/stack.sh doctor`
- 포트 3334의 주인이 이 프로젝트 컨테이너인지, `/health`, init 종료 코드 0, 프로필, 판정 모델 상태를 확인한다.
- `ok`가 아니면(종료 코드 2) 주행하지 않고 원인을 보고한다.

## Drive

`features/README.md`에서 기능을 고르고, 그 파일의 "주행" 절을 따른다.
- API 흐름은 `python3 scripts/verify/f<번호>_*.py`로 증명한다. 종료 코드는 0 통과, 1 실패, 2 전제 불충족이다.
- 화면은 Playwright로 연다. 선택자는 접근성 이름, `id`, `data-*`를 쓰고 좌표는 쓰지 않는다.

## Evidence

- 스크립트가 `.verify-artifacts/<UTC시각>-<기능ID>/transcript.json`을 쓴다. 쿠키, 토큰, 비밀번호, csrf는 `***`로 가린다.
- 화면 캡처는 같은 폴더에 저장한다.
- 보고에는 판정과 이 경로를 쓴다.

## Cleanup

`scripts/verify/stack.sh down`
- 이 프로젝트만 `down -v`한다. 익명 볼륨 수가 up 때보다 늘면 실패(종료 코드 1)다.
- 증거 폴더는 지우지 않는다.
- 프로세스를 이름으로 죽이지 않는다.

## Helpers

| 명령 | 역할 |
|---|---|
| `scripts/verify/stack.sh up\|doctor\|down` | 스택 수명주기 |
| `python3 scripts/verify/f1_accounts.py` | F1 회원 |
| `python3 scripts/verify/f2_backtest.py` | F2 백테스트 영수증 |
| `scripts/verify/common.py` | 공용 도구(직접 실행하지 않음) |

구조와 형식은 cursor/plugins pstack(MIT)의 create-verification-skill을 참고해 새로 썼다.
```

- [ ] **Step 2: 지도 색인 작성**

`.claude/skills/verify-stockdesk/features/README.md`:

```markdown
# stockdesk 기능 지도

각 기능을 사용자가 어떻게 쓰는지, 무엇이 동작의 증거인지 적는다. 주행 전에 이 색인을 읽고 해당 파일을 따른다.

## 공통 전제

- `scripts/verify/stack.sh doctor`가 `ok`, 프로필 `local`, 주소 `http://127.0.0.1:3334`.
- 외부 과금 기능(판정 모델, DART 수집)은 검증 스택에서 꺼져 있다.

## 증거 규칙

- 사용자 행동과 그 결과 상태를 함께 남긴다. 저장이 일어나면 DB나 재조회로 한 번 더 확인한다.
- 다른 경로로 대신 확인한 것을 "검증됨"으로 쓰지 않는다. 못 간 경로는 시도한 명령과 부족한 전제를 적는다.

## 파일 형식

기능마다 H1 제목과 한 단락 설명, 그리고 네 절(`하위 기능`, `사용자 경로`, `주행`, `함정`)을 이 순서로 둔다.

## 기능

- [F1 회원](./F1-accounts.md): 가입, 로그인 상태, 로그아웃, 재로그인
- [F2 백테스트와 계산 영수증](./F2-backtest.md): 영수증 재현과 조회

F3 명령 바, F4 김프·공지 경고, F5 공시 화면은 해당 기능을 다음에 고칠 때 추가한다.
```

- [ ] **Step 3: 처음부터 끝까지 증명(PM)**

Run: `scripts/verify/stack.sh up && scripts/verify/stack.sh doctor && python3 scripts/verify/f1_accounts.py && python3 scripts/verify/f2_backtest.py && scripts/verify/stack.sh down; echo "exit=$?"`
Expected
- 각 단계가 `ok`/`PASS`를 출력하고, `down: ok 익명 볼륨 N→M`(M ≤ N), `exit=0`.
- 정리 후에도 `ls -d .verify-artifacts/*-F1 .verify-artifacts/*-F2`가 증거 폴더를 보여 준다.

- [ ] **Step 4: 화면 캡처(PM, Playwright MCP)**

스택을 다시 올린다(`up`, `doctor`). Playwright로 `http://127.0.0.1:3334/quant.html`에 가서 기본 실행을 누르고, 결과 영역이 보이면 캡처해 최신 F2 증거 폴더에 `quant.png`로 저장한다.

- [ ] **Step 5: 독립 재현(Evidence Collector)**

Agency-Agents Evidence Collector에게 다음 브리프를 준다. 브리프에는 `docs/agents/standing-orders.md`를 그대로 붙인다.
- 목적: `.claude/skills/verify-stockdesk/SKILL.md`만 읽고 F2를 주행해 판정과 증거 경로를 보고한다.
- 범위: `up`/`doctor`/F2/`down`만 한다. 파일 수정은 금지다.
- 완료 기준: 판정, 종료 코드, 증거 경로, dangling 전후 수.

PM은 보고된 증거 파일을 직접 열어 판정을 확인한다.

- [ ] **Step 6: 증거 문서 작성**

`docs/evidence/verify-skill-2026-09-26.md`에 다음을 표로 적는다.
- Step 3~5의 명령, 종료 코드, 판정
- 증거 경로, dangling 전후 수
- 로컬 스택 무변경 확인(Task 3 Step 4)
- Evidence Collector의 재현 결과

- [ ] **Step 7: Commit**

```bash
git add .claude/skills/verify-stockdesk/SKILL.md .claude/skills/verify-stockdesk/features/README.md docs/evidence/verify-skill-2026-09-26.md
git commit -m "feat: verify-stockdesk 검증 스킬과 실행 증거를 추가한다"
```

---

### Task 7: PR

- [ ] **Step 1: 전체 단위 테스트와 린트**

Run: `docker run --rm -v "$PWD":/repo -w /repo sct-test:dev python -m pytest -q -m "not integration"`
Expected: 기존 테스트와 새 4개가 모두 통과한다.
Run: `docker run --rm -v "$PWD":/repo -w /repo sct-test:dev ruff check .`
Expected: `All checks passed!`

- [ ] **Step 2: diff 검토, ponytail-review, 기록**

Run: `git diff main --stat` 후 `/ponytail-review`, 이어서 `bash ~/.agents/hooks/record-ponytail-review.sh`.

- [ ] **Step 3: push와 PR**

```bash
git push -u origin feat/verify-stockdesk
gh pr create -R Noah-TaeHwan/stock-coin-trade --base main --head feat/verify-stockdesk \
  --title "feat: 검증 스킬 verify-stockdesk와 에이전트 상시 지시(T0-1·T0-3)" \
  --body "요약과 증거: docs/evidence/verify-skill-2026-09-26.md"
```

Expected: PR URL 출력. CI 세 작업(lint·unit, 통합, 이미지 빌드)이 초록. PR 본문 끝에 Claude Code 생성 표기를 붙인다.
