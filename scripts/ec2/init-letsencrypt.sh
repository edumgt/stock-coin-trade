#!/usr/bin/env bash
set -euo pipefail

# AWS EC2에서 1회 실행한다. Let's Encrypt 인증서를 발급하고 TLS 오버레이로
# 스택을 재기동한 뒤, 무중단 자동 갱신(webroot)을 등록한다.
#
# 사용:
#   sudo scripts/ec2/init-letsencrypt.sh
#
# 사전 조건:
#   - DNS: st.edumgt.co.kr 가 이 서버(EIP)를 가리켜야 한다.
#   - 보안그룹: 80, 443 인바운드 허용.
#   - .env: FRONTEND_PORT=80

DOMAIN="${DOMAIN:-st.edumgt.co.kr}"
PROJECT="${COMPOSE_PROJECT:-stock-coin-trade}"
ROOT="${ROOT:-/opt/stock-coin-trade}"
CONF_DIR="$ROOT/certbot/conf"
WWW_DIR="$ROOT/certbot/www"

cd "$ROOT"
mkdir -p "$CONF_DIR" "$WWW_DIR"

if [ -f "$CONF_DIR/live/$DOMAIN/fullchain.pem" ]; then
  echo "[init] 인증서가 이미 존재합니다: $CONF_DIR/live/$DOMAIN"
else
  echo "[init] standalone 방식으로 최초 인증서를 발급합니다 (frontend 80 잠시 중지)."
  docker compose -p "$PROJECT" stop frontend || true
  docker run --rm -p 80:80 \
    -v "$CONF_DIR:/etc/letsencrypt" \
    -v "$WWW_DIR:/var/www/certbot" \
    certbot/certbot certonly --standalone \
    -d "$DOMAIN" --agree-tos --register-unsafely-without-email -n

  # 이후 갱신은 무중단(webroot)으로 하도록 renewal 설정을 전환한다.
  RENEWAL="$CONF_DIR/renewal/$DOMAIN.conf"
  if [ -f "$RENEWAL" ]; then
    sed -i 's/^authenticator = .*/authenticator = webroot/' "$RENEWAL"
    grep -q '^webroot_path' "$RENEWAL" \
      && sed -i 's#^webroot_path = .*#webroot_path = /var/www/certbot,#' "$RENEWAL" \
      || echo 'webroot_path = /var/www/certbot,' >> "$RENEWAL"
    if ! grep -q '^\[\[webroot_map\]\]' "$RENEWAL"; then
      printf '[[webroot_map]]\n%s = /var/www/certbot\n' "$DOMAIN" >> "$RENEWAL"
    fi
  fi
fi

echo "[init] TLS 오버레이로 스택을 기동합니다."
docker compose -p "$PROJECT" -f docker-compose.yml -f docker-compose.ssl.yml up -d

echo "[init] 자동 갱신 cron 을 등록합니다 (매일 03:15, webroot 무중단)."
CRON_LINE="15 3 * * * docker run --rm -v $CONF_DIR:/etc/letsencrypt -v $WWW_DIR:/var/www/certbot certbot/certbot renew -q && docker exec crypto-mock-frontend nginx -s reload"
( crontab -l 2>/dev/null | grep -v 'certbot/certbot renew' ; echo "$CRON_LINE" ) | crontab -

echo "[init] 완료. https://$DOMAIN 확인하세요."
