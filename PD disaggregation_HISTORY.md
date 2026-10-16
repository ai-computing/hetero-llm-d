# 01_pd_disag 워크스페이스 작업 총정리

작성일: 2026-09-08 (UTC)  
대상: `furiosa-bench/`, `rngd_llmd/`, 루트 보관 아카이브  
최신 확인 커밋: `rngd_llmd`의 `42f3e78` (2026-08-25)

## 1. 전체 개요

이 워크스페이스에서는 **NPU 기반 LLM 서빙 성능 분석에서 시작하여, Prefill/Decode 분리(PD disaggregation), 실제 KV cache 이송, Furiosa RNGD와 Rebellions ATOM 간 이기종 서빙, llm-d 배포 및 성능 최적화**까지 진행했다.

작업은 크게 두 묶음이다.

| 영역 | 수행한 작업 | 산출물 |
|---|---|---|
| `furiosa-bench` | 공식 Furiosa 서빙 엔진의 버킷·입출력 길이·동시성·전력 측정, 복제 구성과 PD 비교 | 벤치 하니스, 빌드·실행 스크립트, JSONL, 그래프, HTML 대시보드 |
| `rngd_llmd` | 직접 KV를 소유하는 런타임, vLLM 커넥터, 실제 KV 전송, 이기종 HTTP 서빙, llm-d 배포, 커널·서빙 최적화 | Python 패키지, 벤치, 배포 매니페스트, 테스트, 기술 요청서 |

핵심적인 진전은 초기의 **decode 측 재프리필을 사용하는 PD 모사**에서 **prefill이 만든 KV를 전달받아 decode를 이어가는 실제 PD 구현**으로 발전한 것이다. 성능 측면에서는 배치, `lm_head` 위치, KV 전송 방식, 컴파일 설정을 맞추지 않으면 비교 결론 자체가 달라진다는 점을 반복 측정으로 확인했다.

### 정리 기준과 확인 범위

- 현재 파일, 기존 문서, 보존된 결과 데이터, `rngd_llmd`의 16개 커밋을 근거로 작성했다.
- 8월 7일·10일·13일 작업은 당시 문서에 적힌 날짜를 기준으로 한다. Git에 최초로 보존된 스냅샷은 8월 19일이므로 그 이전 전체 작업 순서를 커밋으로 복원할 수는 없다.
- 아래의 **JSONL 결과**는 이번에 파일 내용을 확인한 값이며, **커밋 기록** 또는 **기존 문서 기록**으로 표시한 수치는 과거 수행 기록이다. 이번 정리 중 NPU 실험이나 원격 클러스터 검증을 새로 실행하지 않았다.
- 초기 문서의 계획·완료 상태가 서로 충돌하면 최신 코드와 후속 커밋을 우선하되, 현재 배포가 실행 중이라고 단정하지 않는다.
- 모델 가중치·패키지·컨테이너·원격 호스트가 모두 이 디렉터리에 포함된 것은 아니다. 파일 보관과 완전한 독립 재현 환경은 구분해야 한다.

## 2. 작업 연혁

| 시점 | 주요 작업 | 근거 |
|---|---|---|
| 초기 벤치 단계, 8월 10일 정리 | Llama 버킷·동시성·전력 측정, EXAONE 비교, PD 순차·파이프라인 실험 | `furiosa-bench/README.md`, 결과·로그, `ANALYSIS_20260810.md` |
| 8월 7일 기록 | KVConnector, shm/TCP, 최소 게이트웨이, resident-KV, 모델 차원 일반화, 배포 PoC 5단계 | `docs/llmd-integration-plan.md` |
| 8월 13일 작성, 후속 내용 포함 | KV API 개방 요청, 컴파일러 오답·로더·K8s 디바이스 이슈 정리 | `docs/furiosa-request.md` |
| 8월 19일 | 이기종 PD 동작 상태를 Git에 보존하고 `src/rngd_pd` 패키지로 재구성 | `16bdc3c`, `203de9e` |
| 8월 19일 | RNGD 배치 디코드, 카드 내 `lm_head`, 4가지 카드 조합 스윕 | `37e1794`, `8d3ae3b` |
| 8월 19일 | continuous batching 구현·측정, ATOM prefill 확장, S=512 검증 | `632178e`, `5070ea8`, `0fa1af5` |
| 8월 19일 | solo 대조군 추가, 불공정 비교 철회, 배치 조건을 맞춘 재측정 | `65e2a5f`, `13bc59c`, `384310c` |
| 8월 19일 | 호스트 연산·복사 축소, KV 레이어 그룹 스트리밍 | `3f1bd9d`, `e21fdb8`, `bca7dac` |
| 8월 20일 | decode 카드까지 KV 프리패치, ATOM 카드 내 `lm_head` 배포 설정 | `805478d`, `4e13216` |
| 8월 25일 | 컴파일 shape 탐색 제한으로 큰 그룹 지원·성능 개선, 호스트 사전 컴파일 도입 | `42f3e78` |

## 3. 공식 엔진 벤치마크: furiosa-bench

