import json, random, urllib.request, concurrent.futures as cf
random.seed(11)
import os
# Pod IPs: POD_A100=… POD_RBLN=… POD_RNGD=… (kubectl get pods -l hetero-l8b/vendor -o wide)
pods = {v: os.environ[f"POD_{v.upper()}"] for v in ("a100", "rbln", "rngd")}
qs = [(random.randint(11, 99), random.randint(11, 99)) for _ in range(40)]
def ask(ip, a, b):
    body = {"model": "meta-llama/Llama-3.1-8B-Instruct", "temperature": 0, "max_tokens": 12,
            "messages": [{"role": "user", "content": f"What is {a}*{b}? Answer with just the number."}]}
    r = urllib.request.urlopen(urllib.request.Request(f"http://{ip}:8000/v1/chat/completions", json.dumps(body).encode(), {"content-type": "application/json"}), timeout=120)
    return json.load(r)["choices"][0]["message"]["content"].strip()
res = {}
for v, ip in pods.items():
    with cf.ThreadPoolExecutor(4) as ex:
        res[v] = list(ex.map(lambda q: ask(ip, *q), qs))
for v in pods:
    ok = sum(str(a*b) in t.replace(",", "") for (a, b), t in zip(qs, res[v]))
    print(v, "correct", ok, "/", len(qs))
for x, y in [("a100", "rngd"), ("a100", "rbln"), ("rngd", "rbln")]:
    print(x, "vs", y, "identical", sum(p == q for p, q in zip(res[x], res[y])), "/", len(qs))
print([(f"{a}*{b}", res["a100"][i], res["rngd"][i], res["rbln"][i]) for i, (a, b) in enumerate(qs) if len({res[v][i] for v in pods}) > 1][:6])
