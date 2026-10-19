<div align="center">

<h1>hetero-llm-d</h1>

<h3>One Kubernetes + llm-d cluster for GPU, NPU and CPU nodes</h3>

<p>
  <strong>English</strong> · <a href="README.ko.md">한국어</a>
</p>

<p>
  <a href="https://github.com/ai-computing/ai-rm"><img src="https://img.shields.io/badge/ai--rm-L4%20cluster%20%26%20placement-fbbf24" alt="ai-rm layer: L4 cluster and placement"></a>
  <a href="https://github.com/ai-computing/rm-core/blob/v0.1.1/PROTOCOL.md"><img src="https://img.shields.io/badge/protocol-v0.1-7c5cff" alt="Protocol v0.1"></a>
  <a href="#-architecture"><img src="https://img.shields.io/badge/target-Kubernetes%20%2B%20llm--d-326ce5?logo=kubernetes&amp;logoColor=white" alt="Target: Kubernetes and llm-d"></a>
  <a href="scripts"><img src="https://img.shields.io/badge/scripts-Bash%20%2B%20kubectl%20%2F%20Helm-4eaa25?logo=gnubash&amp;logoColor=white" alt="Scripts: Bash with kubectl and Helm"></a>
  <a href="STATUS.md"><img src="https://img.shields.io/badge/maturity-prototype-107e72" alt="Maturity: prototype"></a>
</p>

<p>
  <a href="#-quick-start"><b>Quick start</b></a> ·
  <a href="#-ai-rm-integration"><b>ai-rm</b></a> ·
  <a href="#-architecture"><b>Architecture</b></a> ·
  <a href="#-documentation"><b>Docs</b></a> ·
  <a href="STATUS.md"><b>Status</b></a>
</p>

</div>

---

