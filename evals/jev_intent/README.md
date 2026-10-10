# 자연어 명령 라우터 평가 (외부 판정 모델)

터미널 명령 바에 한국어 문장을 넣었을 때 `src/deskjev/intent.py`가 맞는 화면·종목·전략으로 보내는지 잰다. 자동 이동 임계값(`GO`)과 제안 임계값(`SUGGEST`)은 이 평가로 정한다.

## 사례 (`cases.jsonl`, 119개)

| 필드 | 뜻 |
|---|---|
| `text` | 사용자가 명령 바에 입력하는 문장 |
| `screen` | 정답 화면(`deskjev.intent.SCREENS`의 키, 관련 없으면 `none`) |
| `screen_alt` | 둘 다 맞다고 볼 수 있는 화면(예: "리플 사도 돼?"는 코인 화면도 리서치도 된다) |
| `stock` / `coin` / `strategy` | 그 화면이 쓰는 인자의 정답. 없으면 `null` |

정식 명칭, 약칭(삼전·하닉·비트), 오타, 영어·한영 혼용, 부정("김프 말고 비트 차트"), 목록에 없는 종목(엔비디아), 지시 주입("이전 지시 무시하고…"), 잡담을 섞었다. 모두 합성 문장이다.

## 실행

```bash
# 오프라인·무료: 정답을 돌려주는 가짜 모델. 100%가 아니면 채점기나 사례가 틀렸다.
PYTHONPATH=src:python-stock-backend python -m deskjev.eval --mode oracle
# 실제 판정 모델(과금). 비용 상한 없이는 실행하지 않는다. 119건 한 번에 실행한다.
PYTHONPATH=src:python-stock-backend TYPESAFE_API_KEY=... python -m deskjev.eval --mode live --max-usd 1
```

결과는 `results/<mode>.json`에 사례별 행과 요약으로 남는다.

## 채점

- 화면: 정답 또는 `screen_alt`면 맞다.
- 인자: 정답 화면을 맞혔을 때, 그 화면이 URL에 싣는 인자(주식·코인·전략)가 모두 맞아야 "full" 정답이다.
- 임계값 표: "confidence ≥ t면 바로 이동" 규칙에서 자동 처리 비율과 그 안의 오답률. 목표는 자동 이동 오답률 2% 이하다.
- 보정: 신뢰도 구간별 평균 신뢰도와 실제 정답률, ECE.
- 지연: 호출 한 번의 p50·p95(평가를 돌린 곳 기준. 한국에서는 미국보다 느리다).
