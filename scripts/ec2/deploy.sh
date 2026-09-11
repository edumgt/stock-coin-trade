#!/usr/bin/env bash
set -euo pipefail

# EC2 인스턴스의 저장소 루트에서 실행한다. 소스에서 빌드하지 않고 ECR에
# CI가 미리 푸시해 둔 이미지를 당겨와 실행한다(ECR_REGISTRY/IMAGE_TAG는
# .env 또는 환경변수로 재정의 가능, 기본값은 stock-coin-trade ECR:latest).
REGION="${AWS_REGION:-ap-northeast-2}"
aws ecr get-login-password --region "$REGION" | \
  docker login --username AWS --password-stdin "${ECR_REGISTRY:-086015456585.dkr.ecr.$REGION.amazonaws.com}"

docker compose -f docker-compose.yml -f docker-compose.prod.yml pull
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --no-build --remove-orphans
docker compose ps
