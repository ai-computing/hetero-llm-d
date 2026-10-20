# NPU 호환성 보고서 — llm-d 기능별 동작 검증

> 작성: 2026-05-29 (EXAONE/Llama 검증) / **갱신: 2026-06-01 (KONI + DeepSeek V4 Flash 추가)**
> 비교 대상: **Rebellions RBLN-CA22** (`vllm-rbln`), **Furiosa RNGD** (`furiosa-llm`), 기준선 **NVIDIA A100** (`vllm-openai` / `ds4`)
> 인접 문서: [FEATURES.md](./FEATURES.md), [STATUS.md](./STATUS.md), [README.md](./README.md), [PLAYBOOK.md](./PLAYBOOK.md)

## 갱신 사항 (2026-06-01)

| 항목 | 변경 |
|---|---|
| RBLN 한국어 모델 | EXAONE-3.5 → **KISTI-KONI/KONI-Llama3.1-8B-Instruct-20241024** TP=4 (한국어 응답 정상) |
| Furiosa Llama-3.1-8B 서빙 | **한국어 garbage 토큰 발생** 검증 (`profile...rejecting practicallyAKE 텐~`). 사용자 down. KONI/EXAONE 재컴파일로 대체 가능 |
| Furiosa RNGD × 2 (npu-node-1) | chat 대신 **Qwen3-Embedding-8B** (RAG embedding, dim 4096) 운영. dim 1024 BGE-M3 대비 품질 ↑ |
| A100 + ds4 (DwarfStar) | DeepSeek V4 Flash 671B를 97GB hybrid Q4K/IQ2XXS imatrix GGUF로 단일 GPU mmap. inline reasoning + tool calling 둘 다 동작 |
| llm-d EPP | v1.5.0 → **v0.7 image** (`no-hit-lru-scorer` 신규 plugin 포함) |
| 메트릭 | DCGM exporter + vllm-rbln-koni + vllm-a100 ServiceMonitor + furiosa-metrics-exporter PodMonitor 풀-스택 |

## 검증 환경

| 항목 | Rebellions | Furiosa | A100 (기준) |
|---|---|---|---|
| 가속기 | RBLN-CA22 × 4 (15.7 GiB/장) | RNGD × 4 (64 GiB/장 HBM) | A100 80GB × 2 |
| Model server | vllm-rbln 0.10.2 (vLLM 0.13.0+cpu 위 plugin) | furiosa-llm:latest (자체 서버) | vllm-openai:latest |
| Model | EXAONE-3.5-7.8B-Instruct (사전 컴파일 TP=4 bs=8 seq=1024) | furiosa-ai/Llama-3.1-8B-Instruct (HF precompiled) | meta-llama/Llama-3.1-8B-Instruct (런타임 load) |
| TP | 4 | 4 (artifact 내장) | 2 |
| Endpoint | NodePort `:30800`, Gateway `/exaone` | NodePort `:30801`, Gateway `/llama31` | NodePort `:30802`, Gateway `/gpu` |

## 기능 매트릭스 (실측)

