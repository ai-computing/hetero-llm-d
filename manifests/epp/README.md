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

## ai-rm placement scorer slot (not active)

ai-rm protocol v0.1 reserves a scorer in each EPP's `schedulingProfiles` that will read the
placement controller's decisions from ConfigMap `llm-serving/airm-placement`. No live EPP config
is changed for it yet; the format and the exact slot are in `deploy/airm/README.md`.

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
