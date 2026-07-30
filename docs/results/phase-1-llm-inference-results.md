# Phase 1 LLM Inference Results

This page is the sanitized closeout record for the single-node Phase 1 lab
executed on 2026-07-29. Raw responses, IFEval inputs, host logs, credentials,
kubeconfig, model weights, caches, and host identity remain outside Git.

## Reproducibility pins

| Component | Pin |
| --- | --- |
| Project source | `880a1d0592368b18c7c5e1409e9d724e28aaa391` |
| Infrastructure source | `c048f1392c9acb837f34e86e24549630d885698d` |
| Serving image | `ghcr.io/optiplex331/llm-inference-vllm@sha256:8c3465f2b686f526ac797d17e80f6b220563974e31136d7eb609bea4ecdfc75c` |
| Official vLLM base | v0.13.0, `sha256:d623253f2ba246378421c9642e20885e65257f38418ff26d48c81aea1702521b` |
| AWQ target | `Qwen/Qwen3-4B-AWQ@74d4bd2bd4bff9cafc9345221320bffb08b406a3` |
| FP target | `Qwen/Qwen3-4B@1cfa9a7208912126459214e8b04321603b3df60c` |
| Speculative draft | `Qwen/Qwen3-0.6B@c1899de289a04d12100db370d81485cdf75e47ca` |
| IFEval dataset | `google/IFEval@39ed06ce3906b51290c6e95b7c697e928c8a7b00` |
| IFEval checker | `google-research@26d8ccdab6fec61b5c83ad6327ea8bda9e580288` |
| k3s / NVIDIA toolkit | `v1.32.6+k3s1` / `1.17.8` |
| Observability chart | `kube-prometheus-stack` 70.4.2 |

The public GHCR workflow run `30462331929` passed its CPU gate, build, and
publication jobs. The final package is public and the deployed image was
resolved by digest.

## Runtime admission and deployment

The final admission run used the infrastructure revision above and returned
`passed`. It observed one RTX 3080-class GPU with 12 GiB VRAM, one allocatable
`nvidia.com/gpu`, a ready device plugin, and a successful container GPU smoke
test. The dedicated-node taint rejected a non-GPU Pod, and a second GPU Pod
received an actionable insufficient-capacity scheduling event. The run used a
60-second idle sample and passed the 50 GiB free-disk gate.

The default Helm release runs one AWQ replica with a 4096-token model limit,
one sequence, a ClusterIP Service, and a retained 20 GiB `local-path` PVC.
Model listing and chat smoke requests succeeded. A controlled change from the
known-good release revision 2 to candidate revision 3 was rolled back as
revision 4; readiness, the 4096-token configuration, and the same PVC were
restored. The final post-experiment deployment is Helm revision 8 and Ready.

## Serving benchmark

Both profiles used concurrency 1, the same fixed three-class workload, a
4096-token model limit, one sequence, and `gpu_memory_utilization=0.85`.

| Metric | Qwen3-4B-AWQ | Qwen3-4B FP |
| --- | ---: | ---: |
| Successful requests / errors | 3 / 0 | 3 / 0 |
| Latency p50 | 0.192 s | 1.827 s |
| Latency p95 | 1.203 s | 2.965 s |
| TTFT p50 | 0.0147 s | 0.1556 s |
| TTFT p95 | 0.0305 s | 1.3223 s |
| Median ITL | 0.00511 s | 0.01204 s |
| Mean output throughput | 198.54 token/s | 84.72 token/s |
| Runtime-context GPU memory | 10,414 MiB | 10,233 MiB |
| Result digest | `5a18712ca6a2a4a3392939cfebff85566bc29032aaf44d716c330c86aa4f1d2c` | `220361322bb68fc3fea7f205ad49a04dc3f9dca299df853a65f291c3181b85db` |

The similar reported VRAM is not evidence that AWQ saved no weight memory.
AWQ is weight-only quantization, while activations and KV cache are not reduced
proportionally. With the same 0.85 memory-utilization target, vLLM can use
weight savings for a larger KV cache. Initial image download time is also
separate from model startup; cached-image startup was approximately three
minutes for the FP profile. FP8 remains a conditional, non-default Ampere
experiment and was not validated in this run.

## Full manual IFEval

Both complete 541-prompt runs disabled Qwen3 thinking so hidden reasoning did
not consume the bounded answer budget. IFEval was manual and did not affect CI.

| Metric | Qwen3-4B-AWQ | Qwen3-4B FP |
| --- | ---: | ---: |
| Instructions | 834 | 834 |
| Strict prompt accuracy | 0.7579 | 0.7560 |
| Strict instruction accuracy | 0.8213 | 0.8201 |
| Loose prompt accuracy | 0.7745 | 0.7837 |
| Loose instruction accuracy | 0.8357 | 0.8405 |
| Result digest | `46984e5d9bb592c32ea80544b8eacc5bc9e4a3d4278bf538386ea381f9503d41` | `c86ce44215c60bc30538cba5f96007f962fec67cdb35b10975e64b88b81f0d85` |

These observations show similar instruction-following quality for these two
pinned profiles; they do not generalize to other models, prompts, or serving
parameters.

## Observability and optional experiments

Prometheus, Grafana, kube-state-metrics, and the operator became Ready without
public ingress. The ServiceMonitor target was up. The request-rate,
running-request, and vLLM running-request queries returned data; the
request-error query correctly had no failure series for the successful sample.

The isolated speculative release parsed the exact Qwen3-4B target and
Qwen3-0.6B draft revisions, then vLLM 0.13.0 rejected generic draft-model
speculation as unsupported. This is the experiment result. Acceptance rate,
accepted tokens, draft latency, verification latency, and running GPU memory
are `N/A` because serving never started; no values are inferred. The isolated
release was scaled down and the default AWQ release was restored.

The CPU-only prefill/decode prototype passed six tests. A deterministic
96-byte KV-like payload retained integrity over both shared memory and TCP
loopback. Shared-memory serialization, transfer, and end-to-end timings were
approximately 0.000012 s, 0.000309 s, and 0.000342 s; TCP loopback transfer
and end-to-end timings were approximately 0.000602 s and 0.000817 s. These
numbers do not represent GPU-to-GPU transfer, NVLink, RDMA, a distributed
scheduler, or a production vLLM connector.

## Verification and limitations

The Project clean checkout passed 22 CPU-only tests. The Infrastructure
checkout passed the then-current `bin/check-ci` suite. Historical admission
test counts are intentionally not part of the current interface. The final
live GPU smoke and restored AWQ deployment passed.

k3s v1.32 was retained because it is the Phase 1 pin, but it is end-of-life and
must be upgraded before this lab is used as a foundation for maintained or
production infrastructure. All results describe one single-node, single-GPU,
low-concurrency learning environment; they are not production SLO evidence.
