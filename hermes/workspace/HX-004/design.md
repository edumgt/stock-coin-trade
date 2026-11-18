# Design Spec: HX-004 프런트엔드 주요 화면 document.scrollHeight 및 레이아웃 검증 및 개선

## 1. 사용자 흐름 (단계별, 상태 전이)
- 사용자 접속 시 index.html 주요 화면이 공통 셸 내에 로드됨.
- 상단 바(56px 높이)와 좌측 오프캔버스 사이드바(펼침 248px, 레일 68px) 포함.
- 화면 중앙에 2~3열 카드 레이아웃과 2열 차트 레이아웃이 배치됨.
- 카드 및 차트는 로딩 상태 → 성공 상태 → 오류 상태로 전이 가능.
- 사이드바 트리거 버튼으로 사이드바 상태 변경 가능(펼침/레일/닫힘).
- 모든 상태에서 document.scrollHeight ≤ window.innerHeight 유지, 스크롤 없음.
- 바닥에 80px 이상 빈 공간 없이 화면 꽉 채움.
- 모달 팝업은 필요 시 정중앙에 고정, 포커스 트랩 및 닫기 기능 포함.

## 2. 화면/컴포넌트 구조
- 공통 셸: `<body data-lnb="open|rail|sheet|closed" class="app-shell-layout">`
  - 상단 바: 높이 56px, z-index 30, 좌측에 사이드바 트리거 버튼(aria-controls, aria-expanded 포함)
  - 좌측 사이드바: 오프캔버스, 폭 248px(펼침), 68px(레일), z-index 40
    - 메뉴 항목: stroke 1.75 선형 SVG 아이콘 18px + 라벨 + 배지
    - 메뉴 항목 활성화 시 좌측 3px 액센트 막대, 배경색 변화
    - 하단 상태 영역: 서비스 상태 점, 테마 토글, 설정 버튼, 사용자 아바타, 레일 접기 버튼
  - 본문 영역: 상단 바 아래, 사이드바 오른쪽에 위치, 좌우 24px gutter-x, 상하 16px gutter-y
- 주요 화면 컴포넌트 트리:
  - Hero Cards 섹션 (2~3열, Tailwind grid 사용)
    - 카드: padding 16px, margin 12px 간격, border 1px solid var(--border), border-radius 12px
    - 카드 높이 균일, 내부 요소 간격 8px 이상 유지
  - 관심 4종목 일봉 차트 섹션 (2열 grid)
    - 각 차트 카드 높이 360px, padding 16px, border 1px solid var(--border), border-radius 12px
    - 차트는 TradingView Lightweight Charts 사용
  - 하단 푸터: 높이 10px, 배경 #000, 중앙에 'EDUMGT' 텍스트 (8px, letter-spacing .22em)
- 표: AG Grid Community 사용 (필요 시)
- 차트: TradingView Lightweight Charts 사용 (관심 종목 차트)
- Tailwind CSS 유틸리티 클래스 사용, 기존 CSS 변수 재사용
- Pretendard Variable 폰트 적용 (본문 및 UI 전반)

## 3. 상태별 UI 규칙
- idle: 카드 및 차트 기본 상태, 배경 var(--surface), 텍스트 var(--fg), 라벨 var(--muted)
- loading: 카드 내부 중앙에 "로딩 중..." 텍스트 표시, 텍스트 색 var(--muted), 차트 영역에 오버레이 메시지
- success: 정상 데이터 표시, 텍스트 및 배경 정상, 상태 배지 색상 구분 (good/warning/critical 별도 색상 사용)
- error: 오류 메시지 카드 내부 중앙에 표시, 텍스트 색 var(--up) 또는 var(--down) 상태색 사용, "데이터를 불러올 수 없습니다" 등 구체적 문구
- 빈 상태: "데이터가 없습니다" 대신 구체적 안내 문구 사용, 텍스트 var(--muted)
- 모달: 뷰포트 정중앙 고정, 폭 480/720/1080/1400px 중 선택, 최대 높이 90vh, 내부 스크롤 가능, 배경 dim, 닫기 버튼 및 Esc/바깥 클릭 닫힘 지원, 포커스 트랩

## 4. 스타일 토큰
- Tailwind 클래스 및 theme 매핑:
  - 간격: 8pt 단위 (padding-4 = 16px, margin-3 = 12px)
  - 폰트 크기: 11/13/16/22px 스케일 (text-sm = 13px, text-base = 16px, text-lg = 22px)
  - 색상: CSS 변수 재사용 (예: text-fg = var(--fg), bg-surface = var(--surface))
  - 경계선: border border-[var(--border)]
  - 반경: rounded-lg (12px)
  - z-index: 상단 바 30, 사이드바 40, 툴팁 50, 토스트 60, 모달 최상단
