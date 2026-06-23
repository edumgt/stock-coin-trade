"""
Qdrant vector DB — Korean stock market knowledge base (RAG).
Model: intfloat/multilingual-e5-small (Korean support, ~118 MB)
"""

import os
import uuid
import logging
from threading import Lock

logger = logging.getLogger(__name__)

QDRANT_URL  = os.getenv("QDRANT_URL", ":memory:")
COLLECTION  = "market_knowledge"
EMBED_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

_client = None
_lock   = Lock()

# ─── Seed knowledge dataset (Korean stock market) ────────────────────────────
SEED = [
    {
        "title": "RSI(상대강도지수) 분석",
        "category": "technical_analysis",
        "text": (
            "RSI(Relative Strength Index)는 0~100 범위의 모멘텀 지표입니다. "
            "RSI 70 이상은 과매수(overbought) 신호로 단기 조정 가능성을 시사합니다. "
            "RSI 30 이하는 과매도(oversold) 신호로 반등 가능성을 나타냅니다. "
            "14일 RSI가 가장 일반적으로 사용되며, 단기 5일·중기 9일도 활용합니다. "
            "주가가 신고점인데 RSI가 하락하는 약세 다이버전스는 하락 반전 경고 신호입니다."
        ),
    },
    {
        "title": "MACD 분석",
        "category": "technical_analysis",
        "text": (
            "MACD(Moving Average Convergence/Divergence)는 12일 EMA에서 26일 EMA를 뺀 값입니다. "
            "시그널 라인은 MACD의 9일 EMA입니다. "
            "골든 크로스(MACD가 시그널 상향 돌파): 강한 매수 신호입니다. "
            "데드 크로스(MACD가 시그널 하향 돌파): 매도 신호입니다. "
            "히스토그램이 0선을 상향 돌파하면 강세 전환, 하향 돌파하면 약세 전환으로 봅니다."
        ),
    },
    {
        "title": "볼린저 밴드 분석",
        "category": "technical_analysis",
        "text": (
            "볼린저 밴드는 20일 이동평균선(중간 밴드) ± 2표준편차로 구성됩니다. "
            "주가가 상한 밴드를 돌파하면 과매수로 조정 가능성이 있습니다. "
            "주가가 하한 밴드에 닿으면 반등 신호로 해석할 수 있습니다. "
            "밴드 폭이 좁아지는 스퀴즈 구간에서는 이후 큰 변동성 확대가 예상됩니다. "
            "%B 지표가 1 이상이면 과매수, 0 이하면 과매도 상태입니다."
        ),
    },
    {
        "title": "이동평균선(MA) 분석",
        "category": "technical_analysis",
        "text": (
            "이동평균선은 일정 기간의 종가 평균을 연결한 선으로 추세를 파악합니다. "
            "5일선(단기), 20일선(세력 기준선), 60일선(중기), 120일선(장기)을 주로 사용합니다. "
            "5일선이 20일선을 상향 돌파하는 골든 크로스는 단기 매수 신호입니다. "
            "200일선(연간 이동평균) 위에서는 장기 상승 추세, 아래에서는 하락 추세입니다. "
            "정배열(단기>중기>장기)은 강세, 역배열(단기<중기<장기)은 약세 신호입니다."
        ),
    },
    {
        "title": "거래량 분석과 시장 해석",
        "category": "technical_analysis",
        "text": (
            "거래량은 주가 방향성의 신뢰도를 검증하는 핵심 지표입니다. "
            "주가 상승 + 거래량 급증: 강한 상승 신호로 세력 매집 가능성이 있습니다. "
            "주가 상승 + 거래량 감소: 상승 모멘텀 약화로 주의가 필요합니다. "
            "주가 급락 + 거래량 폭증: 패닉셀 구간으로 반등 가능성이 높습니다. "
            "거래량 이동평균선 돌파 여부로 세력 개입 시점을 포착할 수 있습니다."
        ),
    },
    {
        "title": "코스피(KOSPI) 시장 구조와 특성",
        "category": "market_structure",
        "text": (
            "코스피는 한국거래소(KRX) 유가증권 시장으로 대형 우량 기업들이 상장됩니다. "
            "정규 시장 시간은 09:00~15:30이며, 동시호가는 09:00~09:10 / 15:20~15:30입니다. "
            "코스피200 지수는 대표 200개 종목으로 구성되어 파생상품의 기초 자산입니다. "
            "외국인 보유 비중이 시가총액의 30% 이상으로 글로벌 매크로 이벤트에 민감합니다. "
            "삼성전자·SK하이닉스 등 반도체 대형주가 지수 방향에 큰 영향을 미칩니다."
        ),
    },
    {
        "title": "코스닥(KOSDAQ) 시장 특성",
        "category": "market_structure",
        "text": (
            "코스닥은 기술·바이오·중소형 성장 기업들이 주로 상장된 시장입니다. "
            "코스피 대비 변동성이 크고 개인 투자자 비중이 높아 테마 주도 장세가 자주 발생합니다. "
            "기술 특례·성장 특례 상장으로 적자 기업도 상장 가능합니다. "
            "바이오·게임·IT 섹터의 테마주가 단기 급등락을 보이는 경우가 많습니다. "
            "코스닥150 지수는 대표 150개 종목으로 구성되며 ETF·파생상품에 활용됩니다."
        ),
    },
    {
        "title": "반도체 섹터 투자 분석",
        "category": "sector_analysis",
        "text": (
            "한국 반도체 대표 기업은 삼성전자(005930)와 SK하이닉스(000660)입니다. "
            "반도체 사이클은 3~4년 주기로 업턴/다운턴이 반복되며 DRAM·NAND 가격이 실적을 좌우합니다. "
            "AI 서버 투자 확대로 HBM(고대역폭 메모리) 수요가 급증하며 SK하이닉스가 수혜 중입니다. "
            "미국 수출 규제, 중국 접근성, 원/달러 환율이 핵심 리스크 요인입니다. "
            "장비 업체(한미반도체, HPSP)와 소재 업체(솔브레인, 후성)도 함께 주목받습니다."
        ),
    },
    {
        "title": "이차전지·배터리 섹터 분석",
        "category": "sector_analysis",
        "text": (
            "한국 배터리 3사는 LG에너지솔루션(373220), 삼성SDI, SK이노베이션입니다. "
            "전기차(EV) 보급 속도와 배터리 수요는 직결되며 IRA 법안이 실적에 직접 영향을 줍니다. "
            "에코프로비엠(247540)·에코프로(086520)는 양극재 소재 대표 코스닥 기업입니다. "
            "리튬·코발트·니켈 원자재 가격 변동이 배터리 업체 수익성에 영향을 미칩니다. "
            "중국 CATL과의 가격 경쟁 심화가 한국 배터리 업체의 주요 리스크입니다."
        ),
    },
    {
        "title": "바이오·헬스케어 섹터 분석",
        "category": "sector_analysis",
        "text": (
            "바이오 섹터는 임상 데이터, FDA 승인, 기술수출(L/O) 이벤트에 크게 반응합니다. "
            "셀트리온(068270)은 바이오시밀러 분야 글로벌 선두 기업입니다. "
            "삼성바이오로직스(207940)는 세계 최대 바이오의약품 위탁생산(CMO) 기업입니다. "
            "알테오젠(196170)은 피하주사(SC) 플랫폼 기술로 다수의 글로벌 계약을 체결했습니다. "
            "임상 3상 성공 시 급등 가능성이 있으나, 실패 시 -50% 이상 폭락도 흔합니다."
        ),
    },
    {
        "title": "NAVER(035420) 종목 분석",
        "category": "sector_analysis",
        "text": (
            "NAVER는 국내 최대 포털·커머스·클라우드 플랫폼 기업입니다. "
            "라인(LINE)을 통해 일본·동남아 시장에서 메신저·금융 서비스를 운영합니다. "
            "클라우드·AI(HyperCLOVA) 사업이 신성장 동력으로 주목받고 있습니다. "
            "커머스 부문의 SME 입점 수수료와 광고 수익이 핵심 매출원입니다. "
            "카카오와 IT 플랫폼 시장에서 직접 경쟁하며 두 종목의 방향성이 유사합니다."
        ),
    },
    {
        "title": "분산 투자 원칙",
        "category": "investment_strategy",
        "text": (
            "포트폴리오 분산은 개별 종목 리스크를 낮추는 핵심 전략입니다. "
            "동일 섹터 집중 투자는 섹터 리스크에 과다 노출되므로 피하는 것이 좋습니다. "
            "개별 종목은 전체 포트폴리오의 5~10% 이내를 원칙으로 권장합니다. "
            "주식·채권·현금·대체자산 간 자산군 분산도 변동성 완충에 효과적입니다. "
            "상관계수가 낮은 자산 조합이 변동성 대비 수익률(샤프 비율)을 높입니다."
        ),
    },
    {
        "title": "손절 원칙과 리스크 관리",
        "category": "risk_management",
        "text": (
            "손절(Stop Loss)은 특정 손실 수준에서 기계적으로 매도하는 리스크 관리 기법입니다. "
            "일반적으로 매수가 대비 -5% ~ -10%를 손절선으로 설정합니다. "
            "손절 없이 물타기만 반복하면 계좌 전체를 잃을 수 있는 위험이 있습니다. "
            "1:2 이상의 리스크:리워드 비율을 유지해야 장기적으로 수익이 가능합니다. "
            "개별 거래의 최대 손실은 전체 운용 자금의 1~2% 이내로 제한하는 것이 원칙입니다."
        ),
    },
    {
        "title": "외국인·기관 수급 분석",
        "category": "market_structure",
        "text": (
            "외국인 투자자는 코스피 시가총액의 30% 이상을 보유하는 핵심 수급 주체입니다. "
            "원/달러 환율 하락(원화 강세) 시 외국인 자금 유입이 유리한 환경이 됩니다. "
            "미국 금리 인상기에는 외국인이 신흥국 주식을 매도하는 경향이 있습니다. "
            "국민연금은 코스피 최대 기관 투자자로 리밸런싱 매매가 시장에 큰 영향을 줍니다. "
            "기관 순매수가 지속되면 중장기 상승 지지력이 강화되는 경향이 있습니다."
        ),
    },
    {
        "title": "하락장 대응 전략",
        "category": "investment_strategy",
        "text": (
            "하락장에서는 현금 비중을 높여 변동성 리스크를 낮추는 것이 우선입니다. "
            "인버스 ETF(KODEX 인버스, TIGER 인버스)로 하락 방향에 헤지가 가능합니다. "
            "공포 지수(VIX)가 40 이상이거나 공포·탐욕 지수가 '극단적 공포'면 역발상 매수 검토 시기입니다. "
            "분할 매수(DCA)로 평균 매입 단가를 낮추는 전략이 급락장에서 효과적입니다. "
            "하락장에서도 실적이 견조한 배당주·방어주는 상대적 강세를 보이는 경향이 있습니다."
        ),
    },
    {
        "title": "PER·PBR 밸류에이션 분석",
        "category": "fundamental_analysis",
        "text": (
            "PER(주가수익비율) = 주가 / EPS. PER이 낮을수록 이익 대비 주가가 저평가된 상태입니다. "
            "PBR(주가순자산비율) = 주가 / BPS. PBR 1 이하는 자산 대비 주가가 저평가 상태입니다. "
            "코스피 평균 PER은 역사적으로 10~15배 수준이며, 이를 기준으로 고평가·저평가를 판단합니다. "
            "성장주는 높은 PER이 정당화될 수 있으나 수익성 개선 전제가 필요합니다. "
            "동일 섹터 내 PER·PBR 비교로 상대적 저평가 종목을 발굴할 수 있습니다."
        ),
    },
    {
        "title": "기업 공시 분석 방법",
        "category": "fundamental_analysis",
        "text": (
            "전자공시시스템(DART, dart.fss.or.kr)에서 상장 기업의 공식 공시를 확인할 수 있습니다. "
            "실적 발표: 컨센서스 상회 시 주가 상승, 하회 시 하락이 일반적입니다. "
            "유상증자 공시: 주식 희석으로 단기 주가 하락 요인이 됩니다. "
            "자사주 매입 공시: 주주 가치 제고 신호로 주가에 긍정적입니다. "
            "대규모 수주·기술수출·합병 공시는 주가 급등의 주요 트리거가 됩니다."
        ),
    },
    {
        "title": "배당 투자 전략",
        "category": "investment_strategy",
        "text": (
            "배당수익률 = 연간 주당 배당금 / 현재 주가. 국채 금리보다 배당수익률이 높으면 매력적입니다. "
            "한국 상장사는 12월 결산법인이 많아 12월 말 기준 주주에게 이듬해 초 배당을 지급합니다. "
            "배당락일 이후 주가 하락 폭만큼의 배당 수익을 얻는 배당락 전략이 활용됩니다. "
            "고배당 ETF(KODEX 고배당, TIGER 배당성장)로 분산 배당 투자가 가능합니다. "
            "연속 배당 증가 기업(배당 귀족주)은 실적 안정성과 장기 가치 성장이 기대됩니다."
        ),
    },
    {
        "title": "투자 심리와 행동 경제학",
        "category": "investment_strategy",
        "text": (
            "FOMO(Fear of Missing Out): 급등 추격 매수는 고점 매수로 이어지기 쉽습니다. "
            "워런 버핏: '다른 사람이 탐욕스러울 때 두려워하고, 두려울 때 탐욕스러워야 한다.' "
            "손실 회피 편향: 동일 금액의 이익보다 손실을 2.5배 크게 느끼는 심리적 특성이 있습니다. "
            "확증 편향: 자신의 투자 판단을 지지하는 정보만 수집하는 경향을 주의해야 합니다. "
            "시장 공포·탐욕 지수(Fear & Greed Index)로 현재 시장 심리 수위를 수치화합니다."
        ),
    },
    {
        "title": "주식 거래 세금과 비용",
        "category": "market_structure",
        "text": (
            "국내 주식 거래세: 코스피 0.03%, 코스닥 0.18% (2024년 기준)입니다. "
            "국내 소액 투자자는 양도소득세 비과세(대주주 기준 10억 원 이상 예외)입니다. "
            "증권사 온라인 거래 수수료는 0.015% 수준이며 증권사별로 차이가 있습니다. "
            "ETF의 경우 운용 보수(TER)가 연간 0.05~0.3% 별도 부과됩니다. "
            "해외 주식은 연간 250만 원 초과 양도차익에 22% 세율의 양도소득세가 적용됩니다."
        ),
    },
    {
        "title": "삼성전자(005930) 주요 분석 포인트",
        "category": "sector_analysis",
        "text": (
            "삼성전자는 코스피 시가총액 1위로 지수 방향에 가장 큰 영향을 미치는 종목입니다. "
            "반도체(DS부문)와 스마트폰·가전(DX부문)의 투 트랙 사업 구조를 갖추고 있습니다. "
            "DRAM·NAND·파운드리 3개 반도체 사업 모두를 영위하는 세계 유일의 기업입니다. "
            "HBM3E 공급 지연과 TSMC 대비 파운드리 격차는 단기 주가 부담 요인입니다. "
            "외국인 보유 비중이 50% 이상으로 원/달러 환율과 글로벌 반도체 수요에 민감합니다."
        ),
    },
]


