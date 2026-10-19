<div align="center">

<h1>hetero-llm-d</h1>

<h3>GPU·NPU·CPU 노드를 하나로 묶는 Kubernetes + llm-d 클러스터</h3>

<p>
  <a href="README.md">English</a> · <strong>한국어</strong>
</p>

<p>
  <a href="https://github.com/ai-computing/ai-rm"><img src="https://img.shields.io/badge/ai--rm-L4%20cluster%20%26%20placement-fbbf24" alt="ai-rm 계층: L4 클러스터·배치"></a>
  <a href="https://github.com/ai-computing/rm-core/blob/v0.1.1/PROTOCOL.md"><img src="https://img.shields.io/badge/protocol-v0.1-7c5cff" alt="Protocol v0.1"></a>
  <a href="#-아키텍처"><img src="https://img.shields.io/badge/target-Kubernetes%20%2B%20llm--d-326ce5?logo=kubernetes&amp;logoColor=white" alt="대상: Kubernetes와 llm-d"></a>
  <a href="scripts"><img src="https://img.shields.io/badge/scripts-Bash%20%2B%20kubectl%20%2F%20Helm-4eaa25?logo=gnubash&amp;logoColor=white" alt="스크립트: Bash, kubectl, Helm"></a>
  <a href="STATUS.md"><img src="https://img.shields.io/badge/maturity-prototype-107e72" alt="성숙도: 프로토타입"></a>
</p>

<p>
  <a href="#-빠른-시작"><b>빠른 시작</b></a> ·
  <a href="#-ai-rm-연동"><b>ai-rm</b></a> ·
  <a href="#-아키텍처"><b>아키텍처</b></a> ·
  <a href="#-문서"><b>문서</b></a> ·
  <a href="STATUS.md"><b>현황</b></a>
</p>

</div>

---

