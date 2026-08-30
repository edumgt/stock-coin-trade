from QuantConnect import Globals, Resolution, SubscriptionTransportMedium
from QuantConnect.Algorithm import QCAlgorithm
from QuantConnect.Data import SubscriptionDataSource
from QuantConnect.Python import PythonData
import os
from datetime import datetime, timedelta


class SheetSeries(PythonData):
    """AI Sheet가 내보낸 월별 종가 CSV(Date,Open,High,Low,Close,Volume)를 읽는다."""

    def get_source(self, config, date, is_live):
        source = os.path.join(Globals.data_folder, "prices.csv")
        return SubscriptionDataSource(source, SubscriptionTransportMedium.LOCAL_FILE)

    def reader(self, config, line, date, is_live):
        if not line.strip() or line.startswith("Date"):
            return None
        fields = line.split(",")
        if len(fields) < 6:
            return None
        data = SheetSeries()
        data.symbol = config.symbol
        data.time = datetime.strptime(fields[0], "%Y-%m-%d")
        data.end_time = data.time + timedelta(days=1)
        data.value = float(fields[4])
        return data


class GenericBuyAndHold(QCAlgorithm):
    """AI Sheet의 월별 종가 시계열로 매수 후 보유 전략을 빠르게 검증하는 테스트용 알고리즘.

    데이터 파일 하나(/Lean/Data/prices.csv)만 바꿔 끼우면 어떤 종목의 시트든
    재사용할 수 있도록, 종목명은 표시용 라벨로만 쓰고 날짜 범위는 CSV에서
    직접 읽어 결정한다."""

    def initialize(self):
        symbol_label = (os.getenv("SYMBOL_NAME") or "SHEET").strip()[:40] or "SHEET"
        data_path = os.path.join(Globals.data_folder, "prices.csv")
        dates = []
        with open(data_path) as handle:
            for line in handle:
                if not line.strip() or line.startswith("Date"):
                    continue
                dates.append(datetime.strptime(line.split(",")[0], "%Y-%m-%d"))
        if not dates:
            raise ValueError("prices.csv에 유효한 데이터 행이 없습니다.")
        start, end = min(dates), max(dates) + timedelta(days=1)

        self.set_start_date(start.year, start.month, start.day)
        self.set_end_date(end.year, end.month, end.day)
        self.set_cash(1_000_000)

        self.symbol_label = symbol_label
        self.target = self.add_data(SheetSeries, "SHEET", Resolution.DAILY).symbol
        self.bought = False

    def on_data(self, data):
        if self.target not in data:
            return
        close = data[self.target].value
        self.plot(self.symbol_label, "Close", close)
        if not self.bought:
            self.market_order(self.target, 1)
            self.bought = True
            self.debug(f"{self.symbol_label} buy & hold test: {close:,.2f}")
