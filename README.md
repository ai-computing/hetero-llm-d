# llm-d 사내 클러스터 셋업

GPU·NPU·CPU 노드들을 K8s + llm-d로 묶어 관리하기 위한 설치 자동화 스크립트와 운영 메모.

## 목표 토폴로지

```
              ┌─────────────────────────────────────────┐
              │  R7525  (192.0.2.8)                │
              │  gspark-poweredge-r7525                 │
              │  ─ 관리 노드 (worker 역할 X)            │
              │  ─ K8s control-plane (kubeadm)          │
              │  ─ Cilium CNI + Gateway API             │
              │  ─ llm-d Router (Envoy + EPP)           │
              │  ─ Prometheus / Grafana                 │
              └────────────────────┬────────────────────┘
                                   │
                ┌──────────────────┼──────────────────┐
                │                  │                  │
       ┌────────▼────────┐ ┌───────▼────────┐ ┌──────▼─────────┐
       │ etri-001        │ │ (future)       │ │ etri-ESC8000   │
       │ 192.0.2.10  │ │ NVIDIA-only?   │ │ 192.0.2.9 │
       │ A100 x2         │ │                │ │ Furiosa RNGD x4│
       │ RBLN-CA22 x4    │ │                │ │ (보류)         │
       │ Furiosa RNGD x2 │ │                │ │                │
       │ Ubuntu 22.04    │ │                │ │ Ubuntu 22.04   │
       └─────────────────┘ └────────────────┘ └────────────────┘
```

- 사내망 `192.0.2.6/24`, 기본 GW `192.0.2.7`
- 클러스터 내부 CIDR: pod `192.0.2.2/16`, service `192.0.2.15/12` (사내 라우팅과 충돌 없음을 확인)
- 외부 egress OK (huggingface.co / github.com 200 응답)
- Kubernetes 버전 `v1.31` (Gateway API Inference Extension 호환)

## 진행 현황 (2026-06-01)

> 라이브 상태 스냅샷은 [STATUS.md](./STATUS.md). 기능 매트릭스는 [FEATURES.md](./FEATURES.md), NPU 한계는 [NPU-FEATURES.md](./NPU-FEATURES.md), 활용 시나리오는 [PLAYBOOK.md](./PLAYBOOK.md).

| 단계 | 상태 | 비고 |
|------|------|------|
| Control-plane (kubeadm 1.31 + Cilium 1.16.5 + Gateway API) | ✅ | `01-` `02-` 스크립트 |
| Worker join (etri-001, etri-esc8000-e11, cpu-1/2/3) | ✅ | `03-` 스크립트 |
| **Web UI**: Rancher / Headlamp / Hubble / Grafana / Prometheus | ✅ | NodePort 30443/30502/30081/30300/30090 |
| **kube-prometheus-stack** + DCGM exporter + Furiosa metrics + vLLM ServiceMonitors | ✅ | 풀-스택 메트릭 (GPU/NPU/CPU/모델) |
| **Rebellions NPU Operator** v0.3.3 | ✅ | `rebellions.ai/ATOM: 4` allocatable, host KMD 3.0.0 사용 |
| **Furiosa device-plugin** 2026.1.0 | ✅ | `furiosa.ai/rngd: 4` (esc8000) / `2` (etri-001) |
| **NVIDIA device-plugin + DCGM** | ✅ | `nvidia.com/gpu: 2` (A100 80GB × 2), RuntimeClass `nvidia` |
| **envoy-gateway** + Cilium L2 announcement (IP `192.0.2.12`) | ✅ | `Programmed=True` |
| **llm-d EPP v0.7** (`no-hit-lru-scorer` 포함 4-scorer set) | ✅ | image swap `ghcr.io/llm-d/llm-d-router-endpoint-picker-dev:main`, envoy-sidecar 제거 |
| **A100 ds4 (DeepSeek V4 Flash)** | ✅ | antirez `ds4` engine + 97GB hybrid imatrix-fixed GGUF, 한국어 정상 |
| **RBLN KONI-Llama3.1-8B** (TP=4) | ✅ | 사용자 직접 컴파일 → vllm-rbln-koni 배포 |
| **CPU ollama** | ✅ | cpu-1/2/3 풀 |
| **Furiosa Qwen3-Embedding-8B** (RAG embedding) | ✅ | RNGD × 2, dim 4096 |
| **RAG (Qdrant + retriever + NAS SMB read-only)** | 🔄 | NAS SMB Secret 재생성 대기 (사용자) |
| Multi-tenant Quota + Rancher RBAC | ✅ | tenant-a/b + alice/bob 매핑 |
| KEDA autoscaling | ✅ | `vllm_num_requests_waiting` trigger |
| Furiosa-LLM Llama-3.1-8B 서빙 | 🟡 | 한국어 깨짐 이슈로 사용자 down (KONI/EXAONE compile로 대체 가능) |