| # | 기능 | RBLN | Furiosa | A100 | 비고 |
|---|---|:---:|:---:|:---:|---|
| 1 | OpenAI `/v1/chat/completions` | ✅ | ✅ | ✅ | 모두 통과 |
| 2 | OpenAI `/v1/completions` | ✅ | ✅ | ✅ | 풀 endpoint 노출 |
| 3 | OpenAI `/v1/models` | ✅ | ✅ | ✅ | Furiosa는 `artifact_id`, `max_context_len` 부가 정보 노출 |
| 4 | Streaming (SSE) | ✅ | ✅ | ✅ | 모두 `delta.content` chunk 단위 전송 확인 |
| 5 | logprobs + top_logprobs | ✅ | ✅ | ✅ | 토큰별 logprob, bytes 응답 |
| 6 | JSON guided output (`response_format: json_object`) | ✅ | ✅ | ✅ | 모두 valid JSON 반환 (단 schema-strict는 별개) |
| 7 | Tool / function calling | ✅ (옵션 추가 + Llama-3.1) | ❌ | ✅ | 아래 (A) 참조 — RBLN에서 검증 완료 |
| 8 | Long context | ❌ max 1024 | ✅ max 131,072 | ✅ max 131,072 | RBLN은 컴파일 시 고정 |
| 9 | Tensor parallel | ✅ TP=4 | ✅ TP=4 (artifact) | ✅ TP=2 | 모두 동작 |
| 10 | Pipeline parallel | ❌ | 🟡 chart 옵션은 있음 | ✅ | RNGD 단일 carda PP 의미 없음 |
| 11 | Prefix caching | ✅ vLLM default (메트릭 `vllm:gpu_prefix_cache_hit_rate`) | ✅ (`cached_tokens=30` 측정) | ✅ | NPU도 KV cache 재사용 |
| 12 | Chunked prefill | ✅ | ✅ | ✅ | vLLM v0.13 default + furiosa-llm 지원 |
| 13 | Multi-LoRA serving | ❌ | ❌ | ✅ (옵션 추가시) | 아래 (B) 참조 |
| 14 | Speculative decoding | ❌ | ❌ | ✅ (옵션 추가시) | 아래 (C) 참조 |
| 15 | Quantization 런타임 적용 | ❌ | ❌ | ✅ AWQ/GPTQ/FP8/INT4 | 아래 (D) |
| 16 | KEDA autoscaling (replica) | ✅ ScaledObject 동작 | ✋ 가능 | ✋ 가능 | 단 NPU 카드 추가 없으면 max=1 |
| 17 | Prometheus `/metrics` | ✅ vLLM 표준 | ✅ furiosa-llm 자체 | ✅ vLLM 표준 | EPP에서 수집 |
| 18 | InferencePool 등록 | ✅ `llmd-router` | ✅ `furiosa-llama31-8b-pool` | ✋ pool 미생성 | helm/CR로 즉시 |
| 19 | EPP routing (KV-aware) | ✅ vLLM 메트릭 기반 | 🟡 furiosa-llm 메트릭 매핑 검증 필요 | ✅ | KV-cache indexing은 풀별 enable |
| 20 | Disaggregated prefill/decode | ❌ | ✅ chart `prefill.create=true` + NIXL | ✅ vLLM v1 disagg | 아래 (E) |
| 21 | 모델 자동 다운로드 | ❌ 사전 컴파일 hostPath | ✅ HF 자동 (emptyDir 30 GiB) | ✅ HF cache 마운트 | NPU는 컴파일 단계 분리 |
| 22 | 한국어 모델 (EXAONE 등) | ✅ 한국어 EXAONE 사전 컴파일 검증 | 🟡 (Furiosa publish 모델은 영어 위주) | ✅ 어떤 모델이든 | RBLN이 한국어 우위 |

> ✅ 즉시 동작 / 🟡 가능하지만 추가 작업 / ❌ NPU 구조상 직접 안 됨

## 상세 — 안 되는 기능과 원인

### (A) Function/Tool calling

**현상**
- RBLN: `400 Bad Request — "auto" tool choice requires --enable-auto-tool-choice and --tool-call-parser`
- Furiosa: 200 응답이지만 `tool_calls: null`, 그냥 일반 텍스트 답변 (요청 무시)

**원인**
- vLLM의 tool calling은 두 단계: 모델이 `<|tool_call|>` 같은 special token을 출력 → vLLM 파서가 JSON으로 추출. 두 옵션 모두 켜야 동작.
- RBLN은 vLLM 표준이라 옵션 추가하면 즉시 켜짐: `--enable-auto-tool-choice --tool-call-parser llama3_json` (EXAONE은 자체 template — `exaone3` parser 필요할 수도, 존재 여부 확인 필요)
- Furiosa는 furiosa-llm 자체 서버라 tool calling 파싱 로직이 v2026.1엔 없음(혹은 모델 사전 컴파일 시 chat template에 tool 토큰 없음)

