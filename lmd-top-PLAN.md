# lmd-top — 실행 계획 (PLAN)

> **역할 분담**: [`lmd-top-DESIGN.md`](./lmd-top-DESIGN.md) = *왜/무엇*(명제·차별점·4계층·메트릭·뷰·아키텍처).
> 이 문서 = *어떻게 만드나*(마일스톤 상세·폴더 구조·모듈 설계·목업·빌드).
> 언어 **Rust(ratatui)** 확정. 대상 클러스터: [`STATUS.md`](./STATUS.md). 작성 2026-06-30.

---

## 1. 선결조건 & 빌드/실행

```bash
# (1) Rust 툴체인 (control-plane엔 현재 없음 — 사용자 셸에서)
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh

# (2) 빌드/실행
cd lmd-top && cargo run            # 개발
cargo build --release              # 단일 정적 바이너리 → target/release/lmd-top

# (3) 런타임 의존: kubectl(kubeconfig 접근) + Prometheus 도달 (http://192.0.2.8:30090)
```
- 데이터 접근만 필요(클러스터 admin kubeconfig). 가속기 노드 SSH 불필요(Prometheus 경유).
- M0~M8은 `kubectl` 셸링으로 시작(빠름) → M9에서 `kube-rs` 네이티브로 승격 검토.

> **쉬운 셋업 (DESIGN §11)**: 온보딩 = `다운로드 → lmd-top setup → lmd-top`.
> `lmd-top doctor`(데이터 경로 자가진단) + `lmd-top setup`(누락 전제 멱등 적용 — EPP ServiceMonitor,
> RBLN metricsExporter 등을 도구가 대신 켜줌). 매니페스트는 바이너리에 임베드(`manifests/` 원본 추적).
> → **M2 즈음 `doctor` 스텁**, **M7(EPP)/M8 전 `setup` 본체**. 수동 kubectl 단계는 부트스트랩에서 제거가 목표.

---

## 2. 레포 폴더 구조

```
lmd-top/
├── Cargo.toml
├── README.md
├── config/
│   └── lmd-top.toml            # sources(prometheus/ns) + profiles(레이아웃) + 선언적 collector
├── catalog/
│   └── models.yaml             # ModelCatalog (M8, 스키마=DESIGN §8c)
├── templates/                  # 매니페스트 템플릿 (M8)
│   ├── vllm-gpu.yaml.tmpl
│   ├── vllm-rbln.yaml.tmpl
│   ├── furiosa-embed.yaml.tmpl
│   └── ollama-cpu.yaml.tmpl
└── src/
    ├── main.rs                 # 진입점: arg/config 로드, tokio 런타임, 태스크 spawn, 터미널 setup/teardown
    ├── app.rs                  # App 상태머신: 현재 view, 선택 index, focus, filter, 모달, tick
    ├── config.rs               # TOML 모델 + 로드/기본값
    ├── theme.rs                # 색/심볼/상태 컬러(Ready=green, Pending=yellow…)
    ├── bus.rs                  # metric bus: Sample{key,val,labels,ts}, Bus(arc-swap 스냅샷), 키 규칙
    ├── event.rs                # crossterm 이벤트 루프 → InputEvent, KeyMap(뷰별)
    │
    ├── collectors/
    │   ├── mod.rs              # Collector trait, CollectorSet(태스크 spawn/주기), 에러격리
    │   ├── kubectl.rs          # deploy/pod/node/httproute/inferencepool (M0,M2,M4)
    │   ├── prometheus.rs       # 범용 PromQL(reqwest) + 선언적 쿼리표(M1, M9)
    │   ├── epp_config.rs       # EPP ConfigMap YAML introspect (M7)
    │   └── all_smi.rs          # `all-smi snapshot --json` 파싱 (M9, 선택)
    │
    ├── panels/
    │   ├── mod.rs              # Panel trait, Region 레이아웃 헬퍼
    │   ├── pods.rs             # Pods/Deploy 표 (M0)
    │   ├── accel.rs            # 가속기 카드+바+스파크라인 (M2,M3)
    │   ├── models.rs           # Models 표 + 드릴다운 (M4)
    │   ├── overview.rs         # 합체 홈 + 진단 (M6)
    │   ├── epp.rs              # EPP Inspector (M7)
    │   ├── routing.rs          # 라우팅 트리 (M7)
    │   └── launcher.rs         # 런처 위저드 (M8)
    │
    ├── widgets/
    │   ├── sparkline.rs        # braille 스파크라인 (ring buffer 소비)
    │   ├── gauge.rs            # util/mem 바
    │   └── statusbar.rs        # 헤더 요약 바 + 핫키 footer
    │
    ├── actions/
    │   ├── mod.rs              # Action enum + dispatch + 결과 토스트
    │   ├── scale.rs            # deploy scale↑↓ (M5)
    │   ├── exec.rs             # logs/describe (kubectl 셸 핸드오프) (M5)
    │   └── launch.rs           # 매니페스트 렌더+apply+watch (M8)
    │
    └── domain/
        ├── mod.rs
        ├── catalog.rs          # ModelCatalog 파싱 (M8)
        ├── inventory.rs        # InfraInventory: 노드 allocatable−사용 (M8)
        ├── solver.rs           # PlacementSolver: 후보+ReadyState (M8)
        ├── diagnose.rs         # cross-layer 진단 규칙 (M6)
        └── types.rs            # Model, Placement, ReadyState, Pool, Endpoint 등 공용 타입
```

