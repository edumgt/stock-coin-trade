#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
source "${SCRIPT_DIR}/01-env.sh"

kubectl apply -k "${REPO_ROOT}/${KUSTOMIZE_DIR}"
kubectl -n "${APP_NAMESPACE}" set image deployment/k-serve-app app="${ECR_URI}:${IMAGE_TAG}"
kubectl -n "${APP_NAMESPACE}" rollout status deployment/k-serve-app --timeout=300s
