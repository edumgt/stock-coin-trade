# DART 공시 레이더 1단계 — 수집·판정·화면 (local 전용, 외부 판정 모델)

2026-09-26. 브랜치 `feat/dart-radar`. 교육용 분류이며 투자 권유가 아니다.

## 무엇을 만들었나

| 부분 | 파일 | 하는 일 |
|---|---|---|
| 판정 | `src/deskjev/disclosures.py` | 공시 제목(`report_nm`)·비고(`rm`)·법인구분 → 교육용 유형 20개 중 하나, 정정 여부, 매매 불가 위험, 판정 주체(`rules`/`jev`) |
| 수집 | `python-stock-backend/dart_radar.py` | OpenDART `list.json` 오늘 목록 → 상장사만 판정해 `dart_disclosures`에 저장 |
| 스케줄 | `python-stock-backend/scheduler.py` | `price_sources.allowed("dart")`이고 `DART_API_KEY`가 있을 때만 5분 수집 + 매시 30분 하루 전체 훑기 + 00:10 KST 전날 전체 훑기 |
| API | `GET /api/disclosures?date=&symbol=&kind=&risk=&limit=` | DB에서 읽기. `date`가 있으면 그날, 없고 `symbol`만 있으면 그 종목의 최근 30일(접수일 내림차순), 둘 다 없으면 오늘. 처음 본 시각(KST, 접수일과 다른 날이면 `MM/DD HH:mm`), DART 원문 링크, 출처 문구. `SOURCE_DEPENDENT_BLUEPRINTS`에 `("dart",)` → public에서 404 |
| 화면 | `frontend/events.html`, `frontend/js/events.js` | 날짜·종목·유형·위험 필터, 위험 행 강조(색 + ⚠ 글자), 판정 주체와 모델 판단 확률, 유형별 건수. 종목 30일 모드에서는 접수일 열을 보인다. 표는 고정 배치(제목 왼쪽 정렬·줄바꿈) |
| 명령 | `frontend/js/common.js` | `DISC 005930`(별칭 `DART`) → `/events.html?symbol=005930`. 인자를 받는 명령을 6자리 코드 검사보다 먼저 처리하도록 순서를 고쳤다 |
| 평가 | `evals/jev_disclosures/`, `src/deskjev/eval_disclosures.py` | 실제 제목 285건 + 따로 둔 55건, `--mode oracle|rules|live`. 결과 파일은 최종 4개만 둔다 |

## 설계