> 워크스페이스 아님(단일 바이너리 크레이트)로 시작 — 단순. 규모 커지면 `core`/`tui` 크레이트로 분리.

---

## 3. 모듈 설계 (책임 · 핵심 타입 · 데이터 흐름)

### 3.1 데이터 흐름 (런타임)
```
            ┌─────────────────────── tokio runtime ───────────────────────┐
 kubectl ──▶│ CollectorSet: 각 Collector::collect() 를 주기 태스크로        │
 Prom   ──▶│   → Vec<Sample> 을 Bus 에 commit (arc-swap 으로 원자 스왑)     │──┐
 EPP cm ──▶│                                                               │  │ Arc<Snapshot>
            └───────────────────────────────────────────────────────────────┘  │
 crossterm ─▶ event.rs ─▶ InputEvent ─▶ App(상태변이) / Action(scale/launch)    │
                                              │                                  ▼
                              render loop(≈8fps tick): 활성 Panel.render(Frame, area, &Snapshot, &App)
                                              │
                                          ratatui ─▶ 터미널
```
- **단방향**: collector는 Bus에 *쓰기*만, panel은 Bus를 *읽기*만. App 상태(뷰/선택/필터)와 데이터(Bus)는 분리.
- **에러 격리**: 한 collector 실패해도 다른 데이터 유지. 부재 키 → panel이 `–`/`offline` 렌더.

### 3.2 핵심 타입 (`domain/types.rs`, `bus.rs`)
```rust
struct Sample { key: String, val: f64, labels: BTreeMap<String,String>, ts: Instant }
struct Bus    { snap: arc_swap::ArcSwap<HashMap<String, Vec<Sample>>> }  // key→시계열 최신값들
                                                                          // + 패널별 ring buffer(스파크라인)
enum View { Overview, Accel, Models, Epp, Routing, Pods, Launcher }
enum ReadyState { Ready, NeedsDownload, NeedsCompile, Unavailable }
struct Placement { engine: Engine, accel: Accel, resource: String, count: u32,
                   replicas: u32, ready: ReadyState, score: f64 }
```

### 3.3 trait 계약 (확장점)
```rust
#[async_trait] trait Collector { fn name(&self)->&str; fn interval(&self)->Duration;
                                 async fn collect(&self)->Result<Vec<Sample>>; }
trait Panel { fn view(&self)->View; fn render(&self,f:&mut Frame,a:Rect,bus:&Snapshot,app:&App);
              fn on_key(&self,k:KeyEvent,app:&mut App)->Option<Action> { None } }
```
→ 새 데이터=Collector 추가(또는 M9의 선언적 TOML), 새 화면=Panel 추가. core 불변.

