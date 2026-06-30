# 클러스터 현황 스냅샷

> 작성 시점: 2026-06-01 (live, EXAONE-3.5 DP + KONI 최적화 적용)
> 전체 매뉴얼은 [README.md](./README.md), 매니페스트는 `manifests/`, 셋업 스크립트는 `scripts/`

## 한 줄 요약

K8s 1.31 + Cilium 1.16 + llm-d **v0.7 EPP**로 **NVIDIA A100 × 2 / Rebellions RBLN-CA22 × 4 / CPU**에 LLM 3종 동시 서빙 + Furiosa RNGD × 2로 RAG embedding 가속. 사내 IP **192.0.2.12** 단일 entrypoint(envoy-gateway)에서 path 분기.

## 노드 토폴로지

| 노드 | IP | 역할 | CPU/Mem | GPU | RBLN | RNGD |
|---|---|---|---|---|---|---|
| gspark-poweredge-r7525 | .105 | control-plane | 128 / 391 Gi | – | – | – |
| **etri-001** | .183 | worker (이종 가속기 주력) | 96 / 1.55 Ti | **2** A100 80GB | **4** RBLN-CA22 | 2 RNGD |
| etri-esc8000-e11 | .126:10022 | worker (Furiosa 전용, cordoned) | 48 / 1.1 Ti | – | – | 4 RNGD |
| cpu-1 | .178 | worker (CPU 전용) | 128 / 391 Gi | – | – | – |
| cpu-2 | .179 | worker (CPU 전용) | 128 / 391 Gi | – | – | – |
| cpu-3 | .186 | worker (CPU 전용) | 128 / 391 Gi | – | – | – |

## 활성 모델 서버 (성능 최적화 적용)

| Pod | 모델 | 가속기 | t/s | 비고 |
|---|---|---|---|---|
| `vllm-exaone` (× 2 DP) | **EXAONE-3.5-32B-Instruct-AWQ** (vLLM v0.9.2 stable) | A100 × 2 (각 1장, DP) | **~62** | TP=1 × replicas=2, 한국어 LG 검증, NodePort `:30806` |
| `vllm-rbln-koni` | **KONI-Llama3.1-8B-Instruct** (RBLN compile TP=4) | RBLN-CA22 × 4 | ~14 | xxhash prefix-caching + chunked-prefill + block-size 16, NodePort `:30800` |
| `ollama-cpu` | (ollama pull) | CPU pool | 가변 | NodePort `:30803` |
| `furiosa-embed` | **Qwen3-Embedding-8B** (dim 4096) | RNGD × 2 | embed | RAG embedding |

> 옛 리소스 정리됨 (ds4 V4 Flash → A100 sm_80 perf 한계 / EXAONE 4.5 → transformers bug)

## 표준 Label — 카테고리 분류

| Label | 값 |
|---|---|
| `llm-d.ai/accelerator` | gpu-nvidia / npu-rebellions / npu-furiosa / cpu |
| `llm-d.ai/role` | chat / embedding / vector-db / retriever |
| `llm-d.ai/engine` | vllm / vllm-rbln / ollama / furiosa-llm |

## Grafana 대시보드 (admin/admin)

| UID | 제목 | 메트릭 |
|---|---|---|
| `nvidia-dcgm` | NVIDIA GPU — DCGM Exporter | DCGM 22개 |
| `furiosa-npu` | Furiosa NPU — RNGD | npu_alive/util/freq/temp |
| `llm-models` | LLM Models — vLLM / RBLN | requests, KV usage, prefix hit, latency p95, t/s |

## 운영 entrypoint

**공식 통합 IP**: `192.0.2.12` (envoy-gateway LB, Cilium L2 announcement로 광고, gateway `eg` class, `Programmed=True`)

```bash
# A100 → DeepSeek V4 Flash
curl -X POST http://192.0.2.12/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"model":"deepseek-v4-flash","messages":[{"role":"user","content":"안녕"}]}'

# RBLN → KONI Llama 3.1 (한국어 강세)
curl -X POST http://192.0.2.12/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"model":"koni-llama3.1-8b-rbln","messages":[{"role":"user","content":"한국어 시 한 편 써줘"}]}'
```

## llm-d 활성 컴포넌트 (v0.7 EPP)

| 컴포넌트 | 종류 / 이미지 | 비고 |
|---|---|---|
| EPP (router) | `ghcr.io/llm-d/llm-d-router-endpoint-picker-dev:main` | **llm-d v0.7 신규 image** — `no-hit-lru-scorer` 활성 |
| EPP plugin set | queue-scorer(w=2) + kv-cache-utilization-scorer(w=2) + prefix-cache-scorer(w=3) + **no-hit-lru-scorer(w=2)** | v0.7 신규 plugin 포함 |
| InferencePool | `llmd-router` (selector dynamic) | model server 변경 시 selector 패치 |
| Gateway | `llm-d-gateway` (eg class, ADDRESS `192.0.2.12`) | envoy-gateway 1.3.0 |
| HTTPRoute | `openai-route` | path 분기 |
| InferenceObjective | `low-latency`(p=100), `high-throughput`(p=10) | SLO 우선순위 |

