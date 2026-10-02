"""요청 본문 스키마(Pydantic v2).

프런트엔드가 기대하는 한국어 검증 메시지를 유지해야 하는 필드는 ``Any``로 받고 라우트에서 직접 검증한다.
그 외 필드는 Pydantic 타입 검증을 쓰며, 실패 시 400 ``INVALID_REQUEST``로 응답한다(app.core.errors).
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class LoginBody(BaseModel):
    email: str | None = None
    password: str | None = None


class RegisterBody(BaseModel):
    username: str | None = None
    email: str | None = None
    password: str | None = None
    password2: str | None = None


class MemoBody(BaseModel):
    memo: Any = ""


class StockOrderBody(BaseModel):
    symbol: Any = ""
    quantity: Any = 0


class StockPreviewBody(BaseModel):
    symbol: Any = ""
    side: Any = ""
    quantity: Any = 0


class CryptoBuyBody(BaseModel):
    marketCode: str | None = None
    buyKrw: Any = None


class CryptoSellBody(BaseModel):
    marketCode: str | None = None
    sellCount: Any = None


class CryptoPreviewBody(BaseModel):
    marketCode: Any = ""
    side: Any = ""
    buyKrw: Any = ""
    sellCount: Any = 0


class AlternativeOrderBody(BaseModel):
    symbol: Any = ""
    side: Any = ""
    quantity: Any = 0


class QdrantSearchBody(BaseModel):
    query: Any = ""
    limit: int = 5


class QdrantAddBody(BaseModel):
    text: Any = ""
    title: Any = ""
    category: Any = "custom"


class AiAnalyzeBody(BaseModel):
    context: Any = None
    type: Any = None


class CrawlBody(BaseModel):
    url: Any = ""


class SectorSheetBody(BaseModel):
    sector: Any = ""


class SheetBody(BaseModel):
    columns: list[Any] = Field(default_factory=list)
    rows: list[Any] = Field(default_factory=list)
    rowIndex: Any = 0


class KisExplorerCallBody(BaseModel):
    id: Any = ""
    params: dict[str, Any] | None = None
    variant: Any = None


class KisPaperOrderBody(BaseModel):
    symbol: Any = ""
    side: Any = ""
    orderType: Any = "MARKET"
    quantity: Any = None
    price: Any = 0
    approvalToken: Any = ""


class ApprovalTokenBody(BaseModel):
    approvalToken: Any = ""


class KisPracticeOrderBody(BaseModel):
    symbol: Any = ""
    side: Any = ""
    quantity: Any = 0


class ApiKeyCreateBody(BaseModel):
    label: Any = None


class AriaEncryptBody(BaseModel):
    text: Any = None
    passphrase: Any = None
    key_bits: Any = 256


class AriaDecryptBody(BaseModel):
    cipher: Any = None
    passphrase: Any = None
    key_bits: Any = 256


class BacktestBody(BaseModel):
    symbol: Any = "005930"
    fast: Any = 20
    slow: Any = 50
    quantity: Any = 10
    feeRate: Any = 0.00015
    slippage: Any = 0.0005
    strategy: Any = "ma2050"


class OpenApiOrderBody(BaseModel):
    symbol: Any = ""
    side: Any = ""
    quantity: Any = 0


class KisAutotradeOrderBody(BaseModel):
    """KIS 자동매매 Open API 주문/승인 본문. 검증 메시지는 kis_autotrade.normalize_intent 가 만든다."""

    environment: Any = "paper"
    symbol: Any = ""
    side: Any = ""
    orderType: Any = "MARKET"
    quantity: Any = None
    price: Any = 0
    clientOrderId: Any = ""
    approvalToken: Any = ""


class ClientErrorBody(BaseModel):
    message: Any = ""
    type: Any = "JavaScriptError"
    stack: Any = None
    url: Any = None
    line: Any = None
    column: Any = None