## 접속 URL (사내망 직접)

| UI | URL | 인증 |
|---|---|---|
| Headlamp | http://192.0.2.8:30502 | Bearer token: `kubectl create token headlamp -n headlamp --duration=24h` |
| Cilium Hubble UI | http://192.0.2.8:30081 | 없음 |
| Grafana | http://192.0.2.8:30300 | admin / admin (운영 전 변경 필수) |
| Prometheus | http://192.0.2.8:30090 | 없음 |
| **Rancher** | https://192.0.2.8:30443 | admin / admin (첫 로그인 시 비번 변경 요구) |
| **llm-d Gateway** | http://192.0.2.12/v1 | OpenAI 호환 통합 entrypoint (path 분기) |
| ds4 (DeepSeek V4 Flash) 직결 | http://192.0.2.8:30804/v1 | model: `deepseek-v4-flash` |
| vllm-rbln-koni 직결 | http://192.0.2.8:30800/v1 | model: `koni-llama3.1-8b-rbln` |
| ollama-cpu 직결 | http://192.0.2.8:30803/v1 | CPU 풀 |

(NodePort는 모든 노드에서 동일 포트 노출 — `192.0.2.10`, `192.0.2.9`도 동작)

## Rancher에서 사용자/RBAC 셋업 가이드

