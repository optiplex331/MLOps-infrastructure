# MLOps Lab Infrastructure

This repository owns deployment infrastructure, release selection, runtime
policy, observability integration, operational tooling, and sanitized
deployment evidence for the Local Kubernetes MLOps Release Lab.

Ticket 01 provides one deliberately limited, CPU-only synthetic seam. It reads
versioned contracts and a request owned by the Project Repository, applies the
checked-in synthetic rejection policy, and writes a deterministic terminal
decision plus Evidence Package:

```sh
bin/run-synthetic-release \
  --project-repo ../MLOps \
  --request ../MLOps/fixtures/releases/rejected/release-request.template.json \
  --project-revision "$(git -C ../MLOps rev-parse HEAD)" \
  --infrastructure-revision "$(git rev-parse HEAD)" \
  --output-dir /tmp/mlops-synthetic-release
```

Both repositories must have commits, the supplied revisions must equal their
current `HEAD`, and both worktrees must be clean. The command materializes the
explicit revision tokens in Project-owned templates and records both template
and materialized bytes in evidence. The output directory must be outside both
repositories so generating evidence cannot dirty either worktree. It is
offline, requires Python 3.9 or newer, and never contacts a cluster, registry,
model store, or external service. A successful command means
only that the cross-repository contract, immutable digests, rejection policy,
and evidence packaging worked for synthetic fixtures. It does **not** prove GPU
execution, Kubernetes execution, model training or evaluation, serving, model
publication, or production readiness.

See [OWNERSHIP.md](OWNERSHIP.md) for the repository and publication boundary.

## Development

```sh
python3 -m unittest discover -s tests -v
```
