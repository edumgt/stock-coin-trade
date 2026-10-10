# Lightsail 공개 데모 운영

2026-09-28부터 공개 데모는 Amazon Lightsail 인스턴스 한 대에서 돈다. 포트폴리오 두 개(이 저장소와 비공개 실험실 앱)를 같은 서버에 올려 월 비용을 $12로 고정했다. 이전 EC2 구성은 [AWS 배포 절차](aws.md)와 [ADR-0003](../adr/0003-aws-demo-topology.md)에 기록으로 남긴다. 옮긴 과정과 검증은 [이전 기록](../evidence/lightsail-migration-2026-09-28.md)에 있다.

## 구성

| 항목 | 값 |
|---|---|
| 인스턴스 | `noah-portfolio`, 서울 `ap-northeast-2a`, 번들 `small_3_0`(2 GB RAM, 2 vCPU, 60 GB SSD, 전송 3 TB, 월 $12) |
| 고정 IP | `13.124.251.180`(`noah-portfolio-ip`, 인스턴스에 붙어 있으면 무료) |
| OS | Ubuntu 24.04, Docker Engine + Compose v2, 스왑 2 GB, 컨테이너 로그 json-file 10 MB×3 |
| 방화벽 | 80, 443(TCP·UDP) 전체 공개. 22는 관리자 IP만 |
| 주소 | stockdesk `https://13-124-251-180.sslip.io`, 금융상식 랩 `https://lab.13-124-251-180.sslip.io` |

- Caddy 하나가 80·443을 열고 두 호스트명의 인증서(Let's Encrypt)를 받는다. 랩 앱은 호스트 8000번에서 돌고, 8000번은 Lightsail 방화벽에서 막혀 있다.
- stockdesk Compose는 `docker-compose.yml` + `compose.public.yml` + `compose.edge.yml` + [`compose.lightsail.yml`](../../compose.lightsail.yml)이다. `compose.lightsail.yml`은 ECR 대신 로컬 태그 이미지(`stockdesk/*:<SHA>`)를 쓰고, Caddy에 [`docker/Caddyfile.lightsail`](../../docker/Caddyfile.lightsail)(랩 호스트 블록 추가)을 붙인다.
- 서버 경로: 릴리스 `/opt/stockdesk/releases/<SHA>/`, 비밀값 `/opt/stockdesk/app.env`(0600), 래퍼 `/opt/stockdesk/compose.sh` → [`scripts/lightsail/compose.sh`](../../scripts/lightsail/compose.sh). 랩은 `/opt/lab/compose.yml`.
- 재부팅하면 Docker와 두 Compose 앱이 `restart: unless-stopped`로 다시 뜬다.

## 자주 쓰는 명령

```bash
ssh ubuntu@13.124.251.180
sudo /opt/stockdesk/compose.sh ps
sudo /opt/stockdesk/compose.sh logs -f --tail 100 python-backend
cd /opt/lab && sudo docker compose -p ai-quant-8th-advisor-lab -f compose.yml ps
```

## 새 릴리스 올리기(수동)

EC2 시절의 GitHub Deploy 워크플로(OIDC → ECR → SSM)는 대상 자원을 지웠으므로 더 이상 동작하지 않는다. 포트폴리오 용도라 배포는 드물게 손으로 한다.

1. Mac에서 amd64 이미지를 만들어 서버로 바로 보낸다(레지스트리 없음).
   ```bash
   sha=$(git rev-parse HEAD)
   docker buildx build --platform linux/amd64 --build-arg GIT_SHA=$sha -f docker/python-backend.Dockerfile -t stockdesk/python-backend:$sha --load .
   docker buildx build --platform linux/amd64 -f docker/frontend.Dockerfile -t stockdesk/frontend:$sha --load .
   docker save stockdesk/python-backend:$sha stockdesk/frontend:$sha | gzip -1 | ssh ubuntu@13.124.251.180 'gunzip | sudo docker load'
   ```
2. 릴리스 폴더를 올린다: `git archive $sha docker-compose.yml compose.public.yml compose.edge.yml compose.lightsail.yml docker database scripts | ssh ubuntu@13.124.251.180 "sudo mkdir -p /opt/stockdesk/releases/$sha && sudo tar -x -C /opt/stockdesk/releases/$sha"`
3. 서버에서 DB를 먼저 백업하고(아래), `/opt/stockdesk/compose.sh`의 `IMAGE_TAG`를 새 SHA로 바꾼 뒤 `sudo /opt/stockdesk/compose.sh up -d`.
4. `curl -fsS https://13-124-251-180.sslip.io/health`가 `{"status":"ok"}`인지 본다. 문제가 있으면 `IMAGE_TAG`를 이전 SHA로 되돌리고 다시 `up -d`한다(이전 이미지와 릴리스 폴더를 지우기 전까지 가능).

## 백업

자동 백업은 두지 않았다(최소 구성). 바꾸기 전에 손으로 덤프를 받는다. 비밀값은 컨테이너 안에서만 쓴다.

```bash
sudo mkdir -p /opt/stockdesk/backups && cd /opt/stockdesk/backups
ts=$(date -u +%Y%m%dT%H%M%SZ)
sudo docker exec stockdesk-mariadb-1 sh -c 'MYSQL_PWD="$MARIADB_PASSWORD" exec mariadb-dump -u"$MARIADB_USER" --single-transaction --no-tablespaces mockinv' | gzip | sudo tee mariadb-$ts.sql.gz >/dev/null
sudo docker exec stockdesk-postgres-1 sh -c 'exec pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' | sudo tee postgres-$ts.dump >/dev/null
```

- 복원: MariaDB는 `gunzip -c ... | docker exec -i <mariadb> sh -c 'MYSQL_PWD="$MARIADB_ROOT_PASSWORD" exec mariadb -uroot mockinv'`.
- PostgreSQL은 새 컨테이너가 `database/` 초기화 스크립트로 스키마와 샘플을 먼저 만든다. 그래서 `DROP SCHEMA public CASCADE; CREATE SCHEMA public;` 뒤에 `pg_restore --no-owner --no-privileges --single-transaction --exit-on-error`로 넣는다(`--clean`은 파티션 기본키에서 실패한다).
- 행 수 대조는 `scripts/ec2/db-counts.sh`의 `live_counts`·`compare_counts`를 그대로 쓸 수 있다(컨테이너를 Compose 라벨로 찾는다).
- 서버 전체 보관이 필요하면 Lightsail 콘솔에서 수동 스냅샷을 만든다(GB당 월 $0.05).

## 도메인을 살 때

A 레코드를 `13.124.251.180`으로 걸고 `/opt/stockdesk/compose.sh`에서 `SITE_ADDRESS`(필요하면 `LAB_ADDRESS`)를 바꾼 뒤 `up -d caddy`. Caddy가 새 인증서를 받는다.
