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
| Deployment | Helm-first serving release |
| Serving | Official vLLM image pinned by digest |
| Image delivery | Public upstream image, immutable image reference, no image pull Secret |
| Access | ClusterIP and local `kubectl port-forward`; no public ingress |
| Results | Raw runtime output outside Git; sanitized aggregate observations in the Project Repository |

The lab is intentionally single-node and bounded. Multi-node scheduling,
multi-GPU tensor parallelism, autoscaling, service mesh, public ingress, and
production traffic management are outside this platform boundary.

## Ownership seam

This repository owns host setup and preflight, k3s policy, the Helm chart,
observability resources, rollback procedures, and operational entrypoints.
The Project Repository owns the benchmark and IFEval clients, fixed workload,
optional labs, and public experiment records. The upstream registry owns the
official image package, and the remote k3s cluster owns live runtime state.

The chart, vLLM Deployment, observability resources, and rollback procedure are
checked-in Phase 1 implementation. Their live GPU execution and raw output
remain remote-host responsibilities.

## Publication rules

Deployment consumes the public upstream image without a registry pull Secret.
Kubeconfigs, SSH keys, cloud credentials, model weights, raw evaluation data,
runtime logs, caches, host identity, and rendered credentials stay outside the
public repository.

`bin/check-public-surface` checks the tracked and non-ignored files before
publication. Its scope includes path and content checks for secrets, local
paths, host identity, raw logs, caches, kubeconfigs, and rendered credentials.
