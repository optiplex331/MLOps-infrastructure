# Single-node GPU host path

These commands target one prepared native Ubuntu amd64 host with one NVIDIA
GPU. Setup is deliberately separate from preflight, validation, experiments,
and deployment. Nothing in `bin/check-ci`, chart checks, or GPU smoke invokes
setup automatically.

## Explicit setup

Review both scripts before running them. They require root and mutate the host:

```sh
sudo runtime/k3s/install-single-node.sh
sudo runtime/nvidia/configure-k3s-containerd.sh
```

The first operation installs pinned k3s `v1.32.6+k3s1`, writes its system
configuration, changes the runtime user's group membership, and starts the
service. The second operation changes the k3s embedded-containerd
configuration, restarts k3s, and installs the pinned NVIDIA device-plugin
chart. The NVIDIA driver and Container Toolkit `1.17.8-1` are prerequisites;
see `runtime/nvidia/container-toolkit-k3s.md`.

## Read-only preflight

Run without `sudo`:

```sh
bin/host-preflight
```

It performs only reads and reports Ubuntu/architecture, root filesystem and
free disk, total memory, NVIDIA driver and GPU, k3s, embedded-containerd,
device-plugin readiness, and allocatable `nvidia.com/gpu`. Missing facts make
the command exit nonzero.

## Real GPU smoke

After preflight succeeds, run the explicit cluster-mutating smoke operation:

```sh
bin/run-gpu-smoke
```

It applies a dedicated namespace and one digest-pinned CUDA Pod, requests
exactly one GPU, waits for successful exit, and prints `nvidia-smi`. This is a
remote-host check: CI validates shell syntax and manifests offline and does
not claim GPU execution.