### 3.1 측정 환경 및 하니스 구축

기존 문서 기준 환경은 RNGD 4장, 카드당 8 PE·47.5 GiB HBM, `furiosa-llm 2026.3.0`이다. 주 모델은 Llama-3.1-8B Instruct BF16이며 EXAONE-4.0-32B-FP8 측정 자료도 보관되어 있다. SOLAR Open 100B는 확장 대상으로 문서에 등장하지만, 이 워크스페이스에서 해당 모델의 완료된 결과 파일은 확인하지 못했다.

구현한 측정 항목:

- 토큰 ID 프롬프트로 입력 길이 고정.
- `ignore_eos`, 생성 길이 설정 및 응답 `usage` 확인으로 출력 shape 검증.
- TTFT, TPOT, ITL, E2E, output/total tok/s, req/s 측정.
- 동시성 스윕과 정상상태 부하 측정.
- 카드 전력, idle 대비 동적 전력, tok/J, 1,000토큰당 에너지 측정.
- PE 점유 및 추정 메모리 대역폭을 이용한 병목 분석.

주요 코드: [bench.py](furiosa-bench/scripts/bench.py), [power_bench.py](furiosa-bench/scripts/power_bench.py), [build_artifact.py](furiosa-bench/scripts/build_artifact.py), [실행 스크립트](furiosa-bench/runs/).

### 3.2 버킷·패딩·동시성 실험

고정 shape를 사용하는 AOT 엔진에서 prefill/decode 버킷 구성에 따른 패딩 비용을 비교했다. `preset`, `coarse`, `fine` 비교, 입력 길이 경계 실험, 동시성 확장, 반복·지속 부하 실험을 수행했다.

원본 JSONL의 동일 조건 예시: 입력 256, 출력 256, 동시성 1, 요청 24개. 세 결과 모두 `shape_exact=true`, 실패 0이다.

| 버킷 | TTFT p50 (ms) | TPOT p50 (ms) | 출력 tok/s |
|---|---:|---:|---:|
| coarse | 88.12 | 16.48 | 59.7 |
| fine | 27.85 | 16.29 | 61.1 |
| preset | 22.08 | 16.34 | 61.1 |

이 조건에서는 버킷에 따라 첫 토큰 지연은 크게 달라지지만 decode 비용은 유사했다. 이를 모든 입력 길이에 일반화하지 않고 버킷 경계별로 추가 측정했다.

근거: [bucket 결과](furiosa-bench/results/bucket/), `results/edge/`, `edge8/`, `edge_long/`, `trace/`, `cscale*.jsonl`, `logs/build_*.log`.

### 3.3 모델·전력 비교 및 시각화

- Llama preset 길이·동시성 스윕 24행, 전력 결과 9행을 보존했다.
- EXAONE 동시성·전력 결과는 `results/cscale_exaone.jsonl` 9행이다. 해당 데이터의 `npu_index`가 `0,1,2,3`으로 기록되어 있으므로 README의 모델 배치 표만으로 단일 카드 수치라고 해석해서는 안 된다.
- throughput/latency 히트맵, bucket mismatch, concurrency scaling, roofline, 모델 비교 및 PD 그래프를 생성했다.
- [dashboard.html](furiosa-bench/dashboard.html)에 대시보드 산출물을 보존했다.

### 3.4 PD 대 복제 구성 실험

공식 엔진의 KV export/import API 부재로 초기 PD는 prefill 서버에서 처리한 프롬프트를 decode 서버에서 다시 계산했다.

| 방식 | 구현 | 측정 목적 |
|---|---|---|
| 복제 Dupli | 두 카드에 전체 모델 복제, DP=2 | 동일 카드 수 기준선 |
| v1 PD | 요청별 phase A → B, 웨이브 측정 | 순차 단계 구성과 대기 현상 확인 |
| v2 PD pipeline | prefill 슬롯 → 제한 큐 → decode 슬롯 | 단계 중첩 및 정상상태 처리량 측정 |
| cached/prewarm 변형 | prefix cache를 이용한 재계산 회피 모사 | 전송 비용이 없는 이상적 경로의 상한 추정 |
| pfbatch·짧은 출력 변형 | prefill batch, 슬롯 및 출력 길이 변경 | 부하 형태·버킷의 영향 분석 |

핵심 결과: Llama-8B BF16, 구성당 RNGD 2장, 출력 128토큰. 아래는 [8월 10일 분석서](furiosa-bench/pd-disagg/ANALYSIS_20260810.md)의 v2b 기록이다.

| 입력 | In-flight N | Dupli tok/s | PD tok/s | TTFT p50 Dupli/PD (ms) | ITL p99 Dupli/PD (ms) |
|---|---:|---:|---:|---:|---:|
| 512 | 8 | 382.8 | 383.5 | 71 / 27 | 40 / 41 |
| 512 | 32 | 1247 | 969 | 98 / 42 | 87 / 99 |
| 2048 | 8 | 281.7 | 219.4 | 273 / 48 | 92 / 181 |
| 2048 | 32 | 717.6 | 326.3 | 146 / 184 | 187 / 226 |

