#!/usr/bin/env python3
"""Offline check of EPP scheduling configs (EndpointPickerConfig) against the pinned llm-d-router.

The EPP decodes its config strictly: an unknown plugin type or parameter key stops it at start-up.
This catches those before a rollout, plus dangling pluginRefs and a prefix scorer bound to a
producer that is not declared. Requires Python 3.6+ and PyYAML.

    python3 scripts/check-epp-config.py                     # profiles + EPP manifests in this repo
    python3 scripts/check-epp-config.py <file.yaml> ...     # EndpointPickerConfig files or manifests
                                                            # whose ConfigMap holds default-plugins.yaml

Known types and parameter keys: llm-d-router e194457dc507 (cmd/epp/runner/runner.go and the plugins'
JSON tags; llm-d-kv-cache v0.9.0 for the precise producer's nested configs). Re-derive both when the
EPP image moves.
"""
import sys
from pathlib import Path

import yaml

PINNED = "llm-d-router e194457dc507"

KNOWN_TYPES = set("""
active-request-scorer agent-identity always-disagg-multimodal-decider always-disagg-pd-decider
anthropic-parser approx-prefix-cache-producer burst-prefix-cache-producer by-label by-label-selector
concurrency-detector context-length-aware core-metrics-extractor data-parallel-profile-handler
decode-filter destination-endpoint-served-verifier disagg-headers-handler disagg-profile-handler
edf-ordering-policy encode-filter endpoint-notification-source fcfs-ordering-policy file-discovery
global-strict-fairness-policy header-based-testing-filter inflight-load-producer k8s-notification-source
kv-cache-utilization-scorer label-selector-filter latency-scorer latency-slo-admitter load-aware-scorer
lora-affinity-scorer max-score-picker metrics-data-source mm-embeddings-cache-producer
mm-embeddings-cache-scorer models-data-extractor models-data-source no-hit-lru-scorer openai-parser
passthrough-parser pd-profile-handler precise-prefix-cache-producer precise-prefix-cache-scorer
predicted-latency-producer prefill-filter prefill-header-handler prefix-based-pd-decider
prefix-cache-affinity-filter prefix-cache-scorer probabilistic-admitter program-aware-fairness
queue-scorer random-picker request-attribute-reporter round-robin-fairness-policy
running-requests-size-scorer session-affinity-filter session-affinity-scorer session-id-producer
single-profile-handler slo-deadline-ordering-policy slo-headroom-tier-filter static-usage-limit-policy
tokenizer token-load-scorer token-producer utilization-detector vertexai-parser vllmgrpc-parser
vllmhttp-parser weighted-random-picker
""".split())

# Parameter schemas for the plugins this repo configures: {key: nested schema or None (leaf)}.
ENGINE = {k: None for k in (
    "name queuedRequestsSpec runningRequestsSpec kvUsageSpec loraSpec cacheInfoSpec "
    "cacheBlockSizeLabelName cacheNumBlocksLabelName cacheBlockSizeSpec cacheNumBlocksSpec "
    "customMetrics").split()}
PARAMS = {
    "queue-scorer": {},
    "kv-cache-utilization-scorer": {},
    "no-hit-lru-scorer": None,          # has parameters; not configured here, so not checked
    "prefix-cache-scorer": {"prefixMatchInfoProducerName": None},
    "approx-prefix-cache-producer": {k: None for k in (
        "autoTune blockSizeTokens blockSize maxPrefixBlocksToMatch maxPrefixTokensToMatch "
        "lruCapacityPerServer").split()},
    "metrics-data-source": {"scheme": None, "path": None, "insecureSkipVerify": None},
    "core-metrics-extractor": {"engineLabelKey": None, "defaultEngine": None, "engineConfigs": [ENGINE]},
    "token-producer": {"modelName": None, "udsTokenizerConfig": None, "estimate": None,
                       "vllm": {"url": None, "timeout": None, "mmTimeout": None}},
    "precise-prefix-cache-producer": {
        "tokenProcessorConfig": {"blockSize": None, "blockSizeTokens": None, "hashSeed": None},
        "indexerConfig": {"kvBlockIndexConfig": {k: None for k in (
                              "inMemoryConfig redisConfig valkeyConfig costAwareMemoryConfig "
                              "enableMetrics metricsLoggingInterval").split()},
                          "kvCacheBackendConfigs": None, "tokenizersPoolConfig": None},
        "kvEventsConfig": {"zmqEndpoint": None, "topicFilter": None, "concurrency": None,
                           "engineType": None, "discoverPods": None,
                           "podDiscoveryConfig": {"podLabelSelector": None, "podNamespace": None,
                                                  "socketPort": None}},
        "speculativeIndexing": None, "speculativeTTL": None},
    "endpoint-notification-source": {},
}
TOP_KEYS = {"apiVersion", "kind", "featureGates", "plugins", "schedulingProfiles", "dataLayer",
            "flowControl", "requestHandler", "saturationDetector", "parser"}
# Producers of PrefixCacheMatchInfo; the EPP auto-creates the approximate one when none is named.
PREFIX_PRODUCERS = {"approx-prefix-cache-producer", "precise-prefix-cache-producer",
                    "burst-prefix-cache-producer"}


