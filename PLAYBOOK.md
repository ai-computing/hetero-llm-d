# llm-d Serving Playbook — 무엇을 할 수 있나, 어떻게 접근하나

> 작성: 2026-05-29 / **갱신: 2026-06-01** / [STATUS.md](./STATUS.md) [FEATURES.md](./FEATURES.md) [NPU-FEATURES.md](./NPU-FEATURES.md) [README.md](./README.md)
> 대상: 사내 LLM 플랫폼 운영자 + 서빙 사용자

## 갱신 사항 (2026-06-01)

- **A100**: vllm-openai → **`ds4` (DwarfStar) 엔진 + DeepSeek V4 Flash** (97GB hybrid Q4K/IQ2XXS imatrix GGUF). inline reasoning (`reasoning_content`) + tool calling 지원. 한국어 정상.
- **RBLN**: EXAONE → **KONI-Llama3.1-8B-Instruct** (KISTI 한국어 fine-tune)
- **Furiosa**: chat 서빙 → **Qwen3-Embedding-8B** (RAG embedding 가속)
- **EPP**: v0.7 (no-hit-lru-scorer 추가)
- **RAG**: Qdrant + retriever FastAPI + NAS SMB (read-only) 통합

## 0. 이 플랫폼이 자체적으로 줄 수 있는 것

| | 기존 자체 호스팅 (단일 GPU 박스) | 우리 플랫폼 (llm-d 위) |
|---|---|---|
| 모델 추가 | docker run 또 띄움 | InferencePool CR 한 줄, EPP가 자동 라우팅 |
| 가속기 다양화 | 같은 vendor만 | NVIDIA + Rebellions + Furiosa + CPU 동시 |
| 트래픽 변동 대응 | 수동 replica 조정 | KEDA + Prometheus 메트릭 |
| 자원 격리 | namespace만 | Rancher Project + ResourceQuota로 NPU 슬라이스 |
| 사용자별 latency 우선 | 라우터에서 수동 | `InferenceObjective` priority |
| 모델 비교 (A/B) | 따로 두 endpoint | 같은 prompt → 4 path 비교 (다른 backend) |
| 외부 노출 | nginx 직접 | Gateway IP `192.0.2.12` 단일 |

## 1. 워크로드 유형별 라우팅 가이드 (2026-06-01)

| 워크로드 | 추천 모델 | 가속기 | 이유 |
|---|---|---|---|
| **고품질 reasoning 챗봇** | `deepseek-v4-flash` | A100 + ds4 | 671B MoE + inline reasoning_content. 가장 강한 답변 품질 |
| **인터랙티브 한국어 챗봇 (TTFT 중요)** | `koni-llama3.1-8b-rbln` | RBLN x4 | 한국어 fine-tune, 전력 효율 (30W × 4), 첫 토큰 빠름 |
| **함수 호출 (Agent)** | `deepseek-v4-flash` 또는 `koni-llama3.1-8b-rbln` | A100 / RBLN | 둘 다 tool calling 동작 |
| **RAG embedding 생성** | `Qwen3-Embedding-8B` | Furiosa RNGD x 2 | dim 4096 고품질, NPU 가속 |
| **배치 분석 / 오프라인 / 비용 민감** | ollama 모델 | CPU 풀 (cpu-1/2/3) | 전력·가격 최저, 지연 허용 |
| **간단한 영어 챗봇** | ollama 모델 | CPU | 처리량 작아도 됨 |
| **새 모델 PoC** | 먼저 A100/ds4 또는 ollama → 검증 후 NPU 컴파일 | A100 → RBLN | 운영 검증 후 NPU로 이관 |

## 2. 클라이언트 연결 패턴

### (a) 챗봇 UI — Open WebUI / Chatbot UI

```bash
docker run -d \
  -e OPENAI_API_BASE_URL=http://192.0.2.12/v1 \
  -e OPENAI_API_KEY=dummy \
  -p 3000:8080 ghcr.io/open-webui/open-webui:main
```

UI에서 모델 선택 시 `deepseek-v4-flash`, `koni-llama3.1-8b-rbln` 노출.

