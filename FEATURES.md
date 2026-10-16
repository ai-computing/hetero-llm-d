# llm-d 기능 현황 + Worker별 지원 매트릭스

> 작성 시점: 2026-06-01 (live 클러스터 검증 기반)
> 클러스터 스냅샷은 [STATUS.md](./STATUS.md), 전체 매뉴얼은 [README.md](./README.md)
> NPU 기능 한계 상세는 [NPU-FEATURES.md](./NPU-FEATURES.md), 활용 시나리오는 [PLAYBOOK.md](./PLAYBOOK.md)

## 카테고리별 활성 상태

| 기능 | 활성 | 적용 대상 | 비고 |
|---|---|---|---|
| **OpenAI 호환 API** | ✅ | 4 모델 서버 (ds4 / KONI / ollama / Qwen3-Embedding) | `/v1/chat/completions`, `/v1/embeddings`, `/v1/models`, SSE streaming |
| **Multi-model 동시 서빙** | ✅ | DeepSeek V4 Flash / KONI / ollama / embedding | 풀별로 가속기 다름 |
| **Path-based 라우팅** | ✅ | envoy-gateway HTTPRoute on `<gateway-host>` | OpenAI path 통합 |
| **EPP (Endpoint Picker)** | ✅ **v0.7** | `llmd-router-epp` | gRPC ext_proc :9002 — `ghcr.io/llm-d/llm-d-router-endpoint-picker-dev:main` image |
| **EPP scorer plugin set** | ✅ **v0.7** | queue / kv-cache-utilization / prefix-cache + **no-hit-lru-scorer** | LRU eviction on cache miss (v0.7 신규) |
| **InferencePool / InferenceObjective** | ✅ | `llmd-router` 풀에 low-latency(100) / high-throughput(10) | SLO priority |
| **KEDA autoscaling** | ✅ | `vllm-rbln-koni`, 향후 ds4 추가 가능 | `vllm:num_requests_waiting` trigger |
| **vLLM prefix caching** | ✅ | KONI(RBLN), ds4 (KV disk cache 8GB) | – |
| **DeepSeek V4 Flash inline reasoning** | ✅ | ds4 | `reasoning_content` field 별도 (MoE thinking) |
| **Function/tool calling** | ✅ | ds4 (`tools`/`tool_choice`), KONI (`--enable-auto-tool-choice llama3_json`) | 둘 다 OpenAI 호환 |
| **Multi-tenant ResourceQuota** | ✅ | `tenant-a/b` namespace | RBLN 2 + RNGD 2 + alice/bob RBAC |
| **Prometheus 풀-스택 메트릭** | ✅ | DCGM (NVIDIA) + Furiosa metrics-exporter (NPU) + vLLM ServiceMonitor (모델 서버) + node-exporter | Grafana로 시각화 |
| **RAG (Qdrant + Furiosa-Embedding + NAS RO)** | 🔄 | Qwen3-Embedding-8B on RNGD × 2, dim 4096, collection `docs-qwen3` | NAS SMB Secret 재생성 대기 |
| **EPP KV-cache indexing (Redis)** | ❌ | 별도 chart (`llm-d-kv-cache`) | 우리 1-replica 구조엔 가치 작음 |
| **Disaggregated prefill/decode** | ❌ | A100→prefill, NPU→decode | 모델 호환 필요 |
| **Multi-LoRA serving** | ❌ | A100만 native (vLLM) | RBLN/Furiosa는 LoRA fuse 후 재컴파일 |
| **Speculative decoding** | ❌ | A100 (draft model) | NPU는 컴파일 그래프 고정 |
| **Token rate limiting** | ❌ | 모든 path | Envoy ratelimit filter + Redis |

> ✅ 동작 / 🔄 진행 중 / ❌ 미설정

## Worker(가속기)별 활용 매트릭스

### 노드 구성

| 노드 | 가속기 | 현재 워크로드 | TP |
|---|---|---|---|
| etri-001 | A100 80GB × 2 | **`ds4-deepseek-v4-flash`** (V4 Flash, GPU0 단일) | – |
| etri-001 | RBLN-CA22 × 4 | **`vllm-rbln-koni`** (KONI-Llama3.1-8B) | 4 |
| etri-001 | RNGD × 2 | **`furiosa-embed`** (Qwen3-Embedding-8B, RAG용) | 2 |
| etri-esc8000-e11 | RNGD × 4 | (cordoned, 사용자 결정) | – |
| cpu-1/2/3 | CPU only | `ollama-cpu` (모델 자유) | – |

