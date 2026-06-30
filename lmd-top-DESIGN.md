# lmd-top — 설계 문서 (v0, 구현 전)

> llm-d 클러스터를 위한 터미널 관측·운영 도구. `k9s`의 네비게이션 + `all-smi`의 하드웨어 카드 +
> **llm-d EPP 아키텍처에 대한 1급 이해**를 한 화면에 결합한다.
> 작성: 2026-06-30 · 대상 클러스터: [STATUS.md](./STATUS.md) 참조

---

## 0. 한 줄 명제 (Thesis)

> **lmd-top은 `Gateway → EPP → Model Server → Infrastructure` 4계층을 하나의 터미널 화면에서
> 상관(correlate)해서 보여주고, EPP의 `Filter → Score → Pick` 의사결정을 관측·설명하는 유일한 CLI 도구다.**

기존 도구는 한 계층씩만 본다. 장애가 났을 때 "라우팅 오설정인가, 진짜 용량 부족인가"를 가르려면
**계층을 가로질러** 봐야 하는데(아래 §2), 그걸 터미널에서 해주는 도구가 지금 없다.

---

## 1. 차별점 — 왜 새로 만드나

| 도구 | 보는 계층 | llm-d/EPP 이해 | 가속기 | K8s 액션 | 터미널 | 한계 |
|---|---|---|---|---|---|---|
| **k9s** | K8s 오브젝트 | ❌ (그냥 Pod/Deploy) | ❌ | ✅ | ✅ | 추론·가속기·라우팅 의미를 모름 |
| **all-smi** | Infra(가속기)만 | ❌ | ✅✅ (NVIDIA/RBLN/Furiosa 네이티브) | ❌ | ✅ | 모델/EPP/라우팅 레이어 전무 |
| **llmtop** (arinbjornk) | 단일 호스트 psutil | ❌ | ⚠️(GPUtil 언급뿐) | ❌ | ✅ | 클러스터 아님, K8s/Prometheus/vLLM 모름, 플러그인 없음 |
| **Grafana**(llm-d 기본) | 전 계층(메트릭) | ⚠️(대시보드 제공) | ✅ | ❌ | ❌ 웹 | 인터랙션·드릴다운·scale 액션 없음, 토폴로지 인지 없음 |
| **lmd-top** (이 문서) | **4계층 상관** | ✅✅ **EPP Filter/Score/Pick 인지** | ✅ (all-smi/Prometheus 경유) | ✅ (scale/logs/describe) | ✅ | (신규) |

**핵심 차별 포인트 3개**
1. **EPP Decision Inspector** — 어떤 scorer가 활성이고(EPP ConfigMap introspect), 요청이 어느 pod로 갔으며
   (`inference_extension_scheduler_attempts_total{pod_name,status}`), pod별 큐 분포
   (`inference_pool_per_pod_queue_size`)가 고른지/쏠렸는지를 실시간 시각화. **이건 어떤 도구도 안 한다.**
2. **Cross-layer 상관 1줄 진단** — TTFT↑인데 큐만 쏠림 & HW 정상 → "라우팅 오설정",
   TTFT↑ & 풀 전체 포화 & VRAM 높음 → "용량 부족". (Datadog가 정의한 진단 로직을 자동 라벨로.)
3. **plugin-first** — EPP가 Plugins+SchedulingProfiles YAML로 구성되듯, lmd-top도
   **Collectors + Panels + Profiles** 로 구성. 새 가속기/새 메트릭/새 패널을 파일 하나로 붙인다(§6).

---

## 2. 멘탈 모델 — EPP 아키텍처에 매핑한 4계층

llm-d 요청 흐름(조사: GIE + llm-d-inference-scheduler):

```
 client
   │  POST /v1/chat/completions  model=exaone-3.5-32b
   ▼
┌──────────────┐  L1 GATEWAY (Envoy, ext_proc)        gateway addr, HTTPRoute path→pool
│ llm-d-gateway│  ─ 어디로 들어와 어느 InferencePool로 가나
└──────┬───────┘
       ▼
┌──────────────┐  L2 EPP (Endpoint Picker)            ★lmd-top 차별 영역★
│   EPP / GIE  │   Filter → Score → Pick
│  datastore   │   - Filters: decode/prefill/by-label
│  (scrapers)  │   - Scorers(weighted): queue, kv-cache-util, prefix-cache,
│              │       no-hit-lru, active-request, session-affinity, latency-pred
│              │   - Picker: max-score (동점시 random)
└──────┬───────┘   메트릭: inference_pool_*, inference_extension_scheduler_attempts_total
       ▼
┌──────────────┐  L3 MODEL SERVER (vLLM / vLLM-RBLN / ollama)
│  InferencePool│  running/waiting/swapped, KV cache %, prefix hit, TTFT/TPOT, t/s
│   endpoints   │  메트릭: vllm:*  (+ P/D 분리 시 prefill pod / decode pod / NIXL 전송)
└──────┬───────┘
       ▼
┌──────────────┐  L4 INFRASTRUCTURE (가속기 + 노드)
│ A100/RBLN/RNGD│  util%, VRAM, temp, power, freq  ── all-smi 영역
│  + node CPU/메모리 │  DCGM_FI_DEV_*, furiosa_npu_*, node_*
└──────────────┘
```

lmd-top의 모든 뷰는 이 4계층 중 하나(또는 상관)에 속한다.

---

## 3. 메트릭 카탈로그 (실측 확인 + 표준 이름)

