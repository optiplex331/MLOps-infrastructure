# Historical CPU-only Argo, MLflow, and MinIO Workflow

> Historical notice: this document and the files it describes are retained
> for provenance from the former release-lab surface. They are not the active
> Phase 1 path for `llm-inference-lab-infra`, and the default CI workflow does
> not render them. Use [platform-boundary.md](platform-boundary.md) for the
> current single-node k3s/NVIDIA/Helm/vLLM boundary.

Ticket 04 defines a namespace-scoped, bounded synthetic release workflow. The
platform modules use local-path persistence explicitly annotated `lab-only`,
resource requests and limits, health probes, referenced credentials, and
namespace Roles. No Secret values are checked in.

Render the modules without a cluster:

```sh
kubectl kustomize platform/argo
kubectl kustomize platform/mlflow
kubectl kustomize platform/minio
kubectl kustomize workflows
```

On the target single-node k3s lab, an operator must create the
`mlops-object-store` Secret locally, apply the four rendered modules, wait for
MLflow and MinIO health, and submit `cpu-synthetic-release-v1` with immutable
digest and revision parameters. Argo passes every cross-step file as an
artifact; there is no shared hidden workspace. Content identity is stable for
identical inputs, while Workflow UID and MLflow run ID remain distinct execution
identities. MinIO object keys include content digests, and a workflow can emit a
terminal decision only after the MLflow run is finished.

Dependency preflight is fail closed. Injecting `mlflow`, `minio`, or `both`
through the declared test parameter prevents the release DAG from reaching the
decision task. Failed executions accept no partial artifact and the exit
handler attempts to mark an already-created MLflow run `FAILED`.

The checked-in manifests and CPU tests do not prove a live Argo execution,
MLflow lineage, MinIO persistence, Kubernetes reliability, or production
capability. Those claims remain pending until sanitized evidence is captured on
the declared target workstation.
