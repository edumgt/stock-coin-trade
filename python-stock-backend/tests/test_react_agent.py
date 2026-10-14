import json
from types import SimpleNamespace

from app.services import react_agent as agent


def response(content='', calls=None):
    return {'choices':[{'message':{'role':'assistant','content':content,'tool_calls':calls or []}}]}


def call(name,args, id='read1'):
    return {'id':id,'type':'function','function':{'name':name,'arguments':json.dumps(args)}}


def test_observation_returns_to_model_and_sources_are_reported(monkeypatch):
    requests=[]
    def llm(payload, **kwargs):
        requests.append(json.loads(json.dumps(payload)))
        if len(requests)==1: return response(calls=[call('stock_history',{'symbol':'005930'})])
        assert requests[-1]['messages'][-1]['role']=='tool'
        assert '2026-10-13' in requests[-1]['messages'][-1]['content']
        return response('저장 일봉 기준 분석입니다.')
    monkeypatch.setattr(agent,'completion',llm)
    monkeypatch.setattr(agent,'execute_tool',lambda *_:{'source':'pg-stock','status':'recent_daily','as_of':'2026-10-13','fetched_at':'2026-10-14'})
    result=agent.run_react('삼성전자 일봉을 분석해 주세요')
    assert result['iterations']==2 and len(result['tool_calls'])==1
    assert result['references'][0]['as_of']=='2026-10-13'
    assert result['status']=='complete'


def test_order_tool_is_rejected_without_execution(monkeypatch):
    responses=iter([response(calls=[call('place_order',{'symbol':'005930','quantity':1})]),response('주문 도구는 제공하지 않습니다.')])
    monkeypatch.setattr(agent,'completion',lambda *_args,**_kwargs:next(responses))
    def forbidden(*_): raise AssertionError('Executor must not be reached')
    monkeypatch.setattr(agent,'execute_tool',forbidden)
    result=agent.run_react('주문해 주세요')
    assert result['tool_calls'][0]['tool']=='rejected_tool'
    assert result['status']=='partial'


def test_repeated_calls_use_observation_cache_and_loop_is_bounded(monkeypatch):
    executed=[];requests=[]
    def llm(payload,**_):
        requests.append(payload)
        return response(calls=[call('search_documents',{'query':'변동성'})])
    monkeypatch.setattr(agent,'completion',llm)
    monkeypatch.setattr(agent,'execute_tool',lambda *args:executed.append(args) or {'source':'Qdrant','status':'reference'})
    result=agent.run_react('변동성')
    assert len(executed)==1
    assert len(requests)==agent.MAX_ROUNDS+1
    assert 'tools' not in requests[-1]
    assert result['stop_reason']=='tool_limit'


def test_expired_deadline_does_not_call_model(monkeypatch):
    monkeypatch.setattr(agent,'MAX_SECONDS',0)
    monkeypatch.setattr(agent,'completion',lambda *_args,**_kwargs: (_ for _ in ()).throw(AssertionError()))
    assert agent.run_react('질문')['stop_reason']=='time_limit'


def test_stale_history_is_labelled_and_invalid_code_rejected(monkeypatch):
    from app.services import ohlcv_store
    monkeypatch.setattr(ohlcv_store,'public_history',lambda **_:{'ticker':{'name':'삼성전자'},'rows':[{'trade_date':'2020-01-01','close':100,'volume':1}]})
    assert agent.execute_tool('stock_history',{'symbol':'005930'})['status']=='stale'
    import pytest
    with pytest.raises(ValueError): agent.execute_tool('stock_history',{'symbol':'005930;DROP TABLE'})


def test_transport_applies_per_call_timeout(monkeypatch):
    from app.services import qwen_remote
    seen={}
    monkeypatch.setenv('LEAN_SSH_KEY_PATH','/test/key')
    def run(args,**kwargs):
        seen.update(kwargs)
        return SimpleNamespace(returncode=0,stdout=json.dumps({'message':{'content':'답변'}}))
    monkeypatch.setattr(qwen_remote.subprocess,'run',run)
    qwen_remote.completion({'messages':[{'role':'user','content':'질문'}],'num_ctx':4096},timeout_seconds=20)
    assert seen['timeout']==20
    assert json.loads(seen['input'])['options']['num_ctx']==4096


def test_stream_and_structured_routes_preserve_contract(client,monkeypatch):
    from app.api.routes import ai
    monkeypatch.setattr(ai,'run_react',lambda *args,**kwargs:{'answer':'검증 답변','tool_calls':[], 'references':[], 'status':'complete','iterations':1})
    response=client.post('/api/ai/analyze',json={'context':'시세 데이터','type':'stock'})
    assert response.status_code==200 and '검증 답변' in response.text
    assert response.headers['x-ai-agent']=='react-read-only'
    result=client.post('/api/ai/react',json={'question':'테스트 질문'})
    assert result.status_code==200 and result.json()['answer']=='검증 답변'


def test_concurrent_analysis_is_rejected(client):
    from app.api.routes import ai
    assert ai._slots.acquire(blocking=False)
    try: assert client.post('/api/ai/react',json={}).status_code==429
    finally: ai._slots.release()