> ✅=현재 Prometheus에 존재, ⏳=해당 워크로드 가동 시 자동 등장(모델/DCGM 지금 0/0), 🔌=직접 스크랩/EPP:9090

### L2 — EPP / InferencePool (llm-d 고유, port 9090) 🔌⏳
| 메트릭 | 타입 | 라벨 | 용도 |
|---|---|---|---|
| `inference_objective_request_total` | counter | model_name, target_model_name | 모델별 요청수 |
| `inference_objective_request_error_total` | counter | model_name | 에러율 |
| `inference_objective_request_duration_seconds` | dist | model_name | E2E p50/p95/p99 |
| `inference_objective_normalized_time_per_output_token_seconds` | dist | model_name | 정규화 TPOT |
| `inference_objective_input_tokens` / `output_tokens` | dist | model_name | 토큰 분포 |
| `inference_objective_running_requests` | gauge | model_name | 활성 요청 |
| `inference_pool_average_kv_cache_utilization` | gauge | name | 풀 평균 KV |
| `inference_pool_average_queue_size` | gauge | name | 풀 평균 큐 |
| **`inference_pool_per_pod_queue_size`** | gauge | **model_server_pod**, name | ★pod별 큐 분포(쏠림 탐지) |
| `inference_pool_ready_pods` | gauge | name | 준비된 pod 수 |
| **`inference_extension_scheduler_attempts_total`** | counter | **status, pod_name**, target_model_name | ★라우팅 결정 분포(누가 픽됨) |
| `inference_extension_flow_control_request_queue_duration_seconds` | dist | outcome | 게이트 대기/셰딩 |
| `inference_extension_flow_control_pool_saturation` | gauge | name | 풀 포화도 0~1+ |

### L3 — vLLM Model Server ⏳
`vllm:num_requests_running` / `_waiting` / `_swapped`, `vllm:gpu_cache_usage_perc`,
`vllm:gpu_prefix_cache_hit_rate`, `vllm:time_to_first_token_seconds`(TTFT hist),
`vllm:time_per_output_token_seconds`(TPOT), `vllm:e2e_request_latency_seconds`,
`rate(vllm:generation_tokens_total)`→t/s, `vllm:num_preemptions_total`,
P/D 분리시 KV 전송(NIXL) 메트릭 (로드맵).

### L4 — Infrastructure
- NVIDIA(DCGM ⏳): `DCGM_FI_DEV_GPU_UTIL`, `_FB_USED`/`_FB_FREE`, `_GPU_TEMP`, `_POWER_USAGE` {gpu, Hostname, modelName}
- Furiosa(✅ 실측): `furiosa_npu_core_utilization`, `_dram_usage`/`_dram_total`, `_hw_temperature`, `_hw_power`, `_alive` {device, core, hostname, arch=rngd}
- RBLN: **하드웨어 메트릭 없음** → vLLM 레벨로만(또는 `rbln-stat`/all-smi 노드 배포 시 🔌)
- 노드(✅): `node_cpu_seconds_total`, `node_memory_MemTotal/MemAvailable_bytes`, `node_load1`

---

## 4. 기능 / 뷰 (Features)

홈 = **Overview(합체)**. 상단 핫키 `0–6`/`:`명령으로 전환(k9s식).

| # | 뷰 | 계층 | 내용 | 차별 |
|---|---|---|---|---|
| **0** | **Overview** (홈) | 전 계층 | 상단 가속기 요약 바 + EPP 풀 상태 + 모델 리스트 + 1줄 cross-layer 진단 | ★상관 |
| 1 | **Accelerators** | L4 | all-smi식 디바이스 카드(util/VRAM/temp/power/freq + 스파크라인) | all-smi류 |
| 2 | **Models** | L3 | 모델별 run/wait/swap, KV%, prefix-hit, TTFT/TPOT, t/s, replica, path, 상태 | vLLM+kubectl |
| 3 | **EPP Inspector** | L2 | ★활성 scorer 목록(ConfigMap introspect) + 가중치 + 라우팅 결정 분포 + pod별 큐 히트맵 + 포화도 | **고유** |
| 4 | **Routing/Topology** | L1–L2 | Gateway addr→HTTPRoute path→InferencePool→endpoints 트리 다이어그램 | 토폴로지 |
| 5 | **Pods/Nodes** | L3–L4 | llm-serving pod 상태 + 노드 CPU/메모리 바 (k9s 미니) | k9s류 |
| 6 | **Request Lifecycle** | L1→L4 | (로드맵) 단일 요청을 Gateway→EPP결정→prefill/decode pod→토큰까지 추적(Tempo/OTel) | 트레이스 |

**액션(k9s식, 행 선택 후)**: `s`=scale(꺼진 모델 켜기/끄기), `l`=logs, `d`=describe, `e`=EPP ConfigMap edit, `Enter`=드릴다운, `/`=필터, `?`=도움말, `q`=종료.

---

## 5. 레이아웃 (ASCII, ≈100칼럼, 반응형)

### 공통 프레임 (k9s 크롬)
```
┌ lmd-top · llm-d @ k8s1.31 · 6 nodes ──────────── gw 192.0.2.12 ●Programmed ┐
│ A100 1/2  RBLN 4idle  RNGD 0/6  │ pool koni: 0pods sat0.00 │ models 0/4 ⚡685W │  ← 집계 요약 바
├ 0:Overview 1:Accel 2:Models 3:EPP 4:Route 5:Pods ─────────────── /filter  ?help┤  ← 뷰 탭
│  …본문…                                                                          │
├────────────────────────────────────────────────────────────────────────────────┤
│ ↑↓ sel  ⏎ drill  s scale  l logs  d desc  e epp-cfg  / filter  2s↻  q quit       │  ← 핫키 바
└────────────────────────────────────────────────────────────────────────────────┘
```