### 기능 ↔ Worker 매트릭스

| 기능 | A100 + ds4 | RBLN + vllm-rbln-koni | Furiosa + furiosa-embed | CPU + ollama |
|---|:---:|:---:|:---:|:---:|
| OpenAI `/v1/chat/completions` | ✅ | ✅ | – (embed 전용) | ✅ |
| OpenAI `/v1/embeddings` | – | – | ✅ | – |
| Streaming (SSE) | ✅ | ✅ | N/A | ✅ |
| Tensor parallel | – (single-GPU + host mmap) | ✅ TP=4 | TP=2 | – |
| Prefix caching | ✅ KV disk cache 8GB | ✅ vLLM | N/A | 🟡 ollama 자체 |
| Long context | 32768 | 8192 (재컴파일로 ↑) | 8192 | 모델별 |
| **Inline reasoning** | ✅ V4 Flash `reasoning_content` | ❌ | – | ❌ |
| **Tool/function calling** | ✅ | ✅ Llama3 json | – | 🟡 모델별 |
| **Quantization** | Q4K + IQ2XXS hybrid imatrix | INT8 (컴파일 시) | FP16 (컴파일 시) | Q4_K_M default |
| **Multi-LoRA** | 🟡 ds4 비지원, vLLM은 지원 | ❌ | ❌ | ❌ |
| **Speculative decoding** | 🟡 ds4 MTP module (3GB) 사용 가능 | ❌ | ❌ | ❌ |
| **InferencePool 등록** | ✋ | ✅ `llmd-router` | ❌ (embed라 무관) | ✋ |
| **InferenceObjective(SLO)** | ✋ | ✅ | – | ✋ |
| **Autoscaling (KEDA)** | ✋ | ✅ | ✋ | ✋ |
| **Multi-tenant Quota** | ✅ `nvidia.com/gpu` | ✅ `rebellions.ai/ATOM` | ✅ `furiosa.ai/rngd` | ✅ CPU/Mem |
| **Prometheus `/metrics`** | ✅ ds4 자체 메트릭 + DCGM | ✅ vllm-rbln 표준 | ✅ furiosa-embed + furiosa-metrics-exporter | ❌ 별도 endpoint |
| **모델 자동 다운로드** | ✅ HF (init container, 100GB GGUF) | ❌ 사전 컴파일 hostPath | ✅ HF (HF_TOKEN env) | ✅ ollama pull |
| **컨테이너 이미지** | nvidia/cuda:12.6.0-{devel,runtime} | ubuntu:22.04 + host site-packages | furiosa-llm | ollama/ollama:latest |

### Worker별 강점/약점 한 줄

- **A100 (ds4 + DeepSeek V4 Flash)** — 671B 파라미터 모델을 97GB GGUF로 단일 GPU에 mmap. MTP 가속 지원. inline reasoning. 약점: ds4 single-GPU 설계 (GPU 1은 다른 워크로드용으로 비축)
- **RBLN-CA22 (Rebellions, KONI)** — 전력 효율 압도 (30W/장 × 4 = 120W), KISTI 한국어 fine-tune. 약점: LoRA·speculative 불가, 사전 컴파일 필요
- **RNGD (Furiosa, embedding)** — Qwen3-Embedding-8B 가속, dim 4096 고품질 embedding. 약점: chat 서빙은 한국어 깨짐 이슈 (현재 down)
- **CPU (ollama)** — 모델 hot-swap 자유, Quota 분배 쉬움. 약점: 처리량 ↓

## 즉시 활성화 가능한 다음 3가지

1. **A100용 InferencePool 만들기** — ds4도 EPP 라우팅 (`/v1/chat/completions` 통합 path)
2. **ds4 GGUF 영구화** — PVC + hostPath 캐시로 재시작 시 100GB 재다운로드 방지
3. **KV-cache indexing (Redis)** — `llm-d-kv-cache` chart, 다중 replica로 확장 시 가치 ↑
