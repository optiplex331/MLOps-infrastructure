# RTX 3080 and Single-Node k3s Runtime Admission

This repository's runtime profile is
`config/runtime-admission-profile.v1.json`. It describes one native Ubuntu
amd64 workstation with one RTX 3080 and one k3s server. k3s uses its embedded
containerd; `local-path` and `metrics-server` remain enabled, while Traefik
and ServiceLB are disabled.

## Installation order

Run these commands on the remote native Ubuntu host only:

```sh
sudo runtime/k3s/install-single-node.sh
sudo runtime/nvidia/configure-k3s-containerd.sh
sudo runtime/k3s/verify-packaged-components.sh
```

The NVIDIA package pin and k3s/containerd path are documented in
`runtime/nvidia/container-toolkit-k3s.md`. The configurator fails with an
actionable message when `nvidia-ctk`, `systemctl`, or the k3s-generated
containerd configuration is missing.

## Device plugin and smoke workload

Apply the declarative device-plugin resources after containerd is configured:

```sh
kubectl apply -f manifests/runtime-admission/nvidia-device-plugin.yaml
kubectl apply -f manifests/runtime-admission/namespace.yaml
kubectl apply -f manifests/runtime-admission/gpu-smoke.pod.yaml
kubectl wait -n mlops-runtime-admission --for=jsonpath='{.status.phase}'=Succeeded pod/gpu-smoke --timeout=120s
kubectl logs -n mlops-runtime-admission gpu-smoke
```

The NVIDIA device-plugin chart is pinned to `0.17.1` and receives
`runtime/nvidia/device-plugin-values.yaml` semantics through the K3s
`HelmChart` manifest. The smoke Pod is namespace-scoped, requests exactly one
`nvidia.com/gpu`, uses the `nvidia` RuntimeClass, and prints only the GPU
model, driver version, and memory reported by `nvidia-smi`.

## Sanitized evidence

`contracts/runtime-admission/v1/evidence.schema.json` defines the reviewable
runtime shape. Start from
`contracts/runtime-admission/v1/pending-evidence.template.json`, then record
the allowlisted host, toolkit, K3s, device-plugin, container, and smoke fields.
Every check has an explicit next action so missing tools, failed scheduling,
and insufficient storage are visible outcomes rather than skipped checks. The
existing `config/host-admission-limits.v1.json` remains the single owner of
measurement thresholds; the runtime contract records its reference instead of
copying those values.

Store collected evidence outside this repository. Do not include kubeconfig,
credentials, host paths, hostnames, private addresses, GPU serials, or raw
containerd configuration.

This is a one-node, one-GPU lab admission. It does not claim production
reliability, high availability, multi-node scheduling, autoscaling, or durable
portable storage.
