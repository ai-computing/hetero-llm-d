# 클러스터 현황 스냅샷

<!-- research-hub:header:begin (maintained by .research/report.py; keep the "- **Key**: value" format) -->
- **State**: active
- **Updated**: 2026-10-19 11:26+09:00
- **Agent**: claude@gspark-PowerEdge-R7525
- **Task**: 이종 혼합 풀 라우팅 검증 (Llama-8B A100·ATOM·RNGD)
- **Last result**: 한 InferencePool에 A100·RBLN·RNGD 3벤더 라우팅 동작(engine-type 라벨로 메트릭 매핑). 기본 EPP 점수는 속도 무시: 3벤더 unique-prefix c64 128tok 37.6s(3.4 req/s) vs A100 단독 5.5s(23.3 req/s) — RBLN 꼬리지연이 전체 결정, 유휴 RNGD는 거의 미선택. 출력 일치: A100·RNGD 38/40 동일(정답 32/40), RBLN(PD실험 아티팩트) 23/40
- **Next**: capacity-aware heterogeneous scorer(LMDTOP-22) 이미지 빌드 후 같은 부하로 비교
- **Blockers**: none
<!-- research-hub:header:end -->

## Goal

이 레포의 목표는 GPU(A100)·Rebellions ATOM(RBLN-CA22)·Furiosa RNGD·CPU가 섞인 사내 K8s 클러스터를 **llm-d(Gateway → InferencePool → EPP)로 묶어 이기종 LLM 서빙을 운영하는 것**이다 (`README.md` 「목표 토폴로지」, `FEATURES.md`). 그 위에서 NPU가 llm-d 기능을 어디까지 지원하는지 검증하고 (`NPU-FEATURES.md`), 공유 모델 스토어로 다운로드·컴파일·배포를 일원화한다 (`manifests/README-model-store.md`, `0e90396`). 연구 범위는 이기종 PD disaggregation(2026-08, `PD disaggregation_HISTORY.md`)과, 2026-10부터 이종 가속기의 같은 부하 성능·에너지 비교(`scripts/hetero-sweep.py`)까지 넓혔다. 운영 TUI `lmd-top`은 `lmd-top/STATUS.md`, RNGD 파인튜닝 학습(`npu-lora/`)은 `npu-lora/STATUS.md`에서 따로 추적한다.

## Findings

최신순. 출처를 괄호에 적었다. 레포에 원자료가 없는 수치는 그렇다고 밝혔다.

