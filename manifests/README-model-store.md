# 공유 모델 스토어 (llm-d)

노드마다 모델을 중복 다운로드/컴파일하던 hostPath 방식을 **공유 RWX PVC** 하나로 대체합니다.
"한 번 받고/컴파일하고, 어디서나 서빙" — 그리고 lmd-top `Deploy` 뷰가 이걸 단일 진실원천으로 읽습니다.

## 구성

- **`model-store.yaml`** — SMB(NAS, `LLMD_MODEL_STORE_SMB`(예: `//<nas-host>/lab`), 기존 `smb.csi.k8s.io` + `rag/smb-creds`) 위 RWX PVC `model-store`(ns `llm-serving`). SMB 라 RWX 가능. *전제: 그 share 에 쓰기 권한.*
- **`model-store-discovery.yaml`** — PVC 를 RO 스캔해 인벤토리를 ConfigMap `model-inventory` 로 발행하는 CronJob(10분). lmd-top 이 읽음.

## 레이아웃 규약

```
model-store/
  hub/models--{org}--{name}/snapshots/{rev}/       # HF 원본 가중치(공유 캐시)
  compiled/{org}--{name}/rbln/{npu}-tp{n}-s{len}/  # RBLN 컴파일본(optimum-rbln)
  compiled/{org}--{name}/furiosa/{opts}/           # Furiosa 컴파일본(furiosa-llm)
```

## 적용

```bash
scripts/render-manifest.sh manifests/model-store.yaml | kubectl apply -f -   # ${LLMD_MODEL_STORE_SMB} ← cluster.local.env
kubectl -n llm-serving get pvc model-store            # STATUS=Bound 확인
kubectl apply -f manifests/model-store-discovery.yaml
kubectl -n llm-serving create job --from=cronjob/model-discovery scan-now   # 즉시 1회
kubectl -n llm-serving get cm model-inventory -o jsonpath='{.data.inventory}'
```

## 기존 워크플로 연동

- **컴파일 스크립트**(`manifests/compile-*.py`): 이제 **스토어-aware** — `MODEL_STORE`(마운트 경로)만
  주면 `OUTPUT`/`HF_HOME` 이 스토어 레이아웃(`compiled/{repo}/rbln/...`, `hub/`)으로 자동 설정.
  예) `MODEL_STORE=/mnt/store python3 manifests/compile-koni-tp4.py`. 산출물이 디스커버리 스캔 레이아웃을
  따르므로 lmd-top Deploy 에 자동 노출.
- **컴파일을 k8s Job 으로**: `manifests/compile-job.yaml`(템플릿) — 스토어 PVC 마운트 + 스크립트 ConfigMap +
  RBLN 노드. image/nodeSelector/디바이스만 채우면 됨. *주의: RBLN 노드가 SMB 마운트 가능해야 함(현재 cpu-1/cpu-3만 확인).*
- **서빙(Deployment/ModelService)**: 모델 경로를 hostPath 대신 `model-store` PVC subPath 로 마운트
  (`--model /mnt/store/compiled/.../rbln/...` 또는 `/mnt/store/hub/...`).
- **HF 다운로드**: `HF_HOME=/mnt/store/hub` 로 두면 받는 즉시 공유 캐시에 적재.

## lmd-top 연동

`lmd-top` 은 `model-inventory` ConfigMap 을 읽어 `Deploy` 뷰에 **배포되지 않은(스토어에만 있는) 모델과
컴파일 타깃**까지 표시합니다. (ConfigMap 이 없으면 배포된 것만 표시 — 무해하게 degrade.)

향후(Phase 2): Deploy 뷰의 `[c] compile` / `[d] deploy` 액션이 이 스토어에 쓰는 컴파일 Job /
스토어를 마운트하는 ModelService 를 생성(권한모드 게이팅).

## 트러블슈팅 — CIFS mount error(115)/exit 32

첫 적용 시 스캔 파드가 `cpu-2` 에 스케줄되어 마운트 실패했음(같은 share·creds 로 `rag` 의
읽기전용 마운트는 `cpu-1/cpu-3` 에서 정상). 확인 순서:
1. **share 쓰기 권한**: `rag` 는 이 share 를 **ro**(`file_mode=0444`)로 씀. `smb-creds` 로
   `LLMD_MODEL_STORE_SMB`(예: `//<nas-host>/lab`) 에 쓰기가 되는지(안 되면 쓰기 가능한 전용 share 로 `source:` 변경).
2. **노드별 접근**: 모든 서빙/스캔 노드에서 SMB 서버(445/tcp)가 닿는지. 특정 노드만 막히면
   디스커버리 CronJob 에 `nodeSelector`/`affinity` 로 접근 가능한 노드에 고정.
3. **다이얼렉트**: 서버가 요구하는 `vers=`(3.0/3.1.1/2.1) 확인. `nas-lab` 은 `vers=3.0` 사용.

Discovery publishes `data.scanned_at` as Unix seconds when the scan completes.
Updated lmd-top shows scan age separately from ConfigMap fetch quality and exports
`store_scanned_at` in JSON. Older scanners remain readable but show unknown scan
age; a recent fetch does not establish that the filesystem was recently scanned.
The updated CronJob manifest must be applied through the normal deployment process
before existing clusters start publishing this field.

Offline scanner regression checks: `python3 scripts/test-model-store-discovery.py`
(from the setup repository root; requires Python 3, PyYAML and bash). The test runs
the actual manifest script with temporary model trees and a fake kubectl, covering
successful publication, mandatory size-scan failure, missing root, ConfigMap creation
and apply failure, optional capacity failure and absent legacy build provenance.
It never contacts Kubernetes or scans the production store.
