"""stock-coin-trade 백엔드 (FastAPI).

패키지 구성
- app.core      : 설정, DB 세션, 서버 세션(Redis), CSRF, 공통 의존성·예외·미들웨어
- app.models    : SQLAlchemy 2.0 타입 매핑 모델
- app.services  : HTTP와 무관한 도메인 로직(시세, 모의 주문, 증권사 게이트웨이 등)
- app.api       : FastAPI 라우터(얇은 HTTP 어댑터)
- app.jobs      : APScheduler 배치와 OHLCV 수집
- app.cli       : 독립 실행 스크립트
"""
