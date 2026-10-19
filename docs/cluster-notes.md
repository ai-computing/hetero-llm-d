# 클러스터 운영 메모 (참고 자료)

[README](../README.md)에서 옮겨 온 운영 메모입니다. 내용은 작성 당시 그대로이며, 시점이 지난 항목은 날짜를 함께 적었습니다.
현재 상태는 [STATUS.md](../STATUS.md)를 기준으로 봅니다.

- 노드는 역할로 부릅니다: **control-plane 노드**(Dell R7525, 가속기 없음), **NPU 노드**(RBLN-CA22 ×4 + RNGD ×3),
  **GPU·NPU 노드**(RNGD ×2 + A100 80GB ×2, 2026-10-15부터), **CPU 노드** ×3.
- `<cp-node-ip>`, `<gateway-host>`, `<npu-node-ip>`, `<gpu-npu-node-ip>` 같은 placeholder의 실제 값은 untracked
  `cluster.local.env`에만 둡니다 ([`cluster.example.env`](../cluster.example.env) 참고).

## 목차

- [진행 현황 스냅샷 (2026-06-01)](#진행-현황-스냅샷-2026-06-01)
- [Rancher 사용자/RBAC 셋업](#rancher-사용자rbac-셋업)
- [GPU vs NPU — LLM 서빙 관점 비교](#gpu-vs-npu--llm-서빙-관점-비교)
- [사내 IP 정책 메모](#사내-ip-정책-메모)
- [트러블슈팅 메모](#트러블슈팅-메모)
- [다음 트랙 메모](#다음-트랙-메모)
- [노드별 하드웨어 메모](#노드별-하드웨어-메모)

GPU vs NPU 비교 표의 가격·전력 수치는 작성 당시의 일반 참고치이며, 이 레포에서 측정한 값이 아닙니다.

## 진행 현황 스냅샷 (2026-06-01)

> 2026-06-01 기준 표입니다. 이후 A100 위치, 활성 모델이 바뀌었습니다([STATUS.md](../STATUS.md)).

| 단계 | 상태 | 비고 |
|------|------|------|
| Control-plane (kubeadm 1.31 + Cilium 1.16.5 + Gateway API) | ✅ | `01-` `02-` 스크립트 |
| Worker join (NPU 노드, GPU·NPU 노드, CPU 노드 ×3) | ✅ | `03-` 스크립트 |
| **Web UI**: Rancher / Headlamp / Hubble / Grafana / Prometheus | ✅ | NodePort 30443/30502/30081/30300/30090 |
| **kube-prometheus-stack** + DCGM exporter + Furiosa metrics + vLLM ServiceMonitors | ✅ | 풀-스택 메트릭 (GPU/NPU/CPU/모델) |
| **Rebellions NPU Operator** v0.3.3 | ✅ | `rebellions.ai/ATOM: 4` allocatable, host KMD 3.0.0 사용 |
| **Furiosa device-plugin** 2026.1.0 | ✅ | `furiosa.ai/rngd: 4` (GPU·NPU 노드) / `2` (NPU 노드) |
| **NVIDIA device-plugin + DCGM** | ✅ | `nvidia.com/gpu: 2` (A100 80GB × 2), RuntimeClass `nvidia` |
| **envoy-gateway** + Cilium L2 announcement (IP `<gateway-host>`) | ✅ | `Programmed=True` |
| **llm-d EPP v0.7** (`no-hit-lru-scorer` 포함 4-scorer set) | ✅ | image swap `ghcr.io/llm-d/llm-d-router-endpoint-picker-dev:main`, envoy-sidecar 제거 |
| **A100 ds4 (DeepSeek V4 Flash)** | ✅ | antirez `ds4` engine + 97GB hybrid imatrix-fixed GGUF, 한국어 정상 |
| **RBLN KONI-Llama3.1-8B** (TP=4) | ✅ | 사용자 직접 컴파일 → vllm-rbln-koni 배포 |
| **CPU ollama** | ✅ | CPU 노드 풀 |
| **Furiosa Qwen3-Embedding-8B** (RAG embedding) | ✅ | RNGD × 2, dim 4096 |
| **RAG (Qdrant + retriever + NAS SMB read-only)** | 🔄 | NAS SMB Secret 재생성 대기 (사용자) |
| Multi-tenant Quota + Rancher RBAC | ✅ | tenant-a/b + alice/bob 매핑 |
| KEDA autoscaling | ✅ | `vllm_num_requests_waiting` trigger |
| Furiosa-LLM Llama-3.1-8B 서빙 | 🟡 | 한국어 깨짐 이슈로 사용자 down (KONI/EXAONE compile로 대체 가능) |

## Rancher 사용자/RBAC 셋업

Rancher UI(`https://<cp-node-ip>:30443`)에 로그인 후:

1. **첫 로그인**: bootstrap 비번으로 로그인 → 새 비번 설정 요구
2. **Users 생성**: 좌측 메뉴 `☰` → **Users & Authentication** → **Users** → **Create**
3. **Cluster 권한 부여**: 사용자 생성 후 → **Cluster Management** → 클러스터 선택 → **Members** → **Add Member**로 사용자 추가, 역할 선택 (Owner / Member / Read-only)
4. **Namespace 단위 권한**: 클러스터 안에서 **Projects/Namespaces** → 프로젝트 만들고 멤버 + 자원 quota 지정
5. **NPU quota**: namespace ResourceQuota로 `rebellions.ai/ATOM: 2`, `furiosa.ai/rngd: 1` 같이 지정해 사용자별 NPU 분배

## GPU vs NPU — LLM 서빙 관점 비교

| 축 | **GPU** (예: NVIDIA A100/H100) | **NPU** (Rebellions ATOM+, Furiosa RNGD) |
|---|---|---|
| **설계 철학** | 범용 SIMT/SIMD 병렬 (graphics + HPC + AI 다 함) | LLM·CNN 추론 특화. systolic / matrix engine 중심 |
| **연산 단위** | CUDA core (수천) + Tensor core (수백) | 매트릭스 곱 전용 PE (Processing Element) 배열 |
| **메모리** | HBM2e/HBM3 80GB (A100) ~ 192GB (MI300X). 1~3TB/s bandwidth | 16GB (CA22 on-chip) ~ 64GB (RNGD HBM). SRAM on-chip 비중 ↑ |
| **정밀도** | FP32/TF32/BF16/FP16/FP8/INT8 — multi-precision | INT8/INT4 native + 일부 FP8/BF16. quantization-first 설계 |
| **소프트웨어 스택** | CUDA · cuDNN · NCCL · PyTorch/TF first-class · vLLM/SGLang OOTB | 벤더 SDK (rebel-compiler, furiosa-llm), 모델 사전 **컴파일** 필요 |
| **모델 적재** | weight를 HBM에 직접 load (런타임) | `.rbln` 같은 **사전 컴파일된 artifact** 필요. 모델별 컴파일 시간 들음 |
| **유연성** | 새 모델·새 아키텍처 즉시 실행, 학습/추론 둘 다 | 추론 위주. 새 모델은 컴파일러 지원 매트릭스 안에 있어야 |
| **TP/PP** | NVLink/NVSwitch(900GB/s) 같은 고속 interconnect | PCIe + 자체 link. multi-chip TP가 더 비싸지만 동작 |
| **전력 효율** | A100 400W / H100 700W TDP | RNGD ~150W, CA22 ~30W. **perf/W LLM 추론에서 NPU 우위** |
| **단가** | H100 ~$30K, A100 ~$10K (2026 기준) | NPU 다양 — 보통 동급 throughput 대비 30~60% 가격 |
| **공급 안정성** | NVIDIA 의존 (export control, allocation 이슈) | 국산/유럽/Intel 대안. 다변화 ↑ |
| **K8s 통합** | NVIDIA GPU Operator (검증·완성도 최상) | 벤더별 device-plugin + NPU Operator (Rebellions/Furiosa 등) — 표준화 진행 중 |
| **모니터링** | DCGM-exporter (Prometheus, 광범위) | 벤더별 metrics-exporter (rbln-metrics, furiosa-metrics) |
| **장점** | ① 어떤 모델이든 즉시 돌아감 ② 학습·연구에도 동일 HW ③ 압도적 ecosystem | ① 추론 perf/W가 압도적 ② 가격 경쟁력 ③ 공급망 다변화 ④ 사전 컴파일로 latency 예측 가능 |
| **단점** | ① 비쌈 ② 전력 큼 ③ 학습용 HBM이 추론엔 과잉 ④ 공급 부족 | ① 모델 호환 매트릭스 좁음 ② 컴파일 단계 추가 ③ 학습 못 함 ④ 디버깅 도구 미성숙 |
| **언제 GPU** | 모델 자주 바꿈 / fine-tuning / 새 architecture / 한 클러스터로 학습+추론 | |
| **언제 NPU** | | 정해진 모델 대량 서빙 / 전력 budget 빠듯 / 비용 민감 / multi-tenant 안정 latency 필요 |

### 우리 환경 시사점

- **NPU 노드**: RBLN-CA22×4 + RNGD×3 — 한 노드에 두 NPU 진영 공존 (A100×2는 2026-10 기준 GPU·NPU 노드로 이동) → llm-d로 **이종 풀(heterogeneous pool)** 운영 검증 환경으로 이상적
- **GPU·NPU 노드**: RNGD×2 + A100 80GB×2 → Furiosa와 NVIDIA GPU가 한 노드에 공존
- **추천 운영 패턴**:
  - **모델 종류 자주 바꾸는 R&D** → A100 살려서 vLLM 자유 실행
  - **production 서빙 (모델 fix)** → NPU로 옮겨 비용/전력 최적화
  - **prefill/decode 분리**: GPU에서 prefill(짧고 컴퓨트 무거움) → NPU에서 decode(긴 사이클, 메모리 무거움). llm-d의 `prefill.create=true` + NIXL connector

### 추론 stack 비교 한 줄

| 스택 | 가속기 | 컴파일 | 모델 변경 비용 |
|---|---|---|---|
| vLLM / SGLang (NVIDIA) | GPU | 런타임 JIT | 즉시 (모델 weight만 다운) |
| vllm-rbln (Rebellions) | RBLN ATOM | `optimum-rbln` 사전 컴파일 (수분~수십분) | 모델별 한 번 컴파일 후 재사용 |
| furiosa-llm (Furiosa) | RNGD | Furiosa가 HF에 사전 컴파일 모델 publish | HF artifact 다운로드만 |

## 사내 IP 정책 메모

⚠️ **임의 IP 점유 금지** — Cilium LoadBalancer IP pool에 회사가 할당 안 한 IP(<미할당 IP> 등)를 잡으면 사내 다른 시스템과 ARP 충돌 위험. IT에서 정식 할당받은 IP만 사용한다.

회사에서 신규 IP를 받으면 재구성:

```bash
kubectl apply -f - <<EOF
apiVersion: cilium.io/v2alpha1
kind: CiliumLoadBalancerIPPool
metadata:
  name: llm-d-pool
spec:
  blocks:
    - start: <할당받은 시작 IP>
      stop:  <할당받은 끝 IP>
---
apiVersion: cilium.io/v2alpha1
kind: CiliumL2AnnouncementPolicy
metadata:
  name: llm-d-l2-policy
spec:
  serviceSelector:
    matchLabels:
      gateway.networking.k8s.io/gateway-name: llm-d-gateway
  loadBalancerIPs: true
  interfaces:
    - ^eno1\$|^ens.+\$
EOF
```

그동안 임시 노출:
- **envoy Gateway NodePort `30788`**: `http://<cp-node-ip>:30788/{exaone,llama31,gpu}/chat/completions` (HTTPRoute path-based 분기 동작)
- 각 모델 직결: `:30800` (EXAONE/RBLN) · `:30801` (Llama/Furiosa) · `:30802` (Llama/A100)

## 트러블슈팅 메모

진행하면서 부닥친 문제와 해결:

1. **`[ERROR FileExisting-conntrack]: conntrack not found`** → `01-cp-install-tooling.sh`에 `conntrack socat ethtool ebtables` 추가 (반영 완료).
2. **`error execution phase upload-config/kubelet: Error writing Crisocket information for the control-plane node: nodes "<Mixed-Case-Hostname>" not found`** → 호스트네임 대소문자 충돌. `02-cp-init-cluster.sh`의 `--node-name`을 `hostname -s | tr '[:upper:]' '[:lower:]'`로 소문자 강제 (반영 완료). 호스트네임 자체는 그대로 둠.
3. **`detected that the sandbox image "" of the container runtime is inconsistent`** → containerd 2.x `containerd config default`가 `sandbox_image`를 비워두는 경우 있어 `01-cp-install-tooling.sh`에서 `registry.k8s.io/pause:3.10`로 명시 패치.
4. **부분 init 실패 후 재실행** → `sudo kubeadm reset -f && sudo rm -rf /etc/cni/net.d /etc/kubernetes /var/lib/etcd ~/.kube /root/.kube` 후 stage2 재실행. 스크립트는 idempotent.

## 다음 트랙 메모

### Furiosa-LLM 모델 서버 배포

Furiosa 공식 가이드 https://developer.furiosa.ai/latest/en/cloud_native_toolkit/llm_d.html — 핵심 단계:

```bash
helm install furiosa-modelservice furiosa/llm-d-modelservice \
  -n llm-serving \
  -f manifests/furiosa-llm-modelservice-values.yaml
```

`values.yaml` 예시:
```yaml
modelArtifacts:
  name: "furiosa-ai/Llama-3.1-8B-Instruct"
  uri: "pvc+hf://model-pvc/furiosa-ai/Llama-3.1-8B-Instruct"
accelerator:
  type: "furiosa"
decode:
  replicas: 1
  containers:
    - name: "furiosa-llm"
      image: furiosaai/furiosa-llm:latest
      modelCommand: furiosaLLMServe
      resources:
        limits:
          furiosa.ai/rngd: 4
        requests:
          furiosa.ai/rngd: 4
```

선결: NFS/PVC 또는 hostPath로 모델 가중치 prefetch + Furiosa의 `furiosa-ai/Llama-3.1-8B-Instruct` 모델이 RNGD 호환임을 확인.

### vllm-rbln 컨테이너 이미지 영구화

현재 Deployment는 매 시작마다 `apt install` ~30s 소요. 한 번 빌드해 두면 idempotent + 빠름.

Dockerfile: [`manifests/vllm-rbln.Dockerfile`](../manifests/vllm-rbln.Dockerfile) (pypi.rbln.ai 인증 불요, apt만)

```bash
# NPU 노드에서:
cp ~/llm-d-setup/manifests/vllm-rbln.Dockerfile /tmp/Dockerfile
podman build -t localhost/vllm-rbln-base:2026.05 /tmp
podman save -o /tmp/vllm-rbln-base.tar localhost/vllm-rbln-base:2026.05
sudo ctr -n k8s.io images import /tmp/vllm-rbln-base.tar
```

Deployment 매니페스트 갱신:
```yaml
image: localhost/vllm-rbln-base:2026.05
imagePullPolicy: Never
command: ["python3", "-m", "vllm.entrypoints.openai.api_server"]
args:
  - "--model=/models/..."
  - ...
# bash apt-get install 단계 제거
```

### Llama-3.1-8B TP=4 재컴파일

스크립트: [`manifests/compile-llama31-8b-tp4.py`](../manifests/compile-llama31-8b-tp4.py)

- `rbln_npu="RBLN-CA22"` + `rbln_create_runtimes=False` 로 NPU 점유 없이 컴파일 (다른 pod이 NPU 사용 중이라도 OK)
- 출력: `~/rbln-Llama-3.1-8B-Instruct-tp4-bs1-s8192/`
- 완료 후 Deployment의 `volumes.model.hostPath.path`를 이 디렉토리로 교체

### manifests/ 추가 예정 목록 (작성 당시)

- `rebellions-device-plugin.yaml` — Rebellions가 제공하는 DaemonSet (벤더 매뉴얼 참조)
- `vllm-rbln-deployment.yaml` — vllm-rbln 컨테이너 + RBLN 디바이스 요청 + HF cache hostPath + HF token Secret
- `inference-pool.yaml` — Gateway API Inference Extension `InferencePool` CR
- `gateway.yaml` + `httproute.yaml` — 사내망 노출 (MetalLB L2 모드)
- `prometheus-values.yaml` — kube-prometheus-stack 커스터마이즈

## 노드별 하드웨어 메모

### control-plane 노드 (Dell R7525, `<cp-node-ip>`)
- Ubuntu 26.04 "resolute", 커널 7.x, 128 vCPU / 373GB RAM
- NIC: `eno1` UP (`<cp-node-ip>/24`), 나머지 down
- 가속기 없음 (의도적 — 관리/컨트롤 플레인 전용)

### NPU 노드 (worker, `<npu-node-ip>`)
- Ubuntu 22.04.5, 커널 6.8, 96코어 / 1.5TB RAM, NUMA 2-node, disk 1.5TB 여유
- ~~NVIDIA A100 PCIe 80GB × 2 (44:00.0, 45:00.0)~~ — **GPU·NPU 노드로 이동**(2026-10-15 확인, 현재 이 노드에 NVIDIA 장치 없음, 45:00.0은 RNGD)
- Rebellions RBLN-CA22 × 4 (83/84/c3/c4:00.0, NUMA 1, 15.7GiB/장) — KMD 3.0.0 정상
- Furiosa RNGD × 3 (03/04/45:00.0)
- containerd active, docker installed (inactive), helm 설치됨, kubectl/kubeadm 미설치
- venv: `~/vllm_test/venv` (vllm_rbln 0.10.2.post1, rebel-compiler 0.10.2, optimum-rbln 0.10.2)
- HF cache: `~/.cache/huggingface` (143GB 사용)

### GPU·NPU 노드 (worker, `<gpu-npu-node-ip>`)
- Ubuntu 22.04.5, 48코어 / 1TB RAM, 16 NUMA (SNC)
- Furiosa RNGD × 2 (50/63:00.0), driver 2026.4.0
- NVIDIA A100 PCIe 80GB × 2 (99/bd:00.0), driver 580.178, nvidia-container-toolkit 1.19.1 (`/etc/containerd/conf.d/99-nvidia.toml`) — 2026-10-15 복구
- 노드 라벨 `feature.node.kubernetes.io/pci-10de.present=true`는 수동 부여(nvidia-device-plugin DS selector가 요구)
- kubelet `evictionHard` nodefs/imagefs 5% (디스크 대부분이 사용자 홈 데이터, 백업 `config.yaml.bak-20261015`)
- SSH는 기본이 아닌 포트 사용
