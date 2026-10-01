"""PostgreSQL 기반 퀀트 데이터 브라우저와 전략 백테스트·팩터 분석."""

from __future__ import annotations

import json
import math
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import create_engine, text

from app.core.config import get_settings

_engine = None

STRATEGY_NAMES = {
    "ma2050": "이동평균 교차 MA 20/50",
    "trend": "단기 추세추종 MA 5/20",
    "pullback": "상승추세 눌림목 MA 20/60",
    "rsi": "RSI 과매도 반등",
    "breakout": "거래량 20일 돌파",
    "momentum": "60일 모멘텀",
}
FACTOR_LABELS = {"market_excess": "시장 베타", "smb": "규모(SMB)", "hml": "가치(HML)",
                 "rmw": "수익성(RMW)", "cma": "투자(CMA)", "mom": "모멘텀(MOM)"}


def engine():
    global _engine
    if _engine is None:
        _engine = create_engine(get_settings().quant_database_url, pool_pre_ping=True, pool_size=3, max_overflow=2)
    return _engine


def _number(value):
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def _rows(result):
    return [{key: _number(value) for key, value in row.items()} for row in result.mappings()]


def validate_symbol(symbol: str) -> str:
    symbol = (symbol or "").upper().strip()
    if not symbol or len(symbol) > 20 or not all(char.isalnum() or char in "-_" for char in symbol):
        raise ValueError("유효한 symbol을 입력하세요.")
    return symbol


def _solve(matrix, vector):
    """아래 정규방정식 소규모 선형계를 위한 가우스 소거법."""
    size = len(vector)
    augmented = [list(matrix[index]) + [vector[index]] for index in range(size)]
    for column in range(size):
        pivot = max(range(column, size), key=lambda row: abs(augmented[row][column]))
        if abs(augmented[pivot][column]) < 1e-12:
            raise ValueError("팩터 데이터가 서로 너무 유사해 회귀분석을 할 수 없습니다.")
        augmented[column], augmented[pivot] = augmented[pivot], augmented[column]
        scale = augmented[column][column]
        augmented[column] = [value / scale for value in augmented[column]]
        for row in range(size):
            if row == column:
                continue
            ratio = augmented[row][column]
            augmented[row] = [value - ratio * base for value, base in zip(augmented[row], augmented[column], strict=True)]
    return [augmented[row][-1] for row in range(size)]


def _regression(rows, factors):
    # OLS: 자산 초과수익 = alpha + 팩터 로딩 × 팩터 수익률.
    x = [[1.0] + [float(row[name]) for name in factors] for row in rows]
    y = [float(row["asset_return"]) - float(row["risk_free"]) for row in rows]
    columns = len(x[0])
    xtx = [[sum(row[i] * row[j] for row in x) for j in range(columns)] for i in range(columns)]
    xty = [sum(row[i] * y[index] for index, row in enumerate(x)) for i in range(columns)]
    coefficients = _solve(xtx, xty)
    predicted = [sum(row[index] * coefficients[index] for index in range(columns)) for row in x]
    mean_y = sum(y) / len(y)
    total = sum((value - mean_y) ** 2 for value in y)
    residual = sum((value - predicted[index]) ** 2 for index, value in enumerate(y))
    return {"alpha_daily": coefficients[0], "loadings": dict(zip(factors, coefficients[1:], strict=True)),
            "r_squared": 1 - residual / total if total else 0.0, "observations": len(rows)}


def _ensure_factor_schema(conn):
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS factor_returns (
          factor_date date PRIMARY KEY, risk_free numeric(12,8) NOT NULL, market_excess numeric(12,8) NOT NULL,
          smb numeric(12,8) NOT NULL, hml numeric(12,8) NOT NULL, rmw numeric(12,8) NOT NULL,
          cma numeric(12,8) NOT NULL, mom numeric(12,8) NOT NULL, source varchar(100) NOT NULL DEFAULT 'learning_sample'
        )
    """))
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS factor_exposures (
          symbol varchar(20) NOT NULL, model varchar(20) NOT NULL, factor_name varchar(30) NOT NULL,
          start_date date NOT NULL, end_date date NOT NULL, loading numeric(18,8) NOT NULL,
          alpha_annual numeric(18,8), r_squared numeric(18,8), observations integer NOT NULL,
          calculated_at timestamptz NOT NULL DEFAULT now(),
          PRIMARY KEY(symbol,model,factor_name,start_date,end_date)
        )
    """))
    conn.execute(text("""
        INSERT INTO factor_returns(factor_date,risk_free,market_excess,smb,hml,rmw,cma,mom)
        SELECT factor_day, 0.00008, round((0.00035 + sin(n / 13.0) * 0.006)::numeric,8),
          round((cos(n / 9.0) * 0.0025)::numeric,8), round((sin(n / 17.0) * 0.0022)::numeric,8),
          round((cos(n / 21.0) * 0.0018)::numeric,8), round((sin(n / 25.0) * 0.0015)::numeric,8),
          round((sin(n / 11.0) * 0.0030)::numeric,8)
        FROM (SELECT DISTINCT trade_time::date AS factor_day, row_number() OVER (ORDER BY trade_time::date)-1 AS n FROM market_data) d
        ON CONFLICT(factor_date) DO NOTHING
    """))


