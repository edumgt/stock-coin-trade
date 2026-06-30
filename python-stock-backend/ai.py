import json
import os

import requests
from flask import Blueprint, Response, request, stream_with_context

ai_bp = Blueprint("ai", __name__, url_prefix="/api/ai")

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


@ai_bp.post("/analyze")
def analyze():
    body = request.get_json(silent=True) or {}
    context = body.get("context") or "시세 데이터 없음"
    type_ = body.get("type") or "general"
    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()

    if not api_key:
        def fallback():
            yield ("⚠️ ANTHROPIC_API_KEY가 설정되지 않았습니다.\n\n"
                   "환경변수 ANTHROPIC_API_KEY를 설정하면 AI 분석이 활성화됩니다.")
        return Response(fallback(), mimetype="text/event-stream")

    payload = {
        "model": "claude-haiku-4-5-20251001",
        "max_tokens": 1024,
        "stream": True,
        "system": SYSTEM_PROMPT,
        "messages": [{"role": "user", "content": _build_prompt(type_, context)}],
    }

    def generate():
        try:
            with requests.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "Content-Type": "application/json",
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                },
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
        except Exception as e:
            yield f"\n\n⚠️ AI 분석 중 오류가 발생했습니다: {e}"

    return Response(stream_with_context(generate()), mimetype="text/event-stream")
