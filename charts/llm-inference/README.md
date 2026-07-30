# Minimal Qwen3 inference chart

This chart owns one Helm release for the Phase 1 single-node k3s lab:

- namespace `llm-inference` and release `llm-inference`;
- one `Recreate` Deployment replica requesting exactly one `nvidia.com/gpu`;
- one `ClusterIP` Service on port `8000`;
- one `local-path` `ReadWriteOnce` model-cache PVC requesting `20Gi`;
- one least-privilege ServiceAccount with token automount disabled;
- Prometheus scrape discovery annotations controlled by Helm values;
- a non-root serving container with an explicit `RuntimeDefault` seccomp
  profile and PVC `fsGroup` ownership.

The chart does not create the namespace. This keeps the namespace and its
model-cache lifecycle outside normal Helm uninstall. The PVC has
`helm.sh/resource-policy: keep`, so an uninstall leaves the cache available
for inspection or an explicitly approved cleanup.

## Install

The default values directly pin the official `vllm/vllm-openai` image by
digest and `Qwen/Qwen3-4B-AWQ` by Hugging Face commit:

```sh
helm upgrade --install llm-inference ./charts/llm-inference \
  --namespace llm-inference \
  --create-namespace
```

The image is consumed as `repository@sha256:digest`; tags and a custom wrapper
are not used. The default serving profile is
`max_model_len=4096`, `max_num_seqs=1`, `max_new_tokens=512`, and
`gpu_memory_utilization=0.85`.

## Speculative decoding experiment

Keep the default AWQ release unchanged. Run the draft-model experiment as a
separate release and namespace with an exact draft revision:

```sh
helm upgrade --install llm-inference-speculative ./charts/llm-inference \
  --namespace llm-inference-speculative \
  --create-namespace \
  --set-string namespace=llm-inference-speculative \
  --set-string fullnameOverride=llm-inference-speculative \
  --set speculativeDecoding.enabled=true \
  --set-string speculativeDecoding.draftModel.revision=<40-lowercase-hex-draft-commit>
```

The pinned vLLM build may reject a generic Qwen draft model. Treat that direct
compatibility failure as an experiment result; do not alter the default
release or infer acceptance metrics when the server never becomes Ready.

## Inspect, access, and rollback

The API contract used by the probes and smoke checks is:

| Purpose | Endpoint |
| --- | --- |
| Process/API health | `GET /health` |
| Model readiness | `GET /v1/models` |
| Chat inference | `POST /v1/chat/completions` |

```sh
helm history llm-inference --namespace llm-inference
kubectl get all,pvc -n llm-inference -l app.kubernetes.io/instance=llm-inference
kubectl port-forward -n llm-inference svc/llm-inference 8000:8000
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/v1/models

helm upgrade llm-inference ./charts/llm-inference \
  --namespace llm-inference \
  --reuse-values \
  --set serving.maxModelLen=3072
helm rollback llm-inference <known-good-revision> --namespace llm-inference
```

The chat smoke request must use the model ID returned by `/v1/models` and set
`max_tokens: 512`. The chart does not run model requests during rendering or
CI. The `ConfigMap` records the serving defaults and endpoint contract for
clients and evidence capture.

`local-path` storage is node-local and not portable between nodes. A `20Gi`
PVC request is a storage request, not a hard disk quota. This chart is a
single-node learning deployment; it does not provide ingress, autoscaling,
multi-GPU serving, or production traffic management.

## Runtime evidence

Live API smoke, upgrade, and rollback evidence must run on the declared remote
Linux validation host after host preflight succeeds. Local and CI checks
remain CPU-safe and only lint, render, and inspect the chart.