## 메트릭 / 모니터링 풀-스택

| 대상 | 종류 | 수집 메트릭 |
|---|---|---|
| **NVIDIA A100** (etri-001) | ServiceMonitor `dcgm-exporter` | DCGM 22개 (memory, util, power, temp, NVLink, etc.) |
| **RBLN ATOM+ × 4** (etri-001) | ServiceMonitor `vllm-rbln-koni` | vLLM 표준 메트릭 (num_requests_waiting/running, gpu_cache_usage_perc, etc.) |
| **Furiosa RNGD × 2** (etri-001) | PodMonitor `furiosa-metrics-exporter` | RNGD utilization, memory, temperature |
| Furiosa embed 서버 | ServiceMonitor `furiosa-embed` | embedding 서버 vLLM 메트릭 |
| CPU/Mem/Disk/Net (전 노드) | ServiceMonitor `node-exporter` | 표준 host 메트릭 |
| kube-state + control-plane | ServiceMonitor `kube-prometheus-stack-*` | apiserver, etcd, scheduler, controller, kubelet |

## RAG 스택

| 컴포넌트 | 위치 | 비고 |
|---|---|---|
| Vector DB | `qdrant` (kind:StatefulSet) | collection `docs-qwen3` (dim 4096) |
| Embedding | `furiosa-embed` (Qwen3-Embedding-8B, Furiosa NPU × 2) | `/v1/embeddings` (OpenAI 호환) |
| Retriever | `retriever-src` ConfigMap → FastAPI app | langchain 패턴, `repetition_penalty=1.15` default |
| Document source | NAS SMB (192.0.2.13 시놀로지) | **PV ReadOnlyMany + volumeMount readOnly** — 무결성 보장 |
| NAS folders | `aicomputing`, `kcloud_rm`, `lab` | SMB 인증은 `smb-creds` Secret (재생성 대기 — 사용자 입력 필요) |

## 관리/관측 UI

| UI | URL | 인증 |
|---|---|---|
| **Rancher** | https://192.0.2.8:30443 | admin / 첫 로그인 비번 변경 |
| Headlamp | http://192.0.2.8:30502 | `kubectl create token headlamp -n headlamp --duration=24h` (또는 `headlamp-admin` SA token) |
| Hubble UI | http://192.0.2.8:30081 | 없음 |
| Grafana | http://192.0.2.8:30300 | admin / admin |
| Prometheus | http://192.0.2.8:30090 | 없음 |

> **Headlamp RBAC**: `headlamp-events-reader` ClusterRole 추가 (events list/get/watch 권한)

## 설치된 helm 릴리스 (21개)

| 릴리스 | namespace | 차트 / 버전 |
|---|---|---|
| cilium | kube-system | cilium-1.16.5 |
| eg | envoy-gateway-system | gateway-helm-v1.3.0 |
| cert-manager | cert-manager | cert-manager-v1.20.2 |
| rancher | cattle-system | rancher-2.14.2 |
| headlamp | headlamp | headlamp-0.42.0 |
| kube-prometheus-stack | monitoring | 86.0.1 |
| keda | keda | keda-2.19.0 |
| llmd-router | llm-serving | standalone-v1.5.0 (GAIE) + v0.7 EPP image |
| rbln-npu-operator | rbln-system | v0.3.3 |
| furiosa-device-plugin | furiosa-system | 2026.1.0 |
| furiosa-feature-discovery | furiosa-system | 2026.1.0 |
| furiosa-metrics-exporter | furiosa-system | 2026.1.0 |
| nvidia-device-plugin | nvidia-device-plugin | nvidia-device-plugin-0.19.2 |
| **dcgm-exporter** | nvidia-device-plugin | dcgm-exporter-4.8.2 |
| **csi-driver-smb** | kube-system | csi-driver-smb-1.20.1 |
| **csi-driver-nfs** | kube-system | csi-driver-nfs-4.13.2 |
| fleet / rancher-webhook / rancher-turtles | cattle-* | Rancher 부속 |

## Multi-tenant 자원 분배

| Namespace | RBLN | RNGD | CPU | Memory | RBAC |
|---|---|---|---|---|---|
| `tenant-a` | 2 | 2 | 32~64 | 128~256 GB | user `alice` → developer Role |
| `tenant-b` | 2 | 2 | 32~64 | 128~256 GB | user `bob` → developer Role |

