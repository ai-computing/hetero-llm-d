#!/usr/bin/env bash
# Render a manifest that contains ${LLMD_*} placeholders with values from cluster.local.env.
#   scripts/render-manifest.sh manifests/model-store.yaml | kubectl apply -f -
set -euo pipefail
source "$(dirname "$0")/lib/cluster-env.sh"
f="${1:?usage: render-manifest.sh <manifest.yaml>}"
vars="$(grep -o '\${LLMD_[A-Z0-9_]*}' "$f" | sort -u | tr -d '${}' || true)"
[[ -z "$vars" ]] || require_env $vars
envsubst "$(printf '${%s} ' $vars)" < "$f"
