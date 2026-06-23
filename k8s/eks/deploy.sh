#!/usr/bin/env bash
# EKS 전체 배포 스크립트
# 사전 조건: info-pro 계정에 AmazonEKSFullAccess + IAMFullAccess + CloudFormationFullAccess 추가

set -euo pipefail

REGION="ap-northeast-2"
CLUSTER_NAME="crypto-mock"
ACCOUNT_ID="086015456585"
ECR_URI="${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/java-crypto-mock"
NAMESPACE="crypto-mock"

echo "=== 1. EKS 클러스터 생성 ==="
eksctl create cluster -f "$(dirname "$0")/cluster-config.yaml"

echo "=== 2. kubeconfig 업데이트 ==="
aws eks update-kubeconfig --region "${REGION}" --name "${CLUSTER_NAME}"

echo "=== 3. AWS Load Balancer Controller 설치 ==="
# OIDC 프로바이더 확인
eksctl utils associate-iam-oidc-provider \
  --region "${REGION}" \
  --cluster "${CLUSTER_NAME}" \
  --approve

# LBC IAM Policy 생성
curl -fsSL -o /tmp/iam-policy.json \
  https://raw.githubusercontent.com/kubernetes-sigs/aws-load-balancer-controller/v2.7.2/docs/install/iam_policy.json

aws iam create-policy \
  --policy-name AWSLoadBalancerControllerIAMPolicy \
  --policy-document file:///tmp/iam-policy.json 2>/dev/null || echo "Policy already exists"

# LBC Service Account 생성
eksctl create iamserviceaccount \
  --cluster="${CLUSTER_NAME}" \
  --namespace=kube-system \
  --name=aws-load-balancer-controller \
  --role-name AmazonEKSLoadBalancerControllerRole \
  --attach-policy-arn="arn:aws:iam::${ACCOUNT_ID}:policy/AWSLoadBalancerControllerIAMPolicy" \
  --approve

# Helm으로 LBC 설치
helm repo add eks https://aws.github.io/eks-charts
helm repo update
helm upgrade --install aws-load-balancer-controller eks/aws-load-balancer-controller \
  -n kube-system \
  --set clusterName="${CLUSTER_NAME}" \
  --set serviceAccount.create=false \
  --set serviceAccount.name=aws-load-balancer-controller

echo "LBC 준비 대기 (60초)..."
kubectl rollout status deployment/aws-load-balancer-controller -n kube-system --timeout=120s

echo "=== 4. ECR 이미지 최신화 ==="
aws ecr get-login-password --region "${REGION}" | \
  docker login --username AWS --password-stdin "${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com"
docker build -t "${ECR_URI}:latest" -f docker/java-backend.Dockerfile .
docker push "${ECR_URI}:latest"

echo "=== 5. k8s 리소스 배포 ==="
kubectl apply -k "$(dirname "$0")"

echo "=== 6. 배포 완료 확인 ==="
kubectl rollout status deployment/crypto-mock-app -n "${NAMESPACE}" --timeout=180s
kubectl get all -n "${NAMESPACE}"
kubectl get ingress -n "${NAMESPACE}"

echo ""
echo "=== ALB 주소 ==="
kubectl get ingress crypto-mock-ingress -n "${NAMESPACE}" \
  -o jsonpath='{.status.loadBalancer.ingress[0].hostname}'
echo ""
echo "배포 완료!"
