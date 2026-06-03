#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP_PROPS="$ROOT_DIR/java-backend/src/main/resources/application.properties"
SQL_FILE="$ROOT_DIR/database/db.sql"

CONTAINER_NAME="${DB_CONTAINER_NAME:-crypto-mariadb}"
ROOT_PASSWORD="${DB_ROOT_PASSWORD:-123456}"
DB_NAME="${DB_NAME:-mockinv}"
APP_USER="${DB_USER:-mockinv}"
APP_PASSWORD="${DB_PASSWORD:-mockinv1234}"
HOST_PORT="${DB_PORT:-3306}"
MARIADB_IMAGE="${MARIADB_IMAGE:-mariadb:11.4}"

if [[ "${1:-}" == "--help" ]]; then
  cat <<USAGE
Usage: $(basename "$0")

Runs MariaDB in Docker, imports db.sql, and rewrites application.properties
for local Docker DB connection.

Environment overrides:
  DB_CONTAINER_NAME  (default: crypto-mariadb)
  DB_ROOT_PASSWORD   (default: 123456)
  DB_NAME            (default: mockinv)
  DB_USER            (default: mockinv)
  DB_PASSWORD        (default: mockinv1234)
  DB_PORT            (default: 3306)
  MARIADB_IMAGE      (default: mariadb:11.4)
USAGE
  exit 0
fi

if ! command -v docker >/dev/null 2>&1; then
  echo "[ERROR] docker command not found." >&2
  exit 1
fi

if [[ ! -f "$SQL_FILE" ]]; then
  echo "[ERROR] db.sql not found at $SQL_FILE" >&2
  exit 1
fi

if [[ ! -f "$APP_PROPS" ]]; then
  echo "[ERROR] application.properties not found at $APP_PROPS" >&2
  exit 1
fi

container_exists() {
  docker ps -a --format '{{.Names}}' | grep -qx "$CONTAINER_NAME"
}

container_running() {
  docker ps --format '{{.Names}}' | grep -qx "$CONTAINER_NAME"
}

if container_exists; then
  if ! container_running; then
    echo "[INFO] Starting existing container: $CONTAINER_NAME"
    docker start "$CONTAINER_NAME" >/dev/null
  else
    echo "[INFO] Container already running: $CONTAINER_NAME"
  fi
else
  echo "[INFO] Creating MariaDB container: $CONTAINER_NAME"
  docker run -d \
    --name "$CONTAINER_NAME" \
    -e MARIADB_ROOT_PASSWORD="$ROOT_PASSWORD" \
    -p "$HOST_PORT":3306 \
    "$MARIADB_IMAGE" >/dev/null
fi

echo "[INFO] Waiting for MariaDB to become healthy..."
for _ in $(seq 1 60); do
  if docker exec "$CONTAINER_NAME" mariadb-admin ping -uroot -p"$ROOT_PASSWORD" --silent >/dev/null 2>&1; then
    break
  fi
  sleep 2
done

if ! docker exec "$CONTAINER_NAME" mariadb-admin ping -uroot -p"$ROOT_PASSWORD" --silent >/dev/null 2>&1; then
  echo "[ERROR] MariaDB did not start in time." >&2
  exit 1
fi

echo "[INFO] Ensuring database/user exists..."
docker exec -i "$CONTAINER_NAME" mariadb -uroot -p"$ROOT_PASSWORD" <<SQL
CREATE DATABASE IF NOT EXISTS \
  \\`$DB_NAME\\` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS '$APP_USER'@'%' IDENTIFIED BY '$APP_PASSWORD';
GRANT ALL PRIVILEGES ON \\`$DB_NAME\\`.* TO '$APP_USER'@'%';
FLUSH PRIVILEGES;
SQL

echo "[INFO] Importing db.sql into $DB_NAME ..."
docker exec -i "$CONTAINER_NAME" mariadb -u"$APP_USER" -p"$APP_PASSWORD" "$DB_NAME" < "$SQL_FILE"

upsert_prop() {
  local key="$1"
  local value="$2"

  if grep -qE "^${key}=" "$APP_PROPS"; then
    sed -i "s|^${key}=.*|${key}=${value}|" "$APP_PROPS"
  else
    echo "${key}=${value}" >> "$APP_PROPS"
  fi
}

echo "[INFO] Updating application.properties for local Docker DB..."
upsert_prop "spring.datasource.driver-class-name" "org.mariadb.jdbc.Driver"
upsert_prop "spring.datasource.url" "jdbc:mariadb://localhost:${HOST_PORT}/${DB_NAME}?useUnicode=true&characterEncoding=utf8"
upsert_prop "spring.datasource.username" "$APP_USER"
upsert_prop "spring.datasource.password" "$APP_PASSWORD"
upsert_prop "spring.jpa.hibernate.ddl-auto" "update"

echo "[DONE] Docker DB is ready and application.properties has been updated."
echo "       Run the app with: mvn spring-boot:run"
