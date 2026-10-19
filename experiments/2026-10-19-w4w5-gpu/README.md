# W4 / W5 live on the A100 pool: prefix-aware routing and KEDA autoscaling

- **Date**: 2026-10-19
- **Task**: roadmap W4 (cache-aware routing) and W5 (autoscaling), live check of what PR #4 merged
- **Host / device**: A100 80GB × 2 on the A100 node (one per replica; Deployment `vllm-a100-llama31-8b`,
  vLLM v0.11.0, Llama-3.1-8B-Instruct, `--enable-prefix-caching`, max-model-len 8192, 445,680-token KV
  cache per pod, chunked prefill 2048). EPP `vllm-a100-epp` from `manifests/epp/make-epp.sh`, image
  `llm-d-router-endpoint-picker-dev:main` (digest `sha256:30ff81cd…`, logs `llm-d.ai/v1alpha1` as
  deprecated but loads it). Gateway: llm-d-gateway (Envoy) through a temporary HTTPRoute
  `/gpu/llama8b` → `/v1` → InferencePool `vllm-a100-pool`. KEDA 2.19.
- **Commit**: hetero-llm-d `dce87ca` (PR #4 merged) + this record

## Question

1. Does prefix affinity in the EPP (`approx-prefix`, then `precise-prefix`) raise vLLM's prefix-cache
   hits and lower TTFT against load-only routing (`queue-kv`) on two A100 replicas?
2. Does `keda-vllm-a100.yaml` scale 1 → 2 under queue pressure and back after the window, and how
   long does an A100 vLLM replica take from pod start to Ready (the gap PR #4 left open)?

## Setup

The Deployment was at 0 replicas and the pool pointed at `llmd-router-epp` (which serves another pool).
For the run: replicas 2 (W4) or 1 + ScaledObject (W5), a dedicated `vllm-a100-epp`, the pool's
`endpointPickerRef` switched to it, and the HTTPRoute above. Everything was restored afterwards (see
the end of this file).

Load: [`prefix_load.py`](prefix_load.py), streaming chat completions through the gateway, TTFT = first
content chunk at the client; per-pod `vllm:prefix_cache_{hits,queries}_total` and
`vllm:request_success_total` deltas scraped from the pods. Hit ratio = hits / queries (tokens). Every
run uses a fresh `SALT`, so its prefixes are new to both the engines and the EPP. Answers are
temperature 0, 32 tokens max.
(`hetero_load.py` from the mixed-pool experiment was not reused: it measures end-to-end latency only,
non-streaming, and reads that pool's vendor labels.)

| workload | prompts | conc | what it tests |
|---|---|---:|---|
| `probe1` | 20 requests, one 1.4k-token system prompt, sequential | 1 | affinity alone: do all requests go to one pod? |
| `probe8-c1` | 64 requests over 8 prefixes of 1.4k tokens, sequential | 1 | affinity with several prefixes |
| `shared8` | 256 requests over 8 prefixes of 1.4k tokens | 16 | the shared-system-prompt case, light load |
| `unique` | 128 requests, every prefix unique (control) | 16 | no reuse possible |
| `pressure220` | 1100 requests over 220 prefixes of 2.9k tokens (640k tokens of prefixes) | 32 | more prefixes than one pod's 446k-token cache holds, fewer than two pods hold |

Profiles: `queue-kv` (queue 2, KV 2), `approx-prefix` (+ prefix 1, as merged), `approx-prefix-w3`
(the same with prefix 3, now committed as `profiles/approx-prefix-gpu.yaml`), `precise-prefix` with
three engine settings (below). Each profile switch re-ran `make-epp.sh` and restarted the EPP, so the
EPP's prefix state starts empty.

## Command

```bash
# on the control-plane node, in a clone of this repo
kubectl -n llm-serving scale deploy vllm-a100-llama31-8b --replicas=2
EPP_PROFILE=queue-kv manifests/epp/make-epp.sh vllm-a100-pool /gpu      # then approx-prefix, approx-prefix-gpu, precise-prefix
kubectl apply -f <HTTPRoute /gpu/llama8b -> InferencePool vllm-a100-pool>
GW=http://<gateway>/gpu/llama8b MODE=shared N=256 CONC=16 SALT=<run> python3 prefix_load.py out.json
GW=... MODE=shared PREFIXES=220 PREFIX_WORDS=2300 N=1100 CONC=32 SALT=<run> python3 prefix_load.py out.json
python3 summarize.py results/

# W5
kubectl -n llm-serving scale deploy vllm-a100-llama31-8b --replicas=1
kubectl apply -f manifests/autoscaling/keda-vllm-a100.yaml
GW=... MODE=unique PREFIX_WORDS=4600 N=1200 CONC=160 MAXTOK=256 SALT=keda python3 prefix_load.py keda-load.json
```

The full sequences are [`run-w4.sh`](run-w4.sh) and [`run-w5-keda.sh`](run-w5-keda.sh).

## Results — W4 prefix-aware routing

Unique-prefix control (128 requests, conc 16): hit ratio 0.011-0.016, TTFT p50 0.60 s, p90 0.80-0.91 s
for both `queue-kv` and `approx-prefix`. Prefix routing costs nothing measurable when there is no reuse.

Mean of two runs each (single runs in [`results.md`](results.md)):

| workload | profile | vLLM hit ratio | TTFT p50 (s) | TTFT p90 (s) | wall (s) |
|---|---|---:|---:|---:|---:|
| probe1 (1 prefix, seq.) | queue-kv | 0.891 (split 10/10) | 0.042 | 0.136 | 1.6 |
| | approx-prefix | 0.934 (20/0) | 0.042 | 0.046 | 1.5 |
| probe8-c1 (8 prefixes, seq.) | queue-kv | 0.742 | 0.042 | 0.130 | 5.7 |
| | approx-prefix (w1 and w3 alike) | **0.864** | 0.042 | 0.127 | 5.0 |
| shared8 (conc 16) | queue-kv | 0.925 | 0.225 | 0.319 | 4.4 |
| | approx-prefix | 0.935 | 0.169 | 0.281 | 3.75 |
| | approx-prefix-w3 | 0.945 | **0.127** | **0.255** | **3.1** |
| pressure220 (conc 32) | queue-kv | 0.560 | 1.172 | 2.522 | 56.6 |
| | approx-prefix | 0.574 | 1.145 | 2.483 | 54.7 |
| | approx-prefix-w3 | **0.639** | **0.941** | **2.330** | **47.4** |
| | precise-prefix, engine block 64 | 0.630 | 1.030 | 2.276 | 49.1 |

- **Affinity works.** One shared prefix, sequential: `approx-prefix` sends 20/20 to one pod, `queue-kv`
  splits 10/10. With 8 prefixes each prefix misses once instead of once per pod: hit ratio 0.864
  against 0.742 (the ceiling with 8 first-visit misses is about 0.86).
- **With prefix weight 1 the load scores outvote affinity under concurrency.** Under cache pressure
  the merged `approx-prefix` (queue 2, KV 2, prefix 1) is within noise of `queue-kv` (0.574 vs 0.560;
  rep a 0.557 was below `queue-kv`). Prefix weight 3 keeps the affinity: hit ratio +0.08,
  TTFT p50 -20 %, p90 -8 %, wall time -16 % for the same 1100 requests. At light load (`shared8`)
  weight 3 also gives the lowest TTFT (p50 0.127 s vs 0.225 s). Hence the new
  `approx-prefix-gpu.yaml` (weight 3) for the A100 pool; `approx-prefix` (weight 1) stays for engines
  without prefix reuse, where affinity would only concentrate load.
- Request split stayed balanced with weight 3 (pressure: 579/521 and 539/561), so the gain is not
  bought with a hot pod at this load.

## Results — W4 precise prefix (optional part)

vLLM got `--kv-events-config` (ZMQ PUB on 5557), env `POD_IP`, containerPort 5557; the EPP got the
`precise-prefix` profile and the CPU render sidecar (`vllm/vllm-openai-cpu:v0.21.0`, pulled in 48 s,
1.2 GB). The EPP connected one ZMQ subscriber per pod (`Connected subscriber socket`,
`llm_d_epp_kv_cache_events_active_subscribers 2`) and received events. Render token IDs were checked
against vLLM's `/tokenize` for a chat request: identical (48 tokens).

| engine setting | index lookups → hits (block hits) | predicted cached / prompt tokens | vLLM hit ratio, pressure220 |
|---|---|---|---:|
| topic `kv@$(POD_IP)@<model>` (as PR #4 documented), block 16 | probe1: 20 → 0 | 0 % | 0.554 (= queue-kv) |
| topic `kv@$(POD_IP):8000@<model>`, block 16 | probe8-c1: 64 → 168; shared8: 512 → 0; pressure: 2200 → 0 | 12 % seq., 0 % concurrent | 0.557 |
| topic with port, `--block-size=64` | probe8-c1: 64 → 1224; shared8: 512 → 10292; pressure: 2200 → 75045 | 85 % / 89 % / 62 % | **0.630** |

- **Topic bug in PR #4's contract.** llm-d-kv-cache's vLLM adapter takes the pod identifier from the
  topic (`kv@<id>@<model>`), and the precise producer looks blocks up for endpoints named
  `<address>:<port>`. A topic without the port stores everything under `10.x.y.z` and no lookup can
  match. Fixed in `profiles/precise-prefix.yaml` and `manifests/epp/README.md` (the aicomp#46 contract
  text): `kv@<pod-ip>:<serving-port>@<model>`.
- **Block size.** With vLLM's default 16-token blocks the index still matched nothing under concurrent
  load, and counted stores skipped as `unresolved_sub_canonical_parent`; with `--block-size=64`
  (equal to the EPP's `blockSizeTokens`) it predicted 85-89 % of prompt tokens for shared prefixes and
  routed like `approx-prefix-w3` (pressure hit ratio 0.630 vs 0.639, wall 49.1 s vs 47.4 s). We did
  not trace the 16-token path in the EPP further; the contract now asks for 64-token blocks.
- precise-prefix gives no gain over `approx-prefix-gpu` here: one engine type, no evictions the EPP's
  estimate could get wrong at this scale, and it costs a render sidecar plus an engine restart.
  It earns its place where engine caches evict a lot or several EPP replicas need one shared view.
- `make-epp.sh` waited 120 s for the EPP rollout; the first precise-prefix rollout (130 s Recreate
  grace period + image pull + tokenizer download) took longer and the script exited. It now waits
  600 s when the render sidecar is added (`EPP_ROLLOUT_TIMEOUT` overrides).
- 2 of 6600 precise-prefix pressure requests failed with an EPP `parsing response` error
  (`ModelServerError`), 0 of 6600 in the other profiles' pressure runs. Not investigated.

## Results — W5 KEDA autoscaling and A100 cold start

`keda-vllm-a100.yaml` applied unchanged on the Deployment at 1 replica (ScaledObject READY, HPA
`keda-hpa-vllm-a100-llama31-8b` showing `0/4 (avg), 0/1`). Load: 1200 requests with unique 5.8k-token
prompts at concurrency 160 (the answers are a few tokens, so each pod is prefill-bound at ~12k prompt
tokens/s, ~2 requests/s, and the rest queue). Watch log every 5 s: [`results/keda/watch.tsv`](results/keda/watch.tsv).

| time (UTC) | event |
|---|---|
| 11:03:54 | load starts (1 replica) |
| 11:04:14 | Prometheus: `sum(vllm:num_requests_waiting)` = 158, TTFT p90 6.7 s |
| 11:04:15 | HPA `SuccessfulRescale` → 2 (+21 s after load start; both triggers above target) |
| 11:04:15 / :16 | new pod created / container started (node already had the image) |
| 11:06:03 | vLLM API server up |
| 11:06:05 | pod Ready → **110 s pod start to Ready** |
| 11:09:46 | load ends: 1200 requests, 0 errors, 348.5 s; the new pod served 464 of them |
| 11:10:04 | queue empty (`waiting` 0) |
| 11:11:42 | TTFT p90 trigger back to 0 (its 2-minute rate window has emptied) |
| 11:21:31 | HPA `SuccessfulRescale` → 1, "All metrics below target": 600 s after the last above-target sample, **11 min 45 s after the load ended**; the extra pod is deleted |

**A100 cold start** (pod start → Ready, Llama-3.1-8B, vLLM v0.11.0, weights from the node's HF cache,
image present): **110-111 s** for a pod starting alone (the KEDA scale-up, and the 1-replica
restore), **120-121 s** when both replicas start together on the node (8 pods in 4 rollouts during
W4). Breakdown from the scaled-up pod's log, seconds after container start:

| phase | s |
|---|---:|
| API server process up, args parsed | 14 |
| engine core start + weights (16.4 GiB in 3.5 s) | 24 |
| Dynamo transform + torch.compile (no persistent compile cache in the pod) | 46 |
| KV-cache profiling (445,680 tokens) | 2 |
| CUDA graph capture | 19 |
| engine init → API listening → readiness probe (10 s period) | 4 |
| **total** | **109-110** |

torch.compile and graph capture are half of it; the compile cache lives in the container
(`/root/.cache/vllm/torch_compile_cache`), so every new pod compiles from scratch. Mounting it from the
node (or `--enforce-eager`, at a throughput cost) is the obvious next lever, not measured here.

- The scale-up policy (1 pod / 120 s) assumed a cold start under two minutes: it is (110 s alone), with
  little margin. At max 2 the policy never limited anything: the HPA went 1 → 2 on its first look.
- Both triggers fired; under this load TTFT p90 reached 75 s (client concurrency 160 against two
  prefill-bound pods), so the queue trigger alone would have been enough. Max 2 is the node's card count,
  so the queue stayed high (~155) after the scale-up: the ScaledObject cannot fix overload beyond two
  A100s, only spread it (TTFT p90 75 s → 40 s within 3 minutes of the second pod).

## Conclusion

- W4 on the A100 pool: EPP prefix affinity raises vLLM prefix-cache reuse only if it is weighted high enough
  to survive concurrent load. The merged `approx-prefix` (weight 1) behaves like `queue-kv` under pressure;
  weight 3 (`approx-prefix-gpu`) gives +0.08 hit ratio, -20 % TTFT p50 and -16 % wall time on a workload
  whose prefixes exceed one pod's KV cache, and the lowest TTFT at light load. With 8 prefixes that fit
  everywhere the gain is small (hit ratio 0.925 → 0.945), as expected with two replicas.
- precise-prefix works on vLLM v0.11 only with the corrected contract: topic `kv@<pod-ip>:<port>@<model>`
  and engine block size 64. That is what aicomp#46 must publish for the PD path. On one engine type and
  this scale it matches `approx-prefix-gpu` and does not beat it.
- W5: `keda-vllm-a100.yaml` works as written: 1 → 2 within 21 s of overload, back to 1 about 12 minutes
  after the load ends (600 s window + the 2-minute TTFT rate window). A100 cold start is 110 s alone,
  120 s for two pods at once, which the 120 s scale-up step just covers.
- Next: persist vLLM's torch.compile cache on the node and re-measure the cold start; run
  `approx-prefix-gpu` with more replicas (the case where affinity matters more); find why the 16-token
  engine block path matches nothing (llm-d-kv-cache, not this repo).

## Cluster state restored

Recorded before the first change and checked after the last: Deployment `vllm-a100-llama31-8b` at
replicas 0 with a pod template identical to the original (the KV-event args, `POD_IP` env, port 5557
and `--block-size=64` removed again), InferencePool `vllm-a100-pool` spec identical (EPP ref back to
`llmd-router-epp`), ScaledObject (and its HPA), `vllm-a100-epp` (Deployment, Service, ConfigMap,
ServiceAccount, RoleBindings, ClusterRoleBinding) and the temporary HTTPRoute deleted. No other
Deployment, EPP or route was touched.
