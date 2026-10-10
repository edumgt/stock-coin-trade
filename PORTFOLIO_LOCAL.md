# 포트폴리오 로컬 실행

이 저장소는 원본 저장소(edumgt/stock-coin-trade)를 기반으로 한 GitHub 포크이며, 이 작업공간은 원본 기준 커밋 `d5a105f0256ac4ddfa0a0223cc736498c7891c92`에서 시작했다. `compose.portfolio.yml`과 이 문서는 Noah의 로컬 실행 격리 작업이다. 원본 앱의 기존 화면·거래·KIS 연동은 새 개인 구현으로 표시하지 않는다.

## 준비와 실행

[Docker Compose v2.24.4 이상](https://docs.docker.com/reference/compose-file/merge/#replace-value)이 필요하다(`!override` 사용). 아래 모든 명령은 이 작업공간의 루트에서 실행한다. `.env.portfolio`는 `.gitignore`에 포함되며, 브로커·클라우드 자격 증명은 넣지 않는다. 아직 파일이 없을 때만 다음 명령으로 로컬 DB 비밀번호와 Flask 세션 키를 생성한다. 비밀번호는 DB URL에도 들어가므로 URL에 안전한 16진수로 만든다.

```bash
python3 - <<'PY'
import os
import secrets

values = {
    'FRONTEND_PORT': '3333',
    'MARIADB_USER': 'mockinv',
    'MARIADB_PASSWORD': secrets.token_hex(24),
    'MARIADB_ROOT_PASSWORD': secrets.token_hex(24),
    'QUANT_DB_NAME': 'quant_research',
    'QUANT_DB_USER': 'quant',
    'QUANT_DB_PASSWORD': secrets.token_hex(24),
    'SECRET_KEY': secrets.token_hex(32),
}
fd = os.open('.env.portfolio', os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
with os.fdopen(fd, 'w') as output:
    output.writelines(f'{key}={value}\n' for key, value in values.items())
PY
```

기존 `.env.portfolio`가 있으면 생성 명령은 덮어쓰지 않고 실패한다. MariaDB 데이터베이스 이름은 초기화 SQL에 맞춰 `mockinv`로 고정했다. 기존 DB 볼륨을 유지하면서 비밀번호를 바꾸면 접속할 수 없으므로 같은 파일을 보관한다. 포트 3333을 이미 사용 중이면 파일의 `FRONTEND_PORT`만 빈 포트로 바꾼다.

```bash
docker compose --env-file .env.portfolio -p stock-portfolio-local -f docker-compose.yml -f compose.portfolio.yml --profile local-db config --services
docker compose --env-file .env.portfolio -p stock-portfolio-local -f docker-compose.yml -f compose.portfolio.yml --profile local-db up -d --build --wait
docker compose --env-file .env.portfolio -p stock-portfolio-local -f docker-compose.yml -f compose.portfolio.yml --profile local-db ps
```

`config --services`는 서비스 이름만 출력한다. 전체 `config` 출력에는 비밀번호와 세션 키가 포함되므로 공유하지 않는다. 초기 이미지 빌드에는 시간이 걸릴 수 있다.

서비스는 여섯 개다: `frontend`, `mariadb`, `postgres`, `init`, `python-backend`, `worker`.

- `init`은 테이블 생성(`flask --app app init-db`)과 샘플 데이터 시드(`flask --app app seed-demo`)를 한 번 실행하고 종료 코드 0으로 끝난다.
  - `python-backend`와 `worker`는 `init`이 성공한 뒤에 시작한다.
  - 두 명령은 멱등이라 `up`을 다시 실행해 `init`이 또 돌아도 기존 데이터는 바뀌지 않는다.
- `worker`는 코인 랭킹·업비트 마켓 동기화와 시장 봇 같은 주기 작업을 웹 서버와 분리된 프로세스에서 실행한다.
- 따라서 `ps`에서 `init`이 `Exited (0)`인 것은 정상이다.

## 확인

1. `http://127.0.0.1:3333/`에서 홈 화면을 열고, `http://127.0.0.1:3333/member/login.html`에서 앱 자체 로그인을 확인한다. 포트를 바꿨으면 URL도 바꾼다.
2. `/member/register.html`에서 테스트 전용 계정을 만들고 로그아웃·로그인한다. 새 계정의 초기 가상 현금은 100,000,000원이다.
3. 코인 또는 주식의 **앱 내 모의 주문** 1건을 실행하고 주문 내역·보유자산의 변화를 기록한다. KIS 모의계좌 API 기능은 별도 키가 필요하며 이 범위의 확인 대상이 아니다.
4. 다음 명령으로 DB와 백엔드를 재시작하고 DB 건강 상태가 돌아온 뒤 다시 로그인해 같은 주문 내역과 보유자산이 남아 있는지 확인한다. MariaDB와 PostgreSQL은 프로젝트 전용 named volume을 사용한다.

```bash
docker compose --env-file .env.portfolio -p stock-portfolio-local -f docker-compose.yml -f compose.portfolio.yml --profile local-db restart mariadb postgres
docker compose --env-file .env.portfolio -p stock-portfolio-local -f docker-compose.yml -f compose.portfolio.yml --profile local-db up -d --wait mariadb postgres
docker compose --env-file .env.portfolio -p stock-portfolio-local -f docker-compose.yml -f compose.portfolio.yml --profile local-db restart python-backend
docker compose --env-file .env.portfolio -p stock-portfolio-local -f docker-compose.yml -f compose.portfolio.yml --profile local-db up -d --wait
docker compose --env-file .env.portfolio -p stock-portfolio-local -f docker-compose.yml -f compose.portfolio.yml --profile local-db ps
curl --fail --silent --output /dev/null http://127.0.0.1:3333/api/member/me
```

DB의 healthy 상태와 백엔드 프로세스 준비는 별개다. 마지막 HTTP 확인이 실패하면 초기화가 끝난 뒤 다시 확인한다. 포트를 변경했으면 URL도 맞춘다.

브로커 키 파일, AWS 자격 증명, 호스트 Docker socket은 백엔드에 전달하지 않는다. `KIS_ENVIRONMENT=paper`지만 키가 없으므로 KIS 주문·잔고 기능은 사용할 수 없다. LEAN 버튼도 Docker socket이 없어 동작하지 않는다. Qdrant는 프로세스 메모리를 사용하므로 해당 데이터는 백엔드 재시작 후 보존되지 않는다. `database/quant-postgres.sql`의 퀀트 시세는 교육용 생성 샘플이다. 별도 외부 OHLCV DB의 실제 과거 시세·스키마는 이 로컬 DB에 없으며 `/api/ohlcv-db/*` 집계는 사용할 수 없다. 기존 스케줄러·모의 봇은 실행 중 자체 샘플 데이터를 바꿀 수 있다.

## 종료와 상태

```bash
docker compose --env-file .env.portfolio -p stock-portfolio-local -f docker-compose.yml -f compose.portfolio.yml --profile local-db down
```

`down`은 컨테이너와 네트워크만 내리고 MariaDB·PostgreSQL 볼륨을 보존한다. 데이터 보존이 필요하므로 `down -v`는 사용하지 않는다. 로컬 접속만 허용하도록 프런트엔드 포트는 `127.0.0.1`에 바인딩한다.

2026-09-23 로컬 빌드·실행, 브라우저 가입·로그인·모의 매수, API 모의 매수·매도, 두 DB와 백엔드 재시작 후 데이터 보존을 확인했다. [실행 증거와 남은 문제](docs/evidence/local-run-2026-09-23.md)를 참고한다. AWS 배포는 수행하지 않았다. 이 포크에서는 원본의 자동 운영 배포 워크플로를 제거했다.

2026-09-24에는 앱 팩토리·`init`·`worker` 분리 후 같은 절차(API 가입·로그인·모의 매수, DB와 백엔드 재시작 후 보존)를 다시 확인했다. [기반 작업 검증](docs/evidence/foundation-2026-09-24.md)을 참고한다.
