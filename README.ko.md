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
  <a href="#-캐시-인지-라우팅과-오토스케일"><b>라우팅·스케일</b></a> ·
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
| `LLMD_NODE_NPU1`, `LLMD_NODE_NPU2`, `LLMD_HOME` | `manifests/`의 노드 고정과 홈 디렉터리 hostPath (`compile-job`, `ds4-deepseek-v4-flash`, `hetero-llama8b-mixed`, `ipmi-exporter`, `vllm-a100-llama31-8b`, `vllm-exaone`, `vllm-rbln-deployment`, `vllm-v4flash`, `furiosa-*-modelservice-values` 두 개). `scripts/render-manifest.sh`로 렌더해 적용한다(helm은 `-f <(scripts/render-manifest.sh …)`). `scripts/hetero-sweep.py`도 노드 이름을 읽는다 |
| `LLMD_KUBE_USER` (선택) | `scripts/02-cp-init-cluster.sh`: kubeconfig를 받을 계정 (기본: sudo 실행 사용자) |

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
| 배치 반영 훅 | `scripts/airm-placement.py`, `scripts/airm-install.sh … placement`가 실행: `decisions.json`으로 node affinity와 KEDA 상한을 건다 |
| umbrella chart 공통 값 | `deploy/helm/cluster-values.yaml` |

```bash
scripts/airm-install.sh dry-run              # 서버 dry-run: CRD + ScrapeConfig + ConfigMap + 대시보드
scripts/airm-install.sh apply crd            # CRD 설치
scripts/airm-install.sh apply manifests      # 수집 설정·airm-placement·대시보드
scripts/airm-install.sh dry-run placement    # rm-controller 결정이 Deployment에 무엇을 바꿀지 확인
scripts/airm-install.sh apply placement      # 반영 (옮겨지는 pod는 재시작된다. `all`에 포함되지 않음)
# 되돌리기 (CRD를 지우면 모든 AcceleratorProfile 객체도 함께 지워진다)
scripts/airm-install.sh delete manifests
scripts/airm-install.sh delete crd
```

