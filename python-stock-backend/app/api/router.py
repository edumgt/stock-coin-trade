"""모든 라우터를 하나로 모은다. 경로 접두사는 각 라우터가 소유한다."""

from fastapi import APIRouter

from app.api.routes import (
    admin,
    ai,
    ai_sheet,
    alpaca_test,
    alpaca_test_aws,
    alternatives,
    api_keys,
    api_usage,
    aria,
    broker_test,
    broker_test_aws,
    crypto,
    crypto_exchange_test,
    error_analysis,
    health,
    kis_chart,
    kis_explorer,
    kis_practice,
    kis_real,
    market,
    members,
    ohlcv_db,
    openapi,
    quant,
    stocks,
)

api_router = APIRouter()
for module_router in (
    health.router,
    members.router,
    api_keys.router,          # /api/member/api-keys 는 /api/member 보다 먼저 등록할 필요는 없지만 명시적으로 묶어 둔다.
    market.router,
    stocks.router,
    crypto.market_router,
    crypto.trade_router,
    crypto_exchange_test.router,
    admin.router,
    ai.router,
    ai_sheet.router,
    alpaca_test.router,
    alpaca_test_aws.router,
    aria.router,
    broker_test.router,
    broker_test_aws.router,
    kis_explorer.router,
    kis_chart.router,
    kis_practice.router,
    kis_real.router,
    openapi.router,
    ohlcv_db.router,
    quant.router,
    alternatives.router,
    error_analysis.router,
    api_usage.router,
):
    api_router.include_router(module_router)
