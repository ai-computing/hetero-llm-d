#!/usr/bin/env python3
"""Markdown table of the prefix_load.py runs in a results directory.

usage: summarize.py results/
"""
import json
import pathlib
import sys

ORDER = ["queue-kv", "approx-prefix", "approx-prefix-w3", "precise-prefix", "precise-fixed", "precise-bs64"]
rows = []
for f in sorted(pathlib.Path(sys.argv[1]).glob("*.json")):
    s = json.load(open(f, encoding="utf-8"))["summary"]
    prof = next(p for p in sorted(ORDER, key=len, reverse=True) if f.stem.startswith(p + "-"))
    run = f.stem[len(prof) + 1:]
    split = "/".join(str(p["request_success"]) for p in s["pods"].values())
    rows.append((run, ORDER.index(prof), prof, s, split))
print("| workload | profile | prompt tok | conc | wall s | TTFT p50 | p90 | p99 | vLLM hit ratio | requests per pod | errors |")
print("|---|---|---:|---:|---:|---:|---:|---:|---:|---|---:|")
for run, _, prof, s, split in sorted(rows, key=lambda r: (r[0], r[1])):
    print(f"| {run} | {prof} | {s['prompt_tokens_mean']} | {s['conc']} | {s['wall_s']} | {s['ttft_p50']} | {s['ttft_p90']} "
          f"| {s['ttft_p99']} | {s['hit_ratio']} | {split} | {s['errors']} |")
