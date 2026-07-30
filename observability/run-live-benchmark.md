# Live benchmark run

Run this on the declared remote Linux host after both pinned charts and the
vLLM release are Ready. The Project Repository owns the client and fixed
workload classes. These checks intentionally use HTTP APIs and `kubectl`; no
browser automation is needed.

```sh
kubectl -n llm-inference port-forward svc/llm-inference 8000:8000
helm history llm-inference --namespace llm-inference
kubectl -n monitoring port-forward svc/monitoring-kube-prometheus-prometheus 9090:9090
kubectl -n monitoring port-forward svc/monitoring-grafana 3000:80
uv run python -m llm_inference_lab.inference.benchmark \
  --base-url http://127.0.0.1:8000/v1 \
  --model Qwen/Qwen3-4B-AWQ \
  --workload data/benchmark/workload.jsonl \
  --concurrency 1 \
  --repetitions 3 \
  --output /tmp/llm-inference-benchmark.json
```

After the benchmark has produced traffic, verify both scrape targets through
the Prometheus API:

```sh
curl --fail --silent --get \
  --data-urlencode 'state=active' \
  http://127.0.0.1:9090/api/v1/targets > /tmp/prometheus-targets.json
curl --fail --silent --get \
  --data-urlencode 'query=sum(rate(vllm:request_success_total[5m]))' \
  http://127.0.0.1:9090/api/v1/query
curl --fail --silent --get \
  --data-urlencode 'query=histogram_quantile(0.95, sum by (le) (rate(vllm:e2e_request_latency_seconds_bucket[5m])))' \
  http://127.0.0.1:9090/api/v1/query
curl --fail --silent --get \
  --data-urlencode 'query=sum(rate(vllm:prompt_tokens_total[5m])) + sum(rate(vllm:generation_tokens_total[5m]))' \
  http://127.0.0.1:9090/api/v1/query
curl --fail --silent --get \
  --data-urlencode 'query=avg(DCGM_FI_DEV_GPU_UTIL)' \
  http://127.0.0.1:9090/api/v1/query
curl --fail --silent --get \
  --data-urlencode 'query=sum(DCGM_FI_DEV_FB_USED)' \
  http://127.0.0.1:9090/api/v1/query
```

Inspect `/tmp/prometheus-targets.json` outside Git and require healthy vLLM
and DCGM targets. Every query response must have `"status":"success"` and a
non-empty result. If the pinned vLLM version exposes renamed metric families,
record the actual names and update the dashboard and offline contract together
instead of adding fallback queries.

Verify Grafana health, its Prometheus datasource, and the provisioned dashboard
through the API:

```sh
grafana_user=$(kubectl -n monitoring get secret monitoring-grafana \
  -o jsonpath='{.data.admin-user}' | base64 --decode)
grafana_password=$(kubectl -n monitoring get secret monitoring-grafana \
  -o jsonpath='{.data.admin-password}' | base64 --decode)
curl --fail --silent http://127.0.0.1:3000/api/health
curl --fail --silent --user "$grafana_user:$grafana_password" \
  http://127.0.0.1:3000/api/datasources
curl --fail --silent --user "$grafana_user:$grafana_password" \
  http://127.0.0.1:3000/api/datasources/uid/prometheus/health
curl --fail --silent --user "$grafana_user:$grafana_password" \
  http://127.0.0.1:3000/api/dashboards/uid/llm-inference-lab
unset grafana_user grafana_password
```

Require a healthy database, one Prometheus datasource, and dashboard UID
`llm-inference-lab`. Do not save API responses or credentials in Git.

The runtime context JSON must contain the chart name/version, Helm release
revision, `hardware_class` (for example `rtx-3080-12gb`), and sanitized GPU
memory/utilization measurements. Take the GPU sample on the host without
copying the raw output into Git:

```sh
nvidia-smi --query-gpu=memory.used,utilization.gpu \
  --format=csv,noheader,nounits
```

Capture the model listing, image digest, request observations, p50/p95 TTFT and
latency, output-token rate, request throughput, error count, and selected
Prometheus queries in the runtime output. Do not mix the manual IFEval result
into latency statistics or CI status. Raw files stay outside Git; publish only
the necessary sanitized aggregate observations in the Project Repository's
`lab-result.json`.
