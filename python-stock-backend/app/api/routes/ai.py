"""Qwen ReAct market analysis; existing text streaming API remains compatible."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from queue import Empty, Queue
from threading import BoundedSemaphore

from fastapi import APIRouter, Body, HTTPException
from fastapi.responses import StreamingResponse

from ..schemas import AiAnalyzeBody
from app.services.react_agent import MODEL, run_react

router = APIRouter(prefix='/api/ai', tags=['ai'])
_slots = BoundedSemaphore(1)
_workers = ThreadPoolExecutor(max_workers=1, thread_name_prefix='react-agent')


def _reserve():
    if not _slots.acquire(blocking=False):
        raise HTTPException(status_code=429, detail='AI 분석이 진행 중입니다. 완료 후 다시 시도하세요.')


def _run(payload, emit=lambda _: None):
    try:
        return run_react(payload.question, str(payload.context or '')[:4000], str(payload.type or 'general'), emit)
    finally:
        _slots.release()


def _stream(payload):
    events = Queue()
    future = _workers.submit(_run, payload, events.put)
    yield f'Qwen({MODEL}) · ReAct 읽기 전용 분석\n\n'
    while not future.done() or not events.empty():
        try:
            yield events.get(timeout=10)
        except Empty:
            yield '\n'
    try:
        result = future.result()
        yield '\n### 분석 결과\n' + result['answer']
        if result['references']:
            yield '\n\n### 조회 출처\n'
            for ref in result['references']:
                yield f'- {ref["source"]} · {ref["as_of"] or ref["fetched_at"]} · {ref["status"]}\n'
        if result['status'] != 'complete':
            yield '\n일부 조회가 실패했거나 데이터가 오래되어 분석이 제한되었습니다.\n'
    except Exception:
        yield '\n분석에 실패했습니다. 잠시 후 다시 시도하세요.\n'


@router.post('/analyze')
def analyze(payload: AiAnalyzeBody = Body(default_factory=AiAnalyzeBody)):
    _reserve()
    return StreamingResponse(_stream(payload), media_type='text/plain; charset=utf-8',
                             headers={'X-LLM-Model': MODEL, 'X-AI-Agent': 'react-read-only', 'X-Accel-Buffering': 'no', 'Cache-Control': 'no-store'})


@router.post('/react')
def react(payload: AiAnalyzeBody = Body(default_factory=AiAnalyzeBody)):
    """Structured answer plus tool execution traces; no internal reasoning text."""
    _reserve()
    return _run(payload)
