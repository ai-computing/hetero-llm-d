#!/usr/bin/env python3
"""Concurrent varied-prompt load through the gateway; joins EPP decisions by x-request-id.

usage: hetero_load.py N CONCURRENCY OUT.json
"""
import concurrent.futures as cf
import json
import os
import random
import subprocess
import sys
import time
import urllib.request
import uuid
import os

MAXTOK = int(os.environ.get("MAXTOK", "24"))
UNIQUE_PREFIX = os.environ.get("UNIQUE_PREFIX") == "1"

GW = os.environ.get("GW", "http://GATEWAY") + "/hetero/llama8b/chat/completions"
N, CONC, OUT = int(sys.argv[1]), int(sys.argv[2]), sys.argv[3]
random.seed(7)
TOPICS = ["rivers", "volcanoes", "bridges", "orchestras", "glaciers", "satellites", "deserts", "libraries"]


def one(i):
    a, b = random.randint(11, 99), random.randint(11, 99)
    filler = " ".join(random.choice(TOPICS) for _ in range(random.randint(5, 60)))
    rid = str(uuid.uuid4())
    body = {
        "model": "meta-llama/Llama-3.1-8B-Instruct",
        "messages": [{"role": "user", "content": (f"[{uuid.uuid4().hex[:12]}] " if UNIQUE_PREFIX else "") + f"Context words (ignore them): {filler}.\nWhat is {a}*{b}? Answer with just the number." + (" Then explain the steps." if MAXTOK > 24 else "")}],
        "max_tokens": MAXTOK,
        "temperature": 0,
    }
    req = urllib.request.Request(GW, json.dumps(body).encode(), {"content-type": "application/json", "x-request-id": rid})
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            d = json.load(r)
        text = d["choices"][0]["message"]["content"].strip()
        ok = str(a * b) in d["choices"][0]["message"]["content"].replace(",", "")
        rid = d.get("id", "").removeprefix("chatcmpl-") or rid
        return {"rid": rid, "lat": time.time() - t0, "status": 200, "ok": ok, "text": text[:40],
                "ptok": d.get("usage", {}).get("prompt_tokens"), "ctok": d.get("usage", {}).get("completion_tokens")}
    except Exception as e:  # noqa: BLE001
        return {"rid": rid, "lat": time.time() - t0, "status": getattr(e, "code", 0), "ok": False, "text": str(e)[:80]}


def counters():
    pods = json.loads(subprocess.run(["kubectl", "-n", "llm-serving", "get", "pods", "-l", "hetero-l8b/vendor", "-o", "json"],
                                     capture_output=True, text=True).stdout)
    out = {}
    for p in pods["items"]:
        ip, v = p["status"].get("podIP"), p["metadata"]["labels"]["hetero-l8b/vendor"]
        try:
            text = urllib.request.urlopen(f"http://{ip}:8000/metrics", timeout=5).read().decode()
        except Exception:  # noqa: BLE001
            continue
        out[v] = sum(float(l.rsplit(" ", 1)[1]) for l in text.splitlines()
                     if l.startswith(("vllm:request_success_total", "furiosa_llm_request_success_total")))
    return out


before = counters()
t0 = time.time()
with cf.ThreadPoolExecutor(CONC) as ex:
    res = list(ex.map(one, range(N)))
wall = time.time() - t0
time.sleep(2)
after = counters()
served = {v: int(after[v] - before.get(v, 0)) for v in after}
logs = subprocess.run(["kubectl", "-n", "llm-serving", "logs", "deploy/hetero-l8b-epp", "--since=30m"],
                      capture_output=True, text=True).stdout
ep = {}
for line in logs.splitlines():
    if '"Request handled"' in line:
        d = json.loads(line)
        ep[d.get("x-request-id")] = d.get("endpoint")
pods = json.loads(subprocess.run(["kubectl", "-n", "llm-serving", "get", "pods", "-l", "app=hetero-l8b", "-o", "json"],
                                 capture_output=True, text=True).stdout)
vendor = {p["status"].get("podIP", "") + ":8000": p["metadata"]["labels"]["hetero-l8b/vendor"] for p in pods["items"]}
for r in res:
    r["endpoint"] = ep.get(r["rid"])
    r["vendor"] = vendor.get(r["endpoint"]) or ("rngd" if r["rid"].startswith("chat-") else "?")
summary = {}
for r in res:
    s = summary.setdefault(r["vendor"], {"n": 0, "ok": 0, "lat": []})
    s["n"] += 1
    s["ok"] += r["ok"]
    s["lat"].append(r["lat"])
for v, s in summary.items():
    lat = sorted(s.pop("lat"))
    s["p50"] = round(lat[len(lat) // 2], 2)
    s["max"] = round(lat[-1], 2)
print(json.dumps({"n": N, "conc": CONC, "wall_s": round(wall, 1), "req_s": round(N / wall, 2), "served_by_counter": served, "by_vendor": summary,
                  "errors": [r for r in res if r["status"] != 200][:3]}, indent=1))
json.dump(res, open(OUT, "w"), indent=1)
