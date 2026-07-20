# Ownership and Publication Boundary

## Owned here

- deployment selection and release policy;
- k3s bootstrap contracts, Argo templates, Helm charts, platform service
  configuration, observability integration, and declared failure scenarios;
- operational tools and sanitized deployment evidence;
- the CPU-only synthetic release executor used to test the repository seam.

## Owned elsewhere

The Project Repository owns data, training, inference, evaluation, benchmark
clients, public project documentation, cross-repository JSON Schemas, and model
artifacts. Data and model registries own datasets, model weights, and lineage
objects. Runtime systems own live Kubernetes, MLflow, and MinIO state. This
repository consumes immutable references; it does not copy those authorities.

## Never publish

Credentials, tokens, kubeconfigs, rendered Secrets, raw datasets, raw held-out
evaluation targets, model weights or caches, MLflow backend state, MinIO data,
and unsanitized host or cluster evidence are excluded from Git. The synthetic
fixture contains identifiers and digests only. The executor rejects unexpected
files in an Evidence Package and has no network or publication operation.

No file in the Ticket 01 slice represents a Kubernetes manifest, GPU run,
trained model, deployment, or promoted candidate.