- **2026-10-19 · 한 InferencePool에 A100·RBLN ATOM·RNGD를 섞어 Llama-3.1-8B를 라우팅했다.** 파드마다 `llm-d.ai/engine-type` 라벨을 달면 EPP가 엔진별 메트릭 매핑(`vllm` / `furiosa-llm`)을 골라 세 벤더 모두에 라우팅한다. 다만 기본 점수(queue·KV·prefix)는 속도를 보지 않는다. 128요청·128토큰·동시성 64에서 3벤더 풀은 37.6초(3.4 req/s)로 A100 단독 5.5초(23.3 req/s)보다 6.6배 느렸다. 느린 RBLN(batch 8)이 받은 요청의 꼬리 지연이 전체 완료 시간을 정했고, 유휴 RNGD는 거의 선택되지 않았다. 고정 프롬프트 40개에서 A100과 RNGD 출력은 38/40 같았고(정답 32/40), 이번 RBLN 아티팩트(PD 실험용, optimum-rbln 0.11.0.post1)는 23/40만 맞았다. 예전 `~/vllm_test` RBLN 아티팩트(0.10.0.post1)는 0.11 런타임이 `LOADING_INVALID_VERSION`으로 거부한다 (`experiments/2026-10-19-hetero-llama8b-mixed-pool.md`, `manifests/hetero-llama8b-mixed.yaml`).
- **2026-10-19 · ai-rm protocol v0.1 통합 (LLMD-32, PR #1).** rm-core v0.1.0의 `AcceleratorProfile` CRD를 실제 클러스터에 설치했다(`scripts/airm-install.sh apply crd`, 객체는 아직 0개). `airm_*` ScrapeConfig, 빈 `llm-serving/airm-placement`, Grafana `airm.json`은 server dry-run만 통과시켰고 적용하지 않았다. EPP placement scorer 자리는 문서로만 표시했다(`deploy/airm/README.md`).
- **2026-10-15 · 하드웨어 배치가 문서와 달랐다.** A100 × 2는 etri-001이 아니라 `etri-esc8000-e11`(PCI 99/bd:00.0)에 있다. 현재 구성은 etri-001 = RBLN×4 + RNGD×3, e11 = RNGD×2 + A100×2다. e11 A100은 driver 580.178과 nvidia-container-toolkit 1.19.1로 복구했다. kubelet `evictionHard`는 nodefs/imagefs 5%로 낮췄다 (README.md 작업 트리 diff 「etri-ESC8000-E11」, 이 파일 아래 하드웨어 변경 메모).
- **2026-10-15 · e11 A100 vLLM v0.11.0 Llama-3.1-8B 미니 sweep 결과다.** 입력 614, 출력 128, 60 s로 돌렸다. 동시성 1/8/32/64에서 각각 84/621/1945/3094 tok/s가 나왔다. 노드 wall 전력은 약 940 → 985 W, tok/J(wall)는 0.09 → 3.15였다. 다만 e11 wall 전력에는 다른 사용자 작업이 섞여 있고, DCGM 스크랩 간격도 거칠다. 그래서 에너지 수치는 잠정치다. 레포에 `experiments/` 기록이나 원본 JSONL은 없다. 매니페스트는 `manifests/vllm-a100-llama31-8b.yaml`, 전력 수집은 `manifests/ipmi-exporter.yaml`(유휴 wall 약 620~670 W/노드)이다.
- **2026-09-10 · 모델 스토어 인벤토리에 출처 정보가 붙었다.** 인벤토리가 각 산출물을 빌드한 toolchain과 스토어 df를 함께 발행한다. 오프라인 회귀 테스트는 `scripts/test-model-store-discovery.py`다 (`33f7a40`, `f232df7`).
- **2026-08 · 이기종 PD disaggregation을 실험했다(`~/workspace/01_pd_disag`).** 정리 문서는 `PD disaggregation_HISTORY.md`다.
  - 공식 Furiosa 엔진에서 재프리필 PD를 복제 구성과 비교했다. 입력 2048, N=32에서 복제 717.6 tok/s, PD 326.3 tok/s였다. 긴 입력에서는 PD가 불리했다 (§3.4).
  - 자체 런타임으로 실제 KV를 전송했다. resident-KV로 decode를 48.2 → 16.3 ms/token, 약 2.96배 줄였다 (§5.1).
  - shape 제한 8, group 8에서 B=4 step이 17.62 ms(4.40 ms/token)였다. 게이트웨이 TPOT는 27.00 → 20.10 ms가 됐다 (§5.4, `rngd_llmd` `42f3e78`).
  - 4조합 비교(S=256, B=4)에서 RNGD→RNGD가 52.29 tok/s로 가장 높았다. RNGD→ATOM은 24.56, ATOM→RNGD는 36.75, ATOM→ATOM은 20.65 tok/s였다. ATOM decode TPOT는 약 90 ms로, RNGD 약 30 ms의 3배였다 (§6.2).
  - 같은 배치 조건으로 다시 재면 카드당 처리량은 1카드 solo가 2카드 PD보다 1.48~1.99배 높았다 (§6.5, `384310c`).
  - continuous batching은 static보다 느렸다(34.2 vs 51.9 tok/s, §6.4).
- **2026-07-01 · K-EXAONE-236B-A23B(NVFP4A16)를 RNGD × 4에서 llm-d로 서빙했다.** `/exaone` 경로가 gateway → InferencePool → 전용 EPP → RNGD로 200 응답을 돌려줬다. TTFT p95는 약 0.23 s였다. 차트가 `ceil(tp/8)=1`을 계산하므로 rngd=4 패치가 필요하다 (`9b5f4be`, `689e1cb`).
- **2026-06-01 · 기준 서빙 스냅샷이다.** EXAONE-3.5-32B-AWQ를 A100 × 2 DP로 서빙해 약 62 t/s가 나왔다. KONI-Llama3.1-8B를 RBLN TP=4로 서빙해 약 14 t/s가 나왔다. llm-d v0.7 EPP(`no-hit-lru-scorer` 포함)를 적용했다 (이 파일 아래 표, `FEATURES.md`).
- **2026-05-29 · NPU의 llm-d 기능 호환성이다.** RBLN과 RNGD 모두 OpenAI API, streaming, JSON, prefix caching, chunked prefill, TP, EPP 라우팅을 지원한다. Multi-LoRA serving, speculative decoding, 런타임 양자화는 사전 컴파일 정적 그래프 때문에 지원하지 않는다. Furiosa는 tool calling도 지원하지 않는다. RBLN tool calling(`llama3_json`)은 실측으로 확인했다. Furiosa Llama-3.1-8B는 한국어 응답에서 garbage 토큰을 냈다 (`NPU-FEATURES.md`).

## Open questions

- **이종 에너지 비교가 미완이다.** `scripts/hetero-sweep.py`는 A100 6점만 측정하고 사용자 요청으로 중단했다. DCGM 갱신이 약 20 s 간격이라 A100 카드 전력은 재측정해야 한다(이후 `--collect-interval=1000`으로 바꿨다고 기록돼 있다). e11 wall 전력에서 다른 사용자 부하를 어떻게 빼거나 피할지도 정해야 한다. RNGD solo와 ATOM PD 구성은 아직 측정하지 않았다.
- **PD 재측정이 남았다.** 8/25 최적화까지 반영해 모든 조합과 solo를 같은 메타데이터(commit, shape cap, group, prefetch)로 다시 재야 한다. `load_continuous.jsonl`에서 sched 필드가 불일치하는 원인도 밝혀야 한다. NIXL은 아직 스텁이다. GPU prefill → NPU decode가 가능하고 이득인지도 검증하지 않았다 (`PD disaggregation_HISTORY.md` §12).
- **모델 스토어 SMB 마운트가 노드마다 다르다.** cpu-2에서 CIFS error 115가 났다. 컴파일 Job을 RBLN 노드에서 돌릴 수 있는지도 확인하지 않았다 (`manifests/README-model-store.md` 트러블슈팅). discovery CronJob 변경분(`scanned_at`)은 아직 커밋하지 않았고 클러스터에도 적용하지 않았다 (작업 트리 diff).
- **노드 장애가 남아 있다.** cpu-3은 2026-07-07부터 down이고, open-webui PVC가 cpu-3에 묶여 있다. dgx-spark0과 gx10-4744(GB10)는 DiskPressure 뒤 응답하지 않는다. 물리 접근이 필요하고 원인도 밝히지 못했다. e11은 사용자 결정으로 cordon 상태다.
- **아래 2026-06 스냅샷이 낡았다.** ds4/DeepSeek, A100 위치, 활성 모델 표가 현재와 다르다. 현재 llm-serving의 모델 Deployment는 의도적으로 replicas 0이다. 스냅샷을 현재 상태로 다시 쓸지 정해야 한다.
- **보안 정리가 남았다.** HF 토큰은 revoke하는 것을 권장한다. NAS `smb-creds` Secret은 다시 만들어야 한다 (아래 「알려진 한계」).
  - 2026-10-16 추적 파일에서 내부 IP와 문서의 admin/admin 표기를 지웠다(`181a3e3`, 실제 값은 untracked `cluster.local.env`). git 이력에는 아직 남아 있고, 이력 정리는 hub가 맡는다. 실제 Grafana·Rancher 관리자 비밀번호가 기본값에서 바뀌었는지는 확인하지 않았다. `docs/`의 pptx/pdf 바이너리는 검사 대상이 아니어서 IP가 들어 있을 수 있다.

---

> 작성 시점: 2026-06-01 (live, EXAONE-3.5 DP + KONI 최적화 적용)
> **2026-10-15 하드웨어 변경**: A100 × 2는 이제 **etri-esc8000-e11**에 있다(etri-001에서 이동, 현재 etri-001에는 NVIDIA 장치 없음). 현재 구성은 etri-001 = RBLN×4 + RNGD×3, e11 = RNGD×2 + A100×2. 아래 표는 2026-06 스냅샷이다.
>
> 전체 매뉴얼은 [README.md](./README.md), 매니페스트는 `manifests/`, 셋업 스크립트는 `scripts/`

## 한 줄 요약

K8s 1.31 + Cilium 1.16 + llm-d **v0.7 EPP**로 **NVIDIA A100 × 2 / Rebellions RBLN-CA22 × 4 / CPU**에 LLM 3종 동시 서빙 + Furiosa RNGD × 2로 RAG embedding 가속. 사내 IP **<gateway-host>** 단일 entrypoint(envoy-gateway)에서 path 분기.

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

## Grafana 대시보드

| UID | 제목 | 메트릭 |
|---|---|---|
| `nvidia-dcgm` | NVIDIA GPU — DCGM Exporter | DCGM 22개 |
| `furiosa-npu` | Furiosa NPU — RNGD | npu_alive/util/freq/temp |
| `llm-models` | LLM Models — vLLM / RBLN | requests, KV usage, prefix hit, latency p95, t/s |

## 운영 entrypoint

**공식 통합 IP**: `<gateway-host>` (envoy-gateway LB, Cilium L2 announcement로 광고, gateway `eg` class, `Programmed=True`)

```bash
# A100 → DeepSeek V4 Flash
curl -X POST http://<gateway-host>/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"model":"deepseek-v4-flash","messages":[{"role":"user","content":"안녕"}]}'

# RBLN → KONI Llama 3.1 (한국어 강세)
curl -X POST http://<gateway-host>/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"model":"koni-llama3.1-8b-rbln","messages":[{"role":"user","content":"한국어 시 한 편 써줘"}]}'
```

## llm-d 활성 컴포넌트 (v0.7 EPP)

| 컴포넌트 | 종류 / 이미지 | 비고 |
|---|---|---|
| EPP (router) | `ghcr.io/llm-d/llm-d-router-endpoint-picker-dev:main` | **llm-d v0.7 신규 image** — `no-hit-lru-scorer` 활성 |
| EPP plugin set | queue-scorer(w=2) + kv-cache-utilization-scorer(w=2) + prefix-cache-scorer(w=3) + **no-hit-lru-scorer(w=2)** | v0.7 신규 plugin 포함 |
| InferencePool | `llmd-router` (selector dynamic) | model server 변경 시 selector 패치 |
| Gateway | `llm-d-gateway` (eg class, ADDRESS `<gateway-host>`) | envoy-gateway 1.3.0 |
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
| Document source | NAS SMB (<doc-nas-host> 시놀로지) | **PV ReadOnlyMany + volumeMount readOnly** — 무결성 보장 |
| NAS folders | `aicomputing`, `kcloud_rm`, `lab` | SMB 인증은 `smb-creds` Secret (재생성 대기 — 사용자 입력 필요) |

## 관리/관측 UI

| UI | URL | 인증 |
|---|---|---|
| **Rancher** | https://<cp-node-ip>:30443 | 관리자 계정 (문서에 기록하지 않음) |
| Headlamp | http://<cp-node-ip>:30502 | `kubectl create token headlamp -n headlamp --duration=24h` (또는 `headlamp-admin` SA token) |
| Hubble UI | http://<cp-node-ip>:30081 | 없음 |
| Grafana | http://<cp-node-ip>:30300 | 관리자 계정 (문서에 기록하지 않음) |
| Prometheus | http://<cp-node-ip>:30090 | 없음 |

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
- A100 driver/library mismatch 재발 (현재 e11): `sudo modprobe -r nvidia_uvm nvidia_drm nvidia_modeset nvidia && sudo modprobe nvidia` (참고: `scripts/05-nvidia-setup.sh`). `no runtime for "nvidia"` 에러는 containerd에 nvidia 런타임 미등록이다 → `nvidia-ctk runtime configure --runtime=containerd` 후 containerd 재시작
- Gateway IP `<gateway-host>`: Cilium L2 announcement 통해 광고, 양도 시 `ciliumloadbalancerippool` 패치
- EPP rollback (v1.5.0 standard): `kubectl set image deployment/llmd-router-epp -n llm-serving epp=registry.k8s.io/gateway-api-inference-extension/epp:v1.5.0` (단 no-hit-lru-scorer plugin 제거 ConfigMap 패치 필요)

## Log

<!-- research-hub:log (report.py inserts new entries below this line, newest first) -->

### 2026-10-19 11:26+09:00 — 이종 혼합 풀 라우팅 검증 (Llama-8B A100·ATOM·RNGD)

- Result: 한 InferencePool에 A100·RBLN·RNGD 3벤더 라우팅 동작(engine-type 라벨로 메트릭 매핑). 기본 EPP 점수는 속도 무시: 3벤더 unique-prefix c64 128tok 37.6s(3.4 req/s) vs A100 단독 5.5s(23.3 req/s) — RBLN 꼬리지연이 전체 결정, 유휴 RNGD는 거의 미선택. 출력 일치: A100·RNGD 38/40 동일(정답 32/40), RBLN(PD실험 아티팩트) 23/40
- Next: capacity-aware heterogeneous scorer(LMDTOP-22) 이미지 빌드 후 같은 부하로 비교
- New todos: contrib heterogeneous-capacity EPP 이미지 빌드·혼합 풀 재측정; 벤더 풀 편입 전 고정 프롬프트 출력 일치(parity) 게이트; RBLN Llama-8B 정식 아티팩트로 정확도 재확인(현재 23/40)
- Params: conc=64, max_tokens=128, requests=128, furiosa_llm=2026.3.0, vllm_a100=v0.11.0, vllm_rbln=0.11.0
- Artifacts: experiments/2026-10-19-hetero-llama8b-mixed-pool/run-final-3v-u1-m128-c64.json, experiments/2026-10-19-hetero-llama8b-mixed-pool/run-a100only-u1-m128-c64.json
- Experiments: experiments/2026-10-19-hetero-llama8b-mixed-pool.md
- By: claude@gspark-PowerEdge-R7525 · main@d63c2ce-dirty
### 2026-10-19 09:58+09:00 — LLMD-33 ✅

- Result: PR #1 리뷰 반영(airm/v0.1): rm-core CRD 핀 v0.1.1(extra 필드, sha256 14cde6fa…) + 문서 참조 갱신. dry-run 무한 대기 원인 = CRD curl에 타임아웃 없음(빈 캐시 + 응답 없는 프록시에서 재현); curl --max-time/--retry, kubectl 전부 timeout+--request-timeout 래퍼, /readyz 사전 점검으로 분명한 오류. 검증: dry-run all 1.0 s 통과(CRD configured), 장애 3종 모두 10~60 s 내 rc=1, rm_core.conformance 3/3 PASS, test-model-store-discovery OK, 대시보드 18/18 지표
- Params: rm_core=v0.1.1
- Experiments: experiments/2026-10-19-airm-install-hang.md
- By: claude@gspark-PowerEdge-R7525 · airm/v0.1@48f1a6a-dirty

### 2026-10-19 09:10+09:00 — LLMD-32 ✅

- Result: PR https://github.com/ai-computing/llm-d-setup/pull/1 — rm_core.conformance 3/3 PASS(sim/loopback/greedy; 이 repo는 adapter 없음), CRD acceleratorprofiles.airm.ai-computing.io 실클러스터 설치, ScrapeConfig·airm-placement·대시보드 server dry-run OK, check_sensitive clean
- Next: PR 머지 후 scripts/airm-install.sh apply manifests로 수집 설정·airm-placement·대시보드 적용
- By: claude@gspark-PowerEdge-R7525 · airm/v0.1@0a3fa29-dirty

### 2026-10-16 15:01+09:00 — LLMD-31 ✅

- Result: 민감정보 정리 완료(181a3e3, push): check_sensitive 323건(내부 IP) → clean. 스크립트 4개(02-cp-init, capture-lmd-top, epp/make-epp, 03-worker 안내문)와 model-store.yaml을 cluster.local.env(untracked) + scripts/lib/cluster-env.sh로 파라미터화, render-manifest.sh 추가(라이브 PV와 dry-run 동일), cluster.example.env 커밋. 문서 IP는 placeholder, cast/svg/ASCII는 같은 길이 198.51.100.x로 교체. 문서의 Grafana/Rancher admin/admin 제거. ai-rm.yaml + README ## ai-rm 추가.
- Next: 실제 Grafana/Rancher 관리자 비밀번호 변경 여부 확인, docs/ pptx·pdf 바이너리 내 IP 점검
- By: claude@gspark-PowerEdge-R7525 · main@181a3e3-dirty

### 2026-10-16 11:47+09:00 — LLMD-2 ✅

- Result: STATUS.md를 클러스터 전용으로 정리: lmd-top(성숙도 평가)·npu-lora(LoRA 품질/PoC, full-FT 확장) 항목을 하위 프로젝트 STATUS.md로 옮기고 Goal에서 분리 추적 명시. 하위 초안 2개 실파일 대조·정정, 초안 문구 제거
- Next: 이종 에너지 sweep 재개(A100 1s DCGM 재측정 + RNGD solo/ATOM PD) 및 experiments/ 기록
- By: claude@gspark-PowerEdge-R7525 · main@f232df7-dirty

### 2026-10-16 10:40+09:00 — LLMD-1 ✅

- Result: STATUS.md bootstrap: Goal/Findings(2026-05~10-16, 출처 표기)/Open questions 작성. 최신: RNGD LoRA 품질 = A100 (NSMC 87.5 vs 87.6%)
- Next: 이종 에너지 sweep 재개(A100 1s DCGM 재측정 + RNGD solo/ATOM PD) 및 experiments/ 기록
- By: claude@gspark-PowerEdge-R7525 · main@f232df7-dirty
