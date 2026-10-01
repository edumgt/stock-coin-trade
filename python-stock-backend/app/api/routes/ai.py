"""시세 컨텍스트를 Claude에 보내 한국어 분석을 SSE로 스트리밍한다."""

from __future__ import annotations

import json
from collections.abc import Iterator

import requests
from fastapi import APIRouter, Body
from fastapi.responses import StreamingResponse

from app.core.config import get_settings

from ..schemas import AiAnalyzeBody

router = APIRouter(prefix="/api/ai", tags=["ai"])

SYSTEM_PROMPT = (
    "당신은 한국 금융 시장 전문가입니다. 제공된 실시간 시세 데이터를 분석하여 한국어로 명확하고 실용적인 투자 조언을 제공합니다. "
    "이 내용은 투자 교육 목적이며, 실제 투자 결정은 본인 판단에 따라야 함을 고지합니다."
)


def _build_prompt(type_: str, context: str) -> str:
    label = {"crypto": "코인 시장", "stock": "주식 시장"}.get(type_, "전체 금융 시장")
    return (
        f"다음은 현재 {label}의 실시간 시세 데이터입니다:\n\n{context}\n\n"
        "위 데이터를 바탕으로 다음을 분석해주세요:\n"
        "1. 시장 전반적인 분위기와 트렌드\n"
        "2. 주목할 만한 종목이나 코인과 그 이유\n"
        "3. 단기 관점에서의 유의 사항\n"
        "4. 리스크 관리 조언\n\n"
        "간결하고 실용적으로 답변해주세요. (교육 목적)"
    )


def _stream_claude(api_key: str, model: str, prompt: str) -> Iterator[str]:
    payload = {
        "model": model,
        "max_tokens": 1024,
        "stream": True,
        "system": SYSTEM_PROMPT,
        "messages": [{"role": "user", "content": prompt}],
    }
    try:
        with requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={"Content-Type": "application/json", "x-api-key": api_key, "anthropic-version": "2023-06-01"},
            json=payload,
            stream=True,
            timeout=60,
        ) as resp:
            for raw_line in resp.iter_lines(decode_unicode=True):
                if not raw_line or not raw_line.startswith("data: "):
                    continue
                data = raw_line[6:].strip()
                if data == "[DONE]":
                    break
                try:
                    event = json.loads(data)
                except ValueError:
                    continue
                text = event.get("delta", {}).get("text")
                if text:
                    yield text
    except Exception as exc:  # noqa: BLE001 - 스트림 중 오류는 본문으로 전달한다.
        yield f"\n\n⚠️ AI 분석 중 오류가 발생했습니다: {exc}"


@router.post("/analyze")
def analyze(payload: AiAnalyzeBody = Body(default_factory=AiAnalyzeBody)) -> StreamingResponse:
    context = str(payload.context or "시세 데이터 없음")
    type_ = str(payload.type or "general")
    settings = get_settings()
    api_key = settings.anthropic_api_key.strip()
    if not api_key:
        return StreamingResponse(
            iter(["⚠️ ANTHROPIC_API_KEY가 설정되지 않았습니다.\n\n환경변수 ANTHROPIC_API_KEY를 설정하면 AI 분석이 활성화됩니다."]),
            media_type="text/event-stream",
        )
    return StreamingResponse(_stream_claude(api_key, settings.anthropic_model, _build_prompt(type_, context)), media_type="text/event-stream")
