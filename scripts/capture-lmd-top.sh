#!/usr/bin/env bash
set -euo pipefail

# Capture selected live lmd-top TestBackend views as embeddable SVG images.
# The output is intentionally text-based so it works on headless control-plane nodes.
PROMETHEUS="${LMD_PROM:-192.0.2.8:30090}"
NAMESPACE="${LMD_NS:-llm-serving}"
WIDTH="${LMD_W:-150}"
HEIGHT="${LMD_H:-42}"
OUTPUT_DIR="${1:-docs/images}"

mkdir -p "$OUTPUT_DIR"
rendered="$(mktemp)"
trap 'rm -f "$rendered"' EXIT

LMD_PROM="$PROMETHEUS" LMD_NS="$NAMESPACE" LMD_W="$WIDTH" LMD_H="$HEIGHT" \
  lmd-top --render >"$rendered"

render_svg() {
  local view="$1"
  local slug="$2"
  local output="$OUTPUT_DIR/lmd-top-${slug}.svg"

  awk -v view="$view" -v width="$WIDTH" -v height="$HEIGHT" '
    function xml(s) {
      gsub(/&/, "\&amp;", s)
      gsub(/</, "\&lt;", s)
      gsub(/>/, "\&gt;", s)
      return s
    }
    BEGIN {
      px_width = width * 9.7 + 44
      px_height = height * 20 + 64
      print "<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"" px_width "\" height=\"" px_height "\" viewBox=\"0 0 " px_width " " px_height "\">"
      print "  <title>Live lmd-top " view " view</title>"
      print "  <rect width=\"100%\" height=\"100%\" rx=\"8\" fill=\"#111318\"/>"
      print "  <circle cx=\"20\" cy=\"20\" r=\"5\" fill=\"#ff5f57\"/><circle cx=\"38\" cy=\"20\" r=\"5\" fill=\"#febc2e\"/><circle cx=\"56\" cy=\"20\" r=\"5\" fill=\"#28c840\"/>"
      print "  <text x=\"76\" y=\"25\" fill=\"#9da5b4\" font-family=\"DejaVu Sans Mono, monospace\" font-size=\"13\">lmd-top live capture · " view "</text>"
      print "  <text xml:space=\"preserve\" x=\"22\" y=\"54\" fill=\"#e6e9ef\" font-family=\"DejaVu Sans Mono, monospace\" font-size=\"15\">"
    }
    $0 == "========== VIEW: " view " ==========" { active = 1; next }
    active && /^========== VIEW:/ { active = 0; done = 1 }
    active && lines < height {
      line = xml($0)
      if (lines == 0) {
        print "    <tspan x=\"22\" dy=\"0\" fill=\"#8bd5ca\">" line "</tspan>"
      } else {
        print "    <tspan x=\"22\" dy=\"20\">" line "</tspan>"
      }
      lines++
    }
    END {
      print "  </text>"
      print "</svg>"
      if (!done && lines == 0) exit 2
    }
  ' "$rendered" >"$output"
  printf 'captured %s\n' "$output"
}

render_svg Overview overview
render_svg Flow flow
render_svg EPP epp
render_svg Serving serving
render_svg Devices devices
render_svg Nodes nodes
render_svg Deploy deploy
render_svg Setup setup