## 활성 기능

- ✅ OpenAI 호환 API (`/v1/models`, `/v1/chat/completions`, `/v1/embeddings`, streaming SSE)
- ✅ Multi-accelerator (A100 / RBLN / Furiosa / CPU) 동시 운영
- ✅ Path-based 라우팅 via envoy-gateway HTTPRoute
- ✅ vLLM prefix caching + KV cache utilization scorer
- ✅ **llm-d v0.7 no-hit-lru-scorer** (KV cache miss 시 LRU eviction 우선)
- ✅ KEDA autoscaling (`vllm_num_requests_waiting` trigger)
- ✅ SLO-aware priority (`InferenceObjective` 100/10)
- ✅ Multi-tenant namespace + ResourceQuota + Rancher RBAC
- ✅ Prometheus 풀 메트릭 (GPU/NPU/CPU/모델 서버 모두)
- ✅ RAG (Qdrant + Furiosa-Embedding + NAS SMB read-only)
- ✅ Tool calling (DeepSeek V4 Flash + KONI 둘 다 지원)
- ✅ DeepSeek V4 Flash inline reasoning (`reasoning_content` field)
- ⏳ KV-cache disaggregation (Redis 또는 NIXL) — 별도 helm chart
- ⏳ prefill/decode disaggregation
- ⏳ Token rate limiting

## 검증된 응답 샘플

| 모델 | 입력 | 응답 (실측) |
|---|---|---|
| deepseek-v4-flash | "안녕! 자기소개를 한 문장으로 해줘." | "안녕하세요! 저는 DeepSeek라는 AI 비서로, 궁금한 점이나 도움이 필요할 때 언제든지 질문에 답변해 드리고 있어요! 😊" |
| deepseek-v4-flash | "한국어로 짧은 시 한 편을 써줘." | "창문에 기대어 / 별 한 알을 보았다 / 바람이 불어와 / 내 눈동자를 스치고 갔다..." |
| deepseek-v4-flash | "What is 2+2?" | "2+2 equals 4." |

## 디스크/스토리지

- **StorageClass**: `local-path` (기본 SC, rancher.io/local-path-provisioner)
- **HF cache**: etri-001 `/home/gspark/.cache/huggingface`
- **RBLN compiled 모델**: etri-001 `/home/gspark/rbln-KONI-Llama3.1-8B-Instruct-tp4-bs1-s8192/` (~19 GB)
- **ds4 GGUF cache**: emptyDir, 매 재시작 시 재다운로드 (97GB + 3GB). 영구화하려면 PVC + hostPath로 이동
- **Qdrant data**: PVC `qdrant-storage` (local-path)
- **NAS read-only**: SMB CIFS via `csi-driver-smb`, `ReadOnlyMany` PV (수정/삭제 차단)

## 알려진 한계 / 보류 작업

| 항목 | 상태 |
|---|---|
| Furiosa Llama-3.1-8B 한국어 응답 깨짐 | 사용자가 서빙 down. 향후 KONI 또는 EXAONE compile로 재시도 가능 |
| ds4 multi-GPU 활용 | GPU 0만 사용 (GPU 1 idle). ds4 설계상 single-GPU + host mmap. GPU 1 비축 |
| ds4 GGUF 영구화 | 재시작 시 100GB 재다운로드. PVC + hostPath로 캐시 |
| NAS SMB Secret | username 키에 password 들어간 상태, 재생성 대기 (사용자) |
| HF 토큰 노출 | `hf_Rcb…REDACTED` (git 커밋 위해 마스킹, 2026-06-30) — **revoke 권장** |
| etri-esc8000-e11 노드 | cordoned (사용자 결정) |

## 비상 운영 메모

- ds4 pod 죽으면: `kubectl rollout restart deployment/ds4-deepseek-v4-flash -n llm-serving` (100GB 재다운로드 주의)
- KONI pod 죽으면: `kubectl rollout restart deployment/vllm-rbln-koni -n llm-serving` (모델 로드 ~3분)
- A100 driver/library mismatch 재발: `sudo modprobe -r nvidia_uvm nvidia_drm nvidia_modeset nvidia && sudo modprobe nvidia` (참고: `scripts/05-nvidia-setup.sh`)
- Gateway IP `192.0.2.12`: Cilium L2 announcement 통해 광고, 양도 시 `ciliumloadbalancerippool` 패치
- EPP rollback (v1.5.0 standard): `kubectl set image deployment/llmd-router-epp -n llm-serving epp=registry.k8s.io/gateway-api-inference-extension/epp:v1.5.0` (단 no-hit-lru-scorer plugin 제거 ConfigMap 패치 필요)