### 3.4 메트릭 키 규칙 (Bus 네임스페이스)
```
accel.gpu.<idx>.{util,mem_used,mem_total,temp,power}     ← DCGM_FI_DEV_*
accel.rngd.<dev>.{util,mem_used,mem_total,temp,power}    ← furiosa_npu_*
node.<name>.{cpu,mem_used,mem_total,load1}               ← node_*
model.<name>.{running,waiting,kv_pct,prefix_hit,tps,ttft_p95}  ← vllm:*
epp.pool.<pool>.{ready,queue_avg,sat}  epp.pool.<pool>.pod.<pod>.queue
epp.decide.<pod>.{count,status}        ← scheduler_attempts_total
k8s.deploy.<name>.{ready,desired}      k8s.pod.<name>.phase
```
패널은 prefix 구독(예: `accel.*`). 소스가 prometheus든 all-smi든 무관.

---

## 4. 마일스톤 상세 (M0–M10)

> 각 M = **독립 실행·데모 가능한 최소 증분**. 완료기준(✅)을 지금 클러스터에서 시연.

### M0 — Walking skeleton ★
- **목표**: Rust+ratatui 파이프라인 end-to-end 증명.
- **세부**: 터미널 raw mode setup/teardown(패닉 복구 포함) · 2s 틱 · `q`종료 · `kubectl get deploy -n llm-serving -o json` 1회/틱 파싱 → **Deployment 표**(NAME/READY/DESIRED/STATUS).
- **✅완료기준**: `cargo run` → llm-serving deploy 6개가 표로, 2초마다 갱신, `q`로 깨끗이 종료.
- **산출물**: `main.rs app.rs event.rs bus.rs collectors/{mod,kubectl}.rs panels/{mod,pods}.rs theme.rs`.
- **크레이트**: ratatui crossterm tokio serde serde_json anyhow.

### M1 — 두 번째 소스 ★
- **목표**: 멀티 collector → 단일 패널 합성.
- **세부**: `prometheus.rs`(reqwest로 `/api/v1/query`) · 노드 CPU% + Furiosa util(지금 live) 한 줄 추가 · Bus 키 규칙 적용.
- **✅**: Pods 표 위에 `nodes: cpu avg / rngd util` 라인이 실데이터로 표시.
- **크레이트**: +reqwest.

### M2 — k9s 크롬 + 멀티뷰 ★★
- **목표**: 네비게이션 골격.
- **세부**: `statusbar.rs`(헤더 집계 + 핫키 footer) · 숫자키 뷰 전환 · `↑↓` 선택 · `/`필터(문자열) · 뷰 2개(**Pods / Accel**).
- **✅**: `5`Pods↔`1`Accel 전환, ↑↓로 행 하이라이트, `/koni`로 필터.

### M3 — Accel 카드 + 스파크라인 ★★
- **목표**: all-smi식 비주얼.
- **세부**: `accel.rs` 디바이스 카드(util/VRAM/temp/power 게이지) · `widgets/sparkline.rs`(per-key ring buffer, braille) · NVIDIA(DCGM)/Furiosa/RBLN 행(RBLN 실리콘은 `n/a`, 모델경유 표기).
- **✅**: Furiosa 4코어 카드 + util 스파크라인 흐름. (A100은 device-plugin 0 → `offline` 표기 정상 동작 확인)

### M4 — Models 뷰 ★★
- **목표**: 서빙 레이어(L3) + 라우팅(L1) 결합.
- **세부**: `models.rs` 표(run/wait/KV%/prefix-hit/t/s/TTFT) ← `vllm:*` + kubectl deploy ready 병합 · HTTPRoute path 매핑 · `⏎` 드릴다운(DESIGN §5b).
- **✅**: 모델 켜면(아래 M5) 표에 실데이터; 꺼져 있으면 `Scaled-0` + path 표시.

### M5 — 첫 액션: scale ★★★ (읽기→조작 전환점)
- **목표**: 운영 액션.
- **세부**: `actions/scale.rs`(`kubectl scale deploy --replicas`) · `s`키 모달(±replica) · `actions/exec.rs` `l`logs/`d`describe(curses suspend→kubectl 핸드오프→복귀) · 액션 결과 토스트.
- **✅**: Models에서 `vllm-rbln-koni` 선택→`s`→1로 scale→pod 기동을 같은 화면에서 관찰(M4 표가 채워짐).
- **주의**: 파괴적 작업 확인 프롬프트. RBLN 로드 ~3분/100GB 다운로드 경고(STATUS 비상메모 참조).

