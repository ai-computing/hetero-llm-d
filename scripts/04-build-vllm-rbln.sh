#!/usr/bin/env bash
# Build the vllm-rbln container image on npu-node-1 (where Rebellions packages are reachable)
# and import it into containerd's k8s.io namespace so Kubernetes can use it
# without an external registry.
#
# Run on npu-node-1:
#   bash /tmp/04-build-vllm-rbln.sh
#
# Requires sudo for `ctr -n k8s.io images import` only.
set -euo pipefail

IMAGE="vllm-rbln:0.10.2"
WORKDIR="$(mktemp -d)"
trap 'rm -rf "$WORKDIR"' EXIT

cp ~/vllm-rbln.Dockerfile "$WORKDIR/Dockerfile"

echo "[+] building $IMAGE with podman (rootless)"
cd "$WORKDIR"
podman build -t "$IMAGE" .

echo "[+] saving image tarball"
podman save -o /tmp/vllm-rbln.tar "$IMAGE"

echo "[+] importing into containerd k8s.io namespace (needs sudo)"
sudo ctr -n k8s.io images import /tmp/vllm-rbln.tar
rm -f /tmp/vllm-rbln.tar

echo "[+] verify:"
sudo ctr -n k8s.io images ls | grep vllm-rbln || true

echo
echo "DONE — Deployment에서 image: docker.io/library/vllm-rbln:0.10.2 로 참조 가능"
echo "  (containerd가 fully-qualified name을 기대하므로 library/ 접두사 사용)"
