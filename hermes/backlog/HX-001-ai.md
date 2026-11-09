---
id: HX-001
title: AI 시트 페이지의 스타일 적용 미흡
priority: P1
status: done
area: frontend
stages: [dev, qa]
acceptance:
  - AI 시트 페이지의 스타일이 Tailwind CSS를 사용하여 일관성 있게 적용되어야 함
  - 페이지의 모든 요소가 Tailwind CSS 클래스를 사용하여 스타일이 적용되어야 함
---
## 배경

frontend/css/ai-sheet.css (1 lines)와 frontend/ai-sheet.html (35 lines)에서 확인됨

## 범위

- ai-sheet.css 파일을 수정하여 Tailwind CSS 클래스를 사용하여 스타일을 적용
- ai-sheet.html 파일을 수정하여 Tailwind CSS 클래스를 사용하여 스타일을 적용

## 참고 파일

- frontend/css/ai-sheet.css
- frontend/ai-sheet.html

## 출처

Tech Lead 에이전트 제안. 사람이 검토 후 `hermes-fleet approve <repo> <ID>`로 승인한다.
