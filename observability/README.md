# Phase 1 observability

This directory contains the small, port-forward-only observation surface for
the single-node lab. Install the pinned `kube-prometheus-stack` chart version
listed in `helm-values.yaml`, then apply the candidate-owned resources:

```sh
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update
kubectl create namespace monitoring --dry-run=client -o yaml | kubectl apply -f -
kubectl -n monitoring create secret generic monitoring-grafana \
  --from-literal admin-user admin \
  --from-literal admin-password "$(openssl rand -base64 24)" \
  --dry-run=client -o yaml | kubectl apply -f -
helm upgrade --install monitoring prometheus-community/kube-prometheus-stack \
  --namespace monitoring --create-namespace \
  --version 70.4.2 --values observability/helm-values.yaml
kubectl apply -k observability/manifests
kubectl -n monitoring port-forward svc/monitoring-grafana 3000:80
kubectl -n monitoring port-forward svc/monitoring-kube-prometheus-prometheus 9090:9090
```

The chart supplies the collectors; the manifests here own the vLLM scrape,
recording rules, and dashboard. The Grafana password is created on the remote
host and never written to Git. GPU VRAM/utilization are captured as sanitized
`nvidia-smi` context by the Project Repository benchmark; DCGM exporter is not
a Phase 1 dependency. These resources do not expose an ingress or publish a
production SLO. A live Evidence Package is created by the remote benchmark
run and is not checked into this repository.