관찰한 내용:

1. 웨이브 시작 시 prefill에 요청이 몰리는 convoy 현상은 단계 파이프라이닝으로 완화했다.
2. 전용 prefill 카드는 일부 조건에서 TTFT를 낮췄지만, decode-heavy 부하에서는 decode 카드 2장을 쓰는 복제 구성이 유리했다.
3. 긴 입력에서는 decode 측 재프리필이 처리량·ITL을 악화시켰다.
4. PE 점유가 높아도 실제 연산 처리량이 높은 것은 아니며, decode의 메모리 병목과 구분해야 했다.

기술 요청서의 407 → 263 → 534 tok/s 비교는 각각 복제, 재프리필 PD, **prefix-cache 에뮬레이션**이다. 534 tok/s를 실제 KV 전송 시스템의 측정치로 인용해서는 안 된다. 263은 복제 대비 약 -35%, 534는 약 +31%이므로 두 상대 성능의 간격은 약 66%p다. 요청서 요약의 '+31%p 개선' 표현과도 구분한다.

주요 코드: [pd_sweep.py](furiosa-bench/pd-disagg/pd_sweep.py), [pd_pipeline.py](furiosa-bench/pd-disagg/pd_pipeline.py), [pd_router.py](furiosa-bench/pd-disagg/pd_router.py), [build_pfbatch.py](furiosa-bench/pd-disagg/build_pfbatch.py).

## 4. 실제 KV 전송 런타임 및 커넥터 구축

### 4.1 직접 KV를 소유하는 런타임

당시 조사한 Furiosa 공식 서빙 엔진에서는 KV 소유권과 export/import 훅이 외부에 노출되지 않았다. 이에 furiosa-torch/DSL 기반 계산 그래프와 가중치 로딩 엔진을 구성하여, KV를 명시적인 입출력 텐서로 관리하는 경로를 만들었다.

- single-stream resident decode.
- 기존 KV를 입력받는 chunked prefill.
- 전체 프롬프트를 한 번에 처리하는 KV-free full prefill.
- 배치별 position·mask·rotation을 가지는 batched decode.
- 그룹별 계산 그래프를 연결하여 전체 32개 레이어 실행.
- 실제 모델 가중치 로딩 및 CPU fp32 기준 정확도 비교.

현재 구현은 [kernels](rngd_llmd/src/rngd_pd/kernels/)와 [engines](rngd_llmd/src/rngd_pd/engines/)에 있다. 초기 실험 변형은 [attic/runtime](rngd_llmd/attic/runtime/)에 보존되어 있다.

### 4.2 vLLM KVConnector 계약 및 전송 계층

- 실제 `KVConnectorBase_V1`을 상속하는 `RngdKVConnector` 구현.
- scheduler/worker 측 필수 메서드 7개 및 KV 등록·완료 관련 훅 구현.
- 레이어별 저장·로드와 완료 대기 연결.
- `InProcTransport`, `ShmTransport`, `TcpTransport`로 전송 방식 분리.
- bf16 wire 형식으로 KV 전달.
- NIXL은 인터페이스 스텁이며 실제 전송 구현은 아니다.

8월 7일 문서 기록에는 실제 두 칩 PD 출력과 monolithic 출력 일치, 별도 OS 프로세스 간 TCP bit-exact 검증, NIXL 미지원 시 명시적 실패 확인이 남아 있다.

현재 코드: [rngd_kv.py](rngd_llmd/src/rngd_pd/connector/rngd_kv.py), [transport.py](rngd_llmd/src/rngd_pd/connector/transport.py), [test_connector_tcp.py](rngd_llmd/tests/test_connector_tcp.py).

### 4.3 초기 게이트웨이·캐시 라우팅

워커 registry·heartbeat, prefix 해시 기반 KV cache 인덱스, KV hit 우선 EPP 선택, PD/replica 모드, HTTP `/v1/completions`, Prometheus 지표를 갖춘 최소 게이트웨이를 구현했다.

초기 실측 기록은 짧은 9토큰 요청에서 PD 6343ms, replica 5698ms이며 두 출력 모두 monolithic과 일치했다. 이는 초기 런타임의 특정 조건이고 이후 최적화된 서빙 수치와 직접 비교할 수 없다.

이 프로토타입은 현재 [attic/gateway](rngd_llmd/attic/gateway/)와 [attic/serving](rngd_llmd/attic/serving/)에 있다. 해당 prefix-aware 로직 전부가 최신 외부 llm-d EPP에 이식되었다고 단정하지 않는다.

## 5. 커널 정확도·성능 및 모델 일반화

### 5.1 Resident-KV

토큰마다 KV 전체를 host → device로 다시 올리던 경로를 device tensor 체이닝으로 바꿨다. 기존 문서상 Llama decode는 **48.2 → 16.3ms/token, 약 2.96배** 개선되었고 argmax 9/9 일치를 유지했다.

검증 자료: [probe_resident_kv.py](rngd_llmd/tests/probe_resident_kv.py), `docs/llmd-integration-plan.md` Phase 3.