### [0] Overview (홈) — cross-layer 한 화면
```
─ ACCELERATORS ───────────────────────────────────────────────────────────────
 A100#0 [████████░░82%] 68/80G 64°C 310W  A100#1 [░░░0%] 0/80G 31°C 45W  RNGD×6 idle
─ INFERENCE (EPP pools) ───────────────────────────────────────────────────────
 POOL          READY  QUEUEavg  KVcache  SAT    SCORERS(active)
 llmd-router    0     –         –        0.00   queue·kv·prefix·no-hit-lru
 vllm-a100-pool 0     –         –        0.00   (idle)
─ MODELS ──────────────────────────────────────────────────────────────────────
 MODEL              ACCEL      REPL RUN WAIT KV%  hit% t/s  TTFT  PATH    STATUS
 exaone-3.5-32b     A100×2 DP  0/0   –   –   –    –    –    –     /v1     ○ Scaled-0
 koni-llama3.1-8b   RBLN×4     0/0   –   –   –    –    –    –     /koni   ○ Scaled-0
─ DIAGNOSIS ────────────────────────────────────────────────────────────────────
 ⚠ 모든 모델 0/0 — 추론 백엔드 없음. '2' 뷰에서 모델 선택 후 's'로 scale-up.
```

### [3] EPP Inspector — ★차별 화면
```
─ ACTIVE PLUGINS (from EPP ConfigMap: llmd-router-epp) ──────────────────────────
 SCHEDULING PROFILE: default
 SCORERS                         WEIGHT   FILTERS            PICKER
 queue-scorer                      2      decode-filter      max-score-picker
 kv-cache-utilization-scorer       2      by-label-selector
 prefix-cache-scorer               3
 no-hit-lru-scorer                 2   ← v0.7 신규
─ ROUTING DECISIONS (scheduler_attempts_total, last 5m) ─────────────────────────
 POD                              PICKED   share   status
 vllm-exaone-xxxx-aaaa             1240     58%    ████████████░░░  success
 vllm-exaone-xxxx-bbbb              890      42%    ████████░░░░░░░  success
                                                    (분포 고름 → 라우팅 정상)
─ PER-POD QUEUE (inference_pool_per_pod_queue_size) ─────────────────────────────
 vllm-exaone-aaaa  [██░ 2]   vllm-exaone-bbbb [█ 1]    pool sat 0.13
```

### [1] Accelerators — all-smi식 카드 (생략, §앞 mockup 참조)
### [4] Routing — 트리
```
 llm-d-gateway (192.0.2.12 ●)
 ├─ /v1   → InferencePool: vllm-a100-pool → [exaone ×0]
 ├─ /koni → InferencePool: llmd-router    → [koni ×0]
 ├─ /ds4  → ds4-deepseek-v4-flash (×0)
 └─ /cpu  → ollama-cpu (×0)
```

---

## 5b. 추가 와이어프레임

### Models 드릴다운 (Models 뷰에서 `⏎`)
```
─ exaone-3.5-32b ──────────────────────────────────────────────── [esc] 뒤로 ─
 ENGINE vllm v0.9.2   ACCEL A100×2 (DP)   PATH /v1   POOL vllm-a100-pool
 ┌ throughput ─────────────┐ ┌ latency ──────────────┐ ┌ KV cache ──────────┐
 │ t/s   62  ▁▂▅▇▆▃▇▅▆     │ │ TTFT p95  240ms        │ │ usage 47% ███▌      │
 │ req   run 3  wait 0     │ │ TPOT p95   22ms        │ │ prefix-hit 31%      │
 └─────────────────────────┘ └───────────────────────┘ └────────────────────┘
 PODS: vllm-exaone-aaaa ●Ready 1/1  GPU0 82%   vllm-exaone-bbbb ●Ready 1/1  GPU1 0%
 [l]ogs  [d]escribe  [s]cale  [o]Grafana↗
```

### EPP Inspector (M7) — 상세 (`3` 뷰)
```
─ EPP llmd-router-epp ── profile: default ── api: llm-d.ai/v1alpha1(⚠deprecated cm) ─
 SCORERS                       W   live contribution(정규화)        FILTERS / PICK
 prefix-cache-scorer           3   ████████░░ (최고 가중)            filters: (none)
 queue-scorer                  2   ████░░░░░░                        picker: max-score
 kv-cache-utilization-scorer   2   ███░░░░░░░                        profileHandler:
 no-hit-lru-scorer             2   ██░░░░░░░░  ←v0.7                  single-profile
 ─ data layer ─ metrics-data-source→core-metrics-extractor  saturation: utilization-detector
─ ROUTING DECISIONS  (scheduler_attempts_total · 5m) ──── parsers: openai/anthropic/vllm ─
 POD                       picked  share              status
 vllm-exaone-aaaa           1240   ███████░ 58%       success     ┐ 분포 고름
 vllm-exaone-bbbb            890    █████░░░ 42%       success     ┘ → 라우팅 정상
─ PER-POD QUEUE (inference_pool_per_pod_queue_size) · pool sat 0.13 ───────────────
 aaaa [██ 2]   bbbb [█ 1]                     (쏠림 없음)
 (per-request score breakdown 은 tracing on 필요 → M10)
```

