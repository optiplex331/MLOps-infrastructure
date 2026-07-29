#!/usr/bin/env bash
set -euo pipefail

readonly CONTAINERD_CONFIG='/var/lib/rancher/k3s/agent/etc/containerd/config.toml'

[[ $EUID -eq 0 ]] || { echo 'run the containerd configurator as root' >&2; exit 2; }
command -v nvidia-ctk >/dev/null || { echo 'missing nvidia-ctk; install NVIDIA Container Toolkit 1.17.8 first' >&2; exit 2; }
command -v systemctl >/dev/null || { echo 'missing systemctl; k3s must run as a systemd service' >&2; exit 2; }
[[ -f "$CONTAINERD_CONFIG" ]] || { echo "missing $CONTAINERD_CONFIG; install and start k3s before configuring containerd" >&2; exit 2; }

nvidia-ctk runtime configure --runtime=containerd --config="$CONTAINERD_CONFIG"
systemctl restart k3s

echo "configured NVIDIA runtime in $CONTAINERD_CONFIG"
