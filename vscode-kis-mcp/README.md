# KIS MCP Explorer

VS Code 탐색기 하단에서 이 작업공간의 공식 KIS Code Assistant MCP와 KIS Trading MCP 도구를 사용합니다.

1. 저장소 루트에서 `bash scripts/setup_kis_mcp.sh`로 서버를 준비합니다.
2. `KIS MCP: 탐색기 패널 열기` 명령을 실행하거나 탐색기 아래의 **KIS MCP** 보기를 엽니다.
3. 예시 버튼을 누르거나 서버와 도구를 골라 JSON 인자를 입력한 뒤 **도구 실행**을 누릅니다.

Trading 도구는 이 패널에서 `env_dv=demo`로 실행됩니다. 조회 예시 외의 거래 도구는 실행 전에 VS Code 확인창을 표시합니다. 키와 계좌정보는 기존 `scripts/kis_mcp.py`가 로컬에서 읽으며 Webview로 보내지 않습니다.