### M6 — Overview(홈) + 진단 ★★★
- **목표**: cross-layer 상관.
- **세부**: `overview.rs` 합체(가속기 요약+EPP풀+모델리스트) · `domain/diagnose.rs` 규칙엔진(Datadog 로직: TTFT↑&큐쏠림&HW정상→"라우팅", TTFT↑&풀포화&VRAM↑→"용량") → 1줄 라벨.
- **✅**: 홈 화면 하단에 자동 진단 문장(예: "⚠ 모든 모델 0/0 — 백엔드 없음").

### M7 — EPP Inspector ★★★ (★차별점)
- **목표**: llm-d 고유 가시성.
- **세부**: `epp_config.rs`(ConfigMap `llmd-router-epp`/`default-plugins.yaml` 파싱→활성 scorer+가중치) · `epp.rs`(scorer 가중치 바 + `scheduler_attempts_total` 라우팅 분포 + `per_pod_queue_size` + `pool_saturation`) · `routing.rs` 트리(Gateway→path→pool→endpoints). 와이어프레임 DESIGN §5b.
- **✅**: scorer 4종(prefix3/queue2/kv2/no-hit2)·picker·parser 표시; 트래픽 있으면 결정 분포 막대.

### M8 — Launcher ★★★★ (★사용자 런처 요구)
- **목표**: 모델 선택→배치→배포/런북 위저드.
- **세부**: `catalog.rs`(catalog/models.yaml) · `inventory.rs`(노드 allocatable: `nvidia.com/gpu`/`rebellions.ai/ATOM`/`furiosa.ai/rngd` − 사용량) · `solver.rs`(후보+ReadyState) · `launcher.rs`(3단 위저드, DESIGN §5b) · `actions/launch.rs`(템플릿 렌더→apply→InferencePool/HTTPRoute 패치→watch) · not-ready→준비 런북 출력.
- **✅**: `n`→exaone 선택→배치 후보(A100×2 ✓ready / RBLN×4 ⚙needs-compile / CPU ✓ready)→ready 선택시 apply&watch, compile 선택시 런북.
- **크레이트**: +tera 또는 minijinja(템플릿) +serde_yaml.

### M9 — 플러그인 일반화 ★★★★
- **목표**: 확장성.
- **세부**: 선언적 TOML collector(재컴파일0, DESIGN §6.5) · `inventory` crate로 trait 레지스트리 · `all_smi.rs`(RBLN/Furiosa 실리콘 보강) · profiles(레이아웃) config화.
- **✅**: TOML에 PromQL 1줄 추가→재빌드 없이 새 지표가 패널에. all-smi 배포 노드에서 RBLN util 표시.

### M10 — 심화 ★★★★★
- Request Lifecycle(Tempo, EPP `--tracing=true` + `--v=4` 시 per-request score) · P/D 분리 뷰(NIXL KV전송) · record/replay(all-smi 차용) · Grafana deep-link(`o`키) · 멀티테넌트(tenant-a/b 네임스페이스 뷰).

---

## 5. TUI 목업 (빌드 진행 순서대로)

### M0 — 가장 단순한 화면 (표 하나)
```
 lmd-top — llm-serving deployments                            (q quit · 2s)
 NAME                    READY   DESIRED   STATUS
 llmd-router-epp         1/1     1         ●Running
 vllm-exaone             0/0     0         ○Scaled-0
 vllm-rbln-koni          0/0     0         ○Scaled-0
 ds4-deepseek-v4-flash   0/0     0         ○Scaled-0
 ollama-cpu              0/0     0         ○Scaled-0
 vllm-v4flash            0/0     0         ○Scaled-0
```

### M1 — 두 번째 소스 합성 (노드/가속기 한 줄)
```
 lmd-top — llm-serving                                        (q quit · 2s)
 nodes: cpu avg 12%   rngd util 0%   (prometheus ●)
 ─────────────────────────────────────────────────────────────────────────
 NAME                    READY   DESIRED   STATUS
 …(M0과 동일)…
```