### Launcher 위저드 (M8) — 3단계 (`7` 뷰 / `n`)
```
STEP 1/3  모델 선택                          STEP 2/3  배치 선택 (exaone-3.5-32b)
┌─────────────────────────────────┐        ┌──────────────────────────────────────┐
│ › exaone-3.5-32b      chat       │        │ › A100×1 ×2replica  ✓ready    free:2  │
│   koni-llama3.1-8b    chat       │   ⏎▶   │   RBLN×4            ⚙needs-compile     │
│   deepseek-v4-flash   chat       │        │   (artifact 부재 → 컴파일 런북)         │
│   qwen3-embedding-8b  embedding  │        │   CPU(ollama)      ✓ready    slow      │
└─────────────────────────────────┘        └──────────────────────────────────────┘
STEP 3/3  실행
 ✓ready 선택 시:  매니페스트 미리보기 → [a]pply → watch(Pull→Loading→Ready) → curl 런북
 ⚙needs-compile 선택 시:  apply 안 함. 준비 런북 출력:
   $ bash scripts/04-build-vllm-rbln.sh --model exaone-3.5-32b --tp 4   # ~수분
   (완료 후 다시 Launcher에서 ✓ready 로 표시됨)
```

---

## 6. 아키텍처 & 플러그인 시스템 (★ "쉽게 붙는 형태")

**설계 원칙: EPP를 흉내낸다.** EPP가 `Plugins`(인스턴스) + `SchedulingProfiles`(무엇을 실행)로 구성되듯,
lmd-top은 `collectors`(데이터 수집) + `panels`(렌더) + `profiles`(레이아웃)로 구성한다.
llm-d 사용자에게 익숙한 멘탈 모델.

```
                ┌─────────────── core (event loop, layout engine, input/router) ───────────────┐
                │                                                                                │
  COLLECTORS ───┤  collect() → 표준 dict(metric bus)         PANELS ── render(region, bus) ──────┤── curses
   (data in)    │                                            (view out)                          │
                └────────────────────────────────────────────────────────────────────────────────┘
                          ▲ config: lmd-top.toml  (collectors + panels + profiles)
```

### 6.1 Collector 플러그인 (데이터 소스 추상화) — Rust trait
```rust
#[async_trait]
pub trait Collector: Send + Sync {
    fn name(&self) -> &str;
    fn interval(&self) -> Duration;
    async fn collect(&self) -> Result<Vec<Sample>>; // Sample{ key:"accel.gpu.0.util", val, labels }
}
// 등록: inventory::submit! 또는 빌드시 registry. metric bus = DashMap<String, Sample>.
```
내장 collectors (= 기존 SW 연결점):
| collector | 연결 대상 | 비고 |
|---|---|---|
| `prometheus` | Prometheus `:30090` HTTP API | 범용 PromQL, 메트릭 대부분 |
| `kubectl` | kube-apiserver | pod/deploy/HTTPRoute/InferencePool, **scale 액션** |
| `epp_scrape` | EPP `:9090/metrics` 직접 | port-forward/in-cluster, 트레픽 시 풍부 |
| `epp_config` | EPP ConfigMap | **활성 scorer/filter/picker introspect** (Inspector 뷰) |
| `all_smi` | `all-smi snapshot --json` (노드 배포 시) | RBLN/Furiosa **실리콘** 메트릭 보강 |
| `vendor_cli` | ssh `rbln-stat`/`furiosa-smi` | all-smi 미배포 시 폴백 |
| `tempo` | Tempo(이미 설치됨) | Request Lifecycle 트레이스(로드맵) |

→ 모든 collector는 공통 **metric bus(평면 키스페이스)** 에 쓴다. 패널은 키만 알면 됨(소스 무관).
→ 새 가속기/새 메트릭 = collector 하나 추가. 새 EPP scorer가 나와도 `epp_config`가 자동 인식.

### 6.2 Panel 플러그인 (렌더 추상화) — Rust trait
```rust
pub trait Panel {
    fn title(&self) -> &str;
    fn needs(&self) -> &[&str];                  // 구독할 metric-bus 키 prefix
    fn render(&self, f: &mut Frame, area: Rect, bus: &Bus); // ratatui
}
```
내장 panels: `accel_cards`, `model_table`, `epp_inspector`, `routing_tree`, `pod_list`, `node_bars`, `diagnosis`, `sparkline`, `launcher`.

### 6.3 Config (EPP의 YAML 철학을 미러링)
```toml
# ~/.config/lmd-top/lmd-top.toml
[sources]
prometheus = "http://192.0.2.8:30090"
namespace  = "llm-serving"
epp_service = "llmd-router-epp"

[[collectors]]                 # 인스턴스화 (EPP의 Plugins 절과 동형)
name = "prometheus"
[[collectors]]
name = "epp_config"

[profiles.overview]            # 레이아웃 (EPP의 SchedulingProfiles와 동형)
layout = [["accel_cards"], ["epp_pools","diagnosis"], ["model_table"]]
[profiles.epp]
layout = [["epp_inspector"]]
```
→ 사용자 플러그인: `~/.config/lmd-top/plugins/*.py` 드롭 → TOML에 이름 등록 → 자동 로드(entry-point 레지스트리).

