#!/usr/bin/env bash
# make-epp.sh — generate + apply a DEDICATED EPP (endpoint picker) for an InferencePool,
# cloning the working gemma4-rbln-epp reference. One EPP per pool (llm-d pattern).
#
# Usage:
#   [EPP_PROFILE=<profile>] [EPP_MODEL=<hf-id>] [EPP_RENDER_ONLY=1] ./make-epp.sh <pool-name> <route-path> [namespace]
# Example:
#   ./make-epp.sh koni-pool /koni llm-serving
#   EPP_PROFILE=queue-kv ./make-epp.sh llama8b-pd-pool /pd
#   EPP_PROFILE=precise-prefix EPP_MODEL=meta-llama/Llama-3.1-8B-Instruct ./make-epp.sh vllm-a100-pool /gpu
#   EPP_PROFILE=approx-prefix EPP_RENDER_ONLY=1 ./make-epp.sh koni-pool /koni   # print, touch nothing
#
# EPP_PROFILE picks the scheduling config from profiles/<profile>.yaml (see ../epp/README.md):
#   (unset)         the reference's own config (queue, kv, prefix, no-hit-lru)
#   queue-kv        queue + KV utilization only (NPU pools)
#   approx-prefix   + approximate prefix affinity, no engine support needed
#   precise-prefix  + prefix scoring from engine KV events (opt-in; also adds the render sidecar)
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
#   - renders <name>-epp.yaml from gemma4-rbln-epp.yaml (name + pool substituted, profile config),
#   - applies it, RESUMES the deployment (the reference is spec.paused=true!),
#   - points the InferencePool.endpointPickerRef at the new EPP service,
#   - switches the given route path to the InferencePool and health-tests (auto-revert on failure).
set -euo pipefail
POOL="${1:?pool-name required}"; PATH_="${2:?route-path required}"; NS="${3:-llm-serving}"
NAME="${POOL%-pool}-epp"           # e.g. koni-pool -> koni-epp
DIR="$(cd "$(dirname "$0")" && pwd)"
REF="$DIR/gemma4-rbln-epp.yaml"
OUT_DIR="$DIR"
[[ -z "${EPP_RENDER_ONLY:-}" ]] || OUT_DIR="$(mktemp -d)"   # render-only leaves the repo untouched
OUT="$OUT_DIR/${POOL}-epp.yaml"
PROFILE="${EPP_PROFILE:-}"
MODEL="${EPP_MODEL:-meta-llama/Llama-3.1-8B-Instruct}"
DEFAULT_MODEL="meta-llama/Llama-3.1-8B-Instruct"   # the model named in profiles/precise-prefix.yaml

# Drop the reference's ConfigMap document when a profile replaces it (documents split on '---').
drop_configmap() {
  awk 'function flush() { if (doc != "" && doc !~ /\nkind: ConfigMap\n/) printf "%s", doc; doc = "" }
       /^---$/ { flush(); doc = "---\n"; next }
       { doc = doc $0 "\n" }
       END { flush() }' | awk 'NR == 1 && /^---$/ { next } { print }'
}

profile_configmap() {
  local f="$DIR/profiles/${PROFILE}.yaml"
  [[ -f "$f" ]] || { echo "unknown EPP_PROFILE '$PROFILE' (no $f)" >&2; exit 2; }
  echo "---"
  echo "apiVersion: v1"
  echo "kind: ConfigMap"
  echo "metadata:"
  echo "  name: ${NAME}"
  echo "  namespace: ${NS}"
  echo "  labels: {llm-d.ai/epp-profile: ${PROFILE}}"
  echo "data:"
  echo "  default-plugins.yaml: |"
  sed -e "s#${DEFAULT_MODEL}#${MODEL}#g" -e 's/^/    /' "$f"
}

echo ">> rendering $OUT (name=$NAME pool=$POOL profile=${PROFILE:-reference})" >&2
if [[ -z "$PROFILE" ]]; then
  sed -e "s/gemma4-rbln-epp/${NAME}/g" -e "s/gemma4-rbln-pool/${POOL}/g" "$REF" > "$OUT"
else
  { sed -e "s/gemma4-rbln-epp/${NAME}/g" -e "s/gemma4-rbln-pool/${POOL}/g" "$REF" | drop_configmap
    profile_configmap; } > "$OUT"
fi
SIDECAR=""
if [[ "$PROFILE" == precise-prefix ]]; then
  SIDECAR="$OUT_DIR/${POOL}-epp-render-sidecar.yaml"
  sed -e "s#${DEFAULT_MODEL}#${MODEL}#g" "$DIR/precise-prefix-render-sidecar.yaml" > "$SIDECAR"
fi

if [[ -n "${EPP_RENDER_ONLY:-}" ]]; then
  cat "$OUT"
  [[ -z "$SIDECAR" ]] || { echo "# --- patch for deploy/${NAME} (kubectl patch --patch-file)"; cat "$SIDECAR"; }
  rm -rf "$OUT_DIR"
  exit 0
fi

source "$DIR/../../scripts/lib/cluster-env.sh"
[[ -n "${GW_ADDR:-}" ]] || { require_env LLMD_GATEWAY_HOST; GW_ADDR="$LLMD_GATEWAY_HOST"; }
GW="$GW_ADDR"

echo ">> applying"
kubectl apply -f "$OUT"
if [[ -n "$SIDECAR" ]]; then
  echo ">> adding the vLLM render sidecar (precise-prefix token-producer)"
  kubectl -n "$NS" patch "deploy/${NAME}" --patch-file "$SIDECAR"
fi
kubectl -n "$NS" rollout resume "deploy/${NAME}" 2>/dev/null || true   # reference is paused
kubectl -n "$NS" rollout status "deploy/${NAME}" --timeout=120s

echo ">> pointing InferencePool $POOL endpointPickerRef -> $NAME"
kubectl -n "$NS" patch inferencepool "$POOL" --type=json \
  -p "[{\"op\":\"replace\",\"path\":\"/spec/endpointPickerRef/name\",\"value\":\"${NAME}\"}]"

echo ">> NOTE: switch the route rule for ${PATH_} to InferencePool/${POOL} manually and test:"
echo "   kubectl patch httproute openai-route -n $NS --type=json -p '[{\"op\":\"replace\",\"path\":\"/spec/rules/<N>/backendRefs\",\"value\":[{\"group\":\"inference.networking.k8s.io\",\"kind\":\"InferencePool\",\"name\":\"${POOL}\"}]}]'"
echo "   curl http://$GW${PATH_}/models   # expect 200"
echo ">> EPP $NAME deployed. Verify: kubectl -n $NS logs deploy/${NAME} | grep -i 'Reconciling InferencePool'"