def check_keys(value, schema, where, errors):
    if schema is None:
        return
    if isinstance(schema, list):
        for i, item in enumerate(value or []):
            check_keys(item, schema[0], f"{where}[{i}]", errors)
        return
    if value is None:
        return
    if not isinstance(value, dict):
        errors.append(f"{where}: expected a mapping, got {type(value).__name__}")
        return
    for k, v in value.items():
        if k not in schema:
            errors.append(f"{where}: unknown key '{k}' (strict decoding would reject it)")
        else:
            check_keys(v, schema[k], f"{where}.{k}", errors)


def check_config(cfg):
    """Return a list of problems in one EndpointPickerConfig mapping."""
    errors = []
    if cfg.get("apiVersion") != "llm-d.ai/v1alpha1" or cfg.get("kind") != "EndpointPickerConfig":
        errors.append("apiVersion/kind must be llm-d.ai/v1alpha1 EndpointPickerConfig")
    for k in cfg:
        if k not in TOP_KEYS:
            errors.append(f"unknown top-level key '{k}'")
    names, types = {}, {}
    for i, p in enumerate(cfg.get("plugins") or []):
        t, name = p.get("type"), p.get("name") or p.get("type")
        if t not in KNOWN_TYPES:
            errors.append(f"plugins[{i}]: unknown type '{t}' for {PINNED}")
        if name in names:
            errors.append(f"plugins[{i}]: duplicate plugin name '{name}'")
        names[name] = p
        types.setdefault(t, []).append(name)
        check_keys(p.get("parameters"), PARAMS.get(t), f"plugins[{i}]({t}).parameters", errors)
        producer = (p.get("parameters") or {}).get("prefixMatchInfoProducerName")
        if t == "prefix-cache-scorer" and producer:
            target = names.get(producer) or next(
                (q for q in cfg["plugins"] if (q.get("name") or q.get("type")) == producer), None)
            if target is None:
                errors.append(f"plugins[{i}]: prefixMatchInfoProducerName '{producer}' is not declared")
            elif target.get("type") not in PREFIX_PRODUCERS:
                errors.append(f"plugins[{i}]: '{producer}' is not a prefix-cache producer")
    profiles = cfg.get("schedulingProfiles") or []
    if not profiles:
        errors.append("no schedulingProfiles")
    for prof in profiles:
        for ref in prof.get("plugins") or []:
            if ref.get("pluginRef") not in names:
                errors.append(f"profile '{prof.get('name')}': pluginRef '{ref.get('pluginRef')}' not declared")
            w = ref.get("weight")
            if w is not None and (not isinstance(w, (int, float)) or w < 0):
                errors.append(f"profile '{prof.get('name')}': bad weight {w!r} for {ref.get('pluginRef')}")
    for src in ((cfg.get("dataLayer") or {}).get("sources") or []):
        for ref in [src] + list(src.get("extractors") or []):
            if ref.get("pluginRef") not in names:
                errors.append(f"dataLayer: pluginRef '{ref.get('pluginRef')}' not declared")
    if "precise-prefix-cache-producer" in types:
        tp = [names[n] for n in types.get("token-producer", [])]
        if not any((p.get("parameters") or {}).get("vllm") or (p.get("parameters") or {}).get("modelName")
                   for p in tp):
            errors.append("precise-prefix-cache-producer needs a token-producer with a real tokenizer "
                          "(vllm render); the auto-created estimate backend cannot match engine tokens")
        layer = cfg.get("dataLayer") or {}
        wired = any(x.get("pluginRef") in types["precise-prefix-cache-producer"]
                    for s in layer.get("sources") or [] for x in s.get("extractors") or [])
        if not wired:
            errors.append("precise-prefix-cache-producer is not an extractor of endpoint-notification-source "
                          "in dataLayer, so no per-pod KV-event subscriber is ever started")
    return errors


def configs_in(path):
    """(label, config) pairs: a bare EndpointPickerConfig file or ConfigMaps carrying one."""
    out = []
    for i, doc in enumerate(yaml.safe_load_all(Path(path).read_text(encoding="utf-8"))):
        if not isinstance(doc, dict):
            continue
        if doc.get("kind") == "EndpointPickerConfig":
            out.append((f"{path}", doc))
        elif doc.get("kind") == "ConfigMap":
            for key, text in (doc.get("data") or {}).items():
                if key.endswith(".yaml") and "EndpointPickerConfig" in (text or ""):
                    out.append((f"{path}:{doc['metadata']['name']}/{key}", yaml.safe_load(text)))
    return out


def default_files():
    root = Path(__file__).resolve().parents[1]
    return (sorted((root / "manifests/epp/profiles").glob("*.yaml"))
            + sorted((root / "manifests/epp").glob("*-epp.yaml"))
            + [root / "manifests/hetero-llama8b-mixed.yaml"])


def main(argv):
    files = [Path(a) for a in argv] or default_files()
    bad = 0
    for f in files:
        found = configs_in(f)
        if not found:
            print(f"SKIP {f}: no EndpointPickerConfig")
        for label, cfg in found:
            errors = check_config(cfg)
            print(f"{'FAIL' if errors else 'ok  '} {label}")
            for e in errors:
                print(f"     - {e}")
            bad += bool(errors)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