### 5.2 모델 차원 일반화

DSL 및 모델 연산을 config 기반으로 생성하고, GQA 구조·QKV bias·tied embedding 차이를 처리했다. 기존 문서 기록:

| 모델 | 정확도 | 지연 |
|---|---|---:|
| Qwen2.5-0.5B | argmax 9/9 | 6.4ms |
| Llama-3.1-8B | argmax 9/9 | 14.6ms |

이는 일반화 실험 경로의 결과다. 현재 배치 서빙 커널에는 Llama 차원 상수가 남아 있으므로 모든 backend가 임의 모델을 지원한다는 의미는 아니다. 70B·MoE·MLA의 완료 검증 근거는 확인하지 못했다.

### 5.3 RNGD 배치 디코드 및 lm_head

8월 19일에는 2레이어 그래프를 16번 연결하여 32레이어 배치 디코드를 구현했다. `37e1794` 기록:

| 커널 조건 | ms/step | 배치로 나눈 ms/token |
|---|---:|---:|
| B=1 resident | 25.7 | 25.7 |
| B=4 | 23.19 | 5.80 |
| B=8 | 23.15 | 2.89 |

여러 스트림이 가중치 읽기를 공유하므로 배치가 커져도 스텝 비용은 거의 같았다. CPU fp32 기준 상대오차는 약 0.013으로 기록되어 있다.

또한 RNGD의 `lm_head`를 카드로 이동하고 vocabulary를 나누어 계산했다. B=4 serving engine 기록은 host `lm_head` 78.86ms/step에서 device `lm_head` 26.91ms/step으로 개선되었다.

**지표 주의:** `ms/step ÷ B`는 배치의 처리량을 토큰당 비용으로 환산한 값이다. 개별 요청이 다음 토큰을 기다리는 TPOT는 스텝 간격이므로 이 환산값과 동일하지 않다.

### 5.4 8월 25일 컴파일 설정 개선

당초 큰 배치 그래프의 실패를 tactic 탐색 한계로 설명했지만, 후속 실험에서 `max_num_unique_shapes` 제한이 핵심임을 확인했다. `RNGD_MAX_SHAPES=8`로 group=8 컴파일과 더 빠른 커널을 확보했다.

`42f3e78` 커밋 기록: B=4, S=256, 전체 32레이어, 각 조건 CPU fp32 검증 PASS.

| 그룹 레이어 수 | shape 제한 | 호출 수 | ms/step | 환산 ms/token | 추정 GB/s |
|---|---|---:|---:|---:|---:|
| 2 | 무제한 | 16 | 26.20 | 6.55 | 532 |
| 2 | 8 | 16 | 22.55 | 5.64 | 619 |
| 8 | 1 | 4 | 60.19 | 15.05 | 232 |
| 8 | 8 | 4 | 17.62 | 4.40 | 792 |
| 32 | 1 | 1 | 53.18 | 13.30 | 262 |

큰 단일 그래프나 더 적은 호출 수 자체가 성능을 보장하지 않았다. shape 제한을 1로 과도하게 줄이면 컴파일은 되더라도 실행은 느려졌다.

게이트웨이 경유 B=4, 각 20표본 기록은 TPOT **27.00 → 20.10ms**, decode **478.2 → 369.8ms**, wall **778.5 → 676.5ms**다. 이 수치는 오래된 `sweep_llmd.jsonl`의 전체 스윕과 다른 후속 측정이다.

관련 변경:

- `decode_graph_spec()`에서 컴파일 설정과 캐시 키 생성 통합.
- shape 제한을 캐시 키에 포함하여 이전 아티팩트 오사용 방지.
- [prebake.py](rngd_llmd/bench/prebake.py)로 호스트에서 사전 컴파일.
- 큰 그룹의 캐시가 없으면 메시지를 남기고 group=2로 축소.
- [tactic_probe.py](rngd_llmd/bench/tactic_probe.py)로 설정별 컴파일·성능 조사.
- torch 2.10에서 저장한 pytree가 torch 2.11 실행 시 argument spec 오류를 내는 문제를 확인하고 prebake 환경 검사 추가.

## 6. 이기종 PD 및 llm-d 서빙

### 6.1 서빙 구조

```text
요청
  -> Envoy / InferencePool / EPP
  -> HTTP router
  -> prefill worker (RNGD 또는 ATOM)
  -> KVConnector + 공유 /dev/shm
  -> decode worker (RNGD 또는 ATOM)
  -> 응답

대조군 solo:
  HTTP router -> 단일 RNGD 카드의 prefill + decode (KV는 카드에 유지)
```

현재 [cluster.py](rngd_llmd/src/rngd_pd/serving/cluster.py)는 prefill, decode, gateway, solo 역할과 backend 선택을 제공한다. [vendors](rngd_llmd/src/rngd_pd/vendors/)에는 ATOM prefill·single/batch decode가 있다.