각 path마다 별도 connection 등록하면 사용자가 모델 드롭다운에서 선택.

### (b) VSCode (Continue.dev)

`~/.continue/config.json`:
```json
{
  "models": [
    {"title":"Llama-RBLN","provider":"openai","apiBase":"http://192.0.2.12/exaone","model":"llama-3.1-8b-rbln"},
    {"title":"Llama-Furiosa","provider":"openai","apiBase":"http://192.0.2.12/llama31","model":"furiosa-ai/Llama-3.1-8B-Instruct"},
    {"title":"Llama-A100","provider":"openai","apiBase":"http://192.0.2.12/gpu","model":"llama-3.1-8b-instruct-gpu"}
  ]
}
```

### (c) Python (OpenAI SDK / LangChain)

```python
from openai import OpenAI
clients = {
  "rbln":    OpenAI(base_url="http://192.0.2.12/exaone/v1",    api_key="x"),
  "furiosa": OpenAI(base_url="http://192.0.2.12/llama31/v1",   api_key="x"),
  "a100":    OpenAI(base_url="http://192.0.2.12/gpu/v1",       api_key="x"),
  "cpu":     OpenAI(base_url="http://192.0.2.12/cpu/v1",       api_key="x"),
}
# 같은 prompt를 4 backend에 동시 보내 응답·지연 비교
```

### (d) RAG 시스템 통합

- Vector DB (chroma/qdrant) → namespace tenant-a에 K8s deployment
- Retriever 결과 + path 선택 → `/llama31`(긴 context) 또는 `/exaone`(한국어)
- llm-d Router의 `InferenceObjective`로 latency-sensitive RAG vs batch RAG 분리

### (e) Agent / 함수 호출

`/exaone`(Llama-3.1 RBLN, tool calling 활성)에 OpenAI Function 스펙으로 호출 — 사내 시스템(JIRA, Confluence, 사내 검색)을 tool로 묶어 자율 에이전트.

## 3. 운영자 관점 — 무엇을 어떻게 봐야 하나

### 핵심 대시보드 (Grafana)
- **TTFT p50/p95/p99 by pool** — `histogram_quantile(0.95, vllm:time_to_first_token_seconds_bucket)`
- **Throughput (tokens/sec) by pool** — `rate(vllm:generation_tokens_total[5m])`
- **NPU/GPU util** — DCGM (A100) / rbln-metrics / furiosa-metrics-exporter
- **Queue depth → KEDA trigger** — `vllm:num_requests_waiting`
- **Cost proxy (전력 × 사용시간)** — node-exporter `node_power_consumption` 있으면

### 자동 운영
- 트래픽 증가 → KEDA가 replica ↑ (NPU 카드 여유 있을 때)
- pod 죽으면 Recreate strategy로 재시작 (host site-packages 의존성 안정)
- 노드 장애 → Rancher가 알림, 다른 노드에 reschedule

### Multi-tenant
- 부서별 namespace (tenant-a/b/...)
- Rancher Project로 사용자/그룹 매핑
- ResourceQuota로 `rebellions.ai/ATOM: 2`, `furiosa.ai/rngd: 2` 사전 분배
- 사용자는 자기 namespace에서 자유롭게 InferencePool 생성

## 4. 실험·검증 자동화

### (a) 같은 prompt → 4 backend 응답·지연 비교

```bash
PROMPT='{"messages":[{"role":"user","content":"한국 경제 1줄 요약"}],"max_tokens":80}'
for path in exaone llama31 gpu cpu; do
  echo "=== $path ==="
  case $path in
    exaone)  MODEL='llama-3.1-8b-rbln' ;;
    llama31) MODEL='furiosa-ai/Llama-3.1-8B-Instruct' ;;
    gpu)     MODEL='llama-3.1-8b-instruct-gpu' ;;
    cpu)     MODEL='llama3.2:3b' ;;
  esac
  time curl -s -X POST http://192.0.2.12/$path/chat/completions \
    -H "Content-Type: application/json" \
    -d "{\"model\":\"$MODEL\",$PROMPT}" | jq -r '.choices[0].message.content'
done
```