**해결 가능성**
- RBLN: 옵션 추가만으로 가능. 다만 EXAONE 모델은 tool-special-token 사전 학습 안 됨 → 신뢰성 낮음. Llama-3.1 RBLN 컴파일 + tool parser면 OK.
- Furiosa: 모델 artifact 자체에 tool calling chat template 포함된 변형 필요 (Furiosa publish 측 작업)

**RBLN 검증 결과 (2026-05-29 실측)**:

Llama-3.1-8B-Instruct RBLN 컴파일(TP=4, max_seq=8192) + vllm-rbln args에 `--enable-auto-tool-choice --tool-call-parser llama3_json` 추가 후:

```json
// 요청: "What is the weather in Seoul right now? Please call the tool."
// tools=[get_current_weather(city, unit)]
{
  "tool_calls": [{
    "function": {
      "name": "get_current_weather",
      "arguments": "{\"city\": \"Seoul\", \"unit\": \"celsius\"}"
    }
  }],
  "finish_reason": "tool_calls"
}
```

→ **NPU에서 정상 동작**. tool_calls parsing 정확, finish_reason 올바르게 `tool_calls` 반환.

### (B) Multi-LoRA serving

**현상**
- RBLN: 존재하지 않는 LoRA 어댑터 이름 요청 → `404 model does not exist` (vllm-rbln에 `--enable-lora` 없음 — 정상 거부)
- Furiosa: 이상한 model 이름 요청에도 그냥 답변 → model name 검증 X, LoRA 개념 없음

**원인**
- vLLM Multi-LoRA는 weight를 런타임에 swap. **NPU는 가중치가 사전 컴파일된 정적 그래프**라 동적 LoRA 적용 불가.
- Workaround: LoRA를 base model에 **fuse**(merge) 후 NPU용 다시 컴파일. 어댑터당 분리된 InferencePool로 운영.

**해결 가능성**
- RBLN/Furiosa 모두 native multi-LoRA는 미지원
- 우회: 어댑터 N개면 컴파일 N번 + InferencePool N개. EPP가 model 이름으로 분기 (메모리는 N배)

### (C) Speculative decoding

**원인**
- Speculative decoding = draft model이 다음 N 토큰 추측 → target model이 일괄 검증. draft·target 두 모델 그래프를 같은 inference loop에서 교차 실행.
- NPU는 컴파일 단위가 **고정 그래프 + 고정 batch/seq**라 두 모델 교차 실행이 단순 추가 옵션으로 안 됨.

**해결 가능성**
- 별도 draft 컴파일 + custom pipeline 필요. SDK 레벨 기여 단계. PoC에선 불가.

### (D) 런타임 Quantization

**원인**
- vLLM는 weight load 시 AWQ/GPTQ/FP8 dequantize/dequant kernel을 GPU에서 동적 실행. NPU는 컴파일 단계에 양자화 옵션이 박힘.

**해결 가능성**
- RBLN: 컴파일 시 `rbln_quantization="rbln_w4a16"` 같은 옵션. 모델별 재컴파일.
- Furiosa: HF에 publish된 변형(`furiosa-ai/Llama-3.1-8B-Instruct-INT4` 같은 게 있다면) artifact 교체.

### (E) Disaggregated Prefill/Decode

**현상**
- Furiosa: pod의 `routing-proxy` init container = NIXL sidecar 이미 떠 있음. chart `prefill.create=true` 켜면 prefill 풀 별도 분리.
- RBLN: vllm-rbln 0.10.2에 PD disaggregation 표준 vLLM v1과 동일 인터페이스인지 검증 미완료. NIXL connector 호환성 미확인.
- A100: vLLM v1 disagg 즉시 가능.

