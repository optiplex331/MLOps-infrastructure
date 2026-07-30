# Live lab seam

This runbook composes ordinary remote shell commands; it is not a workflow
engine. Run it only on the declared Linux GPU host. Keep every generated file
under `/tmp/llm-inference-lab` (or another ignored, non-Git runtime directory).
Never copy prompts, credentials, kubeconfigs, model caches, or raw logs into
either repository.

From the local Workbench, open an ordinary remote shell and execute the
following stages there:

```sh
ssh zeng-linux-pc
```

Set the two checkout paths, create the runtime directory, and synchronize
before starting either mode:

```sh
export PROJECT_DIR="$HOME/Projects/mlops-lab/llm-inference-lab"
export INFRASTRUCTURE_DIR="$HOME/Projects/mlops-lab/llm-inference-lab-infra"
export LAB_OUTPUT=/tmp/llm-inference-lab
mkdir -p "$LAB_OUTPUT"
"$INFRASTRUCTURE_DIR/bin/sync-live-checkouts" \
  "$PROJECT_DIR" "$INFRASTRUCTURE_DIR" "$LAB_OUTPUT/revisions.json"
```

The synchronization command stops before fetching when either worktree is
dirty, fast-forwards both clean checkouts to `origin/main`, and writes their
resolved revisions. Review `revisions.json` before continuing.

## Smoke mode

Run each stage separately and stop on its first failure:

```sh
"$INFRASTRUCTURE_DIR/bin/host-preflight"
"$INFRASTRUCTURE_DIR/bin/run-gpu-smoke"

helm upgrade --install llm-inference \
  "$INFRASTRUCTURE_DIR/charts/llm-inference" \
  --namespace llm-inference --create-namespace --reset-values \
  --wait --timeout 15m
kubectl -n llm-inference rollout status deployment/llm-inference --timeout=15m
kubectl -n llm-inference port-forward svc/llm-inference 8000:8000

MODEL=Qwen/Qwen3-4B-AWQ
"$INFRASTRUCTURE_DIR/bin/smoke-openai-api" \
  http://127.0.0.1:8000/v1 "$MODEL"

kubectl -n monitoring port-forward \
  svc/monitoring-kube-prometheus-prometheus 9090:9090
kubectl -n monitoring port-forward svc/monitoring-grafana 3000:80
GRAFANA_USER=$(kubectl -n monitoring get secret monitoring-grafana \
  -o jsonpath='{.data.admin-user}' | base64 --decode)
GRAFANA_AUTH=$(kubectl -n monitoring get secret monitoring-grafana \
  -o jsonpath='{.data.admin-password}' | base64 --decode)
GRAFANA_PASSWORD=${GRAFANA_AUTH}
export GRAFANA_USER GRAFANA_PASSWORD
"$INFRASTRUCTURE_DIR/bin/check-live-observability"
unset GRAFANA_USER GRAFANA_AUTH GRAFANA_PASSWORD

cd "$PROJECT_DIR"
uv sync --frozen
uv run llm-inference-benchmark \
  --base-url http://127.0.0.1:8000/v1 \
  --model "$MODEL" \
  --workload data/benchmark/workload.jsonl \
  --concurrency 4 --repetitions 3 \
  --output "$LAB_OUTPUT/benchmark.json"

helm history llm-inference --namespace llm-inference
"$INFRASTRUCTURE_DIR/bin/rollback-live-release" \
  PREVIOUS_KNOWN_GOOD_REVISION "$MODEL"
helm history llm-inference --namespace llm-inference
```

The rollback proof is deliberately external: Helm must create a new release
revision, the Deployment must become Ready, and model discovery plus one chat
completion must succeed. It does not compare Kubernetes objects or maintain a
custom release state.

## Publication mode

Publication mode is smoke mode plus the complete pinned IFEval stage below.
Acquire the official input and checker at their recorded revisions outside
Git; do not substitute a sample run.

```sh
cd "$PROJECT_DIR"
uv run llm-inference-ifeval \
  --input-data "$LAB_OUTPUT/ifeval-input.jsonl" \
  --base-url http://127.0.0.1:8000/v1 \
  --model "$MODEL" \
  --dataset-revision 39ed06ce3906b51290c6e95b7c697e928c8a7b00 \
  --checker-revision 26d8ccdab6fec61b5c83ad6327ea8bda9e580288 \
  --disable-thinking \
  --output "$LAB_OUTPUT/ifeval.json"
```

Inspect raw outputs outside Git. Publish only the necessary run identity and
aggregate observations by deliberately updating the Project Repository's
single `lab-result.json`. That file is ordinary JSON: it has no schema,
digest, registry metadata, or validity status.
