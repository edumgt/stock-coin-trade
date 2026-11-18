---
id: HX-004
title: 프런트엔드 주요 화면 document.scrollHeight 및 레이아웃 검증 및 개선
priority: P1
status: done
area: frontend
stages: [pm, design, dev, qa]
acceptance:
  - "{'주요 화면(예': 'index.html)의 document.scrollHeight가 window.innerHeight를 초과하지 않도록 레이아웃을 조정한다.'}"
  - 브라우저 세로 스크롤이 발생하지 않도록 CSS 및 DOM 구조를 개선한다.
  - 카드 내부 여백, 폼 레이아웃, 사이드바 및 상단 바 높이 등 가이드에 맞게 조정한다.
  - QA 시 1920×1080 뷰포트에서 세로 스크롤이 없고, 바닥에 80px 이상 빈 공간이 없는지 확인한다.
---
## 배경

index.html 25~116 줄의 주요 화면 레이아웃에서 카드 높이와 내부 여백, 상단 바 및 사이드바 높이 등이 가이드와 완전히 일치하는지 확인 필요. document.scrollHeight 측정 및 레이아웃 최적화가 필요함.

## 범위

- index.html 및 관련 CSS(style.css)에서 레이아웃 높이 및 여백 조정
- 카드 컴포넌트 및 폼 레이아웃이 가이드에 맞게 2~3열 또는 중앙 정렬 적용 검토
- 브라우저 세로 스크롤 발생 여부 측정 및 제거
- QA를 위한 뷰포트 내 스크롤 및 빈 공간 검증

## 참고 파일

- frontend/index.html
- frontend/css/style.css

## 출처

Tech Lead 에이전트 제안. 사람이 검토 후 `hermes-fleet approve <repo> <ID>`로 승인한다.
