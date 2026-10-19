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
set -euo pipefail

RM_CORE_REF="${RM_CORE_REF:-v0.1.0}"
RM_CORE_CRD_SHA256="${RM_CORE_CRD_SHA256:-038ebfd867b9ad30badb7e2627d1ab5eaf79be5a35d291fec5b4aa22e43bb5db}"
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
    curl -fsSL "$CRD_URL" -o "$f.tmp"
    mv "$f.tmp" "$f"
  fi
  if ! echo "$RM_CORE_CRD_SHA256  $f" | sha256sum -c --quiet - >&2; then
    echo "CRD checksum mismatch for rm-core ${RM_CORE_REF} ($f); refusing to apply" >&2
    rm -f "$f"
    exit 1
  fi
  echo "$f"
}

if [[ "$what" == crd || "$what" == all ]]; then
  crd="$(fetch_crd)"
  echo "== AcceleratorProfile CRD (rm-core ${RM_CORE_REF})"
  kubectl "${kubectl_args[@]}" "$crd"
fi

if [[ "$what" == manifests || "$what" == all ]]; then
  echo "== deploy/airm"
  # The ScrapeConfig needs the CRD only for its own kind, not AcceleratorProfile, so order does not matter.
  kubectl "${kubectl_args[@]}" "$MANIFESTS/scrape-airm.yaml"
  kubectl "${kubectl_args[@]}" "$MANIFESTS/airm-placement.yaml"
  # Grafana sidecar (kube-prometheus-stack) loads ConfigMaps labelled grafana_dashboard=1.
  kubectl create configmap grafana-dashboard-airm -n monitoring \
      --from-file=airm.json="$ROOT/monitoring/grafana-dashboards/airm.json" --dry-run=client -o yaml \
    | kubectl label --local -f - grafana_dashboard=1 app.kubernetes.io/part-of=ai-rm -o yaml \
    | kubectl "${kubectl_args[@]}" -
fi