### 6.4 구현 스택 — Rust (확정)
- **TUI**: `ratatui` + `crossterm` (all-smi와 동일 스택). **단일 정적 바이너리**로 배포.
- **데이터**: `reqwest`(Prometheus HTTP API, EPP `:9090` 스크랩) + `serde`/`serde_yaml`(EPP ConfigMap·매니페스트) + k8s 접근은 **`kube-rs`**(권장: 네이티브, watch/scale subresource) 또는 초기엔 `tokio::process`로 `kubectl` 셸링(빠른 시작).
- **런타임**: `tokio` — collector를 독립 태스크로, UI 렌더 루프와 채널(`watch`/`mpsc`)로 분리. 부재 메트릭은 `–`/`offline` 우아하게.
- **metric bus**: `DashMap<String, Sample>` 또는 `arc-swap`된 스냅샷. 패널은 키 prefix만 구독(소스 무관).

### 6.5 Rust에서의 플러그인 전략 (★ "쉽게 붙는 형태" 재설계)
Rust는 `.py` 드롭 같은 런타임 로드가 자연스럽지 않다. 3단 전략:
1. **선언적 collector (config-driven, 코드 0)** — 대부분의 "새 메트릭"은 TOML에 PromQL만 추가하면 끝:
   ```toml
   [[collectors.promql]]   # 컴파일 없이 새 지표 추가
   key   = "accel.gpu.{gpu}.util"
   query = "DCGM_FI_DEV_GPU_UTIL"
   ```
   → `prometheus`/`kubectl`/`epp` collector가 config를 읽어 동적으로 시계열을 버스에 채움. **플러그인의 90%는 여기서 해결.**
2. **컴파일타임 trait 레지스트리** — 진짜 새 로직(panel/비표준 소스)은 trait 구현 + `inventory`로 등록 후 재빌드. 기여자 친화적.
3. **(선택, Phase 4) 동적 플러그인** — `wasmtime`(WASM, 안전·이식적) 또는 임베디드 스크립트(`rhai`)로 런타임 collector. 무겁지만 진짜 plug-in을 원하면 여기로.

→ 일상적 확장(새 가속기/메트릭/대시보드 행)은 **(1) TOML만**으로, 깊은 확장은 (2), 런타임 plug-in은 (3). Python 드롭만큼 가볍진 않지만 "config로 90% 커버 + WASM 탈출구"로 사용자 요구를 충족.

---

## 7. 기존 SW 연결 전략 (Integration)

| 기존 SW | 연결 방식 | lmd-top이 얻는 것 | 중복 안 함 |
|---|---|---|---|
| **Prometheus**(설치됨) | HTTP API 폴링 | 모든 시계열, 스파크라인 | 저장은 Prometheus가, 표시만 |
| **kubectl/kube-api** | subprocess json | 토폴로지·상태·**액션(scale/logs)** | 오케스트레이션은 K8s가 |
| **EPP**(`:9090`,ConfigMap) | 직접 스크랩+introspect | **scorer/결정 가시성** | EPP가 결정, lmd-top은 설명 |
| **all-smi** | `snapshot --json` collector | RBLN/Furiosa 실리콘 메트릭 | 보강(경쟁 아님). all-smi 위에 서빙 레이어를 얹음 |
| **Grafana**(설치됨) | 패널에서 deep-link(`o`키로 브라우저 URL 출력) | 심층 분석은 Grafana로 핸드오프 | 터미널↔웹 상보 |
| **Tempo/OTel**(설치됨) | 트레이스 쿼리 | Request Lifecycle | (로드맵) |

설계 태도: **데이터를 소유하지 않는다. 상관·해석·조작만.** 기존 스택의 얇은 상관 레이어.

---

## 8. 마일스톤 사다리 (난이도 증분 기준)

> **분할 기준(확정)**: 기능 도메인이 아니라 **"독립 실행 가능한 최소 증분"**. 각 M은
> ① 그 자체로 빌드·실행·데모 가능 ② 이전 M 위에만 쌓임 ③ 복잡도 단조 증가.
> 도메인(관측/배포/EPP)은 사다리를 가로지르며 **얇게** 들어온다. "수직 슬라이스" 우선.