**hetero-llm-d**(이전 이름 `llm-d-setup`)는 NVIDIA A100, Rebellions ATOM(RBLN-CA22), Furiosa RNGD, CPU 노드를 하나의 Kubernetes 1.31
클러스터로 묶고 llm-d(Gateway → InferencePool → EPP)로 서빙하기 위한 부트스트랩 스크립트, 매니페스트, 운영 메모를
담고 있습니다. 공유 모델 스토어와 Prometheus/Grafana 모니터링도 포함합니다. [ai-rm](https://github.com/ai-computing/ai-rm)의
**L4 클러스터·배치** 구성요소로, 다른 ai-rm 구성요소가 올라가는 클러스터이자 protocol v0.1 구성 요소들이 만나는 자리입니다.

이 레포는 특정 사이트를 기록한 **프로토타입**입니다. 사이트 값(주소, CIDR, 공유 폴더)은 untracked `cluster.local.env`에만
두고, 추적 파일에는 `<cp-node-ip>`, `<gateway-host>` 같은 placeholder를 씁니다.

## ✨ 주요 기능

<table>
<tr>
<td width="33%" valign="top">
<b>클러스터 부트스트랩</b><br>
kubeadm 1.31, containerd 2.2.2, kube-proxy를 대체하는 Cilium 1.16.5와 Gateway API CRD v1.2.0을 번호 붙은 스크립트(<code>scripts/01</code>–<code>05</code>)로 설치합니다.
</td>
<td width="33%" valign="top">
<b>이기종 가속기</b><br>
NVIDIA device plugin + DCGM, Rebellions NPU Operator, Furiosa device plugin을 함께 운영합니다. 워크로드는 device plugin 리소스와 nodeSelector로 벤더를 골라 배치됩니다.
</td>
<td width="33%" valign="top">
<b>llm-d 라우팅</b><br>
envoy-gateway와 path 기반 HTTPRoute, 모델 풀마다 InferencePool + EPP 하나(<code>manifests/epp/make-epp.sh</code>), A100·ATOM·RNGD 혼합 풀 시험.
</td>
</tr>
<tr>
<td width="33%" valign="top">
<b>공유 모델 스토어</b><br>
가중치와 NPU 컴파일 산출물을 SMB 기반 RWX PVC <code>model-store</code> 하나에 두고, 10분마다 스캔해 lmd-top이 읽는 <code>model-inventory</code> ConfigMap으로 발행합니다.
</td>
<td width="33%" valign="top">
<b>모니터링</b><br>
kube-prometheus-stack에 DCGM·Furiosa·RBLN·vLLM·EPP·IPMI wall 전력 exporter와 Grafana 대시보드, 그리고 k8s 없는 단일 GPU 노드용 docker-compose 스택.
</td>
<td width="33%" valign="top">
<b>ai-rm protocol v0.1</b><br>
<code>scripts/airm-install.sh</code>가 rm-core v0.1.1에 고정한 <code>AcceleratorProfile</code> CRD, <code>airm_*</code> 수집 설정, <code>airm-placement</code> ConfigMap, Grafana 대시보드를 설치합니다.
</td>
</tr>
</table>

## 🚀 빠른 시작

사이트 값을 설정하고, 클러스터나 가속기 없이 도는 검사를 실행합니다.

```bash
git clone https://github.com/ai-computing/hetero-llm-d.git ~/llm-d-setup && cd ~/llm-d-setup   # 스크립트와 문서가 이 경로를 씀
cp cluster.example.env cluster.local.env          # untracked, 사이트 값을 채운다
python3 scripts/test-model-store-discovery.py      # 모델 스토어 discovery 오프라인 회귀 테스트
bash -n scripts/*.sh manifests/epp/make-epp.sh     # 셸 스크립트 문법 검사
```

스크립트는 `scripts/lib/cluster-env.sh`로 `cluster.local.env`를 읽습니다. 이미 환경에 있는 값이 우선하고, 필요한 값이
없으면 스크립트가 바로 실패합니다. 문서에 쓰인 placeholder의 뜻은 [`cluster.example.env`](cluster.example.env) 주석에 있습니다.

| 변수 | 쓰는 곳 |
|---|---|
| `LLMD_CP_IP`, `LLMD_POD_CIDR`, `LLMD_SVC_CIDR` | `scripts/02-cp-init-cluster.sh` (kubeadm init) |
| `LLMD_GATEWAY_HOST` | `manifests/epp/make-epp.sh` 헬스 테스트 (`GW_ADDR`로 덮어쓰기 가능) |
| `LLMD_PROM_ADDR` | `scripts/capture-lmd-top.sh`, lmd-top `LMD_PROM` |
| `LLMD_MODEL_STORE_SMB` | `manifests/model-store.yaml` (`scripts/render-manifest.sh manifests/model-store.yaml \| kubectl apply -f -`) |

<details>
<summary><b>클러스터 부트스트랩 (root, 수동)</b></summary>
<br>

클러스터 부트스트랩은 노드마다 root 권한이 필요해 자동 설치 단계가 없습니다.

**1. control-plane 노드** (sudo):

```bash
sudo bash ~/llm-d-setup/scripts/01-cp-install-tooling.sh
sudo bash ~/llm-d-setup/scripts/02-cp-init-cluster.sh
```

`02-cp-init-cluster.sh` 마지막에 `kubeadm join <cp-node-ip>:6443 --token ... --discovery-token-ca-cert-hash sha256:...` 명령이
출력됩니다. **그 줄을 복사해 두세요.**

**2. 각 worker 노드** (sudo):

```bash
scp ~/llm-d-setup/scripts/03-worker-install.sh <user>@<worker-ip>:/tmp/
ssh <user>@<worker-ip> 'sudo bash /tmp/03-worker-install.sh'
ssh <user>@<worker-ip> 'sudo kubeadm join <cp-node-ip>:6443 --token <...> --discovery-token-ca-cert-hash sha256:<...>'
```

**3. join 확인** (control-plane 노드에서):

```bash
kubectl get nodes -o wide
kubectl get pods -A
```

가속기 노드에는 벤더 구성 요소가 더 필요합니다. `scripts/04-build-vllm-rbln.sh`는 RBLN 노드에서 노드 로컬 이미지
`vllm-rbln:0.10.2`를 빌드해 containerd에 넣고(레지스트리 없음), `scripts/05-nvidia-setup.sh`는 A100 노드에서 NVIDIA
모듈을 다시 올리고 nvidia-container-toolkit을 설치합니다.
</details>

<details>
<summary><b>부트스트랩 스크립트 요약</b></summary>
<br>

**`01-cp-install-tooling.sh`**
- swap off (영구), 커널 모듈 (`overlay`, `br_netfilter`), sysctl 3종 (`br-nf-call-iptables`, `br-nf-call-ip6tables`, `ip_forward`)
- containerd 2.2.2 + runc 1.4.0 + 보조 패키지 (`conntrack`, `socat`, `ethtool`, `ebtables`, `jq`)
- containerd config: `SystemdCgroup=true`, `sandbox_image=registry.k8s.io/pause:3.10`
- pkgs.k8s.io v1.31 apt repo → `kubeadm/kubelet/kubectl 1.31.*` 설치 + `apt-mark hold`
- crictl 엔드포인트 설정

**`02-cp-init-cluster.sh`**
- `kubeadm init --apiserver-advertise-address=<cp-node-ip> --pod-network-cidr=<pod-cidr> --service-cidr=<svc-cidr> --skip-phases=addon/kube-proxy --node-name=<소문자 hostname>`
- kubeconfig를 `/root/.kube/config`와 관리자 사용자의 `~/.kube/config`로 복사 (스크립트 맨 위 `USER_HOME`, 사이트에 맞게 수정)
- Gateway API CRDs (v1.2.0 standard) 설치
- Cilium CLI 다운로드 + Cilium 1.16.5 설치 (`kubeProxyReplacement=true`, `gatewayAPI.enabled=true`, Hubble UI 활성화)
- worker 노드용 `kubeadm join` 명령 출력

**`03-worker-install.sh`**
- worker 측에서 동일한 사전 설정 + kubelet/kubeadm 1.31만 설치 (kubectl 제외)
- containerd가 이미 깔려 있으면 config 갱신만 수행
- 마지막에 join 명령을 출력 (실제 토큰은 2단계 결과에서 가져와 붙임)
</details>

<details>
<summary><b>모델 호출 (OpenAI 호환)</b></summary>
<br>

`<gateway-host>`의 llm-d Gateway가 단일 진입점이고, HTTPRoute가 path로 분기합니다.

```bash
# RBLN: EXAONE-3.5-7.8B (한국어 친화)
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

| 경로 | 모델 | 가속기 | 노드 |
|---|---|---|---|
| `/exaone` | EXAONE-3.5-7.8B-Instruct | Rebellions RBLN-CA22 × 4 | NPU 노드 |
| `/llama31` | Llama-3.1-8B-Instruct | Furiosa RNGD × 4 | GPU·NPU 노드 |
| `/gpu` | Llama-3.1-8B-Instruct | NVIDIA A100 80GB × 2 | GPU·NPU 노드 (2026-10 이전엔 NPU 노드) |

모델 서버를 NodePort로 직접 부를 수도 있습니다. Python OpenAI SDK 예:

```python
from openai import OpenAI
client = OpenAI(
    base_url="http://<cp-node-ip>:30800/v1",
    api_key="dummy"   # vllm은 인증 미적용 시 아무 값
)
resp = client.chat.completions.create(
    model="exaone-3.5-7.8b-instruct",
    messages=[{"role": "user", "content": "Rebellions NPU란?"}],
)
print(resp.choices[0].message.content)
```

어떤 모델이 떠 있는지는 시점마다 다릅니다. 대부분의 모델 Deployment는 `replicas: 0`으로 두고 필요할 때 scale-up 합니다.
[STATUS.md](STATUS.md)를 보세요.
</details>

<details>
<summary><b>Web UI와 NodePort</b> (2026-06 스냅샷)</summary>
<br>

| UI | URL | 인증 |
|---|---|---|
| Headlamp | `http://<cp-node-ip>:30502` | Bearer token: `kubectl create token headlamp -n headlamp --duration=24h` |
| Cilium Hubble UI | `http://<cp-node-ip>:30081` | 없음 |
| Grafana | `http://<cp-node-ip>:30300` | 설치 시 정한 관리자 계정 (문서에 기록하지 않음) |
| Prometheus | `http://<cp-node-ip>:30090` | 없음 |
| **Rancher** | `https://<cp-node-ip>:30443` | 관리자 계정 (첫 로그인 시 비번 변경, 문서에 기록하지 않음) |
| **llm-d Gateway** | `http://<gateway-host>/v1` | OpenAI 호환 통합 entrypoint (path 분기) |
| ds4 (DeepSeek V4 Flash) 직결 | `http://<cp-node-ip>:30804/v1` | model: `deepseek-v4-flash` |
| vllm-rbln-koni 직결 | `http://<cp-node-ip>:30800/v1` | model: `koni-llama3.1-8b-rbln` |
| ollama-cpu 직결 | `http://<cp-node-ip>:30803/v1` | CPU 풀 |

NodePort는 모든 노드에서 같은 포트로 열립니다. Rancher RBAC, LoadBalancer IP 정책, 트러블슈팅 메모는
[docs/cluster-notes.md](docs/cluster-notes.md)에 있습니다.
</details>

## 🔌 ai-rm 연동

이 레포는 [ai-rm](https://github.com/ai-computing/ai-rm)의 **`l4-cluster` 계층, kind `cluster`** 구성요소이며, 메타데이터는
[`ai-rm.yaml`](ai-rm.yaml)에 있습니다. **제공**: `Placement`(Gateway → InferencePool → EPP 라우팅, nodeSelector 기반 가속기
배치), `Metrics`(Prometheus/Grafana, 가속기·노드 wall 전력 exporter). **사용**: `Accelerator`(노드 device plugin),
`Workload`(그 위에 올라가는 서빙·학습 워크로드). `airm_*` 지표는 수집만 하고 직접 내지 않습니다.

[rm-core PROTOCOL v0.1](https://github.com/ai-computing/rm-core/blob/v0.1.1/PROTOCOL.md)의 클러스터 쪽 구성은
[`deploy/airm/`](deploy/airm/README.md)에 있고 `scripts/airm-install.sh`가 적용합니다.

| 항목 | 위치 |
|---|---|
| `AcceleratorProfile` CRD (`airm.ai-computing.io/v1alpha1`) | `scripts/airm-install.sh`가 rm-core 태그 `v0.1.1`에서 받아 sha256 확인 후 적용 (사본 없음) |
| `airm_*` 지표 수집 | `deploy/airm/scrape-airm.yaml`: `airm.ai-computing.io/scrape: "true"` 어노테이션 pod의 `/metrics`(기본 포트 9400)를 수집하는 ScrapeConfig |
| `airm_*` 대시보드 | `monitoring/grafana-dashboards/airm.json` (ConfigMap `grafana-dashboard-airm`) |
| 배치 결정 전달 지점 | `deploy/airm/airm-placement.yaml`: ConfigMap `llm-serving/airm-placement`, 빈 상태로 설치 |
| umbrella chart 공통 값 | `deploy/helm/cluster-values.yaml` |

```bash
scripts/airm-install.sh dry-run              # 서버 dry-run: CRD + ScrapeConfig + ConfigMap + 대시보드
scripts/airm-install.sh apply crd            # CRD 설치
scripts/airm-install.sh apply manifests      # 수집 설정·airm-placement·대시보드
# 되돌리기 (CRD를 지우면 모든 AcceleratorProfile 객체도 함께 지워진다)
scripts/airm-install.sh delete manifests
scripts/airm-install.sh delete crd
```

`airm-placement` ConfigMap은 ai-rm의 [rm-controller](https://github.com/ai-computing/ai-rm/tree/master/packages/rm-controller)가
쓰고, 서빙 pod와 이후의 EPP scorer가 읽습니다. 키는 `decisions.json` 하나이며 `protocol`, `generation` 카운터, `placement`
정책 이름, `{pool, workload, acceleratorIds, kvTransport, reason}` 항목의 `decisions` 목록을 담습니다. 가속기는 주소가 아니라
id로만 가리킵니다. `decisions`가 비어 있으면(설치 직후 상태) ConfigMap이 없는 것처럼 동작합니다. 전체 형식, 필드 표,
EPP scorer 자리(문서로만 정의, 미구현이며 v0.1은 운영 중인 EPP 설정을 바꾸지 않음)는 [deploy/airm/README.md](deploy/airm/README.md)에 있습니다.

<details>
<summary><b>다른 ai-rm 구성요소가 붙는 자리</b></summary>
<br>

| 구성요소 | 계층 | 이 클러스터에 붙는 방식 |
|---|---|---|
| rngd-pd | l3-serving | RNGD 노드에 prefill/decode Pod를 띄우고, 자체 InferencePool + EPP를 만든 뒤 Gateway에 path를 추가한다 (`manifests/epp/make-epp.sh <pool> /<path>`) |
| npu-lora | l3-serving | RNGD 노드에 학습 Job(privileged, `lmd-top --plan train … --apply`)으로 제출한다. 모델·어댑터는 공유 모델 스토어 PVC `model-store`([manifests/README-model-store.md](manifests/README-model-store.md))를 쓰고, 어댑터는 A100 vLLM(`manifests/vllm-a100-llama31-8b.yaml`, `--enable-lora`)이 런타임에 적재한다 |
| lmd-top | l5-ops | control-plane에서 kubectl + Prometheus만 읽는 TUI. `LMD_PROM=$LLMD_PROM_ADDR LMD_NS=llm-serving lmd-top` |
| rm-bench | l5-ops | Gateway(`http://$LLMD_GATEWAY_HOST/<path>/v1`)에 OpenAI 호환 부하를 건다. 같은 부하 에너지 비교는 `scripts/hetero-sweep.py` |
| 모니터링 (`monitoring/`) | l4-cluster | kube-prometheus-stack + DCGM/Furiosa/RBLN exporter + ServiceMonitor(`manifests/*servicemonitor.yaml`, `ipmi-exporter.yaml`)가 지표를 모으고, `monitoring/grafana-dashboards/`를 Grafana에 올린다. `monitoring/standalone-compose/`는 k8s 없는 단일 GPU 노드용 |

여기서 추적하는 KPI: 이종자원수(A100·ATOM·RNGD·GB10·CPU를 한 Gateway로 서빙), 전력효율(DCGM·IPMI wall 전력으로 tok/J,
`scripts/hetero-sweep.py`), SLO(EPP 지표 TTFT/TPOT).
</details>

## 🏗 아키텍처

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

요청 경로: 클라이언트 → `envoy-gateway`(`llm-d-gateway`) → `HTTPRoute` path 분기(`manifests/openai-route.yaml`,
`manifests/llm-d-gateway.yaml`) → `InferencePool` → EPP([`manifests/epp/`](manifests/epp/README.md),
`manifests/llmd-router-values.yaml`) → `llm-serving` 네임스페이스의 모델 서버 Pod. `manifests/`는 kustomize 디렉터리가 아니라
개별 `kubectl apply` 파일과 Helm values 모음입니다.

클러스터 기본 사항: Kubernetes `v1.31`(Gateway API Inference Extension 호환), 사내 라우팅과 겹치지 않게 고른 pod·service
CIDR, huggingface.co·github.com 외부 접근 가능. GB10 노드 두 대도 구성돼 있습니다(`cluster.example.env`). 현재 정상인 노드는
[STATUS.md](STATUS.md)에서 확인하세요.

## 📚 문서

| 목적 | 문서 |
|---|---|
| 🧭 **처음 읽기** | [환경 가이드](docs/ENVIRONMENT-GUIDE.md) · [현황과 결과](STATUS.md) |
| 🧩 **무엇이 어디서 도는지** | [llm-d 기능과 worker별 매트릭스](FEATURES.md) · [NPU 호환성 보고서](NPU-FEATURES.md) · [서빙 플레이북](PLAYBOOK.md) |
| 🔧 **운영** | [InferencePool별 EPP](manifests/epp/README.md) · [공유 모델 스토어](manifests/README-model-store.md) · [모니터링](monitoring/README.md) · [클러스터 운영 메모](docs/cluster-notes.md) |
| 🔌 **ai-rm** | [deploy/airm](deploy/airm/README.md) · [`ai-rm.yaml`](ai-rm.yaml) · [ai-rm 허브](https://github.com/ai-computing/ai-rm) |
| 📊 **실험** | [A100·ATOM·RNGD 혼합 풀](experiments/2026-10-19-hetero-llama8b-mixed-pool.md) · [airm-install 멈춤](experiments/2026-10-19-airm-install-hang.md) |

외부 참고: [llm-d 문서](https://llm-d.ai/docs) ·
[Gateway API Inference Extension](https://github.com/kubernetes-sigs/gateway-api-inference-extension) ·
[Cilium Gateway API](https://docs.cilium.io/en/stable/network/servicemesh/gateway-api/) · vllm-rbln(Rebellions가 제공하는
vLLM 포크, HF Hub `rebellions-sw/*` 컴파일 모델 사용).

## 🗺 현황

- [x] control plane과 worker join (kubeadm 1.31, Cilium 1.16.5, Gateway API), NVIDIA·Rebellions·Furiosa device plugin
- [x] 모델 풀별 Gateway → InferencePool → EPP 라우팅, llm-d로 RNGD × 4에서 K-EXAONE-236B 서빙 (2026-07)
- [x] 인벤토리 discovery와 빌드 출처 정보를 갖춘 공유 모델 스토어
- [x] GPU·NPU·vLLM·EPP·IPMI wall 전력 exporter를 갖춘 모니터링 스택
- [x] ai-rm v0.1: `AcceleratorProfile` CRD를 클러스터에 설치, 수집 설정·`airm-placement`·대시보드는 서버 dry-run 통과
- [x] 한 InferencePool로 Llama-3.1-8B를 A100·ATOM·RNGD에 라우팅([실험](experiments/2026-10-19-hetero-llama8b-mixed-pool.md)). 기본 EPP 점수는 장치 속도를 보지 않아 혼합 풀이 A100 단독보다 느렸다
- [ ] 용량을 고려하는 이기종 EPP scorer를 같은 부하로 비교
- [ ] 가속기 간 같은 부하 에너지 비교 (`scripts/hetero-sweep.py`, 지금까지 A100만 측정)
- [ ] `airm-placement`를 읽는 EPP scorer

미해결 문제, 노드 장애, 각 항목의 측정 근거: [STATUS.md](STATUS.md).

> [!NOTE]
> 이 레포는 공개 저장소입니다. 사이트 설정, 내부 주소, 자격 증명은 추적 파일에 넣지 않습니다. 사이트 값은 untracked
> `cluster.local.env`에만 둡니다.