최신 README와 커밋은 llm-d 파드 배포 및 게이트웨이 경유 스윕 수행을 기록한다. 초기 문서의 'K8s 미실행'은 당시 상태이며, 이후 배포 진행 기록을 반영하지 못한 것이다. 다만 지금의 원격 파드 상태는 이번 정리에서 조회하지 않았다.

### 6.2 4가지 카드 역할 조합 비교

`rngd_alone`, `atom_alone`은 이름과 달리 **prefill/decode가 두 파드·카드로 나뉜 동종 구성**이다. 실제 1카드 대조군은 별도 `solo`다.

아래는 [sweep_llmd.jsonl](rngd_llmd/bench/sweep_llmd.jsonl)의 원본 값이다. S=256 계열, P=224, D=16, B=4 조건이며, 후속 KV·컴파일 최적화 전 스냅샷이다.

| 구성 | Prefill → Decode | TTFT (ms) | 원본 tpot_ms | 출력 tok/s |
|---|---|---:|---:|---:|
| rngd_alone | RNGD → RNGD | 355.2 | 31.4 | 52.29 |
| pd_forward | RNGD → ATOM | 392.6 | 90.6 | 24.56 |
| pd_reverse | ATOM → RNGD | 720.6 | 30.1 | 36.75 |
| atom_alone | ATOM → ATOM | 706.8 | 90.7 | 20.65 |

이 측정에서는 RNGD → RNGD가 가장 높은 처리량을 보였다.

### 6.3 ATOM prefill 확장과 S=512

ATOM prefill의 chunk 폭을 C=16에서 C=128/256으로 늘려 가중치 반복 읽기를 줄였다. `5070ea8` 기록상 P=224에서 prefill은 약 **1077 → 257ms**, B=4 ATOM → RNGD TTFT는 약 **2881 → 721ms**로 개선되었다.

이후 S=512에 맞춰 prefill·decode·ATOM 아티팩트를 확장하고 P=448까지 검증했다. `0fa1af5` 기록상 CPU 상대오차는 약 0.012~0.013이다.

| S=512, P=448, D=16, B=4 | TTFT (ms) | 원본 tpot_ms | 출력 tok/s |
|---|---:|---:|---:|
| RNGD → RNGD | 576.8 | 25.8 | 39.57 |
| RNGD → ATOM | 641.0 | 104.0 | 18.71 |
| ATOM → RNGD | 1419.2 | 25.9 | 22.04 |
| ATOM → ATOM | 1407.2 | 103.7 | 13.82 |

근거: [sweep_llmd_S512.jsonl](rngd_llmd/bench/sweep_llmd_S512.jsonl). 같은 짧은 입력에서는 S=512가 처리량에 불리했고 요청당 KV도 약 33.6 → 67.1MB로 증가하여 기본 S=256을 유지했다.

### 6.4 Continuous batching 구현과 평가

매 스텝 빈 슬롯에 요청을 넣고 완료 요청을 제거하는 스케줄러를 구현했다. 다만 공유 배치 KV 텐서의 재구성과 호스트 왕복 때문에 당시 측정에서는 static보다 느려 기본값을 static으로 유지했다.

`632178e` 기록: P=128, D=4~16, 초당 4개 Poisson 도착.

| 스케줄러 | 출력 tok/s | p50 지연 (ms) | p95 지연 (ms) |
|---|---:|---:|---:|
| static | 51.9 | 1196 | 1899 |
| continuous | 34.2 | 1715 | 2226 |

원인 분석으로 배치 구성 변경 시 KV 왕복 약 112ms, 스텝 자체 약 34ms, iteration scheduling 비용 약 37ms를 기록했다. 슬롯별 KV 입출력을 분리하는 방향을 후속 개선안으로 남겼다.

**자료 한계:** 현재 `load_continuous.jsonl` 40행의 `sched` 값은 모두 `static`이다. 파일명만으로 continuous 실행의 증거로 삼을 수 없으므로 위 비교는 커밋에 남은 측정 기록으로 구분했다.

### 6.5 Solo 대조군과 비교 오류 수정

처음 solo 비교를 할 때 카드 부족으로 배치 decoder 파드가 제거되었고, 이 조건을 놓쳐 잘못된 근거로 카드당 효율을 결론 내렸다. 이를 `13bc59c`에서 명시적으로 철회했다. 이후 solo에도 같은 배치 decoder를 적용하고 closed-loop 동시성을 맞춰 재측정했다.

`384310c`의 공정 조건 재측정 기록:

| 출력 길이 D | In-flight N | solo 1카드 tok/s | PD 2카드 tok/s | solo의 카드당 처리량 우위 |
|---|---:|---:|---:|---:|
| 100~160 | 1 | 11.4 | 11.8 | 1.93배 |
| 100~160 | 4 | 102.8 | 121.0 | 1.70배 |
| 100~160 | 8 | 106.6 | 143.7 | 1.48배 |
| 8~24 | 4 | 66.3 | 66.6 | 1.99배 |
| 8~24 | 8 | 69.8 | 85.9 | 1.62배 |

