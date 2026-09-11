#!/usr/bin/env bash
# 로컬 작업물을 빌드해 ECR에 백업 푸시한다. 커밋하지 않은 변경도 이미지로 남기되,
# 운영이 당겨쓰는 :latest 태그는 건드리지 않고 별도 local-* 태그로만 올린다.
set -euo pipefail

REGION="${AWS_REGION:-ap-northeast-2}"
ACCOUNT_ID="${AWS_ACCOUNT_ID:-086015456585}"
ECR_REGISTRY="$ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

SHA="$(git rev-parse --short HEAD 2>/dev/null || echo nogit)"
DIRTY=""
if [ -n "$(git status --porcelain 2>/dev/null)" ]; then
  DIRTY="-dirty"
fi
TAG="${IMAGE_TAG:-local-$SHA$DIRTY-$(date +%Y%m%d%H%M%S)}"

FRONTEND_IMAGE="$ECR_REGISTRY/stock-coin-trade-frontend"
BACKEND_IMAGE="$ECR_REGISTRY/stock-coin-trade-python-backend"

echo "[1/5] ECR 저장소 존재 확인 (없으면 생성)"
for repo in stock-coin-trade-frontend stock-coin-trade-python-backend; do
  aws ecr describe-repositories --region "$REGION" --repository-names "$repo" >/dev/null 2>&1 \
    || aws ecr create-repository --region "$REGION" --repository-name "$repo" >/dev/null
done

echo "[2/5] ECR 로그인 — $ECR_REGISTRY"
aws ecr get-login-password --region "$REGION" | \
  docker login --username AWS --password-stdin "$ECR_REGISTRY"

echo "[3/5] frontend 이미지 빌드 — $FRONTEND_IMAGE:$TAG"
docker build -f docker/frontend.Dockerfile -t "$FRONTEND_IMAGE:$TAG" .

echo "[4/5] python-backend 이미지 빌드 — $BACKEND_IMAGE:$TAG"
docker build -f docker/python-backend.Dockerfile -t "$BACKEND_IMAGE:$TAG" .

echo "[5/5] ECR 백업 푸시"
docker push "$FRONTEND_IMAGE:$TAG"
docker push "$BACKEND_IMAGE:$TAG"

echo "완료 — 백업 태그: $TAG"
echo "  $FRONTEND_IMAGE:$TAG"
echo "  $BACKEND_IMAGE:$TAG"