| M | 이름 | 새로 추가되는 것 | 증명하는 것 | 난이도 |
|---|---|---|---|---|
| **M0** | **Walking skeleton** | ratatui 렌더 루프 + 2s 틱 + `q`종료. **kubectl** collector 1개로 llm-serving **Deployment 표 1개**(name/ready/replicas/status) | Rust+TUI+데이터+갱신+종료 파이프라인 end-to-end | ★ |
| **M1** | 두 번째 소스 | **prometheus** collector(범용 PromQL) + 화면에 노드 CPU·Furiosa util 1줄(지금 live한 메트릭) | 2개 collector → metric bus → 1패널 합성 | ★ |
| **M2** | k9s 크롬 | 헤더 요약 바 + **탭 전환**(숫자키) + 핫키 footer + `↑↓`선택. 화면 분리: **Pods 뷰 / Accel 뷰** | 멀티뷰 네비게이션·입력 라우팅·레이아웃 엔진 | ★★ |
| **M3** | Accel 카드 + 스파크라인 | all-smi식 디바이스 카드(util/VRAM/temp/power) + braille 스파크라인(ring buffer) | 시계열 히스토리·렌더 품질 | ★★ |
| **M4** | Models 뷰 | vLLM 메트릭(run/wait/KV%/t/s/TTFT) + kubectl deploy 병합 + path 매핑 | 계층 결합(L3+L1) | ★★ |
| **M5** | **첫 액션: scale** | 행 선택 후 `s`로 scale↑↓(꺼진 모델 켜기) + `l`logs `d`describe | 읽기→**조작** 전환(kube write/subresource) | ★★★ |
| **M6** | Overview(홈) + 진단 | 합체 홈 + cross-layer **1줄 진단 라벨** | 상관·해석 로직 | ★★★ |
| **M7** | **EPP Inspector** | `epp_config`(ConfigMap YAML) introspect + 라우팅 결정 분포 + pod별 큐 + Routing tree | ★llm-d 고유 차별 (와이어프레임 §5b) | ★★★ |
| **M8** | **Launcher** | ModelCatalog→PlacementSolver→배포/런북 위저드(§8b, 스키마 §8c) | 카탈로그·솔버·매니페스트 렌더·apply·watch | ★★★★ |
| **M9** | 플러그인 일반화 | **선언적 TOML collector**(재컴파일0) + trait 레지스트리(`inventory`) + `all_smi` collector | 확장성(§6.5) | ★★★★ |
| **M10** | 심화 | Request Lifecycle(Tempo, tracing on) + P/D 분리 뷰 + record/replay + Grafana deep-link + 멀티테넌트 | — | ★★★★★ |

**M0~M2 = 진짜 MVP(걷는 뼈대).** 여기까지면 "뭐가 떠있나"를 TUI로 본다는 최초 목표 달성.
**M5에서 처음으로 "조작"**, **M7이 차별점**, **M8이 사용자 런처 요구**. 각 M 끝마다 지금 클러스터에서 데모.

> 도메인↔마일스톤 매핑: 관측=M0–M6, EPP=M7, 배포(launch)=M8, 플러그인=M9, 고급=M10.

---

## 8b. Phase 2 LAUNCH — 모델 런처 설계 (사용자 아이디어 구체화)

**평가: 아주 적합하다.** llm-d의 본질(모델 → InferencePool → HTTPRoute → 가속기 배치)을 그대로
CLI 위저드로 만든 것. 단, **솔직한 경계**가 있다 → 그 경계가 곧 "가이드라인 출력"의 존재 이유다.

```
 [1] 모델 선택          [2] 배치(Infra) 선택              [3] 실행 / 가이드
 ┌──────────────┐     ┌───────────────────────────┐   ┌────────────────────────┐
 │ MODEL CATALOG│ ──▶ │ PLACEMENT SOLVER           │──▶│ ready  → 매니페스트 생성  │
 │ (큐레이션 YAML)│     │ 모델요건 × 라이브 인프라재고  │   │         +apply +watch    │
 │ exaone, koni │     │ = 가능한 배치 + 준비상태      │   │ not-ready → 준비 런북출력 │
 │ deepseek, …  │     │  ✓ready / ⬇needs-download   │   │  (HF다운/RBLN컴파일 등)  │
 └──────────────┘     │  /⚙needs-compile            │   └────────────────────────┘
                      └───────────────────────────┘
```

### 구성요소
1. **ModelCatalog** (`catalog/models.yaml`, 큐레이션): 모델별
   `{id, hf_repo, engine(vllm|vllm-rbln|ollama|furiosa), size, quant, min_vram_gb,
   accel_options[], tp_degree, artifact_path?, manifest_template, route_path}`.
2. **InfraInventory** (라이브, kubectl): 노드별 allocatable−allocated 로 가용 가속기 산출
   (`nvidia.com/gpu`, `rebellions.ai/...`, `furiosa.ai/npu`, cpu/mem).
3. **PlacementSolver**: 모델요건 × 재고 → 가능한 배치 후보 + **준비상태 라벨**
   - `✓ ready` (예: vLLM on A100 — 즉시 apply 가능)
   - `⬇ needs-download` (HF 가중치 미존재 → 다운로드 런북)
   - `⚙ needs-compile` (RBLN 컴파일 산출물 부재 → `scripts/04-build-vllm-rbln.sh` 런북)
4. **Launcher**: 선택 배치 → 매니페스트 렌더(Deployment+Service, [STATUS.md](./STATUS.md) 표준 label,
   InferencePool selector 패치, HTTPRoute path 추가) → `kubectl apply` → readiness watch → **런북**(curl 예시 + 라우팅 경로).
5. **Guideline 생성**: not-ready 배치는 apply 대신 **준비 단계 런북**을 출력(이게 사용자가 말한 "가이드라인").

### 솔직한 경계 (= 가이드라인이 필요한 이유)
- **vLLM/A100·ollama/CPU**: 사실상 원클릭(가중치 캐시 있으면 즉시).
- **RBLN**: 사전 컴파일 산출물 필요(수 분, 오프라인). 자동화 불가 → 런처가 **컴파일 런북**을 띄움.
- **Furiosa**: 유사(compile/quantize 선행).
- **대형 HF 다운로드**(예: ds4 100GB): 자동 트리거하되 진행률은 Monitor에서 관찰.
→ "알아서 돌리고"는 ready 배치에 한해 완전 자동, 나머지는 **명확한 다음-단계 런북**으로 정직하게 안내.

### 같은-바이너리 루프
런처가 apply하면 → Models 뷰로 복귀 → pod Pull/Init/Loading/Ready 를 실시간 표시 →
Ready 되면 Routing 뷰에 새 path 등장 → curl 런북 제시. **띄우기와 지켜보기가 한 도구에서.**

