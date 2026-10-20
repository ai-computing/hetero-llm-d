# Llama-3.1-8B in one InferencePool across A100, RBLN ATOM and Furiosa RNGD

- **Date**: 2026-10-19
- **Task**: 이종 NPU 혼합 풀 라우팅 테스트 (lmd-top LMDTOP-22 heterogeneous routing의 사전 검증)
- **Host / device**: A100 80GB ×1 on npu-node-2 (vLLM v0.11.0, via nodeName — e11 stays cordoned);
  RBLN-CA22 (ATOM) ×1 on npu-node-1 (host vllm-rbln 0.11.0 / rebel-compiler 0.11.0, driver 3.0.0);
  Furiosa RNGD ×1 on npu-node-1 (furiosa-llm 2026.3.0 image, firmware 2026.4.0, FXB tag `v2026.3`).
  EPP: llm-d-router endpoint picker `@sha256:c0d60804…` (queue 2, kv-cache-utilization 2, prefix-cache 3).
- **Commit**: llm-d-setup `d63c2ce` (+ this record, uncommitted); lmd-top `49ecebc`

## Question

Does llm-d route one model name across three accelerator vendors in a single InferencePool, and
what does the default EPP scoring do with endpoints of very different speed?

## Setup

`manifests/hetero-llama8b-mixed.yaml`: three Deployments serving `meta-llama/Llama-3.1-8B-Instruct`,
one InferencePool, a dedicated EPP and an HTTPRoute (`/hetero/llama8b/*` → `/v1/*`). Pods declare
`llm-d.ai/engine-type` (`vllm` for A100 and RBLN, `furiosa-llm` for RNGD); the EPP's
`core-metrics-extractor` maps `furiosa_llm_*` metrics for the latter.

- RBLN artifact: `~/workspace/01_pd_disag/experiments/native_pd_2026_4/native_atom_b8_20261016/r1/compiled`
  (Llama 8B, optimum-rbln 0.11.0.post1, batch 8, max_seq_len 512), mounted read-only. The
  `~/vllm_test/rbln-Llama-3.1-8B-*` artifacts (optimum-rbln 0.10.0.post1) were tried first and are
  refused by the 0.11 runtime: `LOADING_INVALID_VERSION: … compiled with an incompatible compiler`.
  The host's `/usr/local` RBLN stack is a half-upgraded mix of 0.10.2 and 0.11 that does not import.
- Load: `hetero_load.py` — 128 requests, each a different two-digit multiplication with 5–60 filler
  words, temperature 0; `UNIQUE_PREFIX=1` prepends a random tag so prompts share no prefix;
  `MAXTOK` sets output length. Per-vendor counts come from each server's `request_success_total`
  delta (EPP debug logs rotate too fast to join every request).
- Parity: `parity.py` — 40 multiplications sent directly to each pod (bypassing the EPP).

## Command

```bash
scripts/render-manifest.sh manifests/hetero-llama8b-mixed.yaml | kubectl apply -f -   # LLMD_* from cluster.local.env
GW=http://<gateway> UNIQUE_PREFIX=0 MAXTOK=128 python3 hetero_load.py 128 64 out.json
POD_A100=… POD_RBLN=… POD_RNGD=… python3 parity.py
```

## Results

All runs: 0 HTTP errors. Pool membership was changed with the pool selector (`hetero-l8b/pool=in`).

| pool | prompts | max_tokens | conc | served A100 / RBLN / RNGD | wall | req/s |
|---|---|---:|---:|---|---:|---:|
| A100 only | shared prefix | 128 | 64 | 128 / – / – | 5.5 s | 23.3 |
| A100 only | unique prefix | 128 | 64 | 128 / – / – | 5.7 s | 22.3 |
| A100 + RNGD | unique prefix | 128 | 64 | 128 / – / 0 | 5.7 s | 22.6 |
| A100 + RBLN + RNGD | shared prefix | 128 | 64 | 128 / 0 / 0 | 5.3 s | 24.0 |
| A100 + RBLN + RNGD | unique prefix | 128 | 64 | 97 / 31 / 0 | **37.6 s** | **3.4** |
| A100 + RBLN + RNGD | shared prefix | 24 | 16 | 118 / 10 / 0 | 2.7 s | 47.1 |

Latency in the 3-vendor unique-prefix run: A100 p50 1.94 s (max 2.49 s); RBLN p50 21.3 s (max 37.6 s).
Earlier runs on the same pool (EPP prefix state from previous traffic) sent RNGD 3–18 of 96–128
requests with p50 ≈ 2.4 s at 128 tokens — about A100's latency.

Output parity, 40 prompts, temperature 0, direct to each pod:

| | correct | identical to A100 |
|---|---:|---:|
| A100 | 32 / 40 | – |
| RNGD | 32 / 40 | 38 / 40 |
| RBLN | 23 / 40 | 23 / 40 |

RBLN's differences are digit errors (`68*82 → 5546`, `91*89 → 8069`), not formatting.

Raw: `experiments/2026-10-19-hetero-llama8b-mixed-pool/` (load and parity scripts, per-request JSON).

## Conclusion

- **Mixed-vendor routing works mechanically**: one model name, three vendors, per-pod engine
  labels select the right metric mapping, and the EPP scores and routes to all three. lmd-top's
  generated EPP config does not yet do this — it maps furiosa metrics under the engine name `vllm`,
  which only works for single-vendor pools.
- **Default scoring is speed-blind.** The queue and KV scorers see a slow endpoint with a short
  queue as attractive. When RBLN (batch 8, ~10× slower per request) gets a share, its tail sets the
  completion time: 37.6 s versus 5.5 s for A100 alone — adding hardware made the pool 6.6× slower.
  Conversely an idle RNGD gets almost nothing while A100's queue stays at zero, and tiny KV-usage
  differences plus prefix affinity decide ties. This is the case for the capacity-aware
  heterogeneous scorer (LMDTOP-22); it should be measured against these numbers.
- **Parity must gate pool membership.** A100 and RNGD agree on 38/40 outputs; this RBLN artifact
  is measurably less accurate. Before a vendor joins a pool, a fixed-prompt parity check should pass.
- Not covered: the capacity-aware policy itself (needs the contrib EPP image built), energy (the
  IPMI exporter was not sampled), and a production-quality RBLN Llama-8B artifact.
- Side findings: npu-node-1 disk is back at 90% (user PD experiments, ~350 GB in 3 days), and kubelet
  image GC had removed the furiosa-llm image, whose 783 MB re-pull failed repeatedly with
  `connection reset by peer` from Docker Hub's CDN before succeeding (~25 min).
