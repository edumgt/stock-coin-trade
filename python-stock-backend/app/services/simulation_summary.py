"""Member-scoped lifetime fills plus current valuations; no orders or account creation."""
from datetime import datetime, timezone
from sqlalchemy import select,func,case
from app.models import (Member,StockOrder,StockPosition,CryptoOrder,HoldCrypto,UpbitMarket,
    AlternativeOrder,KisPracticeOrder,KisPracticePosition,KisPracticeAccount)


def history_totals(db,model,member_id,symbol_col):
    total,assets,buy,sell,last=db.execute(select(func.count(),func.count(func.distinct(symbol_col)),
        func.coalesce(func.sum(case((model.order_type=='BUY',model.amount),else_=0)),0),
        func.coalesce(func.sum(case((model.order_type=='SELL',model.amount),else_=0)),0),func.max(model.created_at))
        .where(model.member_id==member_id)).one()
    return {'fills':int(total),'traded_assets':int(assets),'buy_amount':float(buy),'sell_amount':float(sell),
            'last_trade':last.isoformat() if last else None,'history_scope':'저장된 전체 체결 원장 · 기간/최근 N건 제한 없음'}


def value_summary(positions):
    cost=sum(x['cost'] for x in positions);missing=sum(x['value'] is None for x in positions)
    value=sum(x['value'] for x in positions if x['value'] is not None) if not missing else None
    return {'positions':len(positions),'cost':round(cost,2),'value':round(value,2) if value is not None else None,
            'pnl':round(value-cost,2) if value is not None else None,
            'pnl_pct':round((value-cost)/cost*100,2) if value is not None and cost>0 else None,
            'missing_quotes':missing,'assets':positions}


def summary(db,member_id,ledger):
    from app.services.stock_market import get_quote_cached
    result={'ledger':ledger,'currency':'KRW','as_of':datetime.now(timezone.utc).isoformat(),
        'scope':'로그인 회원','cash':None,'status':'complete','source':'시스템 가상 체결 원장 + 조회 시점 평가'}
    if ledger=='cash':
        result.update(cash=float(db.get(Member,member_id).asset),source='주식·코인·대체자산 공용 현금 · 한 번만 합산')
        return result
    positions=[];estimated=False
    if ledger in ('stocks','practice'):
        model,order=(StockPosition,StockOrder) if ledger=='stocks' else (KisPracticePosition,KisPracticeOrder)
        result.update(history_totals(db,order,member_id,order.symbol))
        rows=db.scalars(select(model).where(model.member_id==member_id,model.quantity>0)).all()
        for row in rows:
            value=None
            try:
                q=get_quote_cached(row.symbol);price=float(q['price']);estimated=estimated or bool(q.get('simulated'))
                if price>0:value=price*row.quantity
            except Exception:pass
            positions.append({'symbol':row.symbol,'cost':row.avg_price*row.quantity,'value':value})
        if ledger=='practice':
            account=db.scalars(select(KisPracticeAccount).where(KisPracticeAccount.member_id==member_id)).first()
            result['cash']=float(account.cash) if account else None
            result['account_opened']=account is not None
    elif ledger=='crypto':
        import requests
        result.update(history_totals(db,CryptoOrder,member_id,CryptoOrder.market_code))
        rows=db.execute(select(HoldCrypto,UpbitMarket).join(UpbitMarket,HoldCrypto.upbit_market_id==UpbitMarket.upbit_market_id).where(HoldCrypto.member_id==member_id,HoldCrypto.buy_crypto_count>0)).all()
        prices={}
        try:
            # Upbit ticker supports at most 100 markets per request.
            for i in range(0,len(rows),100):
                codes=','.join(m.market_code for h,m in rows[i:i+100]);r=requests.get('https://api.upbit.com/v1/ticker',params={'markets':codes},timeout=5);r.raise_for_status()
                prices.update({x['market']:float(x['trade_price']) for x in r.json()})
        except Exception:pass
        for h,m in rows:
            price=prices.get(m.market_code)
            positions.append({'symbol':m.market_code,'cost':h.buy_total_krw,'value':h.buy_crypto_count*price if price else None})
        result['source']='시스템 코인 체결 원장 + Upbit 조회 시세'
    elif ledger=='alternatives':
        from app.services.alternatives import get_positions
        result.update(history_totals(db,AlternativeOrder,member_id,AlternativeOrder.symbol))
        for x in get_positions(db,member_id):
            if x['quantity']>0:positions.append({'symbol':x['symbol'],'cost':x['evalAmount']-x['pnl'],'value':x['evalAmount']})
        estimated=True;result['source']='시스템 대체자산 교육용 평가 · 파생상품은 증거금 기준'
    result.update(value_summary(positions))
    if result['missing_quotes']:result['status']='partial'
    elif estimated:result['status']='estimated'
    result['account_total']=result['cash']+result['value'] if result['cash'] is not None and result['value'] is not None else None
    result['coverage_note']='전량 매도한 종목도 누적 거래에 포함. 초기 시드·원장 도입 전 거래·삭제/초기화 이력은 복원 불가. 누적 거래금액과 현재 보유 원가는 다릅니다.'
    return result
