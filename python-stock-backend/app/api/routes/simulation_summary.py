from typing import Literal
from fastapi import APIRouter
from app.core.database import DbSession
from app.core.deps import MemberId
from app.core.errors import ApiError
from app.services.simulation_summary import summary
router=APIRouter(prefix='/api/trade/simulation-summary',tags=['simulation-summary'])

@router.get('/{ledger}')
def ledger_summary(ledger:Literal['cash','stocks','crypto','alternatives','practice'],member_id:MemberId,db:DbSession):
    try:return summary(db,member_id,ledger)
    except Exception as exc:raise ApiError(503,message='모의투자 원장 또는 평가 데이터를 조회하지 못했습니다.') from exc

@router.get('/external/{provider}')
def external_summary(provider:Literal['kis','alpaca'],member_id:MemberId):
    from datetime import datetime,timezone
    from app.services.authz import can_use_kis_account
    from app.services.brokers.common import BrokerApiError
    def number(v):return float(str(v).replace(',','')) if v not in (None,'') else None
    try:
        if provider=='kis':
            if not can_use_kis_account(member_id):raise ApiError(403,message='KIS 공용 모의계좌 조회 권한이 없습니다.')
            from app.services.brokers.kis import get_kis_balance
            b=get_kis_balance();rows=[x for x in b.get('holdings',[]) if (number(x.get('quantity')) or 0)>0]
            value=sum(number(x.get('evalAmount')) or 0 for x in rows);pnl=number(b.get('totalProfitLoss'))
            d={'currency':'KRW','cash':number(b.get('cashBalance')),'account_total':number(b.get('totalEvalAmount')),
               'value':value,'pnl':pnl,'positions':len(rows),'cost':value-pnl if pnl is not None else None,
               'source':'KIS Testbed 잔고 API · 브로커 계좌 전체'}
        else:
            from app.services.alpaca.paper import _get,ALPACA_PAPER_BASE
            a=_get(f'{ALPACA_PAPER_BASE}/account');rows=_get(f'{ALPACA_PAPER_BASE}/positions')
            value=sum(number(x.get('market_value')) or 0 for x in rows);pnl=sum(number(x.get('unrealized_pl')) or 0 for x in rows)
            d={'currency':a.get('currency') or 'USD','cash':number(a.get('cash')),'account_total':number(a.get('equity')),
               'value':value,'pnl':pnl,'positions':len(rows),'cost':value-pnl,'source':'Alpaca Paper 계좌·포지션 API · 브로커 계좌 전체'}
        d['pnl_pct']=round(d['pnl']/d['cost']*100,2) if d.get('pnl') is not None and d.get('cost') and d['cost']>0 else None
        return {**d,'status':'provider_snapshot','scope':'서버 연결 공용 모의계좌','as_of':datetime.now(timezone.utc).isoformat(),
            'history_scope':'브로커 누적 전체 체결 이력은 이 조회에 포함되지 않음','fills':None,'buy_amount':None,'sell_amount':None,
            'coverage_note':'공용계좌 잔고는 내 거래만의 성과가 아니며 계좌 외부 거래도 포함될 수 있습니다. 내부 가상 원장과 합산하지 않습니다.'}
    except ApiError:raise
    except BrokerApiError as exc:raise ApiError(exc.status_code,message=str(exc)) from exc
    except Exception as exc:raise ApiError(503,message='외부 모의계좌 조회 실패. 연결 또는 제공처 상태를 확인하세요.') from exc