def _average(values):
    return sum(values) / len(values) if values else None


def strategy_signals(prices, strategy):
    """미래 캔들 데이터를 쓰지 않는 롱 온리 시그널을 만든다."""
    closes = [float(row["adjusted_close"]) for row in prices]
    volumes = [float(row["volume"]) for row in prices]
    ma5 = [_average(closes[max(0, index - 4):index + 1]) for index in range(len(closes))]
    ma10 = [_average(closes[max(0, index - 9):index + 1]) for index in range(len(closes))]
    ma20 = [_average(closes[max(0, index - 19):index + 1]) for index in range(len(closes))]
    ma50 = [_average(closes[max(0, index - 49):index + 1]) for index in range(len(closes))]
    ma60 = [_average(closes[max(0, index - 59):index + 1]) for index in range(len(closes))]
    gains, losses, rsi = [], [], []
    for index, close in enumerate(closes):
        change = close - closes[index - 1] if index else 0
        gains.append(max(change, 0))
        losses.append(max(-change, 0))
        avg_gain = _average(gains[max(0, index - 13):index + 1])
        avg_loss = _average(losses[max(0, index - 13):index + 1])
        rsi.append(100 if not avg_loss else 100 - 100 / (1 + avg_gain / avg_loss))
    in_position = False
    signals = []
    for index, row in enumerate(prices):
        buy = sell = False
        if strategy == "ma2050":
            buy = index > 0 and ma20[index] > ma50[index] and ma20[index - 1] <= ma50[index - 1]
            sell = index > 0 and ma20[index] < ma50[index] and ma20[index - 1] >= ma50[index - 1]
        elif strategy == "trend":
            buy = index > 0 and ma5[index] > ma20[index] and ma5[index - 1] <= ma20[index - 1]
            sell = index > 0 and ma5[index] < ma20[index] and ma5[index - 1] >= ma20[index - 1]
        elif strategy == "pullback":
            buy = index > 60 and ma20[index] > ma60[index] and closes[index] > ma20[index] and closes[index - 1] <= ma20[index - 1]
            sell = index > 60 and ma20[index] < ma60[index]
        elif strategy == "rsi":
            buy = index > 14 and rsi[index] > 30 and rsi[index - 1] <= 30
            sell = index > 14 and rsi[index] < 70 and rsi[index - 1] >= 70
        elif strategy == "breakout":
            prior_high = max(closes[max(0, index - 20):index]) if index >= 20 else None
            prior_volume = _average(volumes[max(0, index - 20):index]) if index >= 20 else None
            buy = index >= 20 and closes[index] > prior_high and volumes[index] > prior_volume
            sell = index >= 20 and closes[index] < ma10[index]
        elif strategy == "momentum":
            buy = index >= 60 and closes[index] / closes[index - 60] - 1 > 0 and closes[index] > ma60[index]
            sell = index >= 60 and (closes[index] / closes[index - 60] - 1 <= 0 or closes[index] < ma60[index])
        if buy and not in_position:
            signals.append({**row, "signal": "BUY"})
            in_position = True
        elif sell and in_position:
            signals.append({**row, "signal": "SELL"})
            in_position = False
    # 마지막 가격으로 열린 포지션을 닫아 실행마다 비교 가능하게 한다.
    if in_position and prices:
        signals.append({**prices[-1], "signal": "SELL"})
    return signals


def overview() -> dict:
    with engine().connect() as conn:
        result = conn.execute(text("""
            SELECT (SELECT count(*) FROM market_data) AS market_rows,
                   (SELECT count(*) FROM strategies) AS strategy_count,
                   (SELECT count(*) FROM trade_logs) AS trade_count,
                   (SELECT array_agg(symbol ORDER BY symbol) FROM (SELECT DISTINCT symbol FROM market_data) s) AS symbols
        """))
        return _rows(result)[0]


def market_data(symbol: str, limit: int) -> list[dict]:
    with engine().connect() as conn:
        return _rows(conn.execute(text("""
            SELECT symbol, trade_time, open, high, low, close, volume, adjusted_close
            FROM market_data WHERE symbol = :symbol
            ORDER BY trade_time DESC LIMIT :limit
        """), {"symbol": symbol, "limit": limit}))


