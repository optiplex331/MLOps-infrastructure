# llm-inference-lab-infra

This is the Infrastructure Repository for `llm-inference-lab`. It owns the
single-node Kubernetes MLOps Lab platform boundary: host setup, k3s
policy, Helm deployment state, observability, live operation, rollback, and
sanitized operational observations.

## Active Phase 1 boundary

The intended platform surface is one native Ubuntu amd64 workstation with one
single-node k3s server. k3s uses embedded containerd, the NVIDIA runtime and
device plugin expose one `nvidia.com/gpu`, and Helm is the deployment interface
for the vLLM serving release. The serving service is reachable through a
ClusterIP and local `kubectl port-forward`; this repository does not claim
multi-node, multi-GPU, ingress, autoscaling, or production traffic management.

The chart consumes the official public vLLM image by digest, so deployment
needs neither a custom wrapper workflow nor an image pull Secret. No
kubeconfig, SSH credential, model credential, or deployment secret belongs in
this repository.

The repository contains the host setup and GPU smoke procedure, minimal serving
chart, observability resources, and rollback commands.
The exact model revisions, image digest, live admission, benchmark, IFEval,
rollback, and optional-experiment outcomes are recorded in
[the Phase 1 results](docs/results/phase-1-llm-inference-results.md).

See [OWNERSHIP.md](OWNERSHIP.md) for the repository and publication boundary.
See [docs/platform-boundary.md](docs/platform-boundary.md) for the active
surface.
See [docs/host-setup.md](docs/host-setup.md) for the explicit setup,
read-only preflight, and real GPU smoke path.
See [docs/live-lab.md](docs/live-lab.md) for the staged smoke, publication,
revision-recording, and rollback procedure.

## CPU-safe offline checks

Run locally or in CI:

```sh
bin/check-ci
```

`bin/check-ci` runs shell syntax, offline GPU smoke and observability
integration checks, repository-boundary, publication-surface, and Helm checks.
It never invokes setup, Kubernetes, chart repositories, monitoring APIs, or
GPU operations.

## Live operation

Run setup, GPU smoke, Helm, Kubernetes, vLLM, benchmark, monitoring API, and
rollback commands only on the declared remote Linux GPU host. Codex remains
local and uses an ordinary SSH shell; there is no remote Codex dispatch.
Generated runtime output stays outside both repositories.

The canonical staged procedure is [docs/live-lab.md](docs/live-lab.md). Its
synchronization entrypoint rejects dirty remote worktrees, fast-forwards both
checkouts directly to `origin/main`, and records the resolved revisions before
the smoke or publication stages begin.
