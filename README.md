# llm-d 사내 클러스터 셋업

GPU·NPU·CPU 노드들을 K8s + llm-d로 묶어 관리하기 위한 설치 자동화 스크립트와 운영 메모.

> **처음 읽는 분:** llm-d 배경지식 + 우리 환경 구성 + `lmd-top` 실측 스크린샷은  
> **[docs/ENVIRONMENT-GUIDE.md](./docs/ENVIRONMENT-GUIDE.md)** 를 먼저 보세요.

## 목표 토폴로지

```
              ┌─────────────────────────────────────────┐
              │  R7525  (198.51.100.105)                │
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
       │ 198.51.100.183  │ │ NVIDIA-only?   │ │ 198.51.100.126 │
       │ RBLN-CA22 x4    │ │                │ │ Furiosa RNGD x2│
       │ Furiosa RNGD x3 │ │                │ │ A100 80GB x2   │
       │                 │ │                │ │                │
       │ Ubuntu 22.04    │ │                │ │ Ubuntu 22.04   │
       └─────────────────┘ └────────────────┘ └────────────────┘
```

- 사내망 `<site-subnet>`, 기본 GW `<site-gw>`
- 클러스터 내부 CIDR: pod `<pod-cidr>`, service `<svc-cidr>` (사내 라우팅과 충돌 없음을 확인)
- 외부 egress OK (huggingface.co / github.com 200 응답)
- Kubernetes 버전 `v1.31` (Gateway API Inference Extension 호환)

## 진행 현황 (2026-06-01)

> **온보딩:** [docs/ENVIRONMENT-GUIDE.md](./docs/ENVIRONMENT-GUIDE.md) · 라이브 스냅샷: [STATUS.md](./STATUS.md) · 기능: [FEATURES.md](./FEATURES.md) · NPU: [NPU-FEATURES.md](./NPU-FEATURES.md) · 활용: [PLAYBOOK.md](./PLAYBOOK.md)

| 단계 | 상태 | 비고 |
|------|------|------|
| Control-plane (kubeadm 1.31 + Cilium 1.16.5 + Gateway API) | ✅ | `01-` `02-` 스크립트 |
| Worker join (etri-001, etri-esc8000-e11, cpu-1/2/3) | ✅ | `03-` 스크립트 |
| **Web UI**: Rancher / Headlamp / Hubble / Grafana / Prometheus | ✅ | NodePort 30443/30502/30081/30300/30090 |
| **kube-prometheus-stack** + DCGM exporter + Furiosa metrics + vLLM ServiceMonitors | ✅ | 풀-스택 메트릭 (GPU/NPU/CPU/모델) |
| **Rebellions NPU Operator** v0.3.3 | ✅ | `rebellions.ai/ATOM: 4` allocatable, host KMD 3.0.0 사용 |
| **Furiosa device-plugin** 2026.1.0 | ✅ | `furiosa.ai/rngd: 4` (esc8000) / `2` (etri-001) |
| **NVIDIA device-plugin + DCGM** | ✅ | `nvidia.com/gpu: 2` (A100 80GB × 2), RuntimeClass `nvidia` |
| **envoy-gateway** + Cilium L2 announcement (IP `<gateway-host>`) | ✅ | `Programmed=True` |
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
| Headlamp | http://<cp-node-ip>:30502 | Bearer token: `kubectl create token headlamp -n headlamp --duration=24h` |
| Cilium Hubble UI | http://<cp-node-ip>:30081 | 없음 |
| Grafana | http://<cp-node-ip>:30300 | 설치 시 정한 관리자 계정 (문서에 기록하지 않음) |
| Prometheus | http://<cp-node-ip>:30090 | 없음 |
| **Rancher** | https://<cp-node-ip>:30443 | 관리자 계정 (첫 로그인 시 비번 변경, 문서에 기록하지 않음) |
| **llm-d Gateway** | http://<gateway-host>/v1 | OpenAI 호환 통합 entrypoint (path 분기) |
| ds4 (DeepSeek V4 Flash) 직결 | http://<cp-node-ip>:30804/v1 | model: `deepseek-v4-flash` |
| vllm-rbln-koni 직결 | http://<cp-node-ip>:30800/v1 | model: `koni-llama3.1-8b-rbln` |
| ollama-cpu 직결 | http://<cp-node-ip>:30803/v1 | CPU 풀 |

(NodePort는 모든 노드에서 동일 포트 노출 — `<etri-001-ip>`, `<e11-ip>`도 동작)

## Rancher에서 사용자/RBAC 셋업 가이드