def signals(symbol: str, limit: int, fast: int, slow: int) -> list[dict]:
    sql = text("""
        WITH ma AS (
            SELECT symbol, trade_time, adjusted_close,
                   avg(adjusted_close) OVER (PARTITION BY symbol ORDER BY trade_time ROWS BETWEEN :fast PRECEDING AND CURRENT ROW) AS fast_ma,
                   avg(adjusted_close) OVER (PARTITION BY symbol ORDER BY trade_time ROWS BETWEEN :slow PRECEDING AND CURRENT ROW) AS slow_ma
            FROM market_data WHERE symbol = :symbol
        ), crossed AS (
            SELECT *, lag(fast_ma > slow_ma) OVER (ORDER BY trade_time) AS prior_above FROM ma
        )
        SELECT symbol, trade_time, adjusted_close, fast_ma, slow_ma,
               CASE WHEN fast_ma > slow_ma AND coalesce(prior_above, false) = false THEN 'BUY'
                    WHEN fast_ma < slow_ma AND coalesce(prior_above, true) = true THEN 'SELL'
                    ELSE 'HOLD' END AS signal
        FROM crossed ORDER BY trade_time DESC LIMIT :limit
    """)
    with engine().connect() as conn:
        rows = _rows(conn.execute(sql, {"symbol": symbol, "fast": fast - 1, "slow": slow - 1, "limit": limit}))
    return list(reversed(rows))


def run_backtest(data: dict, *, symbol: str, fast: int, slow: int, quantity: int, fee_rate: float,
                 slippage: float, strategy: str) -> dict:
    with engine().begin() as conn:
        strategy_id = conn.execute(text("""
            INSERT INTO strategies(name, parameters) VALUES (:name, CAST(:params AS jsonb)) RETURNING strategy_id
        """), {"name": f"{STRATEGY_NAMES[strategy]} {symbol}", "params": json.dumps(data)}).scalar_one()
        price_rows = _rows(conn.execute(text("""
            SELECT trade_time, adjusted_close, volume FROM market_data WHERE symbol=:symbol ORDER BY trade_time
        """), {"symbol": symbol}))
        signal_rows = strategy_signals(price_rows, strategy)
        entry = None
        trades = []
        for row in signal_rows:
            if row["signal"] == "BUY" and entry is None:
                entry = row
                trades.append((row, "BUY", 0.0))
            elif row["signal"] == "SELL" and entry is not None:
                buy_cost = entry["adjusted_close"] * quantity * (1 + fee_rate + slippage)
                sell_value = row["adjusted_close"] * quantity * (1 - fee_rate - slippage)
                trades.append((row, "SELL", sell_value - buy_cost))
                entry = None
        for row, side, pnl in trades:
            price = row["adjusted_close"] * (1 + slippage if side == "BUY" else 1 - slippage)
            conn.execute(text("""
                INSERT INTO trade_logs(strategy_id,symbol,trade_time,side,price,quantity,fee,slippage,pnl)
                VALUES(:id,:symbol,:time,:side,:price,:quantity,:fee,:slippage,:pnl)
            """), {"id": strategy_id, "symbol": symbol, "time": row["trade_time"], "side": side, "price": price,
                   "quantity": quantity, "fee": row["adjusted_close"] * quantity * fee_rate,
                   "slippage": row["adjusted_close"] * quantity * slippage, "pnl": pnl})
        realized = [pnl for _, side, pnl in trades if side == "SELL"]
        total_pnl = sum(realized)
        first = signal_rows[0]["trade_time"] if signal_rows else datetime.now(UTC)
        last = signal_rows[-1]["trade_time"] if signal_rows else first
        capital = (signal_rows[0]["adjusted_close"] if signal_rows else 1) * quantity
        total_return = (total_pnl / capital * 100) if capital else 0
        equity = capital
        peak = capital
        max_drawdown = 0.0
        periodic_returns = []
        for pnl in realized:
            prior_equity = equity
            equity += pnl
            if prior_equity:
                periodic_returns.append(pnl / prior_equity)
            peak = max(peak, equity)
            if peak:
                max_drawdown = min(max_drawdown, (equity / peak - 1) * 100)
        if len(periodic_returns) > 1:
            mean_return = sum(periodic_returns) / len(periodic_returns)
            deviation = math.sqrt(sum((value - mean_return) ** 2 for value in periodic_returns) / (len(periodic_returns) - 1))
            sharpe = mean_return / deviation * math.sqrt(252) if deviation else None
        else:
            sharpe = None
        first_dt = datetime.fromisoformat(str(first))
        last_dt = datetime.fromisoformat(str(last))
        days = max((last_dt - first_dt).days, 1)
        annual_return = ((equity / capital) ** (365 / days) - 1) * 100 if capital > 0 and equity > 0 else total_return
        conn.execute(text("""
            INSERT INTO performance_metrics(strategy_id,start_date,end_date,sharpe_ratio,max_drawdown,annual_return,total_return,trade_count)
            VALUES(:id,:start,:end,:sharpe,:mdd,:annual,:total,:count)
        """), {"id": strategy_id, "start": first, "end": last, "sharpe": sharpe, "mdd": max_drawdown,
               "annual": annual_return, "total": total_return, "count": len(trades)})
    return {"strategyId": strategy_id, "tradeCount": len(trades), "realizedPnl": round(total_pnl, 2),
            "totalReturn": round(total_return, 4), "sharpeRatio": round(sharpe, 4) if sharpe is not None else None,
            "maxDrawdown": round(max_drawdown, 4), "annualReturn": round(annual_return, 4),
            "message": "백테스트 결과와 거래 로그를 PostgreSQL에 저장했습니다."}