높은 동시성에서는 PD가 전체 처리량과 일부 지연에서 이점을 보였지만, 이 조건의 카드당 효율은 solo가 더 높았다. N=1에서 고정 B=4는 배치 대기와 빈 lane 계산 때문에 특히 불리했다. 이후 최적화가 추가되었으므로 이 결과를 현재 모든 설정의 결론으로 확대하지 않는다.

## 7. KV·호스트 경로 최적화

| 변경 | 구현 내용 | 과거 측정 기록 |
|---|---|---|
| CPU 변환 순서 변경 | `.float().cpu()`를 `.cpu().float()`로 바꿔 장치의 불필요한 CPU bridge 회피 | KV download 29.4 → 6.2ms |
| prefill lm_head 카드 배치 | hidden host 복사와 host argmax 경로 제거 | P=224 prefill 145.2 → 56.4ms |
| 위치 입력 사전 계산 | rotation·mask·one-hot을 매 토큰 생성하지 않고 테이블 조회 | fp32 연산을 유지해 기존 bf16 결과와 일치 검증 |
| 직렬화·로드 복사 제거 | 불필요한 float32 복사 제거, 연속 버퍼에 레이어 view로 직접 로드 | handoff 39.9~45.7 → 37.5~39.3ms |
| 레이어 그룹 스트리밍 | 다음 그룹 계산과 이전 그룹의 bf16 encoding·shm 쓰기 중첩 | P=224 TTFT 87.7 → 76.4ms |
| decode 카드 프리패치 | prefill 시작 전 수신을 시작하고 device upload까지 수행 | P=224 wall 215.4 → 198.5ms |
| ATOM lm_head 카드 배치 | `_lm` 아티팩트 선택, `ATOM_LM` 기본 활성화 | 아티팩트 약 14.2 → 15.2GB, 카드 수용 확인 기록 |

근거 커밋: `3f1bd9d`, `e21fdb8`, `bca7dac`, `805478d`, `4e13216`.

해석 시 주의할 점:

- 각 행은 서로 다른 단계의 A/B 결과이므로 개선량을 단순 합산하지 않는다.
- 스트리밍 이후 `save_ms`가 0.1ms 수준이어도 쓰기 비용이 사라진 것이 아니라 prefill과 겹쳐진 것이다.
- host-only 프리패치는 후속 device upload 비용 증가로 기대한 개선을 내지 못했고, 카드 staging까지 포함했을 때 wall 지연이 줄었다.
- `PD_PREFETCH`로 같은 빌드에서 on/off 비교가 가능해졌다.
- 중간 실패 요청이 프리패치 버퍼를 계속 붙잡지 않도록 항목 수 제한을 추가했다.

## 8. 패키지 재구성·배포·운영 작업

### 8.1 패키지 구조 정리

8월 19일 `203de9e`에서 중복 flat import·경로 계산을 정리하고 다음 구조로 재편했다.

```text
rngd_llmd/
  src/rngd_pd/
    kernels/       DSL, 계산 그래프
    engines/       가중치, 실행 세션, 컴파일 캐시
    vendors/       Rebellions backend
    connector/     KVConnector 및 전송
    serving/       HTTP worker, router, proxy
    paths.py       프로젝트·캐시 경로
  bench/           실행 벤치, JSONL, 그래프
  deploy/          이미지·Compose·K8s 구성
  docs/            통합 문서, 기술 요청
  tests/           전송 및 하드웨어 검증 도구
  attic/           이전 구현과 실험 보존
```

경로 이동으로 캐시를 찾지 못해 재컴파일하던 문제를 중앙 `paths.py`로 정리했고, 사용하지 않는 구현 42개를 attic으로 이동했다. 해당 커밋에는 패키지 21개 모듈 import와 전체 파일 문법 검증 기록이 있다.

### 8.2 배포 및 운영상 수정

- worker/gateway Dockerfile, Docker Compose, K8s Deployment/Service, 관측성 매니페스트 작성.
- [gen_sweep.py](rngd_llmd/deploy/k8s/gen_sweep.py)로 조합별 매니페스트 생성.
- 파드가 `python -m rngd_pd.serving.cluster`와 `/app/src`를 사용하도록 변경.
- 실제 할당된 RNGD 장치 번호를 발견하는 `--chip -1` 경로 구현.
- 카드 중복 점유를 피하기 위해 Deployment `Recreate` 전략 사용.
- 파드 내 컴파일 실패를 우회하도록 호스트 아티팩트 캐시를 공유·로드.
- 장시간 생성에서 발생한 gateway 504 문제에 대응해 경로 timeout 600초 설정 기록.
- vendor 장치 조회 도구·라이브러리와 이미지 의존성 보완 스크립트 작성.
- S, batch, scheduler, prefetch, 그룹 크기, ATOM lm_head를 배포 설정으로 노출.

최신 생성기 기본값: `PD_S=256`, `RNGD_SCHED=static`, `RNGD_GROUP=8`, `RNGD_MAX_SHAPES=8`, `PD_PREFETCH=1`. 이는 코드의 기본값이며 현재 원격 클러스터의 실행 설정을 확인한 값은 아니다.

## 9. 발견한 문제와 대응

