# Ownership and Publication Boundary for `llm-inference-lab-infra`

## Owned by this repository

- the single-node k3s and NVIDIA runtime policy;
- GPU host admission procedures and their sanitized Evidence Packages;
- the Helm serving chart and release selection;
- the thin vLLM wrapper image delivery workflow and its public GHCR package;
- observability resources, rollback procedures, and operational tooling;
- repository-level CI and publication sanitization checks.

The chart, wrapper workflow, observability resources, and rollback procedure
are the Phase 1 implementation surface. Live deployment and runtime evidence
remain remote operations, not checked-in state.

## Owned by the Project Repository or another system

The Project Repository owns data, training, inference, evaluation, benchmark
clients, model profiles, IFEval acquisition metadata, public project
documentation, and model artifacts. Data and model registries own datasets,
model weights, and lineage objects. GitHub Container Registry owns the
published image package. The remote k3s cluster owns live runtime state. This
repository consumes immutable references; it does not copy those authorities.

## Historical material

`platform/argo`, `platform/mlflow`, `platform/minio`, and `workflows` preserve
the former Argo/Kustomize/MLflow/MinIO release-lab surface for provenance.
Those files are not the active Phase 1 architecture, are not CI deployment
entrypoints, and must not be treated as the current system of record.

## Never publish

Credentials, tokens, kubeconfigs, rendered Secrets, local paths, host
identity, raw logs, raw datasets, raw held-out evaluation targets, model
weights, model caches, MLflow backend state, MinIO data, and unsanitized host
or cluster evidence are excluded from Git. `bin/check-public-surface` checks
the tracked and non-ignored publication surface for these classes. Runtime
evidence is written outside the repository and only sanitized, reviewable
summaries may be copied back deliberately.

No checked-in file represents a live serving deployment, trained model,
published model release, or production capability.