Rancher UI(https://192.0.2.8:30443)에 로그인 후:

1. **첫 로그인**: bootstrap 비번 `admin` → 새 비번 설정 요구
2. **Users 생성**: 좌측 메뉴 `☰` → **Users & Authentication** → **Users** → **Create**
3. **Cluster 권한 부여**: 사용자 생성 후 → **Cluster Management** → 클러스터 선택 → **Members** → **Add Member**로 사용자 추가, 역할 선택 (Owner / Member / Read-only)
4. **Namespace 단위 권한**: 클러스터 안에서 **Projects/Namespaces** → 프로젝트 만들고 멤버 + 자원 quota 지정
5. **NPU quota**: namespace ResourceQuota로 `rebellions.ai/ATOM: 2`, `furiosa.ai/rngd: 1` 같이 지정해 사용자별 NPU 분배

## llm-d 모델 서빙 API 사용

OpenAI 호환 호출 예시 (사내 클라이언트에서):

```bash
curl -X POST http://192.0.2.8:30800/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "exaone-3.5-7.8b-instruct",
    "messages": [
      {"role": "user", "content": "안녕하세요"}
    ],
    "max_tokens": 200
  }'
```

또는 Python OpenAI SDK:

```python
from openai import OpenAI
client = OpenAI(
    base_url="http://192.0.2.8:30800/v1",
    api_key="dummy"   # vllm은 인증 미적용 시 아무 값
)
resp = client.chat.completions.create(
    model="exaone-3.5-7.8b-instruct",
    messages=[{"role": "user", "content": "Rebellions NPU란?"}],
)
print(resp.choices[0].message.content)
```

## 실행 순서

### 1. R7525 (control-plane) — sudo 비번 필요

```bash
sudo bash ~/llm-d-setup/scripts/01-cp-install-tooling.sh
sudo bash ~/llm-d-setup/scripts/02-cp-init-cluster.sh
```

`02-cp-init-cluster.sh` 마지막에 `kubeadm join 192.0.2.8:6443 --token ... --discovery-token-ca-cert-hash sha256:...` 명령이 출력됩니다. **그 줄을 복사해두세요.**

### 2. etri-001 (worker) — sudo 비번 필요

스크립트 복사:

```bash
scp ~/llm-d-setup/scripts/03-worker-install.sh gspark@192.0.2.10:/tmp/
```

worker 노드에서 실행:

```bash
ssh gspark@192.0.2.10 'sudo bash /tmp/03-worker-install.sh'
ssh gspark@192.0.2.10 'sudo kubeadm join 192.0.2.8:6443 --token <...> --discovery-token-ca-cert-hash sha256:<...>'
```

### 3. join 확인

R7525에서:

```bash
kubectl get nodes -o wide
kubectl get pods -A
```

## 스크립트 요약

### `01-cp-install-tooling.sh`
- swap off (영구), 커널 모듈 (`overlay`, `br_netfilter`), sysctl 3종 (`br-nf-call-iptables`, `br-nf-call-ip6tables`, `ip_forward`)
- containerd 2.2.2 + runc 1.4.0 + 보조 패키지 (`conntrack`, `socat`, `ethtool`, `ebtables`, `jq`)
- containerd config: `SystemdCgroup=true`, `sandbox_image=registry.k8s.io/pause:3.10`
- pkgs.k8s.io v1.31 apt repo → `kubeadm/kubelet/kubectl 1.31.*` 설치 + `apt-mark hold`
- crictl 엔드포인트 설정

### `02-cp-init-cluster.sh`
- `kubeadm init --apiserver-advertise-address=192.0.2.8 --pod-network-cidr=192.0.2.2/16 --service-cidr=192.0.2.15/12 --skip-phases=addon/kube-proxy --node-name=<소문자 hostname>`
- kubeconfig를 `/root/.kube/config`, `~gspark/.kube/config`로 복사
- Gateway API CRDs (v1.2.0 standard) 설치
- Cilium CLI 다운로드 + Cilium 1.16.5 설치 (`kubeProxyReplacement=true`, `gatewayAPI.enabled=true`, Hubble UI 활성화)
- worker 노드용 `kubeadm join` 명령 출력

### `03-worker-install.sh`
- worker 측에서 동일한 사전 설정 + kubelet/kubeadm 1.31만 설치 (kubectl 제외)
- containerd가 이미 깔려 있으면 config 갱신만 수행
- 마지막에 위 join 명령을 출력 (실제 토큰은 stage2 결과에서 가져와 붙임)

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

- **etri-001**: A100×2(driver 문제 보류) + RBLN-CA22×4(7.8B EXAONE 서빙 중) + RNGD×2 — 한 노드에 GPU/NPU 두 진영 공존 → llm-d로 **이종 풀(heterogeneous pool)** 운영 검증 환경으로 이상적
- **etri-esc8000-e11**: RNGD×4 전용 → Furiosa-LLM으로 Llama-3.1-8B 서빙. GPU 없는 대신 전력 ⅓, **perf/W 1위 후보**
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

## 🎯 운영 entrypoint

**공식 통합 IP**: `192.0.2.12` (사내 IT 할당)

```bash
# RBLN: EXAONE-3.5-7.8B (한국어 친화)
curl -X POST http://192.0.2.12/exaone/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"exaone-3.5-7.8b-instruct","messages":[{"role":"user","content":"..."}]}'

# Furiosa: Llama-3.1-8B (precompiled)
curl -X POST http://192.0.2.12/llama31/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"furiosa-ai/Llama-3.1-8B-Instruct","messages":[{"role":"user","content":"..."}]}'

# NVIDIA A100: Llama-3.1-8B (vllm-openai)
curl -X POST http://192.0.2.12/gpu/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"llama-3.1-8b-instruct-gpu","messages":[{"role":"user","content":"..."}]}'
```

| 경로 | 모델 | 가속기 | 노드 |
|---|---|---|---|
| `/exaone` | EXAONE-3.5-7.8B-Instruct | Rebellions RBLN-CA22 × 4 | etri-001 |
| `/llama31` | Llama-3.1-8B-Instruct | Furiosa RNGD × 4 | etri-esc8000-e11 |
| `/gpu` | Llama-3.1-8B-Instruct | NVIDIA A100 80GB × 2 | etri-001 |

## 사내 IP 정책 메모

⚠️ **임의 IP 점유 금지** — Cilium LoadBalancer IP pool에 회사가 할당 안 한 IP(192.0.2.11-222 등)를 잡으면 사내 다른 시스템과 ARP 충돌 위험. IT에서 정식 할당받은 IP만 사용한다.

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
- **envoy Gateway NodePort `30788`**: `http://192.0.2.8:30788/{exaone,llama31,gpu}/chat/completions` (HTTPRoute path-based 분기 동작)
- 각 모델 직결: `:30800` (EXAONE/RBLN) · `:30801` (Llama/Furiosa) · `:30802` (Llama/A100)

## 트러블슈팅 메모

진행하면서 부닥친 문제와 해결:

1. **`[ERROR FileExisting-conntrack]: conntrack not found`** → `01-cp-install-tooling.sh`에 `conntrack socat ethtool ebtables` 추가 (반영 완료).
2. **`error execution phase upload-config/kubelet: Error writing Crisocket information for the control-plane node: nodes "gspark-PowerEdge-R7525" not found`** → 호스트네임 대소문자 충돌. `02-cp-init-cluster.sh`의 `--node-name`을 `hostname -s | tr '[:upper:]' '[:lower:]'`로 소문자 강제 (반영 완료). 호스트네임 자체는 그대로 둠.
3. **`detected that the sandbox image "" of the container runtime is inconsistent`** → containerd 2.x `containerd config default`가 `sandbox_image`를 비워두는 경우 있어 `01-cp-install-tooling.sh`에서 `registry.k8s.io/pause:3.10`로 명시 패치.
4. **부분 init 실패 후 재실행** → `sudo kubeadm reset -f && sudo rm -rf /etc/cni/net.d /etc/kubernetes /var/lib/etcd ~/.kube /root/.kube` 후 stage2 재실행. 스크립트는 idempotent.

## Furiosa-LLM 모델 서버 배포 (다음 트랙)

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

## vllm-rbln 컨테이너 이미지 영구화 (다음 트랙)

현재 Deployment는 매 시작마다 `apt install` ~30s 소요. 한 번 빌드해 두면 idempotent + 빠름.

Dockerfile: `~/llm-d-setup/manifests/vllm-rbln.Dockerfile` (pypi.rbln.ai 인증 불요, apt만)

```bash
# etri-001에서:
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

## Llama-3.1-8B TP=4 재컴파일 (진행 중)

스크립트: `~/llm-d-setup/manifests/compile-llama31-8b-tp4.py`

- `rbln_npu="RBLN-CA22"` + `rbln_create_runtimes=False` 로 NPU 점유 없이 컴파일 (다른 pod이 NPU 사용 중이라도 OK)
- 출력: `~/rbln-Llama-3.1-8B-Instruct-tp4-bs1-s8192/`
- 완료 후 Deployment의 `volumes.model.hostPath.path`를 이 디렉토리로 교체

## 다음 단계 (manifests/ 디렉터리에 추가 예정)

- `rebellions-device-plugin.yaml` — Rebellions가 제공하는 DaemonSet (벤더 매뉴얼 참조)
- `vllm-rbln-deployment.yaml` — vllm-rbln 컨테이너 + RBLN 디바이스 요청 + HF cache hostPath + HF token Secret
- `inference-pool.yaml` — Gateway API Inference Extension `InferencePool` CR
- `gateway.yaml` + `httproute.yaml` — 사내망 노출 (MetalLB L2 모드)
- `prometheus-values.yaml` — kube-prometheus-stack 커스터마이즈

## 노드별 하드웨어 메모

### R7525 (관리, 192.0.2.8)
- Ubuntu 26.04 "resolute", 커널 7.x, 128 vCPU / 373GB RAM
- NIC: `eno1` UP (192.0.2.8/24), 나머지 down
- 가속기 없음 (의도적 — 관리/컨트롤 플레인 전용)

### etri-001 (worker, 192.0.2.10)
- Ubuntu 22.04.5, 커널 6.8, 96코어 / 1.5TB RAM, NUMA 2-node, disk 1.5TB 여유
- NVIDIA A100 PCIe 80GB × 2 (44:00.0, 45:00.0, NUMA 0) — **드라이버 580.159과 NVML mismatch, reboot 필요**
- Rebellions RBLN-CA22 × 4 (83/84/c3/c4:00.0, NUMA 1, 15.7GiB/장) — KMD 3.0.0 정상
- Furiosa RNGD × 2 (03/04:00.0) — 보너스
- containerd active, docker installed (inactive), helm 설치됨, kubectl/kubeadm 미설치
- venv: `~/vllm_test/venv` (vllm_rbln 0.10.2.post1, rebel-compiler 0.10.2, optimum-rbln 0.10.2)
- HF cache: `~/.cache/huggingface` (143GB 사용)

### etri-ESC8000-E11 (보류, 192.0.2.9:10022)
- Ubuntu 22.04.5, 48코어 / 1TB RAM, 16 NUMA (SNC)
- Furiosa RNGD × 4 (16/6a/94/be:00.0), driver 2026.2.0
- SSH 포트 10022 사용
- 현재 보류 — Rebellions 경로 완성 후 join 예정

## 참고

- llm-d 공식: https://llm-d.ai/docs
- Gateway API Inference Extension: https://github.com/kubernetes-sigs/gateway-api-inference-extension
- Cilium Gateway API: https://docs.cilium.io/en/stable/network/servicemesh/gateway-api/
- vllm-rbln: Rebellions가 제공하는 vLLM 포크 (HF Hub `rebellions-sw/*` 컴파일 모델 사용)