- **규칙 먼저.** `report_nm`은 대부분 정해진 서식명이다. 서식명 조각 → (유형, 위험) 표를 위에서부터 맞춰 첫 줄이 이긴다. 해제·기각처럼 위험이 풀린 서식과 "정리매매"는 원래 사건 줄보다 위에 둔다. 자회사·종속회사 사건은 위험에서 뺀다.
- **판정 모델은 규칙이 비운 것만.** 자유 서식(투자판단관련주요경영사항, 기타시장안내·기타경영사항 부제, 처음 보는 서식)은 유형과 위험을, 조회공시·소송은 위험만 묻는다. 한 공시에 유형 Choice + 위험 Noul을 한 요청으로 보내고 코드가 필요한 답만 쓴다. 보내는 것은 제목·비고(뜻으로 풀어서)·시장 이름뿐이고 회사명·종목코드는 보내지 않는다. 모델은 버전 1.13.0으로 고정.
- **신뢰 경계.** 유형은 분포 argmax(sdk-python#15)로 고르고 `KINDS`에 없는 값은 기타로 둔다. 화면의 DART 링크는 서버 문자열 대신 14자리 접수번호로 다시 만든다.
- **위험 = 판정 모델 ≥ 0.5 또는 낱말.** 평가에서 판정 모델과 낱말 규칙이 서로 다른 공시를 놓쳤고, 합쳐도 정밀도가 떨어지지 않았다(아래 표).
- **폴백.** 판정 모델이 꺼져 있거나(`JEV_ENABLED`) 월 예산(`jev_usage.over_budget`)을 넘었거나 예외가 나면 그 회차의 나머지는 규칙만 쓴다(유형은 기타, 위험은 낱말). `judged_by='rules'`로 남아 나중에 다시 판정할 수 있다. 과금된 호출만 `jev_usage.record`로 적는다.
- **날짜.** `rcept_dt`만 쓴다. 2026-09-23 목록 683건 중 56건은 접수번호 앞 8자리가 접수일과 달랐다(vault `projects/dartcatcher`의 259건 중 83건과 같은 함정). DART는 접수 시각을 주지 않아 `first_seen_at`(UTC)을 적고 화면은 KST로 보여 준다.
- **전날 훑기.** 날짜가 바뀌면 그날 목록만 보므로 23:30 이후 5분 수집이 놓친 공시는 00:10 KST에 전날을 `full=True`로 다시 읽어 채운다.
- **수집 멈춤 조건.** 목록은 접수번호 순서와 딱 맞지 않는다(9/23 인접한 두 건 682쌍 중 166쌍이 오름차순). 그래서 저장된 번호를 만난 **쪽은 끝까지** 읽고 멈추고, 쪽을 넘기는 사이 밀린 중복은 접수번호로 거른다. 매시 30분 하루 전체 훑기로 놓친 것을 채운다. DART 키는 URL 쿼리에 들어가므로 요청 예외는 종류만 남기고(`from None`) 로그에 URL이 나오지 않는다.

## 평가 (evals/jev_disclosures/README.md)

라벨은 에이전트가 달았다(노아 검수 전). 규칙과 라벨을 같은 쪽이 만들었으므로 정해진 서식의 규칙 100%는 독립 측정이 아니다.

| | 사례 | 유형 정확도 | 자유 서식 유형 | 위험 재현율 | 위험 정밀도 |
|---|---|---|---|---|---|
| 규칙만 | 285 | 0.930 | 0.583 | 0.977 | 1.000 |
| 규칙 + 판정 모델 | 285 | **0.989** | **0.938** | 0.977 | 0.977 |
| 규칙만 (held-out) | 55 | 0.618 | 0.533 | 0.615 | 1.000 |
| 규칙 + 판정 모델 (held-out) | 55 | **0.891** | **0.867** | **0.692** | 1.000 |

- 판정 모델이 정한 유형 48건(held-out 45건): 정확도 0.938(0.867), ECE 0.056(0.076). 위험 Noul ECE 0.134(0.080).
- 지연(판정 모델 호출, 이 Mac → 외부 서비스): p50 202ms, p95 274ms. 호출당 입력 약 1,780토큰.
- 위험 질문 v1은 held-out 재현율 0.462로 낱말 규칙(0.538)보다 못했다. 상장폐지 심사 절차를 설명한 v2도 0.615로 낱말과 같았다. 합친 최종 정책은 held-out을 보고 골랐으므로 깨끗한 held-out 수치가 없다.
- 평가: live 실행 6회(285건 3회, 55건 3회), 매회 `--max-usd 1`.

### 하루 호출량

| 대상 | 계산 | 하루 |
|---|---|---|
| DART 5분 수집 | 288회 × 보통 1쪽(5분 사이 100건 넘게 새로 오면 2쪽) | 약 290~350회 |
| DART 매시 전체 훑기 | 24회 × 683건인 날 7쪽 | 약 170회 |
| DART 00:10 전날 훑기 | 1회 × 7쪽 | 약 7회 |
| DART 합계 | 키당 약 20,000건(비공식) 한도의 약 2.7% | 약 530회 |
| 판정 모델 | 2026-09-23 상장사 420건 중 규칙이 비운 23건 | 약 23회 |

## PM 확인 (2026-09-26, 이 브랜치 45f6f8b)

- 로컬 스택을 45f6f8b로 빌드(`DART_API_KEY`, `JEV_ENABLED=true`)하고 init으로 `dart_disclosures` 생성을 확인했다. 워커 컨테이너에서 `dart_radar.collect(day=date(2026,9,23))` 1회 → `{'new': 420, 'calls': 7, 'jev_calls': 23}`. API: 420건, 판정 규칙 397·판정 모델 23, 위험 12(스팩 거래정지·시가총액 미달 상장폐지 우려·회생 개시신청 정지·관리종목 우려 등).
- 브라우저 `/events.html?date=2026-09-23`: 목록·유형별 건수·"교육용 분류이며 투자 권유가 아닙니다" 문구 표시, 콘솔 오류 0(경고 1건은 사이트 공통 Tailwind CDN 경고). 스크린샷 `jev-disclosures-events.png`는 **아래 표 폭·처음 본 시각 수정 전 화면**이다(제목 열이 오른쪽 정렬로 넓어 유형·위험 열이 화면 밖).
- 명령 바 `DISC 011080` → `/events.html?symbol=011080` 이동 확인(6자리 가로채기 수정 동작).
- `common.js` 캐시 버전은 올리지 않는다. nginx가 `location = /js/common.js`에 `Cache-Control: no-cache, no-store, must-revalidate`를 붙인다(`docker/nginx.conf:70-72`, 쿼리스트링과 무관).
- 정정: 1단계 보고서의 "통합 테스트 일회용 컨테이너 잔여 0"은 사실과 달랐다. 09:17·09:18 KST에 만들어진 익명 볼륨 2개(각 약 161MB, MariaDB 데이터 디렉터리)가 남아 PM이 지웠다. 원인은 `--rm`으로 띄운 컨테이너를 `docker rm -f`(볼륨을 지우지 않음)로 없앤 것이다. 후속에서는 `docker stop`으로 멈춰 `--rm`이 익명 볼륨까지 지우게 했고, 끝난 뒤 `docker volume ls -q -f dangling=true`로 새 익명 볼륨 0개를 확인했다(남은 1개는 2026-08-07에 만들어진 것으로 이 작업과 무관).

## 검증 (2026-09-26 후속, main 병합 후 `sct-test:dev` = CI와 같은 python 3.11 이미지)

| 명령 | 결과 |
|---|---|
| `ruff check python-stock-backend src tests` | All checks passed |
| `ruff format --check`(바꾼 src 파일 + `tests/unit tests/integration tests/conftest.py`) | 통과 |
| `python -m pytest -q -m "not integration" tests/unit tests/policy`(B2 병합 후) | 358 passed, 1 skipped(네트워크) |
| `pytest tests/integration/test_bootstrap_mariadb.py`(일회용 `mariadb:11.4` `--rm`, `db.sql` 적재) | 3 passed, 남은 컨테이너 0, 새 익명 볼륨 0 |
| `node --check frontend/js/common.js frontend/js/events.js` | 통과 |
| 1200×800 브라우저(Playwright, 정적 서버 + `/api/disclosures` 목 응답, 긴 실제 제목 3건) | 하루 모드·종목 30일 모드 모두 표 가로 넘침 0px, 페이지 넘침 0px, 판정 열 오른쪽 끝 891px = 패널 끝, 제목 왼쪽 정렬·줄바꿈. `jev-disclosures-events-1200-day.png`, `jev-disclosures-events-1200-span.png`(목 데이터 화면). 콘솔 오류는 목을 걸지 않은 공통 헤더 API(`/api/member/me`, 시세 티커) 404뿐 |
| `eval_disclosures --mode oracle`(단위 테스트, 285·55건) | 100%, 오류 0 |
| 1단계 수집기 시험(실제 DART, 가짜 저장소, 판정 모델 끔) | 오늘(토) 1호출 013 → 0건. 9/23 빈 저장소 7호출 420건(E 0건 저장), 다시 1호출 0건, 전체 훑기 7호출 0건 |

판정 로직은 바꾸지 않아 live 재평가는 하지 않았다.

## 한계

- 종목 30일 모드는 저장된 공시만 보여 준다. 수집기를 켜기 전 날짜는 비어 있다.
- 제목만 본다. 본문(document.xml)은 읽지 않는다. 제목과 본문이 다를 수 있다.
- 라벨 검수 전이다. 판단이 갈리는 라벨(기술적 거래정지, 회생 개시신청 기각, 회생계획인가, 대출원리금 연체)은 평가 README에 적었다.
- 목록 순서가 바뀌는 방식은 하루치 관찰로만 추정했다. 5분 수집이 놓친 것은 매시 전체 훑기와 00:10 전날 훑기가 채운다.
- `dart` 소스는 unverified(약관 확인 전)라 public에서는 등록하지 않는다.

## 하지 않은 것 (다음 단계)

유형별 주가 반응(CAR) 이벤트 스터디와 영수증, 공시 본문 판정, 자연어 명령 라우터에 공시 화면 추가(B1 평가 재측정 필요), 알림, `judged_by='rules'` 행 재판정 작업.
