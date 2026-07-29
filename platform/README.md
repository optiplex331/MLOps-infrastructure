# Historical Platform Surface

Everything under this directory is retained from the former MLOps release-lab
platform. `platform/argo`, `platform/mlflow`, and `platform/minio` are
historical Argo/Kustomize, MLflow, and MinIO resources.

These files are not the active `llm-inference-lab-infra` Phase 1 path. The
active boundary is documented in [../docs/platform-boundary.md](../docs/platform-boundary.md)
and uses single-node k3s, NVIDIA, Helm, vLLM, and public GHCR.
