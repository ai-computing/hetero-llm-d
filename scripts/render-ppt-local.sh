#!/usr/bin/env bash
set -euo pipefail
deck_path="$(realpath "$1")"
output_path="$(realpath "$2")"
bwrap --ro-bind / / --dev-bind /dev /dev --overlay-src /usr/lib --tmp-overlay /usr/lib --overlay-src /etc --tmp-overlay /etc --bind /tmp /tmp --bind "$output_path" "$output_path" --ro-bind /tmp/kcloud-lo-eKTA0n/root/usr/lib/libreoffice /usr/lib/libreoffice --ro-bind /tmp/kcloud-lo-eKTA0n/root/etc/libreoffice /etc/libreoffice --setenv LD_LIBRARY_PATH /usr/lib/libreoffice/program:/tmp/kcloud-lo-eKTA0n/root/usr/lib/x86_64-linux-gnu --setenv PATH /usr/lib/libreoffice/program:/usr/bin:/bin --setenv XDG_CACHE_HOME /tmp/kcloud-lo-cache /tmp/kcloud-ppt-venv/bin/python "$HOME"/.codex/skills/pptx/scripts/office/soffice.py --headless --convert-to pdf --outdir "$output_path" "$deck_path"
