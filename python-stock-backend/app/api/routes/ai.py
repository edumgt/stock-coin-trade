"""시세·RAG 근거를 공통 Docker Qwen 7B로 분석한다."""

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


def _stream_qwen(prompt: str) -> Iterator[str]:
    from concurrent.futures import ThreadPoolExecutor, TimeoutError
    from app.services.qwen_remote import completion
    yield 'Qwen 7B가 검색 근거를 분석하고 있습니다…\n\n'
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(completion, {'messages':[
            {'role':'system','content':SYSTEM_PROMPT + ' 제공된 근거에 없는 사실을 만들지 말고, 출처 제목을 언급하세요. 300자 이내로 답하세요.'},
            {'role':'user','content':prompt[:12000]}], 'max_tokens':200})
        while True:
            try:
                result = future.result(timeout=15)
                yield result['choices'][0]['message']['content']
                break
            except TimeoutError:
                yield '\n'
            except Exception:
                yield 'Qwen 분석 연결에 실패했습니다. 잠시 후 다시 시도해 주세요.'
                break


@router.post('/analyze')
def analyze(payload: AiAnalyzeBody = Body(default_factory=AiAnalyzeBody)) -> StreamingResponse:
    context = str(payload.context or '시세 데이터 없음')
    type_ = str(payload.type or 'general')
    return StreamingResponse(_stream_qwen(_build_prompt(type_,context)), media_type='text/plain; charset=utf-8', headers={'X-LLM-Model':'qwen2.5:7b','X-Accel-Buffering':'no'})
