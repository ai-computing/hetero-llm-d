# deploy/airm — ai-rm protocol v0.1 cluster pieces

This cluster's side of the [ai-rm protocol v0.1](https://github.com/ai-computing/rm-core/blob/v0.1.0/PROTOCOL.md):
the places where the contracts run. Apply everything with `scripts/airm-install.sh`.

| What | Where | Protocol |
|---|---|---|
| `AcceleratorProfile` CRD (`airm.ai-computing.io/v1alpha1`, cluster-scoped) | fetched from the rm-core tag `v0.1.0` by `scripts/airm-install.sh` (sha256-pinned, no copy in this repo) | §3.1 |
| `airm_*` scrape: pods annotated `airm.ai-computing.io/scrape: "true"` | `scrape-airm.yaml` (ScrapeConfig `monitoring/airm-pods`, job `airm`) | §6 |
| `airm_*` Grafana dashboard | `monitoring/grafana-dashboards/airm.json` → ConfigMap `monitoring/grafana-dashboard-airm` (sidecar label `grafana_dashboard=1`) | §6 |
| Placement hand-off | `airm-placement.yaml` (ConfigMap `llm-serving/airm-placement`, empty in v0.1) | §5.2 |
| Umbrella chart cluster values | `deploy/helm/cluster-values.yaml` | integration guide §3 |

`llm-serving` is this cluster's llm-d namespace (Gateway, InferencePools, EPPs, model servers), so
`airm-placement` lives there.

## Install, check, roll back

```bash
scripts/airm-install.sh dry-run            # kubectl apply --dry-run=server for CRD + deploy/airm + dashboard
scripts/airm-install.sh apply crd          # CRD only
scripts/airm-install.sh apply manifests    # ScrapeConfig, airm-placement, dashboard ConfigMap
kubectl get crd acceleratorprofiles.airm.ai-computing.io
kubectl get accp                           # AcceleratorProfiles (written by the L1 node daemon)

# rollback
scripts/airm-install.sh delete manifests
scripts/airm-install.sh delete crd         # also deletes every AcceleratorProfile object
```

Bumping rm-core: change `RM_CORE_REF` and `RM_CORE_CRD_SHA256` in `scripts/airm-install.sh`
together (`curl -fsSL https://raw.githubusercontent.com/ai-computing/rm-core/<tag>/k8s/acceleratorprofile.crd.yaml | sha256sum`).
The script refuses to apply a CRD whose checksum does not match.

## Metrics scrape

A component exposing `airm_*` series (names from `rm_core.metrics.METRICS`, labels from `TAG_KEYS`)
annotates its pod:

```yaml
metadata:
  annotations:
    airm.ai-computing.io/scrape: "true"
    airm.ai-computing.io/port: "9400"      # optional, default 9400 (= charts' airm.metricsPort)
    airm.ai-computing.io/path: /metrics    # optional
```

The ScrapeConfig adds `namespace`, `pod`, `node` target labels. PodMonitor cannot select by
annotation, which is why this is a ScrapeConfig; kube-prometheus-stack picks it up through
`scrapeConfigSelector: {release: kube-prometheus-stack}`. Check targets with
`up{job="airm"}` in Prometheus.

## `airm-placement` ConfigMap format

Writer: the ai-rm placement controller (next step), which runs a `Placement` policy
(`airm.placements` entry point) over `AcceleratorProfile`s and live `airm_*` metrics.
Readers: the EPP scorer (below) and serving pods. One key, `decisions.json`:

```json
{
  "protocol": "0.1",
  "generation": 12,
  "updatedAt": "2026-10-19T00:00:00Z",
  "placement": "greedy",
  "decisions": [
    {
      "pool": "llama8b-pd-pool",
      "workload": {"kind": "decode", "model": "meta-llama/Llama-3.1-8B-Instruct",
                   "slo": {"tpot_p90_ms": 40}, "labels": {}},
      "acceleratorIds": ["<node>/furiosa:0", "<node>/furiosa:1"],
      "kvTransport": "p2p",
      "reason": "lowest tpot_p90 within SLO"
    }
  ]
}
```

| Field | Meaning |
|---|---|
| `protocol` | protocol version the writer implements (`"0.1"`) |
| `generation` | integer, incremented on every write; readers ignore a document older than one they applied |
| `updatedAt` | RFC 3339 UTC time of the write, `null` before the first write |
| `placement` | name of the `Placement` policy that produced the decisions |
| `decisions[].pool` | InferencePool name (= the EPP's `--pool-name`) the decision applies to |
| `decisions[].workload` | `rm_core.Workload` (`kind` ∈ `WORKLOAD_KINDS`, `slo` keys ∈ `SLO_KEYS`) |
| `decisions[].acceleratorIds` | `PlacementDecision.accelerator_ids`, ids `<node>/<vendor>:<index>` as in `AcceleratorProfile.spec.id` |
| `decisions[].kvTransport` | `PlacementDecision.kv_transport`, a `airm.kv_transports` entry-point name, `""` if none |
| `decisions[].reason` | `PlacementDecision.reason`; an empty `acceleratorIds` with a reason means nothing fits |

Rules: no addresses or credentials (protocol §7); ids only, resolved through `AcceleratorProfile`s.
A reader that finds no decision for its pool, or an empty `decisions` list (the v0.1 state),
behaves as if the ConfigMap did not exist.

## Where the EPP reads it (scorer slot)

The EPPs here (`manifests/epp/`, one per InferencePool) take an `EndpointPickerConfig` from a
ConfigMap. The placement scorer is a future plugin in the same `schedulingProfiles` list as the
current scorers. **v0.1 changes no live EPP config**; this is where it will go:

```yaml
apiVersion: llm-d.ai/v1alpha1
kind: EndpointPickerConfig
plugins:
- type: queue-scorer
- type: kv-cache-utilization-scorer
- type: prefix-cache-scorer
- type: no-hit-lru-scorer
# ai-rm (not yet implemented): reads llm-serving/airm-placement, decisions[pool == --pool-name],
# scores an endpoint 1.0 when its pod runs on an accelerator in acceleratorIds, else 0.0;
# neutral (all equal) when there is no decision.
# - type: airm-placement-scorer
#   parameters: {configMap: airm-placement, key: decisions.json}
- type: metrics-data-source
  parameters: {scheme: http, path: /metrics, insecureSkipVerify: true}
- type: core-metrics-extractor
schedulingProfiles:
- name: default
  plugins:
  - {pluginRef: queue-scorer, weight: 2}
  - {pluginRef: kv-cache-utilization-scorer, weight: 2}
  - {pluginRef: prefix-cache-scorer, weight: 3}
  - {pluginRef: no-hit-lru-scorer, weight: 2}
  # - {pluginRef: airm-placement-scorer, weight: 4}   # ai-rm slot
```

The EPP ServiceAccount will then need `get`/`watch` on ConfigMap `airm-placement` in
`llm-serving`, and pod → accelerator mapping comes from the pod's node plus
`AcceleratorProfile`s on that node (`kubectl get accp`).
