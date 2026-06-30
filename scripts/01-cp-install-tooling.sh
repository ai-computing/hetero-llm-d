#!/usr/bin/env bash
# Stage 1: containerd + kubeadm/kubelet/kubectl on R7525 (control-plane host)
# Run with: sudo bash /tmp/llmd-cp-stage1.sh
# Idempotent; safe to re-run.
set -euo pipefail

K8S_MINOR="v1.31"            # Gateway API Inference Extension 권장 호환
KUBE_PKG_VER="1.31.*"

log() { echo -e "\033[1;32m[+]\033[0m $*"; }
warn() { echo -e "\033[1;33m[!]\033[0m $*"; }

[[ $EUID -eq 0 ]] || { echo "run as root (sudo)"; exit 1; }

log "1/8 disable swap (immediate + /etc/fstab)"
swapoff -a || true
sed -ri 's|^([^#].*\s)swap(\s.*)$|#\1swap\2|' /etc/fstab

log "2/8 load kernel modules (overlay, br_netfilter)"
cat >/etc/modules-load.d/k8s.conf <<EOF
overlay
br_netfilter
EOF
modprobe overlay
modprobe br_netfilter

log "3/8 sysctl for k8s networking"
cat >/etc/sysctl.d/99-k8s.conf <<EOF
net.bridge.bridge-nf-call-iptables  = 1
net.bridge.bridge-nf-call-ip6tables = 1
net.ipv4.ip_forward                 = 1
EOF
sysctl --system >/dev/null

log "4/8 install containerd + runc (from Ubuntu archive)"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq containerd runc ca-certificates curl gpg apt-transport-https jq \
  conntrack socat ethtool ebtables

log "5/8 generate containerd config + enable SystemdCgroup"
mkdir -p /etc/containerd
if [[ ! -f /etc/containerd/config.toml ]] || ! grep -q "SystemdCgroup" /etc/containerd/config.toml; then
  containerd config default > /etc/containerd/config.toml
fi
# SystemdCgroup = true (idempotent)
sed -ri 's/(\s*SystemdCgroup\s*=\s*)false/\1true/' /etc/containerd/config.toml || true
grep -q "SystemdCgroup = true" /etc/containerd/config.toml || warn "SystemdCgroup not set — inspect /etc/containerd/config.toml manually"
# sandbox_image must match kubeadm's expectation (suppresses the 'inconsistent sandbox image' warning)
sed -ri 's|^(\s*sandbox_image\s*=\s*).*|\1"registry.k8s.io/pause:3.10"|' /etc/containerd/config.toml || true
systemctl enable --now containerd
systemctl restart containerd

log "6/8 add kubernetes apt repo (${K8S_MINOR})"
install -d -m 0755 /etc/apt/keyrings
if [[ ! -f /etc/apt/keyrings/kubernetes-apt-keyring.gpg ]]; then
  curl -fsSL "https://pkgs.k8s.io/core:/stable:/${K8S_MINOR}/deb/Release.key" \
    | gpg --dearmor -o /etc/apt/keyrings/kubernetes-apt-keyring.gpg
fi
cat >/etc/apt/sources.list.d/kubernetes.list <<EOF
deb [signed-by=/etc/apt/keyrings/kubernetes-apt-keyring.gpg] https://pkgs.k8s.io/core:/stable:/${K8S_MINOR}/deb/ /
EOF
apt-get update -qq

log "7/8 install kubeadm kubelet kubectl + cri-tools (held)"
apt-get install -y -qq kubelet=${KUBE_PKG_VER} kubeadm=${KUBE_PKG_VER} kubectl=${KUBE_PKG_VER} cri-tools
apt-mark hold kubelet kubeadm kubectl
systemctl enable --now kubelet

log "8/8 crictl runtime endpoint"
cat >/etc/crictl.yaml <<EOF
runtime-endpoint: unix:///run/containerd/containerd.sock
image-endpoint: unix:///run/containerd/containerd.sock
timeout: 10
EOF

log "DONE. Versions:"
containerd --version
runc --version | head -1
kubeadm version -o short
kubectl version --client --output=yaml | head -8
crictl --version

echo
log "next: run /tmp/llmd-cp-stage2.sh to kubeadm init + install Cilium"
