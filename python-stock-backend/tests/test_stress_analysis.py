import math
import pytest
from app.api.routes.stress import StressRequest
from app.services.stress_analysis import estimate, simulate

def test_known_beta_and_aligned_dates():
    stock,index={'000':100.0},{'000':100.0}
    for i in range(1,90):
        change=.01 if i%2 else -.008
        index[f'{i:03}']=index[f'{i-1:03}']*(1+change)
        stock[f'{i:03}']=stock[f'{i-1:03}']*(1+1.5*change)
    result=estimate(stock,index)
    assert result['beta']==pytest.approx(1.5)
    assert result['observations']==89

def test_scenarios_use_target_base_and_explicit_flow():
    result=simulate(StressRequest(mode='assumed',price=210000,index=5500,target_index=5500,beta=1.2,foreign_sell=5000,turnover=10000,impact_pct=2))
    assert result['foreign_pressure_pct']==1
    assert result['rows'][0]['price']==207900
    assert result['rows'][2]['price']==182700
    assert result['rows'][2]['index']==4950
    assert result['rows'][2]['low']<result['rows'][2]['price']<result['rows'][2]['high']

def test_observed_failure_stops_calculation(monkeypatch):
    monkeypatch.setattr('app.services.stress_analysis.snapshot',lambda:{'status':'stale'})
    with pytest.raises(ValueError): simulate(StressRequest())

def test_invalid_inputs_rejected():
    for values in [{'turnover':0},{'beta':math.nan},{'days':61},{'foreign_sell':-1}]:
        with pytest.raises(ValueError): StressRequest(**values)