def _init():
    global _client
    if _client is not None:
        return _client
    with _lock:
        if _client is not None:
            return _client
        try:
            from qdrant_client import QdrantClient
            c = QdrantClient(QDRANT_URL if QDRANT_URL != ":memory:" else ":memory:")
            c.set_model(EMBED_MODEL)
            _seed(c)
            _client = c
            logger.info("Qdrant ready — model=%s url=%s docs=%d", EMBED_MODEL, QDRANT_URL, len(SEED))
        except Exception as exc:
            logger.error("Qdrant init failed: %s", exc)
            raise
    return _client


def _seed(c):
    existing = [col.name for col in c.get_collections().collections]
    if COLLECTION not in existing:
        texts = [d["text"] for d in SEED]
        metas = [{"title": d["title"], "category": d["category"]} for d in SEED]
        ids   = [str(uuid.uuid4()) for _ in SEED]
        c.add(collection_name=COLLECTION, documents=texts, metadata=metas, ids=ids)


def search(query: str, limit: int = 5) -> list:
    c = _init()
    hits = c.query(collection_name=COLLECTION, query_text=query, limit=limit)
    return [
        {
            "id":       str(h.id),
            "title":    h.metadata.get("title", ""),
            "category": h.metadata.get("category", ""),
            "text":     h.document or "",
            "score":    round(h.score, 4),
        }
        for h in hits
    ]


def stats() -> dict:
    c = _init()
    info = c.get_collection(COLLECTION)
    return {
        "collection": COLLECTION,
        "model":      EMBED_MODEL,
        "count":      info.points_count,
    }


def list_docs(limit: int = 30) -> list:
    c = _init()
    records, _ = c.scroll(
        collection_name=COLLECTION,
        limit=limit,
        with_payload=True,
        with_vectors=False,
    )
    return [
        {
            "id":       str(r.id),
            "title":    r.payload.get("title", ""),
            "category": r.payload.get("category", ""),
            "text":     (r.payload.get("document", "") or "")[:120] + "…",
        }
        for r in records
    ]


def add_doc(text: str, title: str, category: str = "custom") -> str:
    c = _init()
    doc_id = str(uuid.uuid4())
    c.add(
        collection_name=COLLECTION,
        documents=[text],
        metadata=[{"title": title, "category": category}],
        ids=[doc_id],
    )
    return doc_id
