#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
REPO_ROOT=$(cd "${SCRIPT_DIR}/../.." && pwd)
TARGET_ENV="${1:-local}"
ENV_FILE="${SCRIPT_DIR}/env/${TARGET_ENV}.sh"
PYTHON_CMD="${PYTHON_CMD:-python3}"

if [[ ! -f "${ENV_FILE}" ]]; then
    echo "unknown environment: ${TARGET_ENV}" >&2
    exit 1
fi

source "${ENV_FILE}"

command -v "${PYTHON_CMD}" >/dev/null 2>&1 || {
    echo "missing command: ${PYTHON_CMD}" >&2
    exit 1
}

pushd "${REPO_ROOT}" >/dev/null
"${PYTHON_CMD}" -m py_compile python-stock-backend/*.py

case "${DEPLOY_MODE}" in
    docker-compose)
        command -v docker >/dev/null 2>&1 || {
            echo "missing command: docker" >&2
            exit 1
        }
        docker compose config >/dev/null
        ;;
    k8s-dev)
        command -v kubectl >/dev/null 2>&1 || {
            echo "missing command: kubectl" >&2
            exit 1
        }
        kubectl kustomize "${KUSTOMIZE_DIR}" >/dev/null
        ;;
    eks)
        command -v kubectl >/dev/null 2>&1 || {
            echo "missing command: kubectl" >&2
            exit 1
        }
        kubectl kustomize "${KUSTOMIZE_DIR}" >/dev/null
        ;;
    *)
        echo "unsupported DEPLOY_MODE: ${DEPLOY_MODE}" >&2
        exit 1
        ;;
esac
popd >/dev/null

echo "CI checks passed for ${TARGET_ENV}."