### (b) 벤치마크
- `lm-evaluation-harness` 또는 `vllm-bench`를 K8s Job으로 띄워서 4 backend 동시 측정
- 결과는 PVC 또는 S3로 저장

### (c) llm-as-judge
- A100 풀의 Llama-3.1을 평가자로, 다른 풀 응답 평가 → CI 파이프라인 통합

## 5. SLO 운영 (InferenceObjective)

이미 등록된 두 objective:
- `low-latency` (priority 100) — 챗봇 첫 응답
- `high-throughput` (priority 10) — 일반 분석

추가 권장:
- `batch` (priority 1) — 야간 off-peak 처리, low priority 큐
- `interactive-rag` (priority 80) — 검색 후 답변, 약간 빠른 응답

요청 헤더로 적용:
```
-H "x-gateway-inference-objective: low-latency"
```

## 6. 다음 단계 후보 (구체 작업 단위)

| 우선 | 작업 | 시간 | 기대 효과 |
|---|---|---|---|
| 1 | **A100용 InferencePool** 등록 | 5분 | EPP가 GPU 풀도 라우팅 (KV-affinity, SLO) |
| 2 | **Open WebUI 배포** in tenant namespace | 30분 | 사내 챗봇 즉시 사용 가능 |
| 3 | **RAG endpoint** (chroma + retrieval API) | 1시간 | 사내 문서 기반 QA |
| 4 | **Llama-3.1-8B 다양한 컴파일 변형** (RBLN/Furiosa quantization) | 1~2시간 | 동일 모델 다른 quality/speed tradeoff |
| 5 | **A100 multi-LoRA** | 30분 | 사용자별 fine-tune adapter |
| 6 | **EPP KV-cache indexing 활성** | 10분 | 동일 prefix 요청 latency ↓ |
| 7 | **토큰 사용량 추적 + 빌링 대시보드** | 2시간 | 사용량 가시화, 부서별 정산 기반 |
| 8 | **사내 SSO** (Rancher OIDC/SAML) | 0.5일 | 비번 관리 → 회사 ID로 통합 |

## 7. 비용·효율 의사결정 매트릭스

| 상황 | 결정 |
|---|---|
| 모델이 자주 바뀜 (R&D 단계) | A100 위주 — 런타임 자유로움 |
| 모델 fix됨, 대량 트래픽 | RBLN/Furiosa로 이전 — perf/W 우위 |
| 한 모델 + 다중 어댑터 (multi-tenant fine-tune) | A100 + LoRA |
| 야간 배치 / 비용 최우선 | CPU 풀 (ollama) |
| 긴 컨텍스트 + 적은 동시성 | Furiosa (HBM 64GB 활용) |
| 한국어 + 비용 + 전력 | RBLN (EXAONE 또는 Llama-Korean 컴파일) |

## 8. 잠재적 함정과 회피

- **NPU 모델 변경 = 재컴파일**: 1시간 단위. CI에 미리 컴파일 → artifact 캐싱 권장
- **NPU SDK 버전 ↔ KMD 버전 매핑**: host driver 업그레이드 시 NPU 라이브러리 mismatch 가능
- **Furiosa-LLM emptyDir 30 GiB**: pod 재시작 시 모델 재다운로드. PVC로 옮기면 안정
- **사내 IP 점유**: 임의 IP 사용 금지, IT에서 정식 할당 (현재 `.233`)
- **HF gated model**: Llama 3.x 라이센스 승인 token 필요. 한 번 받아 secret으로 공유
- **Multi-tenant 자원 격차**: 같은 NPU 카드를 두 namespace가 동시 점유 불가 (device-plugin 단위가 카드)

## 9. 한 줄 요약

이 플랫폼은 **vendor-neutral OpenAI 호환 LLM 게이트웨이**입니다. **모델·가속기·workload·user 조합 매트릭스**를 K8s CR로 표현하고 EPP가 자동 라우팅합니다. 사용자는 한 IP만 알면 되고, 운영자는 InferencePool/InferenceObjective/ResourceQuota 세 객체로 거의 모든 정책을 표현할 수 있습니다.
