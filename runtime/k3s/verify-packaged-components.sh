#!/usr/bin/env bash
set -euo pipefail

readonly KUBECONFIG_PATH='/etc/rancher/k3s/k3s.yaml'

command -v k3s >/dev/null || { echo 'missing k3s; run runtime/k3s/install-single-node.sh first' >&2; exit 2; }
command -v kubectl >/dev/null || { echo 'missing kubectl; install the k3s client before verifying the cluster' >&2; exit 2; }
[[ -f "$KUBECONFIG_PATH" ]] || { echo "missing k3s kubeconfig at $KUBECONFIG_PATH" >&2; exit 2; }

export KUBECONFIG="$KUBECONFIG_PATH"
kubectl wait --for=condition=Ready node --all --timeout=60s >/dev/null

node_count=$(kubectl get nodes --no-headers | wc -l | tr -d ' ')
[[ "$node_count" == '1' ]] || { echo "expected one k3s node; found $node_count" >&2; exit 2; }

kubectl get storageclass local-path >/dev/null || { echo 'local-path storage class is missing; do not disable the k3s local-path addon' >&2; exit 2; }
kubectl -n kube-system get deployment metrics-server >/dev/null || { echo 'metrics-server is missing; do not disable the k3s metrics-server addon' >&2; exit 2; }

if kubectl -n kube-system get helmchart traefik >/dev/null 2>&1; then
  echo 'Traefik is enabled; reinstall k3s with traefik disabled' >&2
  exit 2
fi
if kubectl -n kube-system get service traefik >/dev/null 2>&1; then
  echo 'Traefik Service is present; remove the enabled Traefik addon before admission' >&2
  exit 2
fi
if kubectl -n kube-system get daemonset svclb-traefik >/dev/null 2>&1; then
  echo 'ServiceLB is enabled; reinstall k3s with servicelb disabled' >&2
  exit 2
fi

echo 'k3s packaged components satisfy the single-node runtime profile'
