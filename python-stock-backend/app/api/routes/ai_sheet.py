"""AI Sheet: URL 크롤링 시트, 섹터별 월별 종가, 퀀트 분석, LEAN 백테스트."""

from __future__ import annotations

from fastapi import APIRouter, Body
from fastapi.responses import JSONResponse

from app.services import ai_sheet
from app.services.ai_sheet import SheetError

from ..schemas import CrawlBody, SectorSheetBody, SheetBody

router = APIRouter(prefix="/api/ai-sheet", tags=["ai-sheet"])


def _run(build):
    try:
        return build()
    except SheetError as exc:
        return JSONResponse({"message": exc.message, **exc.extra}, status_code=exc.status_code)


@router.post("/crawl")
def crawl_to_sheet(payload: CrawlBody = Body(default_factory=CrawlBody)):
    return _run(lambda: ai_sheet.crawl_to_sheet(str(payload.url or "").strip()))


@router.get("/sectors")
def list_sectors() -> dict:
    return {"sectors": ai_sheet.list_sectors()}


@router.post("/sector-sheet")
def build_sector_sheet(payload: SectorSheetBody = Body(default_factory=SectorSheetBody)):
    sector = str(payload.sector or "").strip()
    if not sector:
        return JSONResponse({"message": "섹터를 선택해주세요."}, status_code=400)
    return _run(lambda: ai_sheet.build_sector_sheet(sector))


@router.post("/quant-analyze")
def quant_analyze(payload: SheetBody = Body(default_factory=SheetBody)):
    return _run(lambda: ai_sheet.quant_analyze(payload.columns, payload.rows))


@router.post("/lean-backtest")
def lean_backtest(payload: SheetBody = Body(default_factory=SheetBody)):
    return _run(lambda: ai_sheet.lean_backtest(payload.columns, payload.rows, payload.rowIndex or 0))
