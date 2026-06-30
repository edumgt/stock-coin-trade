#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
REPO_ROOT=$(cd "${SCRIPT_DIR}/../.." && pwd)

: "${AWS_REGION:=ap-northeast-2}"
: "${CLUSTER_NAME:=crypto-mock-eks}"
: "${APP_NAMESPACE:=crypto-mock}"
: "${ECR_REPO:=python-crypto-mock}"
: "${IMAGE_TAG:=$(date +%Y%m%d%H%M%S)}"
: "${KUSTOMIZE_DIR:=k8s/eks}"

for cmd in aws eksctl kubectl docker; do
    command -v "${cmd}" >/dev/null 2>&1 || {
        echo "missing command: ${cmd}" >&2
        exit 1
    }
done

if [[ -z "${AWS_ACCOUNT_ID:-}" ]]; then
    AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
fi

ECR_URI="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPO}"

export SCRIPT_DIR
export REPO_ROOT
export AWS_REGION
export CLUSTER_NAME
export APP_NAMESPACE
export ECR_REPO
export IMAGE_TAG
export AWS_ACCOUNT_ID
export ECR_URI
export KUSTOMIZE_DIR

printf 'AWS_REGION=%s\n' "${AWS_REGION}"
printf 'CLUSTER_NAME=%s\n' "${CLUSTER_NAME}"
printf 'APP_NAMESPACE=%s\n' "${APP_NAMESPACE}"
printf 'ECR_REPO=%s\n' "${ECR_REPO}"
printf 'IMAGE_TAG=%s\n' "${IMAGE_TAG}"
printf 'ECR_URI=%s\n' "${ECR_URI}"
printf 'KUSTOMIZE_DIR=%s\n' "${KUSTOMIZE_DIR}"
