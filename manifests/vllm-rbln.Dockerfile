# vllm-rbln 베이스 이미지 (apt 부분만 사전 빌드).
# pypi.rbln.ai 인증 필요한 vllm-rbln Python wheel은 컨테이너 안에 넣지 않고,
# Deployment에서 host /usr/local/lib/python3.10/dist-packages 를 hostPath로 마운트하여 사용.
# 따라서 이 이미지는 build context 외부 자원 의존 없이 누구나 빌드 가능.
#
# 빌드 + containerd k8s.io namespace import:
#   on npu-node-1:
#     cp ~/llm-d-setup/manifests/vllm-rbln.Dockerfile /tmp/Dockerfile
#     podman build -t localhost/vllm-rbln-base:2026.05 /tmp
#     podman save -o /tmp/vllm-rbln-base.tar localhost/vllm-rbln-base:2026.05
#     sudo ctr -n k8s.io images import /tmp/vllm-rbln-base.tar
#     # Deployment.image 를 localhost/vllm-rbln-base:2026.05 로 교체 + apt-get install 단계 제거
FROM ubuntu:22.04
ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    HF_HOME=/cache

RUN apt-get update && apt-get install -y --no-install-recommends \
      python3.10 python3.10-dev python3-pip \
      libdrm2 libnuma1 libgomp1 \
      g++ libc6-dev \
      ca-certificates curl \
    && rm -rf /var/lib/apt/lists/* \
    && ln -sf /usr/bin/python3.10 /usr/local/bin/python3 \
    && ln -sf /usr/bin/python3.10 /usr/local/bin/python

EXPOSE 8000
# Deployment의 command에서 host site-packages를 PYTHONPATH로 잡고 vllm 호출
ENTRYPOINT ["python3", "-m", "vllm.entrypoints.openai.api_server"]