def results() -> dict:
    with engine().connect() as conn:
        strategies = _rows(conn.execute(text("""
            SELECT s.strategy_id, s.name, s.parameters, s.created_at, p.total_return, p.annual_return, p.trade_count
            FROM strategies s LEFT JOIN performance_metrics p ON p.strategy_id=s.strategy_id
            ORDER BY s.strategy_id DESC LIMIT 20
        """)))
        trades = _rows(conn.execute(text("""
            SELECT trade_id,strategy_id,symbol,trade_time,side,price,quantity,fee,slippage,pnl
            FROM trade_logs ORDER BY trade_id DESC LIMIT 50
        """)))
    return {"strategies": strategies, "trades": trades}


def factor_analysis(symbol: str) -> dict | None:
    """일간 수익률로 CAPM 알파/베타와 Fama-French 스타일 노출을 계산한다. 관측치 부족 시 None."""
    with engine().begin() as conn:
        _ensure_factor_schema(conn)
        rows = _rows(conn.execute(text("""
            WITH prices AS (
              SELECT trade_time::date factor_date, adjusted_close,
                     lag(adjusted_close) OVER (ORDER BY trade_time) prior_close
              FROM market_data WHERE symbol=:symbol
            )
            SELECT p.factor_date, (p.adjusted_close / p.prior_close - 1) AS asset_return,
                   f.risk_free, f.market_excess, f.smb, f.hml, f.rmw, f.cma, f.mom
            FROM prices p JOIN factor_returns f ON f.factor_date=p.factor_date
            WHERE p.prior_close IS NOT NULL ORDER BY p.factor_date
        """), {"symbol": symbol}))
        if len(rows) < 60:
            return None
        capm = _regression(rows, ["market_excess"])
        multi_factors = ["market_excess", "smb", "hml", "rmw", "cma", "mom"]
        multi = _regression(rows, multi_factors)
        start, end = rows[0]["factor_date"], rows[-1]["factor_date"]
        alpha_annual = capm["alpha_daily"] * 252 * 100
        for name, loading in multi["loadings"].items():
            conn.execute(text("""
                INSERT INTO factor_exposures(symbol,model,factor_name,start_date,end_date,loading,alpha_annual,r_squared,observations)
                VALUES(:symbol,'FF6',:name,:start,:end,:loading,:alpha,:r2,:count)
                ON CONFLICT(symbol,model,factor_name,start_date,end_date) DO UPDATE SET
                  loading=EXCLUDED.loading, alpha_annual=EXCLUDED.alpha_annual, r_squared=EXCLUDED.r_squared,
                  observations=EXCLUDED.observations, calculated_at=now()
            """), {"symbol": symbol, "name": name, "start": start, "end": end, "loading": loading,
                   "alpha": alpha_annual, "r2": multi["r_squared"], "count": multi["observations"]})
    return {"symbol": symbol, "period": {"start": start, "end": end},
            "capm": {"alphaAnnual": round(alpha_annual, 4), "beta": round(capm["loadings"]["market_excess"], 4),
                     "rSquared": round(capm["r_squared"], 4), "observations": capm["observations"]},
            "multiFactor": {"rSquared": round(multi["r_squared"], 4), "observations": multi["observations"],
                            "exposures": [{"name": name, "label": FACTOR_LABELS[name], "loading": round(value, 4)}
                                          for name, value in multi["loadings"].items()]},
            "source": "learning_sample",
            "notice": "팩터 수익률은 교육용 샘플입니다. 실제 운용에는 검증된 시장·팩터 데이터로 교체해야 합니다."}