## 8c. ModelCatalog 스키마 (M8)

큐레이션 YAML(`catalog/models.yaml`). 각 엔트리는 모델 1종 × 배포 가능한 엔진/가속기 옵션을 선언.
PlacementSolver가 이걸 라이브 인프라 재고와 대조해 후보+준비상태를 만든다.

```yaml
# catalog/models.yaml
apiVersion: lmd-top/v1
models:
  - id: exaone-3.5-32b              # /v1, /models 에 노출될 model name
    display: "EXAONE-3.5-32B-Instruct-AWQ"
    hf_repo: LGAI-EXAONE/EXAONE-3.5-32B-Instruct-AWQ
    role: chat                       # chat | embedding | …  (STATUS 표준 label)
    placements:                      # 가능한 배치들 (솔버가 재고와 매칭)
      - engine: vllm                 # vllm | vllm-rbln | ollama | furiosa
        accelerator: gpu-nvidia      # node label llm-d.ai/accelerator 값
        resource: nvidia.com/gpu     # k8s 요청 리소스명
        count: 1                     # 디바이스 수 (TP=1)
        replicas: 2                  # DP=2
        min_vram_gb: 40
        quant: awq
        requires_artifact: false     # HF 가중치만 있으면 ready
        manifest: templates/vllm-gpu.yaml.tmpl
        route_path: /v1
      - engine: vllm-rbln
        accelerator: npu-rebellions
        resource: rebellions.ai/ata  # (실제 리소스명 확인 필요 — Open Q)
        count: 4                     # TP=4
        replicas: 1
        requires_artifact: true      # ★ 사전 컴파일 산출물 필요
        artifact_path: /home/user/rbln-EXAONE-...-tp4   # 없으면 needs-compile
        compile_runbook: scripts/04-build-vllm-rbln.sh
        manifest: templates/vllm-rbln.yaml.tmpl
        route_path: /koni
  - id: qwen3-embedding-8b
    role: embedding
    placements:
      - engine: furiosa
        accelerator: npu-furiosa
        resource: furiosa.ai/npu
        count: 2
        requires_artifact: true
        manifest: templates/furiosa-embed.yaml.tmpl
        route_path: /v1/embeddings
```

**PlacementSolver 판정 규칙**
1. `accelerator` 라벨 가진 노드의 **가용 수량 ≥ count×replicas** ? → 후보
2. `requires_artifact` && `artifact_path` 부재 → `⚙ needs-compile`(compile_runbook 출력)
3. HF 가중치 캐시 부재(대형) → `⬇ needs-download`
4. 위 통과 → `✓ ready` (apply 가능). 점수 = 여유 VRAM·디바이스 적합도로 정렬.

**manifest 템플릿**: `templates/*.tmpl` 에 `{{count}}`/`{{replicas}}`/`{{hf_repo}}`/`{{route_path}}` 등 치환.
렌더 결과 = Deployment+Service(STATUS 표준 label) → apply → InferencePool selector 패치 + HTTPRoute path 추가.

---

## 9. 조사 결과 (resolved) / 남은 Open Questions

**해결됨 (2026-06-30 클러스터 실측):**
1. ✅ **EPP config 파싱**: ConfigMap `llmd-router-epp` 키 `default-plugins.yaml` = 평문 YAML(`EndpointPickerConfig`).
   선언 plugins + schedulingProfiles(가중치)를 그대로 읽으면 됨. *효과적(확장) config*(max-score-picker, parsers,
   utilization-detector 등 시스템 기본값 포함)는 시작 로그 `"EPP config after phase two"` 라인에 존재.
   → `epp_config` collector = ConfigMap YAML 파싱(쉬움) + 선택적 startup-log 파싱.
2. ✅ **결정 가시성**: 현재 `--v=2`, `--tracing=false` → **per-request pod별 score breakdown은 로그에 없음.**
   집계 분포(`inference_extension_scheduler_attempts_total{pod_name,status}`)만 가능. 심층은
   verbosity↑ 또는 tracing on 필요 → **Phase 4 선택 기능**. Inspector v1 = 집계로 확정.
3. ✅ **all-smi RBLN**: Rebellions ATOM 지원(v0.6.3+), rbln SDK 2.0.x 호환(v0.15.2, 2026-01).
   `snapshot --format json` 제공(npu_index/npu_uuid 라벨). → `all_smi` collector로 RBLN/Furiosa 실리콘 보강 확정.

3b. ✅ **EPP 라이브 메트릭 접근 (해결·적용 완료 2026-06-30)**: EPP용 ServiceMonitor가 없어 `inference_*`가
   Prometheus에 부재였음 → **ServiceMonitor 추가**([`manifests/epp-servicemonitor.yaml`](./manifests/epp-servicemonitor.yaml)).
   ⚠ 실측: EPP `:9090`은 **평문 HTTP** (`secure-serving` 미적용 — https로 긁으면 "server gave HTTP response to HTTPS client").
   → ServiceMonitor `scheme: http` + bearer token(metrics-endpoint-auth 대비). RBAC=`inference-gateway-metrics-reader`.
   라이브 값은 **트래픽 발생 시**에만 채워짐. EPP Inspector v1 = config 우선 + 라이브 graceful.
