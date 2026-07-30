# Ownership and Publication Boundary

The canonical infrastructure ownership and publication rules are in
[docs/platform-boundary.md](docs/platform-boundary.md). Executable entry points
are routed from [README.md](README.md).

The Project Repository owns benchmark and IFEval clients, the fixed workload,
optional labs, and public experiment records. This repository owns host,
cluster, deployment, observability, live-operation, and rollback procedures.
The upstream registry owns the official image; external systems own datasets,
model weights, credentials, caches, raw logs, and live runtime state.

`bin/check-public-surface` checks the tracked and non-ignored publication
surface. No checked-in file represents live cluster state or a production
capability.
