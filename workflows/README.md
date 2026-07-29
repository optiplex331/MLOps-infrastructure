# Historical Workflow Surface

This directory contains the former Argo/Kustomize CPU synthetic release
workflow. It is retained for provenance and regression reference only, not as
the active Phase 1 path for `llm-inference-lab-infra`.

The active platform boundary is single-node k3s with NVIDIA, Helm, vLLM, and a
public GHCR image. The default CI workflow does not render this directory.