**hetero-llm-d** (formerly `llm-d-setup`) holds the bootstrap scripts, manifests and operating notes that join NVIDIA A100, Rebellions
ATOM (RBLN-CA22), Furiosa RNGD and CPU nodes into one Kubernetes 1.31 cluster, served through llm-d
(Gateway → InferencePool → EPP) with a shared model store and Prometheus/Grafana monitoring. It is the
**L4 cluster & placement** component of [ai-rm](https://github.com/ai-computing/ai-rm): the cluster the
other ai-rm components run on, plus the protocol v0.1 pieces they meet in.

The repository is site-oriented and a **prototype**: it records one lab cluster. Site values (addresses,
CIDRs, shares) live only in an untracked `cluster.local.env`; tracked files use placeholders such as
`<cp-node-ip>` and `<gateway-host>`.

## ✨ Highlights

<table>
<tr>
<td width="33%" valign="top">
<b>Cluster bootstrap</b><br>
kubeadm 1.31, containerd 2.2.2, Cilium 1.16.5 with kube-proxy replacement and Gateway API CRDs v1.2.0, installed by numbered scripts (<code>scripts/01</code>–<code>05</code>).
</td>
<td width="33%" valign="top">
<b>Heterogeneous accelerators</b><br>
NVIDIA device plugin + DCGM, Rebellions NPU Operator and Furiosa device plugin side by side; workloads land on a vendor through device-plugin resources and nodeSelectors.
</td>
<td width="33%" valign="top">
<b>llm-d routing</b><br>
envoy-gateway with path-based HTTPRoutes, one InferencePool + EPP per model pool (<code>manifests/epp/make-epp.sh</code>), and a mixed A100 · ATOM · RNGD pool test.
</td>
</tr>
<tr>
<td width="33%" valign="top">
<b>Shared model store</b><br>
One SMB-backed RWX PVC <code>model-store</code> for weights and compiled NPU artifacts, scanned every 10 minutes into the <code>model-inventory</code> ConfigMap that lmd-top reads.
</td>
<td width="33%" valign="top">
<b>Monitoring</b><br>
kube-prometheus-stack with DCGM, Furiosa, RBLN, vLLM, EPP and IPMI wall-power exporters, Grafana dashboards, and a docker-compose stack for a single GPU node without Kubernetes.
</td>
<td width="33%" valign="top">
<b>ai-rm protocol v0.1</b><br>
<code>scripts/airm-install.sh</code> installs the <code>AcceleratorProfile</code> CRD pinned from rm-core v0.1.1, the <code>airm_*</code> scrape, the <code>airm-placement</code> ConfigMap and a Grafana dashboard.
</td>
</tr>
</table>

## 🚀 Quick start

Configure the site and run the checks that need no cluster or accelerator:

```bash
git clone https://github.com/ai-computing/hetero-llm-d.git ~/llm-d-setup && cd ~/llm-d-setup   # scripts and notes use this path
cp cluster.example.env cluster.local.env          # untracked; fill in site values
python3 scripts/test-model-store-discovery.py      # offline regression test for model-store discovery
bash -n scripts/*.sh manifests/epp/make-epp.sh     # shell syntax check
```

Scripts read `cluster.local.env` through `scripts/lib/cluster-env.sh`. Values already in the environment win,
and a script fails immediately when a value it needs is missing. The placeholders used in the docs are
explained in [`cluster.example.env`](cluster.example.env).

| Variable | Used by |
|---|---|
| `LLMD_CP_IP`, `LLMD_POD_CIDR`, `LLMD_SVC_CIDR` | `scripts/02-cp-init-cluster.sh` (kubeadm init) |
| `LLMD_GATEWAY_HOST` | `manifests/epp/make-epp.sh` health test (override with `GW_ADDR`) |
| `LLMD_PROM_ADDR` | `scripts/capture-lmd-top.sh`, lmd-top `LMD_PROM` |
| `LLMD_MODEL_STORE_SMB` | `manifests/model-store.yaml` (`scripts/render-manifest.sh manifests/model-store.yaml \| kubectl apply -f -`) |

<details>
<summary><b>Bootstrap the cluster (root, manual)</b></summary>
<br>

Cluster bootstrap needs root on each node, so there is no automated install step.

**1. Control-plane node** (sudo):

```bash
sudo bash ~/llm-d-setup/scripts/01-cp-install-tooling.sh
sudo bash ~/llm-d-setup/scripts/02-cp-init-cluster.sh
```

`02-cp-init-cluster.sh` ends by printing `kubeadm join <cp-node-ip>:6443 --token ... --discovery-token-ca-cert-hash sha256:...`.
**Copy that line.**

**2. Each worker node** (sudo):

```bash
scp ~/llm-d-setup/scripts/03-worker-install.sh <user>@<worker-ip>:/tmp/
ssh <user>@<worker-ip> 'sudo bash /tmp/03-worker-install.sh'
ssh <user>@<worker-ip> 'sudo kubeadm join <cp-node-ip>:6443 --token <...> --discovery-token-ca-cert-hash sha256:<...>'
```

**3. Check the join** on the control-plane node:

```bash
kubectl get nodes -o wide
kubectl get pods -A
```

Accelerator nodes then need their vendor pieces: `scripts/04-build-vllm-rbln.sh` builds the node-local
`vllm-rbln:0.10.2` image on the RBLN node and imports it into containerd (no registry), and
`scripts/05-nvidia-setup.sh` reloads the NVIDIA modules and installs nvidia-container-toolkit on the A100 node.
</details>

<details>
<summary><b>What each bootstrap script does</b></summary>
<br>

**`01-cp-install-tooling.sh`**
- swap off (persistent), kernel modules (`overlay`, `br_netfilter`), three sysctls (`br-nf-call-iptables`, `br-nf-call-ip6tables`, `ip_forward`)
- containerd 2.2.2 + runc 1.4.0 + helpers (`conntrack`, `socat`, `ethtool`, `ebtables`, `jq`)
- containerd config: `SystemdCgroup=true`, `sandbox_image=registry.k8s.io/pause:3.10`
- pkgs.k8s.io v1.31 apt repo → `kubeadm/kubelet/kubectl 1.31.*` + `apt-mark hold`
- crictl endpoint configuration

**`02-cp-init-cluster.sh`**
- `kubeadm init --apiserver-advertise-address=<cp-node-ip> --pod-network-cidr=<pod-cidr> --service-cidr=<svc-cidr> --skip-phases=addon/kube-proxy --node-name=<lower-case hostname>`
- copies the kubeconfig to `/root/.kube/config` and to the admin user's `~/.kube/config` (`USER_HOME` at the top of the script; edit it for your site)
- installs the Gateway API CRDs (v1.2.0 standard)
- downloads the Cilium CLI and installs Cilium 1.16.5 (`kubeProxyReplacement=true`, `gatewayAPI.enabled=true`, Hubble UI)
- prints the `kubeadm join` command for workers

**`03-worker-install.sh`**
- the same node preparation on the worker, plus kubelet/kubeadm 1.31 only (no kubectl)
- if containerd is already installed, only refreshes its config
- prints the join command at the end (paste the real token from step 2)
</details>

<details>
<summary><b>Call the models (OpenAI-compatible)</b></summary>
<br>

The llm-d Gateway at `<gateway-host>` is the single entry point; HTTPRoutes branch by path.

```bash
# RBLN: EXAONE-3.5-7.8B (Korean-friendly)
curl -X POST http://<gateway-host>/exaone/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"exaone-3.5-7.8b-instruct","messages":[{"role":"user","content":"..."}]}'

# Furiosa: Llama-3.1-8B (precompiled)
curl -X POST http://<gateway-host>/llama31/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"furiosa-ai/Llama-3.1-8B-Instruct","messages":[{"role":"user","content":"..."}]}'

# NVIDIA A100: Llama-3.1-8B (vllm-openai)
curl -X POST http://<gateway-host>/gpu/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"llama-3.1-8b-instruct-gpu","messages":[{"role":"user","content":"..."}]}'
```

| Path | Model | Accelerator | Node |
|---|---|---|---|
| `/exaone` | EXAONE-3.5-7.8B-Instruct | Rebellions RBLN-CA22 × 4 | NPU node |
| `/llama31` | Llama-3.1-8B-Instruct | Furiosa RNGD × 4 | GPU/NPU node |
| `/gpu` | Llama-3.1-8B-Instruct | NVIDIA A100 80GB × 2 | GPU/NPU node (the NPU node before 2026-10) |

A model server can also be called directly on its NodePort, e.g. with the Python OpenAI SDK:

```python
from openai import OpenAI
client = OpenAI(
    base_url="http://<cp-node-ip>:30800/v1",
    api_key="dummy"   # any value when vLLM runs without auth
)
resp = client.chat.completions.create(
    model="exaone-3.5-7.8b-instruct",
    messages=[{"role": "user", "content": "What is a Rebellions NPU?"}],
)
print(resp.choices[0].message.content)
```

Which models are up changes over time; most model Deployments are kept at `replicas: 0` and scaled up when
needed. See [STATUS.md](STATUS.md).
</details>

<details>
<summary><b>Web UIs and NodePorts</b> (2026-06 snapshot)</summary>
<br>

| UI | URL | Auth |
|---|---|---|
| Headlamp | `http://<cp-node-ip>:30502` | Bearer token: `kubectl create token headlamp -n headlamp --duration=24h` |
| Cilium Hubble UI | `http://<cp-node-ip>:30081` | none |
| Grafana | `http://<cp-node-ip>:30300` | admin account set at install (not recorded in docs) |
| Prometheus | `http://<cp-node-ip>:30090` | none |
| **Rancher** | `https://<cp-node-ip>:30443` | admin account (password changed at first login, not recorded in docs) |
| **llm-d Gateway** | `http://<gateway-host>/v1` | OpenAI-compatible single entry point (path routing) |
| ds4 (DeepSeek V4 Flash) direct | `http://<cp-node-ip>:30804/v1` | model: `deepseek-v4-flash` |
| vllm-rbln-koni direct | `http://<cp-node-ip>:30800/v1` | model: `koni-llama3.1-8b-rbln` |
| ollama-cpu direct | `http://<cp-node-ip>:30803/v1` | CPU pool |

NodePorts are exposed on every node. Rancher RBAC, LoadBalancer IP policy and troubleshooting notes:
[docs/cluster-notes.md](docs/cluster-notes.md) (Korean).
</details>

## 🔌 ai-rm integration

This repository is the **`l4-cluster` layer, kind `cluster`** of [ai-rm](https://github.com/ai-computing/ai-rm);
its metadata is in [`ai-rm.yaml`](ai-rm.yaml). It **provides** `Placement` (Gateway → InferencePool → EPP routing,
nodeSelector-based accelerator placement) and `Metrics` (Prometheus/Grafana and accelerator and node wall-power
exporters), and **uses** `Accelerator` (node device plugins) and `Workload` (the serving and training workloads on top).
It collects `airm_*` metrics but emits none itself.

The cluster side of [rm-core PROTOCOL v0.1](https://github.com/ai-computing/rm-core/blob/v0.1.1/PROTOCOL.md) lives in
[`deploy/airm/`](deploy/airm/README.md) and is applied by `scripts/airm-install.sh`:

| Piece | Where |
|---|---|
| `AcceleratorProfile` CRD (`airm.ai-computing.io/v1alpha1`) | fetched by `scripts/airm-install.sh` from rm-core tag `v0.1.1`, sha256-checked (no copy in this repo) |
| `airm_*` metrics scrape | `deploy/airm/scrape-airm.yaml`: ScrapeConfig for pods annotated `airm.ai-computing.io/scrape: "true"` (`/metrics`, default port 9400) |
| `airm_*` dashboard | `monitoring/grafana-dashboards/airm.json` (ConfigMap `grafana-dashboard-airm`) |
| Placement hand-off | `deploy/airm/airm-placement.yaml`: ConfigMap `llm-serving/airm-placement`, installed empty |
| Umbrella chart cluster values | `deploy/helm/cluster-values.yaml` |

```bash
scripts/airm-install.sh dry-run              # server dry-run: CRD + ScrapeConfig + ConfigMap + dashboard
scripts/airm-install.sh apply crd            # install the CRD
scripts/airm-install.sh apply manifests      # scrape config, airm-placement, dashboard
# rollback (deleting the CRD also deletes every AcceleratorProfile object)
scripts/airm-install.sh delete manifests
scripts/airm-install.sh delete crd
```

The `airm-placement` ConfigMap is written by ai-rm's
[rm-controller](https://github.com/ai-computing/ai-rm/tree/master/packages/rm-controller) and read by
serving pods and, later, an EPP scorer. It holds one key, `decisions.json`: a `protocol`, a `generation` counter,
the `placement` policy name and a `decisions` list of `{pool, workload, acceleratorIds, kvTransport, reason}`.
Accelerators are referenced by id only, never by address. An empty `decisions` list (the installed state) means
"behave as if the ConfigMap did not exist". The full format, field table and the EPP scorer slot (documented, not
yet implemented; v0.1 changes no live EPP config) are in [deploy/airm/README.md](deploy/airm/README.md).

<details>
<summary><b>Where other ai-rm components attach</b></summary>
<br>

| Component | Layer | How it attaches to this cluster |
|---|---|---|
| rngd-pd | l3-serving | runs prefill/decode pods on the RNGD nodes, creates its own InferencePool + EPP and adds a Gateway path (`manifests/epp/make-epp.sh <pool> /<path>`) |
| npu-lora | l3-serving | submits training Jobs to the RNGD nodes (privileged, `lmd-top --plan train … --apply`); models and adapters use the shared `model-store` PVC ([manifests/README-model-store.md](manifests/README-model-store.md)), and the A100 vLLM (`manifests/vllm-a100-llama31-8b.yaml`, `--enable-lora`) loads adapters at runtime |
| lmd-top | l5-ops | TUI on the control plane that reads only kubectl and Prometheus: `LMD_PROM=$LLMD_PROM_ADDR LMD_NS=llm-serving lmd-top` |
| rm-bench | l5-ops | drives OpenAI-compatible load at the Gateway (`http://$LLMD_GATEWAY_HOST/<path>/v1`); same-load energy comparison is `scripts/hetero-sweep.py` |
| monitoring (`monitoring/`) | l4-cluster | kube-prometheus-stack + DCGM/Furiosa/RBLN exporters + ServiceMonitors (`manifests/*servicemonitor.yaml`, `ipmi-exporter.yaml`) collect metrics, and `monitoring/grafana-dashboards/` is loaded into Grafana; `monitoring/standalone-compose/` is for a single GPU node without Kubernetes |

KPIs tracked here: heterogeneous resources (A100 · ATOM · RNGD · GB10 · CPU behind one Gateway), power efficiency
(tok/J from DCGM and IPMI wall power, `scripts/hetero-sweep.py`) and SLO (EPP TTFT/TPOT metrics).
</details>

## 🏗 Architecture

```
                 ┌────────────────────────────────────────┐
                 │  control-plane node (Dell R7525)       │
                 │  ─ management only, no workloads       │
                 │  ─ K8s control plane (kubeadm 1.31)    │
                 │  ─ Cilium CNI + Gateway API            │
                 │  ─ llm-d Router (Envoy + EPP)          │
                 │  ─ Prometheus / Grafana                │
                 └───────────────────┬────────────────────┘
                                     │
          ┌──────────────────────────┼──────────────────────────┐
          │                          │                          │
 ┌────────▼─────────┐      ┌─────────▼────────┐      ┌──────────▼─────────┐
 │ NPU node         │      │ GPU/NPU node     │      │ CPU nodes × 3      │
 │ RBLN-CA22 × 4    │      │ Furiosa RNGD × 2 │      │ ollama CPU pool    │
 │ Furiosa RNGD × 3 │      │ A100 80GB × 2    │      │                    │
 │ Ubuntu 22.04     │      │ Ubuntu 22.04     │      │                    │
 └──────────────────┘      └──────────────────┘      └────────────────────┘
```

Request path: client → `envoy-gateway` (`llm-d-gateway`) → `HTTPRoute` path routing (`manifests/openai-route.yaml`,
`manifests/llm-d-gateway.yaml`) → `InferencePool` → EPP ([`manifests/epp/`](manifests/epp/README.md),
`manifests/llmd-router-values.yaml`) → model-server pods in namespace `llm-serving`. `manifests/` is not a kustomize
tree: it is a set of files applied one by one with `kubectl apply` or used as Helm values.

Cluster facts: Kubernetes `v1.31` (compatible with the Gateway API Inference Extension), pod and service CIDRs chosen
not to collide with site routing, outbound access to huggingface.co and github.com. Two GB10 nodes are also
configured (`cluster.example.env`); see [STATUS.md](STATUS.md) for which nodes are currently healthy.

## 📚 Documentation

| Goal | Guides |
|---|---|
| 🧭 **Get oriented** | [Environment guide](docs/ENVIRONMENT-GUIDE.md) · [Status and findings](STATUS.md) |
| 🧩 **What runs where** | [llm-d features and per-worker matrix](FEATURES.md) · [NPU compatibility report](NPU-FEATURES.md) · [Serving playbook](PLAYBOOK.md) |
| 🔧 **Operate** | [EPP per InferencePool](manifests/epp/README.md) · [Shared model store](manifests/README-model-store.md) · [Monitoring](monitoring/README.md) · [Cluster notes](docs/cluster-notes.md) |
| 🔌 **ai-rm** | [deploy/airm](deploy/airm/README.md) · [`ai-rm.yaml`](ai-rm.yaml) · [ai-rm hub](https://github.com/ai-computing/ai-rm) |
| 📊 **Experiments** | [Mixed A100 · ATOM · RNGD pool](experiments/2026-10-19-hetero-llama8b-mixed-pool.md) · [airm-install hang](experiments/2026-10-19-airm-install-hang.md) |

Most guides are written in Korean. External references: [llm-d docs](https://llm-d.ai/docs) ·
[Gateway API Inference Extension](https://github.com/kubernetes-sigs/gateway-api-inference-extension) ·
[Cilium Gateway API](https://docs.cilium.io/en/stable/network/servicemesh/gateway-api/) · vllm-rbln (Rebellions'
vLLM fork, using compiled models from HF Hub `rebellions-sw/*`).

## 🗺 Status

- [x] Control plane and workers joined (kubeadm 1.31, Cilium 1.16.5, Gateway API); NVIDIA, Rebellions and Furiosa device plugins
- [x] Gateway → InferencePool → EPP routing per model pool; K-EXAONE-236B served on RNGD × 4 through llm-d (2026-07)
- [x] Shared model store with inventory discovery and build provenance
- [x] Monitoring stack with GPU, NPU, vLLM, EPP and IPMI wall-power exporters
- [x] ai-rm v0.1: `AcceleratorProfile` CRD installed on the cluster; scrape config, `airm-placement` and dashboard pass server dry-run
- [x] One InferencePool routing Llama-3.1-8B across A100, ATOM and RNGD ([experiment](experiments/2026-10-19-hetero-llama8b-mixed-pool.md)); the default EPP scores ignore device speed, so the mixed pool was slower than A100 alone
- [ ] Capacity-aware heterogeneous EPP scorer, compared under the same load
- [ ] Same-load energy comparison across accelerators (`scripts/hetero-sweep.py`; only A100 points measured so far)
- [ ] EPP scorer that reads `airm-placement`

Open issues, node outages and the measurements behind each item: [STATUS.md](STATUS.md).

> [!NOTE]
> This repository is public. Keep site configuration, internal addresses and credentials out of tracked files;
> site values live only in the untracked `cluster.local.env`.