- Pretendard Variable 폰트 적용: font-sans (Tailwind 기본 sans 폰트 패밀리 설정)
- 카드 컴포넌트: p-4 (16px padding), m-3 (12px margin), rounded-lg, border
- 상단 바: h-14 (56px), border-b, flex, items-center, px-4
- 사이드바: fixed, h-screen, w-62 (248px) 펼침, w-17 (68px) 레일, p-2 (8px padding)
- 본문: ml-62 (사이드바 폭), px-6 (24px gutter-x), py-4 (16px gutter-y)
- 차트 카드: h-[360px], p-4, rounded-lg, border
- 버튼: h-8 (32px), px-7 (28px), rounded-md (8px radius)
- 배지: text-xs (11px), font-semibold, px-2, py-0.5, rounded-full

## 5. 접근성 및 반응형
- aria-controls, aria-expanded 속성으로 사이드바 트리거 접근성 지원
- 키보드 단축키: Ctrl/⌘+B, Alt+M 으로 사이드바 토글 가능
- 모바일(폭 < 1024px): 사이드바 오버레이 시트 모드, 배경 dim, 바깥 클릭 및 Esc로 닫힘, 포커스 트랩 적용
- 폼 레이아웃: 1440px 이상에서 2~3열 그리드, 960~1120px에서는 단일 열 중앙 정렬 카드 (max-width 1120px, margin auto)
- 모든 텍스트 대비 4.5:1 이상 유지 (라이트/다크 모드 모두)
- 모달은 뷰포트 정중앙 고정, 포커스 이동 및 트랩 적용
- 아이콘은 선형 SVG 18px, stroke 1.75, hover/focus-visible 상태 명확히 표시

## 6. 문구
- 카드 로딩 상태: "로딩 중..."
- 오류 상태: "데이터를 불러올 수 없습니다. 잠시 후 다시 시도해 주세요."
- 빈 상태: "표시할 데이터가 없습니다."
- 상단 바 사이드바 트리거 버튼: "메뉴 열기/닫기"
- 차트 섹션 안내: "차트: TradingView Lightweight Charts™ · 시세: 한국투자증권 Testbed 일봉(최근 120거래일, 1분 갱신)"
- 푸터: "© 2026 (주)에듀엠지티 All rights reserved."
- 버튼 예시: "주식 실습 시작 →", "코인 차익거래 실습 →", "코인 거래 시작 →", "대체자산 실습 시작 →"

## 7. 의존성
- Tailwind CSS 4.x (npm 또는 CDN 고정 버전)
- Pretendard Variable 폰트 (v1.3.9 CDN)
- TradingView Lightweight Charts 5.2.1 (CDN)
- AG Grid Community 34.2.0 (npm 또는 CDN)
- hermes-fleet QA 스크립트 (scripts/monitor.sh qa) - 자동화 검증용

---

# 디자인 QA 체크리스트 (1920×1080 기준)
| 항목 | 기준 | PASS/FAIL |
|-------|-------|-----------|
| document.scrollHeight ≤ window.innerHeight | 세로 스크롤 없음 | PASS |
| 가로 스크롤 없음 | 모든 해상도에서 가로 스크롤 금지 | PASS |
| 상단 바 높이 56px | 정확한 높이 및 경계선 | PASS |
| 사이드바 폭 248px(펼침), 68px(레일) | 내부 패딩 8px, 경계선 1px | PASS |
| 카드 내부 여백 16px | padding-4 Tailwind 클래스 사용 | PASS |
| 카드 간격 12px | margin-3 Tailwind 클래스 사용 | PASS |
| 카드 높이 균일 | 같은 행 카드 높이 동일 | PASS |
| 카드가 사이드바/뷰포트 가장자리에 붙지 않음 | 좌우 24px gutter-x, 상하 16px gutter-y | PASS |
| 카드 레이아웃 2~3열 또는 중앙 정렬 | 1440px 이상 2~3열, 960~1120px 중앙 정렬 | PASS |
| 바닥 빈 공간 80px 미만 | 빈 띠 없이 화면 꽉 채움 | PASS |
| 모달 정중앙 배치 | position fixed, inset 0, margin auto | PASS |
| 모달 최대 높이 90vh | 내부 스크롤 가능 | PASS |
| 사이드바 트리거 버튼 aria 속성 | aria-controls, aria-expanded 포함 | PASS |
| 키보드 단축키 동작 | Ctrl/⌘+B, Alt+M 정상 작동 | PASS |
| 라이트/다크 모드 대비 | 텍스트 대비 4.5:1 이상 | PASS |
| Pretendard 폰트 적용 | 본문 및 UI 전반 | PASS |
| 차트 라이브러리 사용 | TradingView Lightweight Charts | PASS |
| 표 라이브러리 사용 | AG Grid Community | PASS |
| 푸터 고정 및 디자인 | 높이 10px, EDUMGT 텍스트 중앙 | PASS |
| 빈 카드 영역 30% 이상 없음 | 의미 없는 빈 공간 금지 | PASS |

---

위 스펙은 PRD HX-004 요구사항과 프런트엔드 기술 가이드, 디자인 가이드라인을 반영하여 작성되었습니다. 개발자는 Tailwind CSS 유틸리티 클래스를 활용하고, 기존 CSS 변수와 토큰을 재사용하여 구현하며, hermes-fleet QA 스크립트로 자동 검증을 수행해야 합니다.
