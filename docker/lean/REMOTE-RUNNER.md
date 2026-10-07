# 공통 LEAN 원격 실행

st의 AI Sheet 백테스트는 사설 주소 `172.31.0.151`의 Docker 엔진을 사용합니다.
`docker-compose.yml`은 검증한 QuantConnect LEAN 이미지 digest를 고정합니다.

- 기존 iv 전용 `lean-iv` 계정과 `/opt/stock-kms-portal/secrets/lean-runner.key`를 사용합니다. 키는 백엔드에 읽기 전용으로 마운트하며 저장소에 포함하지 않습니다.
- `known_hosts`는 원격 서버의 확인된 공개 호스트 키입니다. SSH 호스트 키 검증을 유지합니다.
- 실행마다 UUID 작업 디렉터리와 컨테이너를 만들고 완료 또는 실패 후 정리합니다.
- LEAN 컨테이너는 네트워크 없이 CPU 2개, 메모리 2GB 한도로 실행합니다.
- 이미지 갱신 시 공통 서버의 digest와 Compose 설정을 함께 확인해야 합니다.

배포는 기존 SSL/DB Compose 파일을 함께 사용하여 `python-backend`를 재빌드합니다. 백엔드 재생성 후 프런트엔드 Nginx가 이전 컨테이너 주소를 참조하면 `nginx -s reload`로 다시 읽습니다.
