#!/usr/bin/env bash
# Worker stage 1: prepare npu-node-1 (Ubuntu 22.04) to join the k8s cluster.
# Run with: sudo bash /tmp/llmd-worker-stage1.sh
# After this, run the `kubeadm join ...` command printed by control-plane stage2.
set -euo pipefail

K8S_MINOR="v1.31"
KUBE_PKG_VER="1.31.*"

log() { echo -e "\033[1;32m[+]\033[0m $*"; }
warn() { echo -e "\033[1;33m[!]\033[0m $*"; }

[[ $EUID -eq 0 ]] || { echo "run as root (sudo)"; exit 1; }

log "1/7 disable swap"
swapoff -a || true
sed -ri 's|^([^#].*\s)swap(\s.*)$|#\1swap\2|' /etc/fstab

log "2/7 kernel modules"
cat >/etc/modules-load.d/k8s.conf <<EOF
overlay
br_netfilter
EOF
modprobe overlay
modprobe br_netfilter

log "3/7 sysctl"
cat >/etc/sysctl.d/99-k8s.conf <<EOF
net.bridge.bridge-nf-call-iptables  = 1
net.bridge.bridge-nf-call-ip6tables = 1
net.ipv4.ip_forward                 = 1
EOF
sysctl --system >/dev/null

log "4/7 ensure containerd + runc installed; SystemdCgroup=true; sandbox image"
export DEBIAN_FRONTEND=noninteractive
if ! command -v containerd >/dev/null 2>&1; then
  apt-get update -qq
  apt-get install -y -qq containerd runc
fi
mkdir -p /etc/containerd
if [[ ! -f /etc/containerd/config.toml ]] || ! grep -q "SystemdCgroup" /etc/containerd/config.toml; then
  containerd config default > /etc/containerd/config.toml
fi
sed -ri 's/(\s*SystemdCgroup\s*=\s*)false/\1true/' /etc/containerd/config.toml || true
sed -ri 's|^(\s*sandbox_image\s*=\s*).*|\1"registry.k8s.io/pause:3.10"|' /etc/containerd/config.toml || true
grep -q "SystemdCgroup = true" /etc/containerd/config.toml || warn "verify SystemdCgroup manually"
systemctl restart containerd
systemctl enable containerd

log "5/7 add kubernetes apt repo (${K8S_MINOR})"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq ca-certificates curl gpg apt-transport-https \
  conntrack socat ethtool ebtables
install -d -m 0755 /etc/apt/keyrings
if [[ ! -f /etc/apt/keyrings/kubernetes-apt-keyring.gpg ]]; then
  curl -fsSL "https://pkgs.k8s.io/core:/stable:/${K8S_MINOR}/deb/Release.key" \
    | gpg --dearmor -o /etc/apt/keyrings/kubernetes-apt-keyring.gpg
fi
cat >/etc/apt/sources.list.d/kubernetes.list <<EOF
deb [signed-by=/etc/apt/keyrings/kubernetes-apt-keyring.gpg] https://pkgs.k8s.io/core:/stable:/${K8S_MINOR}/deb/ /
EOF
apt-get update -qq

log "6/7 install kubelet kubeadm + cri-tools (kubectl optional on worker)"
apt-get install -y -qq kubelet=${KUBE_PKG_VER} kubeadm=${KUBE_PKG_VER} cri-tools
apt-mark hold kubelet kubeadm
systemctl enable kubelet

log "7/7 crictl runtime endpoint"
cat >/etc/crictl.yaml <<EOF
runtime-endpoint: unix:///run/containerd/containerd.sock
image-endpoint: unix:///run/containerd/containerd.sock
timeout: 10
EOF

log "DONE. now run the kubeadm join command from control-plane stage2 output:"
echo "   sudo kubeadm join <cp-node-ip>:6443 --token <...> --discovery-token-ca-cert-hash sha256:<...>"
