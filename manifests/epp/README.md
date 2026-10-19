# EPP (Endpoint Picker) — routing models through llm-d InferencePool

This dir holds the dedicated **EPP** (Gateway API Inference Extension endpoint picker)
manifests that make `openai-route` paths route **through an InferencePool → EPP**
instead of directly to a Service. The EPP does KV-cache / queue-aware endpoint
selection across a pool's pods.

## Working example: gemma4

`gemma4-rbln-epp.yaml` is the live, working dedicated EPP for `gemma4-rbln-pool`.
`/gemma4` routes through it (verified: HTTP 200 end-to-end, KV/queue-aware).

## Platform prerequisites (one-time, already done on this cluster)

- **Envoy Gateway v1.8.1** (upgraded from 1.3.0; Helm release `eg`).
- **Envoy AI Gateway v1.0.0** (`envoy-ai-gateway-system`) — the extension server that
  teaches EG the `InferencePool` backend kind.
- EG `extensionManager` wired to the AI Gateway controller with
  `backendResources: [{group: inference.networking.k8s.io, kind: InferencePool, version: v1}]`
  (values in the `eg` Helm release).

> Note: `HTTPRoute` status may show `ResolvedRefs=False (InvalidKind)` — this is a
> **cosmetic** EG status quirk for extension-provided custom backends; traffic still flows.

## The pattern: one EPP per InferencePool

The shared `llmd-router-epp` (Helm release `llmd-router`) only watches ONE pool
(`--pool-name`), so **each model needs its own EPP** watching its pool. Reusing/repointing
the shared one is fragile (Helm-managed) and breaks the pools it no longer watches.

### To add EPP routing for a model

1. **Ensure the model is ready** (has running pods) and, for smart scoring, **exports
   `vllm:*` metrics** (scrape target up). Endpoint picking works without metrics but
   scoring is blind.
2. **Create an InferencePool** for it:
   ```yaml
   apiVersion: inference.networking.k8s.io/v1
   kind: InferencePool
   metadata: { name: <model>-pool, namespace: llm-serving }
   spec:
     selector: { matchLabels: { app: <model-pod-app-label> } }
     targetPorts: [{ number: 8000 }]
     endpointPickerRef: { name: <model>-epp, port: { number: 9002 }, kind: Service }
   ```
   (Do NOT include `spec.appProtocol` — the v1 CRD strict-rejects it.)
3. **Generate + deploy the EPP** (clones the gemma4 reference):
   ```bash
   ./make-epp.sh <model>-pool /<route-path>
   ```
4. **Switch the route** rule for that path to the InferencePool, then `curl .../models` → 200.

## Scheduling profiles

`profiles/` holds EndpointPickerConfigs that `make-epp.sh` installs instead of the reference's
config when `EPP_PROFILE` is set (`EPP_RENDER_ONLY=1` prints the manifests and touches nothing).
They are written for the EPP image this repo runs (llm-d-router `e194457dc507`, same as lmd-top's
epp-score-observer) and checked by `python3 scripts/check-epp-config.py`: the EPP decodes its config
strictly, so an unknown plugin type or parameter key would stop it at start-up.

| Profile | Plugins | Needs |
|---|---|---|
| `queue-kv.yaml` | queue-scorer (2), kv-cache-utilization-scorer (2) | `/metrics`; pods labelled `llm-d.ai/engine-type` (`vllm` default, `furiosa-llm` mapped) |
| `approx-prefix.yaml` | + approx-prefix-cache-producer → prefix-cache-scorer (1) | nothing more |
| `approx-prefix-gpu.yaml` | same, prefix-cache-scorer (3) | nothing more; for engines that reuse prefixes (A100 vLLM) |
| `precise-prefix.yaml` | token-producer (vLLM render) → precise-prefix-cache-producer → prefix-cache-scorer (3), queue (2), KV (2) | engine KV events; render sidecar (`precise-prefix-render-sidecar.yaml`, patched in by `make-epp.sh`) |

**Approximate prefix scoring works without engine support.** The producer gets token IDs from the
auto-created `estimate` token-producer (byte packing, no tokenizer), hashes them into blocks
(`blockSizeTokens`, at least 64, or the engine's block size when `vllm:cache_config_info` /
`furiosa_llm_cache_config_info` is scraped) and records the endpoint each request was sent to in a
per-endpoint LRU. Nothing is read from the engine except the optional cache-config metric. The gain
needs an engine that caches prefixes at a block size smaller than the shared prefix: yes for the A100
vLLM pool (`--enable-prefix-caching`); no for vllm-rbln compiled with `--block-size 512` and
`--max-model-len 512` (no full block is ever shared); none on the rngd-pd path until aicomp#46 adds
prefix reuse, where affinity only concentrates load. Hence prefix weight 1 against 2 + 2 for load.