**조합 시사점**
- 이상적: **A100 (prefill, 컴퓨트 무거움) → NPU (decode, 메모리 무거움)** — but cross-vendor KV transfer 호환 검증 필요. NIXL이 다 처리하지만 모델 그래프 일치 필요.
- 현실적: 같은 vendor 안에서만 (Furiosa prefill+decode 분리).

## 컴파일 단계가 만드는 본질적 제약

NPU의 모든 한계는 **사전 컴파일 정적 그래프**에서 비롯됩니다:

| GPU(vLLM)에서 동적인 것 | NPU에서 컴파일 시 박히는 것 |
|---|---|
| max_model_len (요청마다 다름) | `rbln_max_seq_len` / artifact의 `max_context_len` |
| tensor parallel size | `rbln_tensor_parallel_size` |
| batch size 자유 | `rbln_batch_size` (또는 bucketing 옵션) |
| LoRA adapter swap | base만 (LoRA는 fuse 후 재컴파일) |
| draft model attach | 별도 컴파일 + 외부 pipeline |
| 양자화 종류 변경 | 컴파일 시점 결정 |
| 모델 architecture | SDK 컴파일러 지원 매트릭스 안에 있어야 |

GPU는 **PyTorch 그래프를 런타임 JIT** → 자유롭게. NPU는 **컴파일 → 정적 .rbln/.furiosa artifact** → 빠르고 효율적이지만 변경엔 재컴파일.

## NPU에서 잘 되는 것 + 활용 패턴

- **OpenAI 호환 chat/completion + streaming + JSON output** — 일반 LLM 서빙 표준 시나리오 다 커버
- **prefix caching + chunked prefill** — TTFT 개선 (Furiosa는 `cached_tokens` 측정 응답)
- **Long context 8k~131k** (Furiosa) — RAG / long doc summarize 가능
- **Tensor parallel** — 한 모델 여러 카드 분산
- **vLLM 메트릭 → Prometheus → KEDA** — autoscaling
- **InferencePool + EPP routing** — multi-model 게이트웨이
- **InferenceObjective priority** — SLO 분리

## NPU 모델 별 핵심 차이 한 줄

| 모델 서버 | 강점 | 약점 |
|---|---|---|
| **vllm-rbln** | vLLM 호환성 ↑ (옵션 켜기로 tool/logprobs/JSON 다 됨). 한국어 EXAONE 컴파일 publishable. | `rbln_max_seq_len`이 컴파일 옵션 (현재 1024). 모델별 컴파일 시간 들음. |
| **furiosa-llm** | 자체 서버라 안정적. **131k context** 즉시. HF artifact 한 줄 다운로드. | Furiosa publish 모델 한정. Tool calling 미지원. 모델 이름 검증이 느슨함. |

## 다음 NPU 활성화 후보

| 우선 | 항목 | 작업 |
|---|---|---|
| 1 | **RBLN tool calling** | vllm-rbln Deployment args에 `--enable-auto-tool-choice --tool-call-parser llama3_json` 추가 (단 EXAONE 적합성은 검증) |
| 2 | **RBLN 더 긴 context** | Llama-3.1-8B를 `rbln_max_seq_len=32768` `rbln_batch_size=1`로 재컴파일 |
| 3 | **Furiosa disagg prefill** | helm upgrade `--set prefill.create=true --set prefill.replicas=1` (NIXL connector 이미 떠 있음) |
| 4 | **NPU InferencePool에 SLO Objective 추가** | `furiosa-llama31-8b-pool`에 priority=80 objective 묶기 |
| 5 | **NPU 메트릭 → Grafana 대시보드** | rbln-metrics(별도 셋업 필요) + furiosa-metrics-exporter |

## 한 줄 결론

NPU(Rebellions·Furiosa)는 **표준 LLM 서빙(chat/streaming/JSON/prefix caching/multi-model routing/SLO/autoscaling) 거의 다 커버**. **LoRA·speculative·런타임 quantization·function calling parser** 만 GPU 우위. 그 차이는 모두 **컴파일 vs 런타임** 모델 변경의 차이.
