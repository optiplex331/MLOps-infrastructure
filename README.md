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
  --request ../MLOps/fixtures/releases/rejected/release-request.json \
  --project-revision 1111111111111111111111111111111111111111 \
  --infrastructure-revision 2222222222222222222222222222222222222222 \
  --output-dir /tmp/mlops-synthetic-release
```

The command is offline, requires only Python 3.11+, and never contacts a
cluster, registry, model store, or external service. A successful command means
only that the cross-repository contract, immutable digests, rejection policy,
and evidence packaging worked for synthetic fixtures. It does **not** prove GPU
execution, Kubernetes execution, model training or evaluation, serving, model
publication, or production readiness.

See [OWNERSHIP.md](OWNERSHIP.md) for the repository and publication boundary.

## Development

```sh
python3 -m unittest discover -s tests -v
```

