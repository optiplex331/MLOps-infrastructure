#!/usr/bin/env bash
set -euo pipefail

readonly K3S_VERSION='v1.32.6+k3s1'
readonly K3S_CONFIG='/etc/rancher/k3s/config.yaml'

[[ $EUID -eq 0 ]] || { echo 'run this installer as root' >&2; exit 2; }
command -v curl >/dev/null || { echo 'missing curl; install curl before installing k3s' >&2; exit 2; }
command -v systemctl >/dev/null || { echo 'missing systemctl; this installer requires systemd' >&2; exit 2; }

install -d -m 0755 /etc/rancher/k3s
cat >"$K3S_CONFIG" <<'YAML'
write-kubeconfig-mode: "0600"
disable:
  - traefik
  - servicelb
YAML

curl -sfL https://get.k3s.io | INSTALL_K3S_VERSION="$K3S_VERSION" INSTALL_K3S_EXEC='server' sh -s -
systemctl enable --now k3s

echo "installed single-node k3s $K3S_VERSION with embedded containerd"
