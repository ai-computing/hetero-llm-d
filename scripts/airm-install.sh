#!/usr/bin/env bash
# ai-rm protocol v0.1 cluster pieces: AcceleratorProfile CRD (fetched from the pinned rm-core tag,
# never copied into this repo) + deploy/airm/ (airm_* ScrapeConfig, empty airm-placement ConfigMap)
# + the airm Grafana dashboard ConfigMap.
#
#   scripts/airm-install.sh dry-run [crd|manifests|all]   # kubectl apply --dry-run=server (default)
#   scripts/airm-install.sh apply   [crd|manifests|all]
#   scripts/airm-install.sh delete  [crd|manifests|all]   # rollback; deleting the CRD deletes every AcceleratorProfile
#
# Pin: RM_CORE_REF (tag) + RM_CORE_CRD_SHA256. Bump both together with the rm-core dependency.
#
# Nothing here waits without bound: the CRD download and every kubectl call have a deadline
# (AIRM_FETCH_TIMEOUT, AIRM_KUBECTL_TIMEOUT seconds) and fail with a message naming the step.
set -euo pipefail

RM_CORE_REF="${RM_CORE_REF:-v0.1.1}"
RM_CORE_CRD_SHA256="${RM_CORE_CRD_SHA256:-14cde6fa817f08aca2e0b5e9ef0ce8615253502a2093ed59367adfdb77a56555}"
AIRM_FETCH_TIMEOUT="${AIRM_FETCH_TIMEOUT:-60}"
AIRM_KUBECTL_TIMEOUT="${AIRM_KUBECTL_TIMEOUT:-60}"
CRD_URL="https://raw.githubusercontent.com/ai-computing/rm-core/${RM_CORE_REF}/k8s/acceleratorprofile.crd.yaml"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
MANIFESTS="$ROOT/deploy/airm"

action="${1:-dry-run}"
what="${2:-all}"
case "$action" in
  dry-run) kubectl_args=(apply --dry-run=server -f) ;;
  apply)   kubectl_args=(apply -f) ;;
  delete)  kubectl_args=(delete --ignore-not-found -f) ;;
  *) echo "usage: $0 [dry-run|apply|delete] [crd|manifests|all]" >&2; exit 2 ;;
esac
case "$what" in crd|manifests|all) ;; *) echo "unknown target: $what" >&2; exit 2 ;; esac

fetch_crd() {
  local cache="${XDG_CACHE_HOME:-$HOME/.cache}/airm/rm-core-${RM_CORE_REF}"
  local f="$cache/acceleratorprofile.crd.yaml"
  mkdir -p "$cache"
  if [[ ! -s "$f" ]]; then
    if ! curl -fsSL --connect-timeout 10 --max-time "$AIRM_FETCH_TIMEOUT" --retry 2 \
        "$CRD_URL" -o "$f.tmp" </dev/null; then
      rm -f "$f.tmp"
      echo "failed to download the CRD (3 attempts, ${AIRM_FETCH_TIMEOUT}s each): $CRD_URL" >&2
      echo "(no network/proxy? put the file at $f by hand; the checksum is still verified)" >&2
      exit 1
    fi
    mv "$f.tmp" "$f"
  fi
  if ! echo "$RM_CORE_CRD_SHA256  $f" | sha256sum -c --quiet - >&2; then
    echo "CRD checksum mismatch for rm-core ${RM_CORE_REF} ($f); refusing to apply" >&2
    rm -f "$f"
    exit 1
  fi
  echo "$f"
}

# kubectl with a deadline: --request-timeout bounds each API request; the outer timeout also covers
# an exec credential plugin waiting for interactive login and `delete` waiting on finalizers.
kc() {
  local rc=0
  timeout "$AIRM_KUBECTL_TIMEOUT" kubectl --request-timeout="${AIRM_KUBECTL_TIMEOUT}s" "$@" || rc=$?
  if (( rc == 124 )); then
    echo "kubectl $* did not finish within ${AIRM_KUBECTL_TIMEOUT}s (API server unreachable, or an interactive credential prompt?)" >&2
  fi
  return "$rc"
}

# Fail fast with one clear message instead of a timeout per manifest.
if ! kc get --raw /readyz >/dev/null </dev/null; then
  echo "cannot reach the Kubernetes API server ($(kubectl config current-context 2>/dev/null || echo 'no context')); check KUBECONFIG" >&2
  exit 1
fi

if [[ "$what" == crd || "$what" == all ]]; then
  crd="$(fetch_crd)"
  echo "== AcceleratorProfile CRD (rm-core ${RM_CORE_REF})"
  kc "${kubectl_args[@]}" "$crd" </dev/null
fi

if [[ "$what" == manifests || "$what" == all ]]; then
  echo "== deploy/airm"
  # The ScrapeConfig needs the CRD only for its own kind, not AcceleratorProfile, so order does not matter.
  kc "${kubectl_args[@]}" "$MANIFESTS/scrape-airm.yaml" </dev/null
  kc "${kubectl_args[@]}" "$MANIFESTS/airm-placement.yaml" </dev/null
  # Grafana sidecar (kube-prometheus-stack) loads ConfigMaps labelled grafana_dashboard=1.
  kubectl create configmap grafana-dashboard-airm -n monitoring \
      --from-file=airm.json="$ROOT/monitoring/grafana-dashboards/airm.json" --dry-run=client -o yaml \
    | kubectl label --local -f - grafana_dashboard=1 app.kubernetes.io/part-of=ai-rm -o yaml \
    | kc "${kubectl_args[@]}" -
fi
