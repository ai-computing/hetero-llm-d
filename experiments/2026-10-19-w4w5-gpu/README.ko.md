# A100 풀 W4 / W5 실측 요약 (한국어)

전체 기록, 명령, 표는 [README.md](README.md)에 있다. 2026-10-19, A100 80GB × 2(replica당 1장), vLLM v0.11.0
Llama-3.1-8B-Instruct(`--enable-prefix-caching`, pod당 KV 캐시 445,680 토큰), 전용 EPP `vllm-a100-epp`, KEDA 2.19.

## W4 prefix 인지 라우팅

- **affinity는 동작한다.** 한 prefix를 순차로 20번 보내면 `approx-prefix`는 20/20을 한 pod로, `queue-kv`는 10/10으로 나눈다.
  prefix 8개 순차 64요청에서 vLLM prefix 적중률은 0.864 대 0.742다.
- **머지된 `approx-prefix`(prefix 가중치 1)는 동시 부하에서 affinity를 잃는다.** KV 캐시 압박 부하(2.9k 토큰 prefix 220개,
  1100요청, 동시성 32)에서 적중률 0.574로 `queue-kv` 0.560과 차이가 없다. 가중치 3이면 0.639, TTFT p50 1.17 → 0.94 s(-20 %),
  p90 -8 %, 전체 시간 56.6 → 47.4 s(-16 %)이고 pod 간 요청 분배는 균형을 유지했다. 그래서 A100 풀용 `profiles/approx-prefix-gpu.yaml`
  (가중치 3)을 추가했다. prefix를 재사용하지 못하는 NPU 엔진에는 계속 `approx-prefix`(가중치 1)를 쓴다.
- 고유 prefix 대조군(재사용 불가)에서는 두 프로파일이 같다(TTFT p50 0.60 s, 적중률 0.01). prefix 라우팅 비용은 보이지 않는다.

## W4 precise prefix (선택)

- EPP는 pod마다 ZMQ 구독을 열고 이벤트를 받았지만 처음엔 인덱스 적중이 0이었다. render sidecar 토큰은 vLLM `/tokenize`와 같았다.
- 원인 1: llm-d-kv-cache는 토픽 `kv@<id>@<model>`의 `<id>`로 블록을 저장하고, 조회는 endpoint의 `IP:port`로 거른다. PR #4가 적은
  `kv@$(POD_IP)@<model>`로는 절대 맞지 않는다. 계약을 `kv@<pod-ip>:<serving-port>@<model>`로 고쳤다(`precise-prefix.yaml`,
  `manifests/epp/README.md`, aicomp#46 계약 문구).
- 원인 2: vLLM 기본 블록 16에서는 동시 부하 시 인덱스 예측이 0이었다(`unresolved_sub_canonical_parent`로 건너뛴 저장이 집계됨).
  `--block-size=64`(EPP `blockSizeTokens`와 같게)로 맞추자 공유 prefix에서 프롬프트 토큰의 85-89 %를 캐시됨으로 예측했고,
  압박 부하 적중률 0.630으로 `approx-prefix-gpu`(0.639)와 같았다. 16 경로는 더 추적하지 않았다.
- 이 규모에서는 precise가 근사 방식보다 낫지 않다. render sidecar와 엔진 재시작 비용이 있으니 캐시 축출이 잦거나 EPP 여러 개가
  같은 인덱스를 봐야 할 때 쓴다.
- `make-epp.sh`가 EPP 롤아웃을 120 s만 기다려 precise 첫 설치(Recreate 130 s 유예 + 1.2 GB 이미지 + 토크나이저)에서 실패했다.
  sidecar가 있으면 600 s를 기다리게 고쳤다(`EPP_ROLLOUT_TIMEOUT`로 변경 가능).

## W5 KEDA 오토스케일과 A100 cold start

- `keda-vllm-a100.yaml`을 그대로 적용했다. 고유 5.8k 토큰 프롬프트 1200개를 동시성 160으로 보내자 대기 158, 부하 시작 21 s 뒤
  HPA가 1 → 2로 늘렸고 새 pod는 110 s 뒤 Ready가 됐다. 1200요청 348.5 s, 오류 0, 새 pod가 464개를 처리했다.
  부하 종료(11:09:46) 뒤 대기는 18 s 만에 0, TTFT 트리거는 2분 rate 창이 빈 11:11:42에 0이 됐고, 그로부터 600 s 뒤인
  11:21:31에 1로 줄었다(부하 종료 후 11분 45초).
- **A100 cold start**(pod 시작 → Ready): 혼자 뜰 때 110-111 s, 두 replica가 같은 노드에서 동시에 뜰 때 120-121 s(8 pod).
  API 프로세스 14 s, 엔진 시작과 가중치 24 s, Dynamo + torch.compile 46 s, KV 프로파일 2 s, CUDA graph 19 s, 나머지 4 s.
  컴파일 캐시가 컨테이너 안에 있어 매번 처음부터 컴파일한다. 노드에 캐시를 마운트하면 줄 것으로 보이나 재지 않았다.
- 확장 정책(120 s마다 1 pod)은 cold start가 2분 안이라는 가정이었고 실제 110 s로 맞지만 여유는 작다. max 2라 정책이 실제로
  제한한 적은 없다. 최대가 노드의 카드 수 2라서 확장 뒤에도 대기는 ~155로 남았고, TTFT p90은 75 s에서 3분 뒤 40 s로 줄었다.

## 클러스터 복구

시작 전 상태를 저장하고 끝에 비교했다. `vllm-a100-llama31-8b`는 replica 0, pod 템플릿이 원본과 같고(KV 이벤트 인자, `POD_IP`,
5557 포트, `--block-size=64` 제거), `vllm-a100-pool` spec도 원본과 같다(EPP 참조 `llmd-router-epp`로 복귀). ScaledObject와 HPA,
`vllm-a100-epp` 관련 객체 전부, 임시 HTTPRoute는 삭제했다. 다른 Deployment, EPP, 라우트는 건드리지 않았다.