3c. ✅ **RBLN 실리콘 메트릭 (해결·적용 완료)**: `rbln-npu-operator`가 `rbln-metrics-exporter`(이미지 v0.2.4)를 내장,
   `RBLNClusterPolicy/rbln-cluster-policy` `spec.metricsExporter.enabled`로 토글. **활성화 + ServiceMonitor 추가**
   ([`manifests/rbln-metrics-servicemonitor.yaml`](./manifests/rbln-metrics-servicemonitor.yaml)) → Furiosa처럼 RBLN util/온도/전력이 Prometheus로.
   실측 메트릭명: `RBLN_DEVICE_STATUS:{UTILIZATION,TEMPERATURE,CARD_POWER,DRAM_USED,DRAM_TOTAL,HEALTH}`.
   → all-smi/SSH 불필요. 두 NPU 모두 PromQL로 읽음. (이 enablement는 lmd-top `setup`이 대신할 작업 — §11)

**남은 Open Questions:**
4. P/D 분리 시 vLLM KV-transfer(NIXL) 정확한 메트릭 이름 (Phase 4, 미배포라 보류).
5. ModelCatalog 큐레이션 범위 — 현 4~5종만? 아니면 HF 임의 모델까지 수용?
6. 멀티테넌트(tenant-a/b) 뷰 필요 여부 (네임스페이스 필터로 충분한지).
7. **구현 언어** — §10 참조.

---

## 10. 구현 언어 (검토)

| 후보 | 장점 | 단점 | 이 프로젝트 맥락 |
|---|---|---|---|
| **Python3** (stdlib curses) | pip 의존 0, control-plane에 3.14 이미 존재, kubectl/PromQL/YAML 글루에 최적, 빠른 반복 | 단일 바이너리 배포 아님, curses 렌더 한계 | repo 전체가 bash+k8s 글루 스타일과 일치. **Phase 1·2(글루 중심)에 베스트** |
| **Rust** (ratatui) | 단일 정적 바이너리, 고성능 렌더, **all-smi와 동일 스택**, 256노드급 확장 | 빌드 체인 필요, 반복 느림, k8s/PromQL 클라 무거움 | all-smi 생태계 합류·배포 단순화엔 매력. 단 초기 속도 손해 |
| **Go** (bubbletea) | 단일 바이너리, **k8s 클라이언트-go 1급**, k9s와 동일 스택 | TUI 생태계 Rust보다 얇음 | k8s 친화. k9s식 지향엔 합리적 |

**결정: Rust (ratatui) — 처음부터.** (사용자 결정, 2026-06-30)
- 근거: 단일 정적 바이너리 배포, all-smi와 동일 스택(미래 통합 여지), 고성능 렌더, 256노드급 확장.
- 트레이드오프 수용: 초기 반복 속도↓ → §6.5의 **선언적 config(TOML) 우선** 설계로 "재컴파일 없이 메트릭 추가"를 확보해 완화.
- 크레이트: `ratatui` `crossterm` `tokio` `reqwest` `serde`/`serde_yaml` `kube`(or kubectl 셸링) `dashmap` `inventory`.

---

## 11. 셋업 UX — "쉬운 설치"가 1급 요구 (★사용자 강조)

> 제품 원칙: **사용자가 kubectl 매니페스트를 손으로 적용하지 않는다.** lmd-top이 자기에게 필요한
> 데이터 경로를 *진단하고 켜준다.* 방금 수동으로 한 일(EPP ServiceMonitor, RBLN metricsExporter)을
> 도구가 내장 명령으로 대신한다.

- **단일 정적 바이너리** — `cargo build --release` 산출물 1개. 런타임 의존 없음(kubectl/Prometheus 접근만).
- **`lmd-top doctor`** — 데이터 경로 자가진단. 각 항목 ✓/✗ + 한 줄 처방:
  ```
  ✓ kubectl 접근            ✓ Prometheus 도달(:30090)
  ✓ Furiosa exporter         ✗ RBLN metricsExporter (off) → `lmd-top setup` 로 활성화
  ✗ EPP ServiceMonitor       → `lmd-top setup` 로 추가
  ```
- **`lmd-top setup`** (= `doctor --fix`) — 누락된 전제만 **멱등 적용**. 내장 매니페스트(`include_str!`로 바이너리에 임베드, 원본은 [`manifests/epp-servicemonitor.yaml`](./manifests/epp-servicemonitor.yaml)) + RBLNClusterPolicy 패치. 이미 있으면 skip.
- **무설정 기동** — config 없으면 합리적 기본값(Prometheus NodePort 자동탐지, ns=llm-serving)으로 바로 실행. `lmd-top.toml`은 선택.
- **읽기 우선·명시 동의** — `setup`/`scale`/`launch` 등 변경 작업은 확인 프롬프트. 관측은 무권한 읽기.

→ 온보딩 = `다운로드 → lmd-top setup → lmd-top`. 끝.

## 참고 (Sources)
- llm-d EPP / Inference Scheduler: https://llm-d.ai/docs/architecture/Components/inference-scheduler
- GIE EPP 구성 YAML: https://gateway-api-inference-extension.sigs.k8s.io/guides/epp-configuration/config-text/
- GIE 메트릭: https://gateway-api-inference-extension.sigs.k8s.io/guides/metrics-and-observability/
- Datadog: 계층 상관 진단: https://www.datadoghq.com/blog/llm-routing-kubernetes-inference-extension/
- all-smi: https://github.com/inureyes/all-smi · llmtop: https://github.com/arinbjornk/llmtop · k9s: https://github.com/derailed/k9s
