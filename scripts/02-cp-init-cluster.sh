#!/usr/bin/env bash
# Stage 2: kubeadm init + Cilium + Gateway API CRDs on R7525
# Run from the repo: sudo bash scripts/02-cp-init-cluster.sh
#   (or copied elsewhere: sudo LLMD_ENV_FILE=/path/to/cluster.local.env bash <copy>)
# Assumes stage1 done. Idempotent for re-runs.
set -euo pipefail

source "$(dirname "$0")/lib/cluster-env.sh"
require_env LLMD_CP_IP LLMD_POD_CIDR LLMD_SVC_CIDR
APISERVER_IP="$LLMD_CP_IP"
POD_CIDR="$LLMD_POD_CIDR"
SVC_CIDR="$LLMD_SVC_CIDR"
NODE_NAME="$(hostname -s | tr '[:upper:]' '[:lower:]')"
# Account that also gets a kubeconfig: LLMD_KUBE_USER, else the user who ran sudo.
KUBE_USER="${LLMD_KUBE_USER:-${SUDO_USER:-}}"
CILIUM_VER="1.16.5"
GATEWAY_API_VER="v1.2.0"   # Cilium 1.16 호환 standard channel

log() { echo -e "\033[1;32m[+]\033[0m $*"; }

[[ $EUID -eq 0 ]] || { echo "run as root (sudo)"; exit 1; }

log "1/6 kubeadm init (apiserver=${APISERVER_IP}, pod-cidr=${POD_CIDR})"
if ! [[ -f /etc/kubernetes/admin.conf ]]; then
  kubeadm init \
    --apiserver-advertise-address="${APISERVER_IP}" \
    --pod-network-cidr="${POD_CIDR}" \
    --service-cidr="${SVC_CIDR}" \
    --node-name="${NODE_NAME}" \
    --cri-socket=unix:///run/containerd/containerd.sock \
    --skip-phases=addon/kube-proxy   # Cilium은 kube-proxy 대체 가능 (kubeProxyReplacement)
else
  log "  already initialized; skipping"
fi

log "2/6 kubeconfig for root${KUBE_USER:+ + ${KUBE_USER}}"
mkdir -p /root/.kube && cp -f /etc/kubernetes/admin.conf /root/.kube/config
if [[ -n "$KUBE_USER" && "$KUBE_USER" != root ]]; then
  USER_HOME="$(getent passwd "$KUBE_USER" | cut -d: -f6)"
  [[ -n "$USER_HOME" ]] || { echo "unknown user $KUBE_USER (LLMD_KUBE_USER)"; exit 1; }
  mkdir -p "${USER_HOME}/.kube" && cp -f /etc/kubernetes/admin.conf "${USER_HOME}/.kube/config"
  chown -R "$KUBE_USER:$(id -gn "$KUBE_USER")" "${USER_HOME}/.kube"
fi

export KUBECONFIG=/etc/kubernetes/admin.conf

log "3/6 install Gateway API CRDs (${GATEWAY_API_VER}, standard channel)"
kubectl apply -f "https://github.com/kubernetes-sigs/gateway-api/releases/download/${GATEWAY_API_VER}/standard-install.yaml"

log "4/6 install Cilium CLI"
if ! command -v cilium >/dev/null 2>&1; then
  CILIUM_CLI_VER="$(curl -s https://raw.githubusercontent.com/cilium/cilium-cli/main/stable.txt)"
  curl -sL --remote-name-all "https://github.com/cilium/cilium-cli/releases/download/${CILIUM_CLI_VER}/cilium-linux-amd64.tar.gz"
  tar -C /usr/local/bin -xzf cilium-linux-amd64.tar.gz
  rm -f cilium-linux-amd64.tar.gz
fi

log "5/6 install Cilium ${CILIUM_VER} (Gateway API + kube-proxy replacement)"
cilium install --version "${CILIUM_VER}" \
  --set kubeProxyReplacement=true \
  --set k8sServiceHost="${APISERVER_IP}" \
  --set k8sServicePort=6443 \
  --set gatewayAPI.enabled=true \
  --set hubble.relay.enabled=true \
  --set hubble.ui.enabled=true || true

cilium status --wait || true

log "6/6 print join command for worker"
echo
echo "==== run this on the worker (${LLMD_NODE_NPU1:-npu-node-1}) after stage1 there ===="
kubeadm token create --print-join-command
echo "=========================================================="

log "control-plane node:"
kubectl get nodes -o wide
log "done."
