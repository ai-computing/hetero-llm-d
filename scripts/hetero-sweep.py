#!/usr/bin/env python3
"""이종 가속기 × 실행 구성 에너지 sweep (Llama-3.1-8B, 같은 부하).

각 구성에 동시 요청 N 개를 DUR 초 동안 closed-loop 로 넣고, 그 구성에 **배정된 카드**의
전력을 exporter 에서 1초마다 직접 읽어 적분한다(Prometheus 의 15~30s 스크랩은 너무 거칠다).
카드는 exporter 가 붙이는 pod 라벨로 고르므로, 놀고 있어도 배정된 카드는 포함된다.
노드 전체(IPMI) 전력은 다른 사용자 작업이 섞이므로 보정용 참고값으로만 기록한다.

  python3 scripts/hetero-sweep.py --list
  python3 scripts/hetero-sweep.py -c a100-vllm,rngd-solo-B8 --dur 60 -o results.jsonl

부하: 프롬프트 약 241 토큰 + 출력 128 토큰. rngd_pd 런타임이 S=512 로 컴파일돼 있어
모든 구성을 그 안에 맞춘다. 구성의 Deployment 는 미리 띄워 둬야 한다(이 스크립트는
클러스터를 바꾸지 않는다).
"""
import argparse
import json
import os
import re
import subprocess
import sys
import threading
import time
import urllib.request

NS = "llm-serving"
MODEL = "meta-llama/Llama-3.1-8B-Instruct"
PROMPT = " ".join(["energy"] * 240)
OUT_TOK = 128

def site(var):
    """Site value (node names): environment first, then the untracked cluster.local.env."""
    if os.environ.get(var):
        return os.environ[var]
    env = os.environ.get("LLMD_ENV_FILE") or os.path.join(os.path.dirname(__file__), "..", "cluster.local.env")
    try:
        with open(env, encoding="utf-8") as f:
            for line in f:
                k, sep, v = line.strip().partition("=")
                if sep and k == var:
                    return v
    except OSError:
        pass
    return None  # IPMI wall power is then left out; it is only a reference value


NODE_NPU1, NODE_NPU2 = site("LLMD_NODE_NPU1"), site("LLMD_NODE_NPU2")

# name -> (endpoint pod 접두사, 요청 필드, 배정 카드 pod 정규식, IPMI 노드, 기본 동시성)
CONFIGS = {
    "a100-vllm": ("vllm-a100-llama31-8b", {"model": MODEL, "ignore_eos": True, "min_tokens": OUT_TOK},
                  r"^vllm-a100-llama31-8b-", NODE_NPU2, [1, 4, 8, 16, 32, 64]),
    "rngd-solo-B8": ("hetero-pd-gateway", {"model": "llama8b-solo"},
                     r"^sw-rngd-solo-", NODE_NPU1, [1, 4, 8, 16]),
    "atom-pd-B1": ("hetero-pd-gateway", {"model": "llama8b-atom-alone", "batch": 1},
                   r"^sw-atom-(prefill|decode-b1)-", NODE_NPU1, [1, 2]),
    "atom-pd-B2": ("hetero-pd-gateway", {"model": "llama8b-atom-alone", "batch": 2},
                   r"^sw-atom-(prefill|decode-b2)-", NODE_NPU1, [2, 4]),
    "atom-pd-B4": ("hetero-pd-gateway", {"model": "llama8b-atom-alone", "batch": 4},
                   r"^sw-atom-(prefill|decode-b4)-", NODE_NPU1, [4, 8]),
}

# (namespace, pod 이름 접두사, 포트) — 카드 전력 exporter. 노드마다 하나씩 있으면 전부 읽는다.
POWER_EXPORTERS = [("rbln-system", "rbln-metrics-exporter-", 9090),
                   ("furiosa-system", "furiosa-metrics-exporter-", 6254),
                   ("nvidia-device-plugin", "dcgm-exporter-", 9400)]
