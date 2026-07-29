# Live benchmark run

Run this on the declared remote Linux host after the chart is Ready. The
Project Repository owns the client and fixed workload classes; this directory
owns the monitoring queries and Evidence Package shape.

```sh
kubectl -n llm-inference port-forward svc/llm-inference 8000:8000
helm history llm-inference --namespace llm-inference
kubectl -n monitoring port-forward svc/monitoring-kube-prometheus-prometheus 9090:9090
kubectl -n monitoring port-forward svc/monitoring-grafana 3000:80
uv run python -m llm_inference_lab.inference.benchmark \
  --profile /tmp/phase-1-default.json \
  --base-url http://127.0.0.1:8000/v1 \
  --runtime-context /tmp/phase-1-runtime-context.json \
  --output /tmp/llm-inference-evidence.json
```

The runtime context JSON must contain the chart name/version, Helm release
revision, `hardware_class` (for example `rtx-3080-12gb`), and sanitized GPU
memory/utilization measurements. Take the GPU sample on the host without
copying the raw output into Git:

```sh
nvidia-smi --query-gpu=memory.used,utilization.gpu \
  --format=csv,noheader,nounits
```

Capture the model listing, image digest,
request JSON, p50/p95, TTFT, ITL/TPOT, output throughput, error count, and
selected Prometheus queries in the Evidence Package. Run the same workload at
concurrency 1; do not mix the manual IFEval result into latency statistics or
CI status. The resulting file stays outside Git until it is sanitized.