| 문제 | 확인·대응 | 현재 해석 |
|---|---|---|
| 공식 엔진 KV export/import 부재 | 자체 런타임과 커넥터 구현, vendor 기술 요청서 작성 | 당시 조사 환경의 제약이며 최신 vendor 제품 전체에 대한 판정은 아님 |
| 3D activation slice 무음 오답 | RoPE half-slice 대신 회전행렬 matmul 사용 | 요청서 상대오차 0.72 → 약 0.007 기록 |
| 큰 배치 그래프 컴파일 실패 | 초기 2레이어 그룹 연결, 이후 shape 수 제한 | '2레이어 이상 불가'는 최신 상태와 다름 |
| npu3 EDF loader EINVAL | 실험용 RNGD 3장 기준으로 배치 구성 | 후속 해결 확인 없음 |
| K8s p2pmem 장치 누락 | `/dev/rngd` hostPath 및 privileged 우회 | 최소 권한 device plugin/CDI 지원은 후속 과제 |
| 파드 내부 컴파일 실패 | 호스트 prebake, 공유 캐시, 그룹 fallback | 컨테이너 내부 컴파일 해결과는 구분 |
| torch 직렬화 버전 불일치 | prebake 실행 환경 검사 | 컴파일 환경과 서빙 환경 정렬 필요 |
| continuous batching 비용 | static 기본값 유지, 선택 실행 | 슬롯별 KV 구조 개선 필요 |
| 불공정 solo 비교 | 커밋에서 철회 후 같은 배치 조건으로 재측정 | 철회된 측정을 결론 근거로 재사용하지 않음 |
| stale 문서·실행 경로 | 최신 패키지 기준으로 본 문서에 재정리 | 원문과 테스트 runner의 경로 갱신은 미수행 |

기술 요청서는 [furiosa-request.md](rngd_llmd/docs/furiosa-request.md)에 있다. 문서 작성은 확인했지만 실제 vendor 발송·접수·회신 여부는 이 자료만으로 확인할 수 없다.

## 10. 결과 데이터 및 산출물 목록

이번 정리에서 주요 결과 디렉터리의 JSONL을 모두 파싱했다. **45개 파일, 650개 유효 레코드, JSON 문법 오류 0건**이다. 이는 성공한 실험 650회를 뜻하지 않으며 요청별 로그·집계·반복 측정이 함께 포함된다.

| 경로 | JSONL 파일 수 | 유효 레코드 수 | 내용 |
|---|---:|---:|---|
| `furiosa-bench/results/` | 18 | 192 | 버킷·입출력·동시성·전력·모델 비교 |
| `furiosa-bench/pd-disagg/` | 15 | 141 | 재프리필 PD·pipeline·cache·pfbatch |
| `rngd_llmd/bench/` | 12 | 317 | 실제 KV 전송·vendor·이기종·llm-d·부하 |

### rngd_llmd 결과 파일

| 파일 | 행 수 | 용도 |
|---|---:|---|
| `sweep256_full.jsonl` | 10 | S=256 실제 KV streaming PD/dup 비교 |
| `sweep256_v2.jsonl` | 10 | S=256 후속 비교 |
| `sweep512.jsonl` | 4 | S=512 PD/dup 비교 |
| `sweep_wide512.jsonl` | 16 | 넓은 context 실험 |
| `sweep_hetero.jsonl` | 32 | 이기종 구성 실험 |
| `sweep_llmd.jsonl` | 40 | llm-d 게이트웨이 경유 4조합 스윕 |
| `sweep_llmd_S512.jsonl` | 50 | S=512 게이트웨이 스윕 |
| `sweep_vendor.jsonl` | 20 | 공식 엔진 비교 |
| `sweep_vendor_cached.jsonl` | 20 | cache 조건 공식 엔진 비교 |
| `sweep_vendor_full.jsonl` | 35 | 확장 공식 엔진 비교 |
| `load_static.jsonl` | 40 | 요청별 부하 기록 |
| `load_continuous.jsonl` | 40 | 이름과 sched 필드가 불일치하는 부하 기록 |

40행·50행 llm-d 스윕의 `errors` 합계는 각각 0이다. 하니스가 실패한 셀을 건너뛸 수 있으므로 `errors=0`만으로 예정된 모든 조건의 성공을 보장하지 않는다.

### 그래프·분석·아카이브