`airm-placement` ConfigMap은 ai-rm의 [rm-controller](https://github.com/ai-computing/ai-rm/tree/master/packages/rm-controller)가
쓰고, 서빙 pod와 이후의 EPP scorer가 읽습니다. 키는 `decisions.json` 하나이며 `protocol`, `generation` 카운터, `placement`
정책 이름, `{pool, workload, acceleratorIds, kvTransport, reason}` 항목의 `decisions` 목록을 담습니다. 가속기는 주소가 아니라
id로만 가리킵니다. `decisions`가 비어 있으면(설치 직후 상태) ConfigMap이 없는 것처럼 동작합니다. 전체 형식, 필드 표,
EPP scorer 자리(문서로만 정의, 미구현이며 v0.1은 운영 중인 EPP 설정을 바꾸지 않음)는 [deploy/airm/README.md](deploy/airm/README.md)에 있습니다.

**배치 반영 훅.** 서빙 Deployment에 `airm.ai-computing.io/pool=<InferencePool>` 라벨을 달면 대상이 되고, `llm-d.ai/role`
라벨(`prefill`, `decode`, 없으면 serve)로 결정을 고릅니다. `scripts/airm-install.sh apply placement`는 결정의 노드
(`acceleratorIds`의 `<node>/<vendor>:<index>`)**와** rm-controller가 거른 노드 요약 라벨 `airm.ai-computing.io/<vendor>.<model>`을
required node affinity로 걸고, KEDA `maxReplicaCount`를 배치된 카드 수로 낮추고, 문서의 `generation`을 기록해 한 번만
반영합니다. 문서가 비었거나, 풀에 결정이 없거나, 카드가 비어 있으면(맞는 자리가 없음) 아무것도 바꾸지 않습니다. 카드 번호는
여전히 device plugin이 고릅니다. Helm 설치에서는 같은 결정을 값으로 넘깁니다:
`helm upgrade rngd-pd … --set-json "nodeAffinity=$(scripts/airm-placement.py affinity --decisions cm.json --pool llama8b-pd-pool)"`
(역할 공통 값이라 노드만 고정).

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

## 📈 캐시 인지 라우팅과 오토스케일

로드맵 W4(캐시 재사용)와 W5(제어 루프)의 클러스터 쪽입니다. 엔진 쪽은
[aicomp#45](https://github.com/ai-computing/aicomp/issues/45)(PD 단계의 vLLM 호환 `/metrics`)와
[aicomp#46](https://github.com/ai-computing/aicomp/issues/46)(KV 블록 이벤트와 prefix 재사용)에서 추적합니다.

**EPP 스케줄링 프로파일**([`manifests/epp/profiles/`](manifests/epp/README.md#scheduling-profiles))은 고정한 llm-d-router
`e194457dc507` 기준으로 `scripts/check-epp-config.py`가 검사하고, `EPP_PROFILE=<profile> manifests/epp/make-epp.sh <pool> /<path>`로
설치합니다.

| 프로파일 | 점수 | 엔진 쪽 필요 사항 | 지금 쓰는 곳 |
|---|---|---|---|
| `queue-kv` | 대기 큐, KV 캐시 사용률 | `/metrics`(vLLM 또는 furiosa-llm 이름) | NPU 풀, aicomp#45 이후 rngd-pd 경로 |
| `approx-prefix` | + 근사 prefix affinity(EPP가 보낸 프롬프트를 직접 해시) | 없음 | 모든 풀. 엔진이 prefix를 캐시할 때만 이득 |
| `approx-prefix-gpu` | `approx-prefix`에서 prefix 가중치만 3 | 없음 | A100 vLLM 풀 (실측: 가중치 1은 부하가 걸리면 affinity를 잃음) |
| `precise-prefix` (선택) | + 엔진 KV 블록 이벤트(ZMQ, vLLM 형식) 기반 prefix 적중 | KV 이벤트 + 실제 토큰 ID용 render sidecar | 지금은 A100 vLLM, aicomp#46 이후 Optimus Prime |

근사 prefix 점수는 엔진 지원이 필요 없습니다. EPP가 토크나이저 없는 `estimate` 백엔드로 토큰을 어림하고, 프롬프트를 블록으로
해시해 어느 endpoint로 보냈는지 기억하므로 지금 모든 풀에서 돕니다. 효과는 엔진에 달렸습니다. A100 vLLM
(`--enable-prefix-caching`)은 블록을 재사용하지만, `--block-size 512 --max-model-len 512`인 vllm-rbln은 꽉 찬 블록을 재사용할
수 없고, rngd-pd 경로는 aicomp#46 전까지 매 요청을 처음부터 prefill하므로 부하만 몰립니다. 그래서 프로파일은 prefix 가중치(1)를
큐·KV(각 2)보다 낮게 둡니다.

A100 풀 replica 2개에서 실측했습니다([실험](experiments/2026-10-19-w4w5-gpu/README.md)). prefix affinity 자체는 동작합니다(같은
prefix 20요청이 모두 한 pod로, prefix 8개 순차 요청에서 vLLM 적중률 0.864 대 `queue-kv` 0.742). 하지만 가중치 1이면 요청이
동시에 들어올 때 부하 점수가 affinity를 이깁니다. KV 캐시 압박(2.9k 토큰 prefix 220개, pod 하나의 캐시 446k 토큰보다 큼)에서
적중률은 0.574로 `queue-kv` 0.560과 같았고, prefix 가중치 3(`approx-prefix-gpu`)은 0.639, TTFT p50 -20 %, 전체 시간 -16 %였습니다.
`precise-prefix`는 엔진 쪽 두 가지를 고친 뒤에야 같은 수준(0.630)이 됐습니다. KV 이벤트 토픽은 `kv@<pod-ip>:<port>@<model>`,
엔진 블록 크기는 64여야 합니다.

**오토스케일**([`manifests/autoscaling/`](manifests/autoscaling))은 이미 설치된 KEDA 2.19를 씁니다.

| ScaledObject | 대상 | 트리거 | replica | 확장 / 축소 |
|---|---|---|---|---|
| `vllm-a100-llama31-8b` | A100 vLLM | pod당 `vllm:num_requests_waiting` 4, TTFT p90 1 s | 1–2 | 120 s마다 1개 / 10분 뒤 5분마다 1개 |
| `rngd-pd-prefill` | RNGD prefill | pod당 대기 2, TTFT p90 2 s | 1–3 | 120 s마다 1개 / 10분 뒤 5분마다 1개 |
| `rngd-pd-decode` | ATOM decode | pod당 실행 6(B8), 대기 1, TPOT p90 100 ms | 1–4 | 60 s마다 1개 / 10분 뒤 5분마다 1개 |

vLLM은 이 지표를 지금 내므로 GPU 풀을 먼저 연결했습니다. NPU ScaledObject도 같은 이름을 읽는데, PD 단계는 aicomp#45 이후에야
이 지표를 냅니다. 그 전에는 쿼리 결과가 비어 `ignoreNullValues`가 0으로 읽고 풀은 최소 replica에 머뭅니다. 그래프를 미리
컴파일한 cold start는 prefill 62 s, decode 18 s([ai-rm workload traces](https://github.com/ai-computing/ai-rm/blob/master/docs/workload-traces.md))이므로
확장은 120 s / 60 s마다 한 개씩(새 pod가 Ready가 된 뒤 다음 판단), 축소는 10분을 기다리고, 0으로는 줄이지 않습니다. A100 vLLM
cold start는 실측으로 pod 시작부터 Ready까지 110-111 s(replica 2개가 동시에 뜨면 120-121 s, 절반이 torch.compile과 CUDA graph
캡처)이고, 부하가 걸리자 HPA가 21 s 만에 1 → 2로 늘렸습니다. `maxReplicaCount`는 노드당 카드 수이고(shm은 prefill과 decode를 한 호스트에 둔다), 배치 반영
훅이 배치된 카드 수로 낮춥니다.

<details>
<summary><b>실클러스터 확인 (운영자용)</b></summary>
<br>

```bash
python3 scripts/check-epp-config.py && python3 scripts/test-airm-placement.py
# 1. 풀에 EPP 프로파일 (먼저 렌더링, 다음 적용)
EPP_PROFILE=approx-prefix-gpu EPP_RENDER_ONLY=1 manifests/epp/make-epp.sh vllm-a100-pool /gpu | kubectl apply --dry-run=server -f -
EPP_PROFILE=approx-prefix-gpu manifests/epp/make-epp.sh vllm-a100-pool /gpu
kubectl -n llm-serving logs deploy/vllm-a100-epp | grep -iE 'error|plugin'        # strict 설정 로드
# 2. GPU 풀 오토스케일
kubectl apply --dry-run=server -f manifests/autoscaling/keda-vllm-a100.yaml
kubectl apply -f manifests/autoscaling/keda-vllm-a100.yaml
kubectl -n llm-serving get scaledobject vllm-a100-llama31-8b; kubectl -n llm-serving describe hpa keda-hpa-vllm-a100-llama31-8b
# 3. 배치 반영 (rm-controller가 결정을 쓰고 Deployment에 airm.ai-computing.io/pool 라벨이 있을 때)
kubectl -n llm-serving label deploy rngd-pd-prefill rngd-pd-decode airm.ai-computing.io/pool=llama8b-pd-pool
scripts/airm-install.sh dry-run placement && scripts/airm-install.sh apply placement
```
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
| 🔧 **운영** | [InferencePool별 EPP와 프로파일](manifests/epp/README.md) · [오토스케일](manifests/autoscaling) · [공유 모델 스토어](manifests/README-model-store.md) · [모니터링](monitoring/README.md) · [클러스터 운영 메모](docs/cluster-notes.md) |
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
- [x] EPP 프로파일 `queue-kv`, `approx-prefix`, 선택형 `precise-prefix`, A100 풀과 PD 단계용 KEDA ScaledObject, `airm-placement` 배치 반영 훅 (오프라인 검사 통과, 실클러스터 적용 전)
- [x] A100 풀에서 W4/W5 실측([실험](experiments/2026-10-19-w4w5-gpu/README.md)): prefix 라우팅(`approx-prefix-gpu`, 이벤트 계약을 고친 `precise-prefix`), KEDA 1 → 2 → 1, A100 cold start 110 s
- [ ] PD 경로의 precise prefix 라우팅(aicomp#46 필요)과 실지표 기반 NPU 오토스케일(aicomp#45 필요)
- [ ] `airm-placement`를 읽는 EPP scorer

미해결 문제, 노드 장애, 각 항목의 측정 근거: [STATUS.md](STATUS.md).

> [!NOTE]
> 이 레포는 공개 저장소입니다. 사이트 설정, 내부 주소, 자격 증명은 추적 파일에 넣지 않습니다. 사이트 값은 untracked
> `cluster.local.env`에만 둡니다.
