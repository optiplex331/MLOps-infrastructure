# Phase 1 Platform Boundary

This document is the current infrastructure identity for
`llm-inference-lab-infra`. It defines the platform seam and separates checked-in
implementation from remote runtime evidence.

## Active surface

| Concern | Phase 1 boundary |
| --- | --- |
| Host | One native Ubuntu amd64 workstation with one RTX 3080-class GPU |
| Kubernetes | One single-node k3s server with embedded containerd |
| GPU runtime | NVIDIA Container Toolkit and device plugin exposing one `nvidia.com/gpu` |
| Deployment | Helm-first serving release; no Argo or Kustomize default |
| Serving | vLLM through a thin public image wrapper |
| Image delivery | Public GHCR package, immutable image reference, no image pull Secret |
| Access | ClusterIP and local `kubectl port-forward`; no public ingress |
| Evidence | Sanitized host, cluster, serving, and rollback summaries outside live runtime state |

The lab is intentionally single-node and bounded. Multi-node scheduling,
multi-GPU tensor parallelism, autoscaling, service mesh, public ingress, and
production traffic management are outside this platform boundary.

## Ownership seam

This repository owns host admission, k3s policy, the Helm chart, image
delivery workflow, observability resources, rollback procedures, operational
entrypoints, and sanitized runtime evidence. The Project Repository owns the
model profile, inference client, benchmark and IFEval logic, result contracts,
and public project documentation. GitHub Container Registry owns the published
image package, and the remote k3s cluster owns live runtime state.

The chart, vLLM Deployment, observability resources, and rollback procedure are
checked-in Phase 1 implementation. Their live GPU execution and Evidence
Package remain pending until the remote host is admitted.

## Publication rules

The public image is published by repository-scoped GitHub Actions permissions
to GHCR. Deployment does not use a registry pull Secret, kubeconfig, SSH key,
or cloud credential from GitHub Actions. Model weights, raw evaluation data,
runtime logs, caches, host identity, and rendered credentials stay outside the
public repository.

`bin/check-public-surface` checks the tracked and non-ignored files before
publication. Its scope includes path and content checks for secrets, local
paths, host identity, raw logs, caches, kubeconfigs, and rendered credentials.

## Historical surface

The following paths are retained only for repository history and bounded
regression reference:

- `platform/argo` — former Argo controller resources;
- `platform/mlflow` — former MLflow service resources;
- `platform/minio` — former MinIO service resources;
- `workflows` — former Argo/Kustomize CPU synthetic release workflow.

They are not rendered by the default CI workflow and are not the Phase 1
deployment path. Their historical notice files explain this status where the
old files remain.