POWER_RE = re.compile(r'^(RBLN_DEVICE_STATUS:CARD_POWER|furiosa_npu_hw_power|DCGM_FI_DEV_POWER_USAGE)'
                      r'\{(.*?)\}\s+([0-9.eE+-]+)')
POD_RE = re.compile(r'(?:^|,)(?:exported_)?pod="([^"]+)"')


def running_pods(ns):
    out = subprocess.run(["kubectl", "-n", ns, "get", "pods", "-o", "json"],
                         check=True, capture_output=True, text=True).stdout
    return [(p["metadata"]["name"], p["status"].get("podIP"), p["spec"].get("nodeName"))
            for p in json.loads(out)["items"] if p["status"].get("phase") == "Running"]


def ready_nodes():
    out = subprocess.run(["kubectl", "get", "nodes", "-o", "json"],
                         check=True, capture_output=True, text=True).stdout
    return {n["metadata"]["name"] for n in json.loads(out)["items"]
            if any(c["type"] == "Ready" and c["status"] == "True" for c in n["status"]["conditions"])}


def discover():
    # NotReady 노드의 exporter 는 phase=Running 으로 남아 있어도 응답이 없어서, 읽을 때마다
    # timeout 만큼 1초 샘플링을 늦춘다 — 빼고 시작한다.
    ready = ready_nodes()
    power = [f"http://{ip}:{port}/metrics"
             for ns, prefix, port in POWER_EXPORTERS
             for name, ip, node in running_pods(ns) if name.startswith(prefix) and ip and node in ready]
    wall = {node: f"http://{ip}:9290/metrics"
            for name, ip, node in running_pods("monitoring") if name.startswith("ipmi-exporter-") and ip}
    serving = running_pods(NS)
    return power, wall, serving


def fetch(url, timeout=3):
    return urllib.request.urlopen(url, timeout=timeout).read().decode()


def card_power(power_urls, pods_re):
    tot, n = 0.0, 0
    for u in power_urls:
        try:
            body = fetch(u)
        except Exception:
            continue
        for line in body.splitlines():
            m = POWER_RE.match(line)
            if m and any(re.search(pods_re, p) for p in POD_RE.findall(m.group(2))):
                tot += float(m.group(3))
                n += 1
    return tot, n


def wall_power(url):
    try:
        for line in fetch(url, timeout=10).splitlines():
            if line.startswith("ipmi_dcmi_power_consumption_watts "):
                return float(line.split()[1])
    except Exception:
        pass
    return float("nan")


class Sampler(threading.Thread):
    """카드 전력은 1초, 노드 전력은 5초 간격으로 기록한다."""

    def __init__(self, power_urls, pods_re, wall_url):
        super().__init__(daemon=True)
        self.power_urls, self.pods_re, self.wall_url = power_urls, pods_re, wall_url
        self.cards, self.walls = [], []
        self.stop_ev = threading.Event()

    def run(self):
        last_wall = 0.0
        while not self.stop_ev.is_set():
            t = time.time()
            w, n = card_power(self.power_urls, self.pods_re)
            self.cards.append((t, w, n))
            if self.wall_url and t - last_wall >= 5:
                self.walls.append((t, wall_power(self.wall_url)))
                last_wall = t
            self.stop_ev.wait(max(0.0, 1.0 - (time.time() - t)))

    def window(self, t0, t1):
        s = [x for x in self.cards if t0 <= x[0] <= t1]
        e = sum((b[0] - a[0]) * (a[1] + b[1]) / 2 for a, b in zip(s, s[1:]))
        span = s[-1][0] - s[0][0] if len(s) > 1 else 0
        avg = e / span if span else float("nan")
        walls = [w for t, w in self.walls if t0 <= t <= t1 and w == w]
        return {"card_W": avg, "card_J": avg * (t1 - t0), "cards": s[0][2] if s else 0,
                "samples": len(s), "distinct": len({round(x[1], 1) for x in s}),
                "wall_W_ref": sum(walls) / len(walls) if walls else None}


