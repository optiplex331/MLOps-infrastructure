# Minimal observability

This directory contains the port-forward-only observation surface for the
single-node lab: Prometheus, Grafana, one vLLM dashboard, and NVIDIA DCGM
Exporter. It deliberately excludes Alertmanager, default dashboards and
rules, recording rules, SLOs, long retention, high availability,
`kube-state-metrics`, and node exporter.

Run these commands only on the declared remote Linux host. The versions file
pins both upstream charts; do not replace them with an unversioned install.

```sh
set -a
. observability/chart-versions.env
set +a
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo add nvidia https://nvidia.github.io/dcgm-exporter/helm-charts
helm repo update
kubectl create namespace monitoring --dry-run=client -o yaml | kubectl apply -f -
kubectl -n monitoring create secret generic monitoring-grafana \
  --from-literal admin-user admin \
  --from-literal admin-password "$(openssl rand -base64 24)" \
  --dry-run=client -o yaml | kubectl apply -f -
helm upgrade --install monitoring prometheus-community/kube-prometheus-stack \
  --namespace monitoring --create-namespace \
  --version "$KUBE_PROMETHEUS_STACK_CHART_VERSION" \
  --values observability/helm-values.yaml
helm upgrade --install dcgm-exporter nvidia/dcgm-exporter \
  --namespace monitoring \
  --version "$DCGM_EXPORTER_CHART_VERSION" \
  --values observability/dcgm-exporter-values.yaml
kubectl apply -k observability/manifests
```

The stack chart provisions Grafana's Prometheus datasource. The checked-in
ConfigMap provisions exactly one lab dashboard, and the ServiceMonitor
discovers the vLLM service. DCGM Exporter's chart owns its ServiceMonitor.
The Grafana password is created on the remote host and never written to Git.
Nothing exposes an ingress or claims a production monitoring capability.

`bin/check-observability` is the offline CI boundary: it checks pinned chart
versions, minimal values, vLLM scrape integration, valid dashboard JSON, and
the required raw Prometheus queries. It does not contact a chart repository,
cluster, Prometheus, Grafana, vLLM, or GPU. Follow
[`run-live-benchmark.md`](run-live-benchmark.md) for the required live checks.