Measured on the A100 pool with two replicas ([experiment](../../experiments/2026-10-19-w4w5-gpu/README.md)):
affinity works (one shared prefix, sequential: 20/20 requests on one pod, `queue-kv` 10/10), but
with weight 1 the load scores outvote it once requests run concurrently. Under KV-cache pressure
(220 prefixes of 2.9k tokens, more than one pod's 446k-token cache) the vLLM prefix hit ratio was
0.56-0.59 with weight 1 against 0.55-0.57 for `queue-kv`; `approx-prefix-gpu` (weight 3) reached
0.63-0.65 and cut TTFT p50 by 20 % and wall time by 16 %. Use `approx-prefix-gpu` on the A100 pool.

**Precise prefix scoring (opt-in)** follows the engines' own caches. Contract for an engine
(what Optimus Prime needs to publish for aicomp#46, as vLLM does with
`--block-size=64 --kv-events-config '{"enable_kv_cache_events":true,"publisher":"zmq","endpoint":"tcp://*:5557","topic":"kv@$(POD_IP):8000@<model>"}'`):

- a ZMQ PUB socket on the pod at port 5557 (+ data-parallel rank), topic `kv@<pod-ip>:<serving-port>@<model>`.
  The `<pod-ip>:<port>` part is the key the index stores blocks under, and lookups filter on the
  endpoint's `address:port`, so a topic without the port (`kv@<pod-ip>@<model>`, as first written
  here) delivers events that never match. The model name goes into the block key, so it must be the
  served model name requests use;
- vLLM KV-event batches (msgpack): `BlockStored` with the block's `token_ids` (plus `extra_keys` for
  `cache_salt` / multimodal inputs), `BlockRemoved`, `AllBlocksCleared`;
- the EPP rehashes `token_ids` itself (`tokenProcessorConfig.blockSizeTokens`), so the engine's hash
  function does not matter (its hashes are only opaque keys). The block size does, in practice: with
  vLLM's default 16 (and chunked prefill in 2048-token steps) the index predicted 0 cached tokens
  under concurrent load and ~12 % sequentially, and it counted stores skipped as
  `unresolved_sub_canonical_parent` (an event whose parent block ends inside a 64-token block); with
  `--block-size=64` it predicted 85-89 % of prompt tokens for shared prefixes. We did not trace the
  16-token path further. Publish blocks of `blockSizeTokens` (64).

The EPP subscribes per endpoint when it sees the pod (`endpoint-notification-source` →
precise-prefix-cache-producer). An endpoint that publishes nothing scores 0 on prefix and is still
routed by queue and KV, so the profile can run on a mixed pool.

## ai-rm placement scorer slot (not active)

ai-rm protocol v0.1 reserves a scorer in each EPP's `schedulingProfiles` that will read the
placement controller's decisions from ConfigMap `llm-serving/airm-placement`. No live EPP config
is changed for it yet; the format and the exact slot are in `deploy/airm/README.md`. Until then the
decisions act on scheduling instead (node affinity, `scripts/airm-install.sh apply placement`).

## Gotchas learned the hard way

- The reference Deployment has **`spec.paused: true`** — a fresh clone creates no pods
  until `kubectl rollout resume`. `make-epp.sh` does this automatically.
- Don't delete the orphan pools (`llmd-router`, `vllm-a100-pool`) — the shared
  `llmd-router-epp` still watches `llmd-router`; deleting it crashes that EPP.
- `--pool-name` must equal the InferencePool name; `endpointPickerRef.name` must equal
  the EPP Service name.

## Current cluster state

| path | backend | EPP | notes |
|------|---------|-----|-------|
| `/gemma4` | InferencePool `gemma4-rbln-pool` | `gemma4-rbln-epp` (dedicated) | ✅ through EPP, exports vllm metrics |
| `/ds4`, `/v1` | Service `ds4-inject-proxy` | — | proxy-fronted (PD); pool model doesn't fit as-is |
| `/gb10` | Service `vllm-qwen05b-gb10` | — | scaled to 0 |
| `/koni`, `/cpu` | Service | — | scaled to 0 / not vLLM |

Only `gemma4-rbln` currently meets all EPP prereqs (ready + vLLM metrics + direct route).
Scale up + enable metrics on other models first, then run `make-epp.sh`.
