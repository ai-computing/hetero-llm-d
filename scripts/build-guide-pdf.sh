#!/usr/bin/env bash
# Build docs/ENVIRONMENT-GUIDE.pdf from ENVIRONMENT-GUIDE.md
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DOCS="$ROOT/docs"
PY="${LMD_DOCS_PY:-$ROOT/.venv-docs/bin/python}"

if [[ ! -x "$PY" ]]; then
  echo "missing $PY — run: uv venv $ROOT/.venv-docs && uv pip install --python $ROOT/.venv-docs/bin/python markdown weasyprint cairosvg pillow" >&2
  exit 1
fi

mkdir -p "$DOCS/images/pdf"
cd "$DOCS"

for f in overview flow epp serving devices nodes deploy setup; do
  svg="images/lmd-top-$f.svg"
  png="images/pdf/lmd-top-$f.png"
  if [[ -f "$svg" ]]; then
    "$PY" -c "import cairosvg; cairosvg.svg2png(url='$svg', write_to='$png', output_width=1400)"
  fi
done
if [[ -f images/lmd-top-demo.gif ]]; then
  "$PY" -c "from PIL import Image; im=Image.open('images/lmd-top-demo.gif'); im.seek(0); im.convert('RGB').save('images/pdf/lmd-top-demo.png')"
fi

"$PY" <<'PY'
from pathlib import Path
import re
import markdown
from weasyprint import HTML, CSS

src = Path("ENVIRONMENT-GUIDE.md").read_text(encoding="utf-8")

def rewrite_img(m):
    alt, path = m.group(1), m.group(2)
    name = Path(path).stem + ".png"
    png = Path("images/pdf") / name
    if png.exists():
        return f"![{alt}]({png.as_posix()})"
    return m.group(0)

src_pdf = re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", rewrite_img, src)
html_body = markdown.markdown(src_pdf, extensions=["tables", "fenced_code", "nl2br"])
html = f"""<!DOCTYPE html><html lang="ko"><head><meta charset="utf-8"/><title>llm-d 사내 환경 가이드</title></head><body>{html_body}</body></html>"""
css = CSS(string="""
@page { size: A4; margin: 18mm 16mm; @bottom-center { content: counter(page); font-size: 9pt; color: #666; font-family: "Noto Sans CJK KR", sans-serif; } }
body { font-family: "Noto Sans CJK KR", sans-serif; font-size: 10.5pt; line-height: 1.45; color: #1a1a1a; }
h1 { font-size: 20pt; border-bottom: 2px solid #222; padding-bottom: 0.3em; }
h2 { font-size: 14pt; margin-top: 1.4em; border-bottom: 1px solid #ccc; padding-bottom: 0.2em; page-break-after: avoid; }
h3 { font-size: 11.5pt; page-break-after: avoid; }
blockquote { margin: 0.8em 0; padding: 0.5em 0.9em; background: #f5f7fa; border-left: 3px solid #4a6fa5; }
code, pre { font-family: "Noto Sans Mono CJK KR", monospace; font-size: 8.5pt; }
code { background: #f0f2f5; padding: 0.1em 0.3em; border-radius: 3px; }
pre { background: #111318; color: #e6e9ef; padding: 0.8em 1em; border-radius: 6px; white-space: pre-wrap; word-break: break-word; }
pre code { background: transparent; color: inherit; padding: 0; }
table { border-collapse: collapse; width: 100%; margin: 0.7em 0 1em; font-size: 9.5pt; page-break-inside: avoid; }
th, td { border: 1px solid #ccc; padding: 0.35em 0.5em; text-align: left; vertical-align: top; }
th { background: #eef2f7; }
img { max-width: 100%; height: auto; display: block; margin: 0.6em 0 1em; border: 1px solid #ddd; border-radius: 4px; page-break-inside: avoid; }
hr { border: none; border-top: 1px solid #ddd; margin: 1.5em 0; }
a { color: #1a5fb4; text-decoration: none; }
""")
out = Path("ENVIRONMENT-GUIDE.pdf")
HTML(string=html, base_url=".").write_pdf(out, stylesheets=[css])
print(f"wrote {out.resolve()} ({out.stat().st_size} bytes)")
PY
