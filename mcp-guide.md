# KIS MCP 연동 가이드

이 문서는 이 저장소에 연결한 한국투자증권(KIS) MCP의 구성과 사용 방법을 설명합니다. MCP는 AI 클라이언트가 외부 도구를 호출하는 표준 인터페이스입니다. 이 프로젝트는 MCP 서버를 새로 만들지 않고 [한국투자증권 공식 `open-trading-api`](https://github.com/koreainvestment/open-trading-api)의 서버 두 개를 로컬에서 실행합니다.

| 서버 | 이 저장소의 이름 | 용도 |
| --- | --- | --- |
| KIS Code Assistant MCP | `kis-code-assistant` | Open API 검색, 인자 확인, 예제 코드 생성 |
| KIS Trading MCP | `kis-trading-paper` | KIS Open API 호출. 이 저장소에서는 모의투자 키를 전달 |

웹앱의 `/api/*` 및 Flask 백엔드와는 별도 경로입니다. MCP 도구 호출은 개발자의 컴퓨터에서 공식 서버를 거쳐 KIS API로 전달됩니다.

## 구성과 호출 흐름

```text
Codex CLI·IDE (.codex/config.toml) ───────┐
VS Code Copilot Chat (.vscode/mcp.json) ───┼─→ scripts/kis_mcp.py ─→ 공식 KIS MCP 서버
VS Code 탐색기 KIS MCP 패널 ────────────────┘          │                 ├─ Code Assistant
                                                    │                 └─ Trading (모의투자)
                                                    └─ .env 또는 .env에서 모의투자 키 읽기
```

- [`scripts/setup_kis_mcp.sh`](scripts/setup_kis_mcp.sh)는 공식 저장소를 Git 무시 대상인 `mcp/open-trading-api/`에 내려받고, `mcp/.venv/`에 `uv`를 설치한 뒤 각 공식 서버의 의존성을 동기화합니다.
- [`scripts/kis_mcp.py`](scripts/kis_mcp.py)는 `code` 또는 `trade` 서버를 **stdio** 방식으로 실행합니다. 두 클라이언트 설정과 탐색기 확장이 모두 이 스크립트를 사용합니다.
- [`scripts/kis_trading_server.py`](scripts/kis_trading_server.py)는 공식 Trading 서버의 진단 출력을 stderr로 보내 MCP JSON-RPC가 사용하는 stdout을 깨끗하게 유지합니다.
- [`vscode-kis-mcp/`](vscode-kis-mcp/)는 VS Code 탐색기 하단의 도구 실행 패널입니다. 내부 MCP 클라이언트가 서버에 연결해 도구 목록을 읽고 JSON 인자로 호출합니다.

## 설치와 설정 확인

저장소 루트에서 Python 3.12 이상과 Git을 준비합니다. 최초 설치에는 공식 저장소와 Python 패키지를 받을 네트워크 연결이 필요합니다. 설치 스크립트는 마지막에 두 서버의 설정을 검사하므로, 거래 서버까지 준비한다면 먼저 루트 `.env`에 다음 값을 넣습니다. 계좌번호는 `12345678-01`처럼 **8자리 계좌번호-2자리 상품코드** 형식입니다.

```dotenv
KIS_ENVIRONMENT=paper
KIS_PAPER_APP_KEY=<모의투자 App Key>
KIS_PAPER_APP_SECRET=<모의투자 App Secret>
KIS_PAPER_ACCOUNT_NO=12345678-01
```

기존 모의투자용 `.env`의 `App-KEY`, `Secret`, `account`도 사용할 수 있습니다. 호환용 `KIS_PAPER_APP_KEY`, `KIS_PAPER_APP_SECRET`, `KIS_PAPER_ACCOUNT_NO`는 `KIS_ENVIRONMENT=paper`에서만 사용합니다. 새 설정에는 `KIS_PAPER_*` 변수를 사용하세요. 실행 스크립트는 환경변수, `.env`, `.env`를 순서대로 확인하며, 모의투자 키 쌍과 계좌번호 형식을 검사합니다. 키를 `.codex/config.toml`이나 `.vscode/mcp.json`에 넣을 필요는 없습니다.

```bash
bash scripts/setup_kis_mcp.sh
```

Code Assistant만 사용한다면 거래 키 없이도 코드 검색 서버를 사용할 수 있습니다. 다만 설치 스크립트의 마지막 `trade --check`는 키가 없어서 실패합니다. 이때 `code --check`로 코드 검색 서버의 설치 상태를 확인하세요.

설정만 점검하려면 다음 명령을 실행합니다. `--check`는 서버를 시작하거나 KIS API를 호출하지 않고 로컬 경로와 설정을 검사합니다.

```bash
python3 scripts/kis_mcp.py code --check
python3 scripts/kis_mcp.py trade --check
```

각각 `code MCP configuration is ready`, `trade MCP configuration is ready`가 출력되면 로컬 실행 준비가 된 상태입니다. 실제 연결은 아래 클라이언트에서 도구 목록을 열어 확인합니다.

## Codex와 VS Code에서 사용

### Codex CLI·IDE와 VS Code Copilot Chat

[`.codex/config.toml`](.codex/config.toml)과 [`.vscode/mcp.json`](.vscode/mcp.json)에 `kis-code-assistant`, `kis-trading-paper` 서버가 등록되어 있습니다. 두 설정은 `python3 scripts/kis_mcp.py code|trade`를 실행합니다. 설정을 추가하거나 설치한 뒤에는 Codex 또는 VS Code 창을 다시 시작하고 MCP 도구 목록에서 두 서버를 확인합니다. Codex IDE 확장은 VS Code 보조 사이드바에서 열 수 있습니다.

예를 들어 다음처럼 요청할 수 있습니다.

```text
KIS Code Assistant MCP로 국내주식 현재가 API와 필수 인자를 찾아줘.
KIS Trading MCP로 모의투자 삼성전자(005930) 현재가를 조회해줘.
```

Codex 설정의 Trading 서버에는 도구 승인 모드 `prompt`가 지정되어 있습니다. 주문처럼 계좌에 영향을 주는 호출은 실행 내용을 확인한 뒤 승인하세요.

### 탐색기 하단 KIS MCP 패널

[`vscode-kis-mcp/`](vscode-kis-mcp/) 확장을 설치하면 탐색기 하단에 **KIS MCP** 보기가 생깁니다. 새 VS Code 환경에서는 다음 명령으로 VSIX를 만들어 설치합니다. 패키징 명령에는 `vsce` CLI가 필요합니다.

```bash
cd vscode-kis-mcp
vsce package --no-dependencies
code --install-extension kis-mcp-explorer-0.1.0.vsix
```

설치 후 **Developer: Reload Window**를 실행하고 탐색기의 **KIS MCP**를 펼치거나 명령 팔레트에서 **KIS MCP: 탐색기 패널 열기**를 실행합니다. 패널에는 서버 연결 상태, 도구 목록, JSON 인자 입력란, 결과 확인·복사 기능이 있습니다. **API 검색 예시**와 **삼성전자 시세** 버튼으로 조회 예시를 불러올 수 있습니다. 이 패널은 Codex 채팅을 거치지 않고 공식 MCP 도구를 직접 호출합니다.

## 모의투자 처리와 키 보관

`scripts/kis_mcp.py`는 `KIS_ENVIRONMENT=paper`만 허용합니다. 거래 서버에 실전 키·계좌 변수를 전달하지 않고 `KIS_PAPER_*` 값만 설정하며, 공식 서버가 만드는 `~/KIS/config/kis_devlp.yaml`의 홈 디렉터리를 Git 무시 대상인 `mcp/home/`으로 격리합니다. 스크립트의 `ENV=live`는 공식 서버의 `.env.live` 전송 설정 파일을 선택하는 값이며 실전 거래 키를 뜻하지 않습니다.

탐색기 패널은 Trading 도구에서 `env_dv=real`을 거부하고 실제 API 호출에는 `env_dv=demo`를 넣습니다. 조회 예시 외의 Trading 호출에는 VS Code 확인창을 띄웁니다. 패널의 Webview에는 키와 계좌정보를 보내지 않습니다. 다른 MCP 클라이언트에서도 모의 주문 도구를 호출할 수 있으므로 도구명과 인자를 확인한 뒤 실행하세요.

`.env`, 내려받은 `mcp/` 폴더는 Git 무시 대상입니다. 응답이나 화면을 공유할 때도 App Key, Secret, 토큰, 계좌번호를 제거하세요.

## 연결 문제 확인

| 증상 | 확인할 곳 |
| --- | --- |
| `KIS MCP source is missing` | 저장소 루트에서 `bash scripts/setup_kis_mcp.sh` 실행 |
| `uv is missing` | 설치 스크립트로 `mcp/.venv/bin/uv` 설치 확인 |
| 거래 서버의 키 또는 계좌 오류 | `.env`의 `KIS_PAPER_*` 세 값, 계좌번호 형식, `KIS_ENVIRONMENT=paper` 확인 |
| MCP 도구가 보이지 않음 | VS Code·Codex 재시작 후 두 서버 연결 상태 확인 |
| 탐색기 패널이 보이지 않음 | VSIX 설치, 창 다시 로드, 명령 팔레트의 **KIS MCP: 탐색기 패널 열기** 실행 |
| 패널에 연결 실패 표시 | **서버 새로고침** 후 표시되는 오류와 `--check` 결과 확인 |

공식 기능과 API 목록은 [KIS MCP 안내](https://apiportal.koreainvestment.com/tools-mcp) 및 [공식 MCP 소스](https://github.com/koreainvestment/open-trading-api/tree/main/MCP)를 참고하세요.