Rancher UI(https://<cp-node-ip>:30443)에 로그인 후:

1. **첫 로그인**: bootstrap 비번 `admin` → 새 비번 설정 요구
2. **Users 생성**: 좌측 메뉴 `☰` → **Users & Authentication** → **Users** → **Create**
3. **Cluster 권한 부여**: 사용자 생성 후 → **Cluster Management** → 클러스터 선택 → **Members** → **Add Member**로 사용자 추가, 역할 선택 (Owner / Member / Read-only)
4. **Namespace 단위 권한**: 클러스터 안에서 **Projects/Namespaces** → 프로젝트 만들고 멤버 + 자원 quota 지정
5. **NPU quota**: namespace ResourceQuota로 `rebellions.ai/ATOM: 2`, `furiosa.ai/rngd: 1` 같이 지정해 사용자별 NPU 분배

## llm-d 모델 서빙 API 사용

OpenAI 호환 호출 예시 (사내 클라이언트에서):

```bash
curl -X POST http://<cp-node-ip>:30800/v1/chat/completions \
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
    base_url="http://<cp-node-ip>:30800/v1",
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

`02-cp-init-cluster.sh` 마지막에 `kubeadm join <cp-node-ip>:6443 --token ... --discovery-token-ca-cert-hash sha256:...` 명령이 출력됩니다. **그 줄을 복사해두세요.**

### 2. etri-001 (worker) — sudo 비번 필요

스크립트 복사:

```bash
scp ~/llm-d-setup/scripts/03-worker-install.sh gspark@<etri-001-ip>:/tmp/
```

worker 노드에서 실행:

```bash
ssh gspark@<etri-001-ip> 'sudo bash /tmp/03-worker-install.sh'
ssh gspark@<etri-001-ip> 'sudo kubeadm join <cp-node-ip>:6443 --token <...> --discovery-token-ca-cert-hash sha256:<...>'
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
- `kubeadm init --apiserver-advertise-address=<cp-node-ip> --pod-network-cidr=<pod-cidr> --service-cidr=<svc-cidr> --skip-phases=addon/kube-proxy --node-name=<소문자 hostname>`
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

- **etri-001**: RBLN-CA22×4 + RNGD×3 — 한 노드에 두 NPU 진영 공존 (A100×2는 2026-10 기준 e11로 이동) → llm-d로 **이종 풀(heterogeneous pool)** 운영 검증 환경으로 이상적
- **etri-esc8000-e11**: RNGD×2 + A100 80GB×2 → Furiosa와 NVIDIA GPU가 한 노드에 공존
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

**공식 통합 IP**: `<gateway-host>` (사내 IT 할당)

```bash
# RBLN: EXAONE-3.5-7.8B (한국어 친화)
curl -X POST http://<gateway-host>/exaone/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"exaone-3.5-7.8b-instruct","messages":[{"role":"user","content":"..."}]}'

# Furiosa: Llama-3.1-8B (precompiled)
curl -X POST http://<gateway-host>/llama31/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"furiosa-ai/Llama-3.1-8B-Instruct","messages":[{"role":"user","content":"..."}]}'

# NVIDIA A100: Llama-3.1-8B (vllm-openai)
curl -X POST http://<gateway-host>/gpu/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"llama-3.1-8b-instruct-gpu","messages":[{"role":"user","content":"..."}]}'
```

| 경로 | 모델 | 가속기 | 노드 |
|---|---|---|---|
| `/exaone` | EXAONE-3.5-7.8B-Instruct | Rebellions RBLN-CA22 × 4 | etri-001 |
| `/llama31` | Llama-3.1-8B-Instruct | Furiosa RNGD × 4 | etri-esc8000-e11 |
| `/gpu` | Llama-3.1-8B-Instruct | NVIDIA A100 80GB × 2 | etri-esc8000-e11 (2026-10 이전엔 etri-001) |

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

### R7525 (관리, <cp-node-ip>)
- Ubuntu 26.04 "resolute", 커널 7.x, 128 vCPU / 373GB RAM
- NIC: `eno1` UP (<cp-node-ip>/24), 나머지 down
- 가속기 없음 (의도적 — 관리/컨트롤 플레인 전용)

### etri-001 (worker, <etri-001-ip>)
- Ubuntu 22.04.5, 커널 6.8, 96코어 / 1.5TB RAM, NUMA 2-node, disk 1.5TB 여유
- ~~NVIDIA A100 PCIe 80GB × 2 (44:00.0, 45:00.0)~~ — **e11로 이동**(2026-10-15 확인, 현재 etri-001에 NVIDIA 장치 없음, 45:00.0은 RNGD)
- Rebellions RBLN-CA22 × 4 (83/84/c3/c4:00.0, NUMA 1, 15.7GiB/장) — KMD 3.0.0 정상
- Furiosa RNGD × 3 (03/04/45:00.0)
- containerd active, docker installed (inactive), helm 설치됨, kubectl/kubeadm 미설치
- venv: `~/vllm_test/venv` (vllm_rbln 0.10.2.post1, rebel-compiler 0.10.2, optimum-rbln 0.10.2)
- HF cache: `~/.cache/huggingface` (143GB 사용)

### etri-ESC8000-E11 (worker, <e11-ip>:10022)
- Ubuntu 22.04.5, 48코어 / 1TB RAM, 16 NUMA (SNC)
- Furiosa RNGD × 2 (50/63:00.0), driver 2026.4.0
- NVIDIA A100 PCIe 80GB × 2 (99/bd:00.0), driver 580.178, nvidia-container-toolkit 1.19.1 (`/etc/containerd/conf.d/99-nvidia.toml`) — 2026-10-15 복구
- 노드 라벨 `feature.node.kubernetes.io/pci-10de.present=true`는 수동 부여(nvidia-device-plugin DS selector가 요구)
- kubelet `evictionHard` nodefs/imagefs 5% (디스크 대부분이 사용자 홈 데이터, 백업 `config.yaml.bak-20261015`)
- SSH 포트 10022 사용

## ai-rm

이 레포는 [ai-rm](https://github.com/ai-computing/ai-rm)(AI 반도체 통합 자원관리)의 **`l4-cluster` 계층, kind `cluster`** 구성요소다. 다른 구성요소가 올라가는 바탕인 K8s + llm-d 클러스터를 정의한다: 노드 부트스트랩 스크립트, Gateway/HTTPRoute, InferencePool·EPP, 모델 서버 매니페스트, 공유 모델 스토어, 관측 스택. 메타데이터는 루트의 `ai-rm.yaml`에 있다.

**k8s + llm-d 연결.** 요청 경로는 `envoy-gateway (llm-d-gateway)` → `HTTPRoute`(path 분기, `manifests/openai-route.yaml`, `llm-d-gateway.yaml`) → `InferencePool` → EPP(`manifests/epp/`, `llmd-router-values.yaml`) → 모델 서버 Pod(`llm-serving` ns)다. 가속기는 노드의 device plugin 리소스(`nvidia.com/gpu`, RBLN, RNGD)와 nodeSelector로 배치한다. `manifests/`는 kustomize 디렉터리가 아니라 개별 `kubectl apply` / helm values 모음이다.

**다른 ai-rm 구성요소가 붙는 자리**

| 구성요소 | 계층 | 이 클러스터에 붙는 방식 |
|---|---|---|
| rngd-pd | l3-serving | RNGD 노드(`etri-001`, `etri-esc8000-e11`)에 prefill/decode Pod를 띄우고, 자체 InferencePool + EPP를 만든 뒤 Gateway에 path를 추가한다 (`manifests/epp/make-epp.sh <pool> /<path>`; 기록은 `PD disaggregation_HISTORY.md`) |
| npu-lora | l3-serving | RNGD 노드에 학습 Job(privileged, `lmd-top --plan train … --apply`)으로 제출한다. 모델·어댑터는 공유 모델 스토어 PVC `model-store`(`manifests/README-model-store.md`)를 쓰고, 어댑터는 A100 vLLM(`manifests/vllm-a100-llama31-8b.yaml`, `--enable-lora`)이 런타임에 적재한다 |
| lmd-top | l5-ops | control-plane에서 kubectl + Prometheus만 읽는 TUI. `LMD_PROM=$LLMD_PROM_ADDR LMD_NS=llm-serving lmd-top` |
| rm-bench | l5-ops | Gateway(`http://$LLMD_GATEWAY_HOST/<path>/v1`)에 OpenAI 호환 부하를 건다. 같은 부하 에너지 비교는 `scripts/hetero-sweep.py` |
| 모니터링 (`monitoring/`) | l4-cluster | 클러스터에서는 kube-prometheus-stack + DCGM/Furiosa/RBLN exporter + ServiceMonitor(`manifests/*servicemonitor.yaml`, `ipmi-exporter.yaml`)가 지표를 모으고, `monitoring/grafana-dashboards/`를 Grafana에 올린다. `monitoring/standalone-compose/`는 k8s 없는 단일 GPU 노드용 |

**ai-rm v0.1.** `ai-rm.yaml`의 `deploy.manifests`는 `deploy/airm`(수집 설정·`airm-placement`), CRD와 되돌리기는 아래 「ai-rm protocol v0.1」.

**설치·테스트.** 클러스터 부트스트랩은 root 권한 수동 단계라 `ai-rm setup`이 실행할 install 명령은 없다(위 「실행 순서」, `scripts/01~05`). 가속기 없이 도는 빠른 검사:

```bash
python3 scripts/test-model-store-discovery.py      # 모델 스토어 discovery 오프라인 회귀 테스트
bash -n scripts/*.sh manifests/epp/make-epp.sh       # 셸 스크립트 문법 검사
```

**인터페이스.** 제공: `Placement`(Gateway → InferencePool → EPP 라우팅, nodeSelector 기반 가속기 배치), `Metrics`(Prometheus/Grafana, 가속기·노드 wall 전력 exporter). 사용: `Accelerator`(노드 device plugin과 가속기 리소스), `Workload`(그 위에 올라가는 serving/학습 워크로드).

**KPI.** 이종자원수(A100·ATOM·RNGD·GB10·CPU를 한 Gateway로 서빙), 전력효율(DCGM·IPMI wall 전력으로 tok/J, `scripts/hetero-sweep.py`), SLO(EPP 지표 TTFT/TPOT).

**사이트 설정 (`cluster.local.env`).** 실제 주소는 커밋하지 않는다. `cp cluster.example.env cluster.local.env`(untracked) 후 값을 채우면 `scripts/lib/cluster-env.sh`가 읽는다. 이미 환경에 있는 값이 우선하고, 필요한 값이 없으면 스크립트가 바로 실패한다. 문서의 `<gateway-host>`, `<cp-node-ip>` 같은 placeholder 뜻도 `cluster.example.env` 주석에 있다.

| 변수 | 쓰는 곳 |
|---|---|
| `LLMD_CP_IP`, `LLMD_POD_CIDR`, `LLMD_SVC_CIDR` | `scripts/02-cp-init-cluster.sh` (kubeadm init) |
| `LLMD_GATEWAY_HOST` | `manifests/epp/make-epp.sh` 헬스 테스트 (`GW_ADDR`로 덮어쓰기 가능) |
| `LLMD_PROM_ADDR` | `scripts/capture-lmd-top.sh`, lmd-top `LMD_PROM` |
| `LLMD_MODEL_STORE_SMB` | `manifests/model-store.yaml` (`scripts/render-manifest.sh manifests/model-store.yaml \| kubectl apply -f -`) |

### ai-rm protocol v0.1 (rm-core `v0.1.1`)

이 클러스터는 [rm-core PROTOCOL v0.1](https://github.com/ai-computing/rm-core/blob/v0.1.1/PROTOCOL.md)이 돌 자리를 제공한다. 상세와 형식은 [`deploy/airm/README.md`](deploy/airm/README.md).

| 항목 | 위치 |
|---|---|
| `AcceleratorProfile` CRD (`airm.ai-computing.io/v1alpha1`) | `scripts/airm-install.sh`가 rm-core 태그 `v0.1.1`에서 받아 sha256 확인 후 적용(사본 없음) |
| `airm_*` 지표 수집 | `deploy/airm/scrape-airm.yaml` — `airm.ai-computing.io/scrape: "true"` 어노테이션 pod의 `/metrics`(기본 포트 9400) |
| `airm_*` 대시보드 | `monitoring/grafana-dashboards/airm.json` (ConfigMap `grafana-dashboard-airm`) |
| 배치 결정 전달 지점 | ConfigMap `llm-serving/airm-placement` (v0.1은 빈 값, EPP scorer 자리만 문서화) |
| umbrella chart 공통 값 | `deploy/helm/cluster-values.yaml` |

```bash
scripts/airm-install.sh dry-run              # 서버 dry-run: CRD + ScrapeConfig + ConfigMap + 대시보드
scripts/airm-install.sh apply crd            # CRD 설치
scripts/airm-install.sh apply manifests      # 수집 설정·airm-placement·대시보드
```

**되돌리기.** `scripts/airm-install.sh delete manifests` 후 `scripts/airm-install.sh delete crd`(= `kubectl delete crd acceleratorprofiles.airm.ai-computing.io`). CRD를 지우면 모든 `AcceleratorProfile` 객체도 함께 지워진다. 운영 중인 모델 서버·EPP 설정은 이 단계에서 바꾸지 않는다.

## 참고

- llm-d 공식: https://llm-d.ai/docs
- Gateway API Inference Extension: https://github.com/kubernetes-sigs/gateway-api-inference-extension
- Cilium Gateway API: https://docs.cilium.io/en/stable/network/servicemesh/gateway-api/
- vllm-rbln: Rebellions가 제공하는 vLLM 포크 (HF Hub `rebellions-sw/*` 컴파일 모델 사용)
