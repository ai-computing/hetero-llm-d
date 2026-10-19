#!/usr/bin/env python3
"""Shared-prefix load through the gateway: streaming TTFT plus per-pod vLLM prefix-cache deltas.

usage: prefix_load.py OUT.json
env:
  GW            gateway base incl. route, e.g. http://<gateway>:30788/gpu/llama8b  (-> /chat/completions)
  MODE          shared (default) | unique   unique = every request gets its own prefix (control)
  PREFIXES      number of distinct shared prefixes (shared mode), default 8
  PREFIX_WORDS  words per prefix, default 1100 (~1.5k Llama-3 tokens)
  N, CONC       requests and concurrency, default 256 / 16
  MAXTOK        output tokens, default 32
  SALT          makes the prefix texts unique per run, so a run never reuses an earlier run's cache
  POD_LABEL     pods to scrape, default app=vllm-a100-llama31-8b (namespace llm-serving)
"""
import concurrent.futures as cf
import json
import os
import random
import subprocess
import sys
import time
import urllib.request

GW = os.environ.get("GW", "http://GATEWAY/gpu/llama8b") + "/chat/completions"
MODE = os.environ.get("MODE", "shared")
PREFIXES = int(os.environ.get("PREFIXES", "8"))
PREFIX_WORDS = int(os.environ.get("PREFIX_WORDS", "1100"))
N = int(os.environ.get("N", "256"))
CONC = int(os.environ.get("CONC", "16"))
MAXTOK = int(os.environ.get("MAXTOK", "32"))
SALT = os.environ.get("SALT", str(int(time.time())))
POD_LABEL = os.environ.get("POD_LABEL", "app=vllm-a100-llama31-8b")
MODEL = "meta-llama/Llama-3.1-8B-Instruct"
OUT = sys.argv[1]

WORDS = ("river mountain signal theory engine market garden window silver orbit harbor canvas "
         "lantern meadow circuit violin glacier archive compass falcon granite quarry ribbon "
         "saddle thunder velvet whisper anchor beacon cobalt dune ember fjord harvest island "
         "jungle kettle lagoon marble nectar oasis pepper quartz raven summit timber umbra "
         "valley walnut yonder zephyr").split()


def prefix_text(key):
    rnd = random.Random(f"{SALT}/{key}")
    body = " ".join(rnd.choice(WORDS) for _ in range(PREFIX_WORDS))
    return f"You are assistant #{key} of run {SALT}. Reference notes follow; ignore them unless asked.\n{body}"


rnd = random.Random(SALT)
plan = []
for i in range(N):
    key = f"p{rnd.randrange(PREFIXES)}" if MODE == "shared" else f"u{i}"
    a, b = rnd.randint(11, 99), rnd.randint(11, 99)
    plan.append((i, key, a, b))
prefix_cache = {}


def one(item):
    i, key, a, b = item
    system = prefix_cache.get(key) or prefix_cache.setdefault(key, prefix_text(key))
    body = {"model": MODEL, "temperature": 0, "max_tokens": MAXTOK, "stream": True,
            "stream_options": {"include_usage": True},
            "messages": [{"role": "system", "content": system},
                         {"role": "user", "content": f"What is {a}*{b}? Answer with just the number."}]}
    req = urllib.request.Request(GW, json.dumps(body).encode(), {"content-type": "application/json"})
    t0 = time.time()
    ttft, text, usage = None, "", {}
    try:
        with urllib.request.urlopen(req, timeout=600) as r:
            for raw in r:
                line = raw.decode().strip()
                if not line.startswith("data:") or line == "data: [DONE]":
                    continue
                d = json.loads(line[5:])
                usage = d.get("usage") or usage
                for c in d.get("choices", []):
                    piece = c.get("delta", {}).get("content")
                    if piece:
                        ttft = ttft if ttft is not None else time.time() - t0
                        text += piece
        return {"i": i, "key": key, "status": 200, "ttft": ttft, "lat": time.time() - t0,
                "ok": str(a * b) in text.replace(",", ""), "ptok": usage.get("prompt_tokens")}
    except Exception as e:  # noqa: BLE001
        return {"i": i, "key": key, "status": getattr(e, "code", 0), "ttft": None,
                "lat": time.time() - t0, "ok": False, "err": str(e)[:120]}


COUNTERS = ("vllm:prefix_cache_hits_total", "vllm:prefix_cache_queries_total",
            "vllm:request_success_total", "vllm:prompt_tokens_total")


def counters():
    pods = json.loads(subprocess.run(["kubectl", "-n", "llm-serving", "get", "pods", "-l", POD_LABEL, "-o", "json"],
                                     capture_output=True, text=True, check=True).stdout)
    out = {}
    for p in pods["items"]:
        ip = p["status"].get("podIP")
        if not ip:
            continue
        try:
            text = urllib.request.urlopen(f"http://{ip}:8000/metrics", timeout=5).read().decode()
        except Exception:  # noqa: BLE001
            continue
        c = dict.fromkeys(COUNTERS, 0.0)
        for line in text.splitlines():
            name = line.split("{", 1)[0].split(" ", 1)[0]
            if name in c:
                c[name] += float(line.rsplit(" ", 1)[1])
        out[p["metadata"]["name"]] = c
    return out


def pct(xs, q):
    xs = sorted(xs)
    return round(xs[min(len(xs) - 1, int(q * len(xs)))], 3) if xs else None


before = counters()
t0 = time.time()
with cf.ThreadPoolExecutor(CONC) as ex:
    res = list(ex.map(one, plan))
wall = time.time() - t0
time.sleep(3)
after = counters()
pods = {}
for pod, c in after.items():
    d = {k.split(":", 1)[1].removesuffix("_total"): int(c[k] - before.get(pod, {}).get(k, 0)) for k in COUNTERS}
    d["hit_ratio"] = round(d["prefix_cache_hits"] / d["prefix_cache_queries"], 3) if d["prefix_cache_queries"] else None
    pods[pod[-5:]] = d
hits = sum(p["prefix_cache_hits"] for p in pods.values())
queries = sum(p["prefix_cache_queries"] for p in pods.values())
ttfts = [r["ttft"] for r in res if r["ttft"] is not None]
ptoks = [r["ptok"] for r in res if r.get("ptok")]
summary = {"mode": MODE, "prefixes": PREFIXES if MODE == "shared" else N, "prompt_tokens_mean": round(sum(ptoks) / len(ptoks)) if ptoks else None,
           "n": N, "conc": CONC, "maxtok": MAXTOK, "salt": SALT, "wall_s": round(wall, 1), "req_s": round(N / wall, 2),
           "errors": sum(r["status"] != 200 for r in res), "correct": sum(r["ok"] for r in res),
           "ttft_p50": pct(ttfts, 0.5), "ttft_p90": pct(ttfts, 0.9), "ttft_p99": pct(ttfts, 0.99),
           "lat_p50": pct([r["lat"] for r in res], 0.5), "hit_ratio": round(hits / queries, 3) if queries else None,
           "pods": pods}
print(json.dumps(summary, indent=1))
json.dump({"summary": summary, "requests": res}, open(OUT, "w"), indent=1)
