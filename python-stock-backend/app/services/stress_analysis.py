"""Read-only market stress calculations. No simulated provider prices."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import math
import statistics
import threading
import time
import requests
from zoneinfo import ZoneInfo

_cache = None
_lock = threading.Lock()


def fetch_series(symbol):
    response = requests.get(f'https://query1.finance.yahoo.com/v8/finance/chart/{symbol}',
        params={'range': '1y', 'interval': '1d'}, headers={'User-Agent': 'Mozilla/5.0'}, timeout=12)
    response.raise_for_status()
    item = response.json()['chart']['result'][0]
    quote = item['indicators']['quote'][0]
    adjusted = item['indicators'].get('adjclose', [{}])[0].get('adjclose', quote['close'])
    rows = {}
    for i, ts in enumerate(item['timestamp']):
        value = adjusted[i]
        if value and math.isfinite(value) and value > 0:
            rows[datetime.fromtimestamp(ts, timezone.utc).strftime('%Y-%m-%d')] = value
    # Exclude today's incomplete daily bar from the fitted model.
    rows.pop(datetime.now(ZoneInfo('Asia/Seoul')).strftime('%Y-%m-%d'), None)
    meta = item['meta']
    price = float(meta['regularMarketPrice'])
    if not math.isfinite(price) or price <= 0:
        raise ValueError('Invalid quote')
    asof = datetime.fromtimestamp(meta['regularMarketTime'], timezone.utc)
    age = (datetime.now(timezone.utc) - asof).total_seconds()
    return {'price': price, 'as_of': asof.isoformat(), 'status': 'stale' if age > 96*3600 else 'delayed',
            'source': 'Yahoo Finance · 지연 가능 시세', 'rows': rows}


def estimate(stock, index):
    dates = sorted(set(stock) & set(index))
    pairs = [(stock[b]/stock[a]-1, index[b]/index[a]-1) for a,b in zip(dates, dates[1:])][-120:]
    if len(pairs) < 60:
        raise ValueError('공통 수익률 관측치가 60개 미만입니다.')
    ys, xs = zip(*pairs)
    variance = statistics.variance(xs)
    if variance <= 0:
        raise ValueError('지수 수익률 분산이 없습니다.')
    beta = statistics.covariance(xs, ys)/variance
    alpha = statistics.mean(ys)-beta*statistics.mean(xs)
    residual = statistics.stdev([y-alpha-beta*x for y,x in pairs])
    return {'beta': round(beta, 6), 'residual_daily': residual, 'observations':len(pairs),
            'start': dates[-len(pairs)-1], 'end':dates[-1],
            'annual_volatility': statistics.stdev(ys)*math.sqrt(252)}


def snapshot():
    global _cache
    with _lock:
        if _cache and time.monotonic()-_cache[0] < 60:
            return _cache[1]
        fetched = datetime.now(timezone.utc).isoformat()
        try:
            with ThreadPoolExecutor(max_workers=2) as pool:
                stock, index = list(pool.map(fetch_series, ['005930.KS', '^KS11']))
            model = estimate(stock['rows'], index['rows'])
            state = 'stale' if 'stale' in (stock['status'], index['status']) else 'delayed'
            result = {'status':state, 'fetched_at':fetched, 'stock':{k:v for k,v in stock.items() if k!='rows'},
                      'index':{k:v for k,v in index.items() if k!='rows'}, 'model': model,
                      'foreign_flow': {'status':'unavailable', 'message':'외국인 실측 수급 미연결. 순매도는 사용자 가정으로만 반영합니다.'}}
        except Exception:
            result = {'status':'unavailable', 'fetched_at':fetched,
                      'message':'시세 또는 과거 수익률을 확보하지 못했습니다. 자동 계산을 중단합니다. 가정 모드를 이용할 수 있습니다.'}
        _cache = (time.monotonic(), result)
        return result


def simulate(p):
    if p.mode == 'observed':
        data = snapshot()
        if data['status'] not in ('delayed',):
            raise ValueError('최신 시세·모델을 사용할 수 없습니다. 가정 모드로 전환하거나 다시 조회하세요.')
        price, index, beta = data['stock']['price'],data['index']['price'],data['model']['beta']
        residual = data['model']['residual_daily']
    else:
        data = None
        price,index,beta,residual = p.price,p.index,p.beta,p.residual_pct/100
    base = price*(1+beta*(p.target_index/index-1))
    if base <= 0:
        raise ValueError('기준지수 이동이 선형 모델 범위를 벗어났습니다.')
    # Foreign pressure is an explicit user assumption, not a fitted causal effect.
    pressure = p.foreign_sell/p.turnover*p.impact_pct/100
    width = 1.645*residual*math.sqrt(p.days)
    rows=[]
    for shock in [0,-5,-10,-15,-20,-25]:
        change=beta*shock/100-pressure
        value=max(0,base*(1+change))
        rows.append({'shock_pct':shock,'index':round(p.target_index*(1+shock/100),2),
                     'price':round(value),'change_pct':round(change*100,2),
                     'low':round(max(0,value-base*width)), 'high':round(value+base*width)})
    return {'mode':p.mode,'snapshot':data,'inputs':p.model_dump(),'base_price':round(base), 'beta':beta,
            'foreign_pressure_pct':round(pressure*100,3), 'rows':rows,
            'method':'기준가격 = 현재가 × [1 + β × (목표지수/현재지수 − 1)]. 시나리오 가격 = 기준가격 × [1 + β × 지수충격 − 수급충격]. 수급충격 = 순매도/일평균거래대금 × 가정 영향률.',
            'limitations':'범위는 잔차 표준편차 × √기간 × 1.645를 적용한 참고 범위입니다. 정규·독립·일정 변동성 가정이며 급락장 꼬리위험과 가격제한폭은 반영하지 않습니다. 외국인 매도와 지수 하락 영향이 중복될 수 있습니다. 지지선·적정가·예측 보장이 아닙니다.'}
