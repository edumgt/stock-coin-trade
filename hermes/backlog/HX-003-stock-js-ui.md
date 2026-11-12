---
id: HX-003
title: 프런트엔드 stock.js 실시간 데이터 갱신 및 UI 초기화 오류 처리 강화 및 테스트 보완
priority: P2
status: todo
area: frontend
stages: [pm, dev, qa]
acceptance:
  - stock.js 내 실시간 데이터 갱신 함수(refreshStockPanels 등)에서 실패 시 사용자에게 명확한 오류 메시지를 표시하도록 개선한다.
  - initPage, loadStockList, setTradeMode 등 초기화 함수 호출 순서와 예외 처리를 점검해 안정성 강화한다.
  - 주요 UI 요소 존재 여부 확인 및 예외 처리 추가로 UI 깨짐 방지한다.
  - 변경 후 기존 테스트 명령으로 정상 동작 확인 및 실패 케이스에 대한 테스트 보완을 제안한다.
---
## 배경

['frontend/js/stock.js 900~1050, 1000~1035 (실시간 갱신 setInterval 다수, Promise.allSettled 사용 중 실패 처리 미흡 가능성, 초기화 순서 중요)']

## 범위

- 실시간 갱신 함수 실패 처리 로직 개선 및 사용자 알림 강화
- 초기화 함수 예외 처리 및 UI 요소 존재 확인 추가
- 관련 테스트 보완 및 정상 동작 검증

## 참고 파일

- frontend/js/stock.js

## 출처

Tech Lead 에이전트 제안. 사람이 검토 후 `hermes-fleet approve <repo> <ID>`로 승인한다.