- [Furiosa 그래프](furiosa-bench/plots/): roofline, bucket 효과, PD pipeline throughput·SLO·overlap, 이상적·현실적 PD 비교.
- [런타임 비교 그래프](rngd_llmd/bench/plots/): PD/DUP, context·load·chat mix, TPOT·utilization.
- [이기종 지표 그래프](rngd_llmd/bench/plots_metrics/): TTFT, TPOT, handoff, tokens, utilization.
- [Furiosa 기존 개요](furiosa-bench/README.md), [초기 PD 분석](furiosa-bench/pd-disagg/ANALYSIS_20260810.md).
- [최신 패키지 개요](rngd_llmd/README.md), [초기 통합 계획](rngd_llmd/docs/llmd-integration-plan.md), [초기 호환성 문서](rngd_llmd/docs/llmd-usage-and-compat.md), [기존 로드맵](rngd_llmd/ROADMAP.md).
- 루트의 `furiosa-bench-code.tar.gz`, `furiosa-bench-artifacts.tar.gz`, `rngd-llmd.tar.gz`는 보관 아카이브다. 현재 작업 트리와 동일 버전인지 또는 완전한 백업인지 이번에 검증하지 않았다.
- `furiosa-bench/artifacts/` 및 `rngd_llmd/artifacts_cache/`에 컴파일·모델 관련 파일이 존재한다. 필요한 가중치·외부 경로까지 모두 충족하는지는 별도 확인이 필요하다.

## 11. 수치를 읽을 때 지켜야 할 기준

1. **실제 KV 전송과 캐시 에뮬레이션을 구분한다.** 초기 prefix-cache 상한을 실전 handoff 성능으로 쓰지 않는다.
2. **1카드 solo와 2카드 동종 PD를 구분한다.** `*_alone`이라는 이름만으로 카드 수를 판정하지 않는다.
3. **TPOT와 배치 환산 비용을 구분한다.** 원본 `tpot_ms=31.4`, B=4에서 7.85ms/token은 31.4/4로 환산한 처리 비용이다.
4. **커널, 엔진, HTTP, 게이트웨이 wall 측정을 구분한다.** 그래프의 0.14ms/token과 서빙 prefill 전체 비용은 다르다.
5. **스윕 시점과 최적화 단계를 맞춘다.** 최신 코드와 이전 JSONL을 동일 버전으로 취급하지 않는다.
6. **스윕의 통계 방식을 확인한다.** `sweep_llmd.py`는 기본 3회 중 가장 짧은 wall 실행을 선택하므로 전체 반복 평균으로 읽으면 안 된다.
7. **대역폭은 추정치다.** 하니스의 weight bytes 기반 계산은 직접 HBM 계측이 아니며, ATOM prefill 계산에는 이전 C=16 가정이 남아 있어 C=256 결과 해석에 주의해야 한다.
8. **전력 집계 정의를 확인한다.** 카드별 평균과 여러 카드의 총 전력을 혼동하여 tok/J를 계산하지 않는다.
9. **테스트 기록과 현재 실행 가능 여부를 구분한다.** 초기 '12/12 PASS' 기록은 남아 있지만 현재 `tests/run_selftests.sh`는 이동 전 파일 경로를 참조한다.

## 12. 현재까지의 성과와 남은 일

### 완료 근거가 있는 작업

- 공식 RNGD 엔진 버킷·길이·동시성·전력 벤치와 시각화.
- 재프리필 기반 PD의 구조적 손실 및 pipeline 효과 분석.
- 자체 런타임을 통한 실제 KV cache 소유·이송과 출력 정합 검증 기록.
- vLLM KVConnector 계약 구현 및 shm/TCP 전송 경로.
- RNGD/ATOM prefill·decode 역할 교환과 llm-d 게이트웨이 측정 기록.
- resident-KV, batched decode, 카드 내 lm_head, prefill 확장.
- solo 대조군 및 비교 오류 철회·재측정.
- 호스트 복사 제거, KV streaming, 카드 staging 프리패치.
- 패키지 재구성, 배포 생성기, 컴파일 캐시·prebake.
- shape 탐색 제한을 이용한 그룹 확대와 후속 성능 개선.

### 미완료 또는 재확인이 필요한 작업

| 항목 | 남은 내용 |
|---|---|
| 문서·테스트 정합 | 초기 ROADMAP·deploy 문서·runner 경로를 최신 구조로 갱신 |
| 최신 버전 통합 스윕 | 8월 25일 최적화까지 반영한 전 조합·solo A/B 결과를 같은 메타데이터로 보존 |
| 측정 메타데이터 | commit, artifact key, torch 버전, group, shape cap, batch, scheduler, prefetch 기록 통합 |
| 부하 결과 정리 | `load_continuous.jsonl`의 sched 불일치 원인 및 정확한 비교 원자료 확인 |
| Continuous batching | 슬롯별 resident KV 구조와 iteration overhead 개선 후 재측정 |
| NIXL·장치 직접 전송 | 스텁을 실제 backend로 구현하거나 현재 shm/TCP 범위를 유지 |
| 배포 권한 | privileged·전체 장치 마운트를 대체할 plugin/CDI 지원 |
| 하드웨어 이슈 | npu3 EDF loader 오류 해결 여부 확인 |
| 확장성 | 4K~8K context, 70B, MoE/MLA, 다양한 모델의 현재 서빙 경로 검증 |
| 운영 검증 | 현재 클러스터 배포·장시간 안정성·재시작·장애 복구·최소 권한 상태 확인 |

이 문서는 기존 자료를 정리한 작업 이력이다. 이번에는 애플리케이션 코드, 원본 결과, 기존 문서를 수정하지 않았고 실서버 재배포·벤치 재실행·vendor 연락도 수행하지 않았다.