def client(url, body, stop, stats, errs):
    data = json.dumps(dict(prompt=PROMPT, max_tokens=OUT_TOK, temperature=0, **body)).encode()
    while time.time() < stop:
        t0 = time.time()
        try:
            req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
            d = json.load(urllib.request.urlopen(req, timeout=900))
            stats.append((t0, time.time(), d["usage"]["completion_tokens"], d["usage"]["prompt_tokens"]))
        except Exception as e:
            errs.append(repr(e)[:200])
            time.sleep(1)


def run_point(name, url, body, conc, dur, smp):
    stats, errs = [], []
    t0 = time.time()
    threads = [threading.Thread(target=client, args=(url, body, t0 + dur, stats, errs)) for _ in range(conc)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()                      # 진행 중 요청은 끝까지 기다린다 — 그 에너지도 이 점의 몫
    t1 = time.time()
    time.sleep(1.5)                   # 마지막 1초 샘플 확보
    p = smp.window(t0, t1)
    toks = sum(s[2] for s in stats)
    el = t1 - t0
    lat = sorted(s[1] - s[0] for s in stats)
    return {"config": name, "conc": conc, "reqs": len(stats), "errors": len(errs),
            "in_tok": stats[0][3] if stats else None, "out_tok": OUT_TOK, "elapsed_s": round(el, 1),
            "out_tok_s": round(toks / el, 2) if el else 0,
            "e2e_p50_s": round(lat[len(lat) // 2], 3) if lat else None,
            "e2e_p95_s": round(lat[int(len(lat) * 0.95)], 3) if lat else None,
            "cards": p["cards"], "card_W": round(p["card_W"], 1), "card_J": round(p["card_J"]),
            "J_per_tok": round(p["card_J"] / toks, 4) if toks else None,
            "tok_per_J": round(toks / p["card_J"], 3) if p["card_J"] else None,
            "wall_W_ref": round(p["wall_W_ref"]) if p["wall_W_ref"] else None,
            "power_samples": p["samples"], "power_distinct": p["distinct"],
            "first_err": errs[0] if errs else None, "ts": int(t0)}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-c", "--configs", default=",".join(CONFIGS), help="쉼표로 구분한 구성 이름")
    ap.add_argument("--conc", default="", help="동시성 목록(쉼표). 비우면 구성별 기본값")
    ap.add_argument("--dur", type=float, default=60, help="측정점당 부하 시간(초)")
    ap.add_argument("-o", "--out", default="hetero-sweep.jsonl")
    ap.add_argument("--list", action="store_true", help="구성과 발견된 엔드포인트만 출력")
    a = ap.parse_args()

    power, wall, serving = discover()
    print(f"# power exporters: {len(power)}  ipmi: {sorted(wall)}", file=sys.stderr)
    plan = []
    for name in a.configs.split(","):
        if name not in CONFIGS:
            sys.exit(f"unknown config {name!r}; have {sorted(CONFIGS)}")
        prefix, body, pods_re, node, conc = CONFIGS[name]
        ep = next((ip for n, ip, _ in serving if n.startswith(prefix + "-") and ip), None)
        print(f"# {name:14s} endpoint={ep or 'NOT RUNNING'} cards={pods_re} node={node}", file=sys.stderr)
        if ep:
            conc = [int(x) for x in a.conc.split(",")] if a.conc else conc
            plan.append((name, f"http://{ep}:8000/v1/completions", body, pods_re, wall.get(node), conc))
    if a.list or not plan:
        return
    for name, url, body, pods_re, wall_url, conc in plan:
        smp = Sampler(power, pods_re, wall_url)
        smp.start()
        time.sleep(3)
        for c in conc:
            rec = run_point(name, url, body, c, a.dur, smp)
            print(json.dumps(rec), flush=True)
            with open(a.out, "a") as f:
                f.write(json.dumps(rec) + "\n")
            time.sleep(10)
        smp.stop_ev.set()


if __name__ == "__main__":
    main()
