#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
REPO_ROOT=$(cd "${SCRIPT_DIR}/../.." && pwd)
TARGET_ENV="${1:-local}"
ENV_FILE="${SCRIPT_DIR}/env/${TARGET_ENV}.sh"

if [[ ! -f "${ENV_FILE}" ]]; then
    echo "unknown environment: ${TARGET_ENV}" >&2
    exit 1
fi

source "${ENV_FILE}"

pushd "${REPO_ROOT}" >/dev/null

case "${DEPLOY_MODE}" in
    docker-compose)
        docker compose up -d --build
        ;;
    k8s-dev)
        docker build -t python-k-serve-app:dev -f docker/python-backend.Dockerfile .
        kubectl apply -k "${KUSTOMIZE_DIR}"
        kubectl -n "${K8S_NAMESPACE}" rollout status deployment/k-serve-app --timeout=300s
        ;;
    eks)
        export AWS_REGION
        export CLUSTER_NAME
        export APP_NAMESPACE
        export ECR_REPO
        export IMAGE_TAG
        export KUSTOMIZE_DIR
        "${REPO_ROOT}/scripts/aws/03-build-push-image.sh"
        "${REPO_ROOT}/scripts/aws/04-deploy.sh"
        ;;
    *)
        echo "unsupported DEPLOY_MODE: ${DEPLOY_MODE}" >&2
        exit 1
        ;;
esac

popd >/dev/null

echo "Deployment finished for ${TARGET_ENV}."
