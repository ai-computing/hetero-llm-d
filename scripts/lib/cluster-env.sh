# shellcheck shell=bash
# Load site-specific values. Source this from a script, then call `require_env VAR...`.
# Order: variables already in the environment, then $LLMD_ENV_FILE, then <repo>/cluster.local.env.
_llmd_repo="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
_llmd_env="${LLMD_ENV_FILE:-$_llmd_repo/cluster.local.env}"
if [[ -f "$_llmd_env" ]]; then
  while IFS='=' read -r _k _v; do
    [[ "$_k" =~ ^[A-Z_][A-Z0-9_]*$ ]] || continue
    [[ -n "${!_k:-}" ]] || export "$_k=$_v"
  done < "$_llmd_env"
fi

require_env() {
  local missing=() v
  for v in "$@"; do [[ -n "${!v:-}" && "${!v}" != *"<"* ]] || missing+=("$v"); done
  if (( ${#missing[@]} )); then
    echo "error: missing ${missing[*]}; set it in the environment or in $_llmd_env (template: $_llmd_repo/cluster.example.env)" >&2
    exit 1
  fi
}