### M2 — k9s 크롬 + 탭 (Pods / Accel)
```
┌ lmd-top · llm-d @k8s1.31 · 6 nodes ─────────── gw 192.0.2.12 ●Programmed ┐
│ A100 0/2(offline)  RBLN 4idle  RNGD 0/4  │ models 0/4 serving               │
├ 1:Accel  [5:Pods] ──────────────────────────────────────────── /filter ?help┤
│ NAME                    READY  DESIRED  NODE   STATUS                         │
│›vllm-rbln-koni          0/0    0        –      ○Scaled-0                      │
│ llmd-router-epp         1/1    1        cpu-1  ●Running                       │
│ …                                                                            │
├──────────────────────────────────────────────────────────────────────────────┤
│ ↑↓ select   s scale   l logs   d describe   / filter   2s↻   q quit           │
└──────────────────────────────────────────────────────────────────────────────┘
```

### Target — Overview(홈, M6) 완성형
```
┌ lmd-top · llm-d @k8s1.31 · 6 nodes ─────────── gw 192.0.2.12 ●Programmed ┐
│ A100 0/2  RBLN 4idle  RNGD 0/4  │ pool koni:0 sat0.00 │ models 0/4  ⚡—W      │
├ [0:Overview] 1:Accel 2:Models 3:EPP 4:Route 5:Pods ──────────── /filter ?help┤
│ ─ ACCELERATORS ─────────────────────────────────────────────────────────────│
│  A100#0 offline   A100#1 offline   RNGD×4 [░0%] idle   (RBLN×4 via vLLM)      │
│ ─ INFERENCE (EPP pools) ─────────────────────────────────────────────────────│
│  POOL          READY QUEUEavg KV%  SAT   SCORERS(active)                      │
│  llmd-router    0    –        –    0.00  prefix·queue·kv·no-hit-lru           │
│ ─ MODELS ────────────────────────────────────────────────────────────────────│
│  MODEL            ACCEL      REPL RUN WAIT KV% t/s TTFT PATH   STATUS          │
│ ›exaone-3.5-32b   A100×2 DP  0/0   –   –   –   –   –   /v1    ○Scaled-0        │
│  koni-llama3.1-8b RBLN×4     0/0   –   –   –   –   –   /koni  ○Scaled-0        │
│ ─ DIAGNOSIS ──────────────────────────────────────────────────────────────── │
│  ⚠ 모든 모델 0/0 — 추론 백엔드 없음.  'n' 런처 또는 '2'→'s'로 기동.            │
├──────────────────────────────────────────────────────────────────────────────┤
│ ↑↓ sel ⏎ drill  s scale  n launch  l logs  o Grafana↗  / filter  2s↻  q quit  │
└──────────────────────────────────────────────────────────────────────────────┘
```

> EPP Inspector / Models 드릴다운 / Launcher 위저드 목업은 [`lmd-top-DESIGN.md`](./lmd-top-DESIGN.md) §5·§5b 참조.

---

## 6. 부록 — 클러스터 실측 (2026-06-30, 솔버/인벤토리 근거)

| 가속기 | k8s 리소스명 | npu-node-1 allocatable | 노드 라벨 |
|---|---|---|---|
| NVIDIA A100 | `nvidia.com/gpu` | **0** (device-plugin 0/0 — 현재 미광고) | `accelerator.nvidia=present` |
| Rebellions ATOM(RBLN-CA22) | `rebellions.ai/ATOM` | **4** | `accelerator.rebellions=present` |
| Furiosa RNGD | `furiosa.ai/rngd` | **4** | `accelerator.furiosa=present`, `furiosa.ai/npu.family=rngd` |

> ⚠ A100가 현재 `nvidia.com/gpu:0` → 솔버는 "GPU 배치 불가(device-plugin 점검 필요)"로 정직히 표기.
> EPP ConfigMap: `llmd-router-epp` / key `default-plugins.yaml` (평문 YAML). Prometheus: `:30090`.
