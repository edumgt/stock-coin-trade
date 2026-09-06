"""보유자산 화면에 쓰는 공통 변동성(연환산 표준편차) 계산 유틸리티.

일별 종가로부터 일간 수익률의 표준편차를 구하고, 거래일수의 제곱근을 곱해
연환산한다. 주식·대체자산은 연 252거래일, 코인은 연중무휴이므로 365일을
기준으로 호출하는 쪽에서 trading_periods를 다르게 넘긴다.
"""
import statistics


def annualized_volatility(closes: list[float], trading_periods: int = 252) -> float | None:
    """일별 종가 리스트에서 연환산 변동성(%)을 계산한다. 데이터가 부족하면 None."""
    prices = [price for price in closes if price and price > 0]
    if len(prices) < 3:
        return None
    returns = [(prices[i] - prices[i - 1]) / prices[i - 1] for i in range(1, len(prices))]
    if len(returns) < 2:
        return None
    daily_std = statistics.pstdev(returns)
    return round(daily_std * (trading_periods ** 0.5) * 100, 2)
