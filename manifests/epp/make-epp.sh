#!/usr/bin/env bash
# make-epp.sh — generate + apply a DEDICATED EPP (endpoint picker) for an InferencePool,
# cloning the working gemma4-rbln-epp reference. One EPP per pool (llm-d pattern).
#
# Usage:
#   ./make-epp.sh <pool-name> <route-path> [namespace]
# Example:
#   ./make-epp.sh koni-pool /koni llm-serving
#
# Prereqs (per model):
#   1. The model Deployment is READY and its pods carry a stable app label.
#   2. An InferencePool <pool-name> exists with:
#        spec.selector.matchLabels = <model pod labels>
#        spec.targetPorts=[{number: <model port>}]
#        spec.endpointPickerRef={name: <pool>-epp, port:{number:9002}, kind: Service}
#      (endpointPickerRef.name MUST equal "<pool-name-without-pool>-epp" produced below,
#       or edit ENDPOINT_PICKER below to match.)
#   3. Envoy Gateway >= v1.8.1 + Envoy AI Gateway v1.0.0 installed and wired
#      (extensionManager.backendResources InferencePool) — see ../README or project notes.
#   4. (For KV/queue-aware scoring) the model server must export vllm:* metrics.
#
# This script:
#   - renders <name>-epp.yaml from gemma4-rbln-epp.yaml (name + pool substituted),
#   - applies it, RESUMES the deployment (the reference is spec.paused=true!),
#   - points the InferencePool.endpointPickerRef at the new EPP service,
#   - switches the given route path to the InferencePool and health-tests (auto-revert on failure).
set -euo pipefail
POOL="${1:?pool-name required}"; PATH_="${2:?route-path required}"; NS="${3:-llm-serving}"
NAME="${POOL%-pool}-epp"           # e.g. koni-pool -> koni-epp
DIR="$(cd "$(dirname "$0")" && pwd)"
REF="$DIR/gemma4-rbln-epp.yaml"
OUT="$DIR/${POOL}-epp.yaml"
source "$DIR/../../scripts/lib/cluster-env.sh"
[[ -n "${GW_ADDR:-}" ]] || { require_env LLMD_GATEWAY_HOST; GW_ADDR="$LLMD_GATEWAY_HOST"; }
GW="$GW_ADDR"

echo ">> rendering $OUT (name=$NAME pool=$POOL)"
sed -e "s/gemma4-rbln-epp/${NAME}/g" -e "s/gemma4-rbln-pool/${POOL}/g" "$REF" > "$OUT"

echo ">> applying"
kubectl apply -f "$OUT"
kubectl -n "$NS" rollout resume "deploy/${NAME}" 2>/dev/null || true   # reference is paused
kubectl -n "$NS" rollout status "deploy/${NAME}" --timeout=120s

echo ">> pointing InferencePool $POOL endpointPickerRef -> $NAME"
kubectl -n "$NS" patch inferencepool "$POOL" --type=json \
  -p "[{\"op\":\"replace\",\"path\":\"/spec/endpointPickerRef/name\",\"value\":\"${NAME}\"}]"

echo ">> NOTE: switch the route rule for ${PATH_} to InferencePool/${POOL} manually and test:"
echo "   kubectl patch httproute openai-route -n $NS --type=json -p '[{\"op\":\"replace\",\"path\":\"/spec/rules/<N>/backendRefs\",\"value\":[{\"group\":\"inference.networking.k8s.io\",\"kind\":\"InferencePool\",\"name\":\"${POOL}\"}]}]'"
echo "   curl http://$GW${PATH_}/models   # expect 200"
echo ">> EPP $NAME deployed. Verify: kubectl -n $NS logs deploy/${NAME} | grep -i 'Reconciling InferencePool'"
