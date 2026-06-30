#!/usr/bin/env bash
# A100 두 장을 K8s에서 사용 가능하게 만들기.
# 1) NVIDIA driver/library version mismatch → kernel module reload (reboot 없이)
# 2) nvidia-container-toolkit 설치 + containerd 연동
# 3) DCGM 등 추가 도구는 GPU Operator로 별도 처리
#
# 실행: sudo bash /tmp/05-nvidia-setup.sh
set -eux

# ─── 0) 점유 process 확인 (unload 가능 여부) ──────────────────
lsof /dev/nvidia* 2>/dev/null | head || true

# ─── 1) module reload ───────────────────────────────────────
# 만약 unload 실패하면 (점유 process 있음) reboot 필요.
modprobe -r nvidia_uvm nvidia_drm nvidia_modeset nvidia
modprobe nvidia
nvidia-smi || { echo "[!] still failing — likely needs reboot"; exit 1; }

# ─── 2) nvidia-container-toolkit ────────────────────────────
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq curl gnupg
distribution="$(. /etc/os-release; echo "$ID$VERSION_ID")"
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey \
  | gpg --yes --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
curl -fsSL "https://nvidia.github.io/libnvidia-container/${distribution}/libnvidia-container.list" \
  | sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' \
  > /etc/apt/sources.list.d/nvidia-container-toolkit.list
apt-get update -qq
apt-get install -y -qq nvidia-container-toolkit

# ─── 3) containerd CRI 연동 ─────────────────────────────────
nvidia-ctk runtime configure --runtime=containerd --set-as-default
systemctl restart containerd

# ─── 4) sanity check ────────────────────────────────────────
nvidia-ctk --version
nvidia-smi
echo "OK — proceed to deploy nvidia-device-plugin via Helm on the control-plane"
