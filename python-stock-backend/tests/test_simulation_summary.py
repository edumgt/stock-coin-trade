from datetime import datetime
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from app.models import Member,StockOrder,StockPosition
from app.services.simulation_summary import summary,value_summary

@pytest.fixture
def db():
    engine=create_engine('sqlite:///:memory:')
    for table in [Member.__table__,StockOrder.__table__,StockPosition.__table__]:table.create(engine)
    with Session(engine) as s:
        s.add_all([Member(member_id=1,asset=1000),Member(member_id=2,asset=999999)])
        for index,(member,symbol,side,amount) in enumerate([(1,'005930','BUY',100),(1,'005930','SELL',120),(1,'000660','BUY',200),(2,'005930','BUY',999999)],1):
            s.add(StockOrder(stock_order_id=index,member_id=member,symbol=symbol,order_type=side,quantity=1,price=amount,amount=amount,source='WEB',created_at=datetime(2025,1,1)))
        s.add(StockPosition(stock_position_id=1,member_id=1,symbol='000660',quantity=1,avg_price=200));s.commit();yield s

def test_all_history_and_member_isolation_includes_closed_asset(db,monkeypatch):
    monkeypatch.setattr('app.services.stock_market.get_quote_cached',lambda _: {'price':250})
    d=summary(db,1,'stocks')
    assert d['fills']==3 and d['traded_assets']==2
    assert d['buy_amount']==300 and d['sell_amount']==120
    assert d['positions']==1 and d['value']==250 and d['pnl']==50
    assert d['cash'] is None

def test_shared_cash_is_not_repeated_on_investment_card(db,monkeypatch):
    monkeypatch.setattr('app.services.stock_market.get_quote_cached',lambda _: {'price':250})
    assert summary(db,1,'cash')['cash']==1000
    assert summary(db,1,'stocks')['account_total'] is None

def test_missing_quote_is_not_silent_zero(db,monkeypatch):
    def fail(_):raise RuntimeError('unavailable')
    monkeypatch.setattr('app.services.stock_market.get_quote_cached',fail)
    d=summary(db,1,'stocks')
    assert d['status']=='partial' and d['value'] is None and d['pnl'] is None

def test_simulated_quote_is_labeled(db,monkeypatch):
    monkeypatch.setattr('app.services.stock_market.get_quote_cached',lambda _: {'price':250,'simulated':True})
    assert summary(db,1,'stocks')['status']=='estimated'

def test_zero_positions_keeps_zero_and_no_return_division():
    d=value_summary([])
    assert d['value']==0 and d['pnl']==0 and d['pnl_pct'] is None

def test_unauthenticated_summary_is_blocked(client):
    assert client.get('/api/trade/simulation-summary/stocks').status_code==401
    assert client.get('/api/trade/simulation-summary/external/alpaca').status_code==401
