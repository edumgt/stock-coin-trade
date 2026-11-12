---
id: HX-002
title: 프런트엔드 index.html에 Tailwind CSS 및 Pretendard 웹폰트 미적용 및 CDN 버전 미고정 문제 개선
priority: P1
status: todo
area: frontend
stages: [pm, design, dev, qa]
acceptance:
  - index.html에서 Tailwind CSS를 npm 의존성으로 고정 버전 설치 및 빌드에 포함하도록 변경한다.
  - Pretendard 웹폰트는 CDN 대신 npm 패키지로 적용하거나, CDN 버전을 명확히 고정하고 <head>에 링크를 넣는다.
  - lightweight-charts CDN 버전이 4.2.0으로 가이드 5.2.1과 다르므로 5.2.1로 고정하고, 로드 실패 시 안내 문구를 보여준다.
  - 기존 inline style과 style 태그 내 리터럴 색상 대신 Tailwind 토큰 및 유틸리티 클래스로 스타일을 변경한다.
  - 변경 후 1920×1080 뷰포트에서 세로 스크롤 및 가로 스크롤이 없고, 하단 푸터가 겹치지 않는지 확인한다.
---
## 배경

[{'frontend/index.html': '1~173 (Tailwind CSS는 CDN 최신 대신 npm 고정 버전 권장, Pretendard 웹폰트는 CDN 미사용, lightweight-charts 버전 4.2.0 → 5.2.1 불일치)'}, {'inline style과 리터럴 색상 다수 발견 (예': '32, 39, 46, 53, 60, 66, 78, 84줄)'}]

## 범위

- Tailwind CSS를 npm 의존성으로 전환 및 빌드에 포함
- Pretendard 웹폰트 CDN 제거 후 npm 패키지 적용 또는 CDN 버전 고정
- lightweight-charts CDN 버전 5.2.1로 변경 및 로드 실패 안내 구현
- inline style 제거 및 Tailwind 유틸리티 클래스로 대체
- 뷰포트 스크롤 및 푸터 겹침 문제 점검 및 수정

## 참고 파일

- frontend/index.html

## 출처

Tech Lead 에이전트 제안. 사람이 검토 후 `hermes-fleet approve <repo> <ID>`로 승인한다.
