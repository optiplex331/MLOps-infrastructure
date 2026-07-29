# llm-inference-lab-infra

This is the Infrastructure Repository for `llm-inference-lab`. It owns the
single-node Kubernetes MLOps Lab platform boundary: GPU host admission, k3s
policy, Helm deployment state, image delivery, observability, rollback, and
sanitized runtime Evidence Packages.

## Active Phase 1 boundary

The intended platform surface is one native Ubuntu amd64 workstation with one
single-node k3s server. k3s uses embedded containerd, the NVIDIA runtime and
device plugin expose one `nvidia.com/gpu`, and Helm is the deployment interface
for the vLLM serving release. The serving service is reachable through a
ClusterIP and local `kubectl port-forward`; this repository does not claim
multi-node, multi-GPU, ingress, autoscaling, or production traffic management.

The image delivery boundary is a public GHCR package. The serving image is a
thin wrapper around an official vLLM image and is consumed by a digest-pinned
image reference; the public image needs no image pull Secret. GitHub Actions may
publish the package with repository workflow permissions, but no kubeconfig,
SSH credential, model credential, or deployment secret belongs in this
repository.

The repository contains the runtime admission procedure, minimal serving
chart, wrapper-image workflow, observability resources, and rollback commands.
The exact model revision, image digest, and live GPU evidence remain pending
until the remote host completes the compatibility and admission checks.

See [OWNERSHIP.md](OWNERSHIP.md) for the repository and publication boundary.
See [docs/platform-boundary.md](docs/platform-boundary.md) for the active and
historical surfaces.

## Local editing and remote execution

Edit source and documentation locally. Run host admission, Helm, Kubernetes,
vLLM, benchmark, and evidence commands only on the declared remote Linux
validation host. Generated evidence must be written outside this repository.

The CPU-safe CI entrypoint is `bin/check-ci`; the publication boundary check
is available separately as `bin/check-public-surface`.

## Historical compatibility surface

The former Argo/Kustomize/MLflow/MinIO release-lab files remain in Git for
provenance and regression reference. They are explicitly historical, are not
the Phase 1 deployment path, and are not rendered by the default CI workflow.
See [platform/README.md](platform/README.md),
[workflows/README.md](workflows/README.md), and the historical notice in
[docs/cpu-workflow.md](docs/cpu-workflow.md).

## Development

Run this check on the Linux validation host after pulling the intended
Infrastructure and Project Repository revisions. The local workstation is for
reading and modifying source only; it does not run project tests or services.

```sh
bin/check-ci
```

`bin/check-ci` runs only the active host-admission, repository-boundary, and
runtime-contract tests plus `helm lint`/`helm template` for the Phase 1 chart.
The former Ticket 04 Argo/MLflow/MinIO tests remain available as historical
regression tests but are not part of the active CI gate.
