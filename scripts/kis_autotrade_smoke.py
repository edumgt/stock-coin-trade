"""KIS 자동매매 Open API 스모크 테스트 (lumina 컨테이너 안에서 실행: 같은 shared-net, 같은 API 키 설정을 사용).

사용:  docker exec fin-ai-app python /app/scripts/kis_autotrade_smoke.py [--order]
  기본  : 잔고 조회 + 당일 주문 목록 + 승인 토큰 발급(주문은 내지 않음)
  --order: 삼성전자 1주를 현재가 -8%(호가 보정) 지정가로 모의 매수 접수 → 체결 조회 → 취소까지 수행 (체결 안 되는 가격)
"""
import json
import os
import sys

import httpx

base = os.environ["STOCK_COIN_TRADE_BASE_URL"].rstrip("/")
key = os.environ["STOCK_COIN_TRADE_API_KEY"]
cli = httpx.Client(base_url=base, headers={"Authorization": f"Bearer {key}"}, timeout=20)


def show(title, r):
    print(f"\n== {title}: HTTP {r.status_code}")
    try:
        print(json.dumps(r.json(), ensure_ascii=False, indent=1)[:1500])
    except ValueError:
        print(r.text[:500])
    return r


bal = show("잔고", cli.get("/openapi/v1/kis/balance", params={"environment": "paper"}))
show("당일 주문", cli.get("/openapi/v1/kis/orders", params={"environment": "paper", "status": "ALL"}))

if bal.status_code != 200:
    sys.exit("잔고 조회 실패 — API 키/스코프/KIS 자격증명을 확인하세요")

def tick(p):
    return 1 if p < 2000 else 5 if p < 5000 else 10 if p < 20000 else 50 if p < 50000 else 100 if p < 200000 else 500 if p < 500000 else 1000

holdings = {h["symbol"]: h for h in bal.json()["balance"]["holdings"]}
cur = int(holdings.get("005930", {}).get("currentPrice") or 0)
if not cur:
    # 보유 중이 아니면 현재가를 모르므로 보수적으로 50,000원 기준(삼성전자 하한가 밖이면 KIS가 거부 → 그것도 유효한 테스트)
    cur = 50000
price = int(cur * 0.92); price -= price % tick(price)
intent = {"environment": "paper", "symbol": "005930", "side": "BUY", "orderType": "LIMIT", "quantity": 1, "price": price,
          "clientOrderId": f"smoke:{os.getpid()}"}
ap = show("승인 토큰", cli.post("/openapi/v1/kis/order-approval", json=intent))
if "--order" not in sys.argv or ap.status_code != 200:
    print("\n(주문은 내지 않았습니다. --order 로 접수→조회→취소까지 실행)")
    sys.exit(0)

od = show("주문 접수", cli.post("/openapi/v1/kis/orders", json={**intent, "approvalToken": ap.json()["approvalToken"]}))
if od.status_code != 200:
    sys.exit(1)
no = od.json()["order"]["orderNo"]
show("체결 조회", cli.get(f"/openapi/v1/kis/orders/{no}", params={"environment": "paper"}))
show("취소", cli.delete(f"/openapi/v1/kis/orders/{no}", params={"environment": "paper"}))
show("취소 후 조회", cli.get(f"/openapi/v1/kis/orders/{no}", params={"environment": "paper"}))
