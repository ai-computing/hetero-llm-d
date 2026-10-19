# airm-install.sh dry-run 무한 대기 원인과 타임아웃

- **Date**: 2026-10-19
- **Task**: LLMD-33
- **Host / device**: gspark-poweredge-r7525 (control-plane), kubectl/server v1.31.14, rm-core v0.1.1
- **Commit**: airm/v0.1 48f1a6a + 이 작업 diff (커밋 전 측정)

## Question

리뷰에서 `bash scripts/airm-install.sh dry-run all`이 15분 넘게 끝나지 않았다. 어디서 멈추나?

## Setup

이 노드는 프록시가 없고 kubeconfig가 client-cert 인증이며 CRD 캐시가 차 있어서, 그대로는 재현되지 않는다(0.6 s).
그래서 원인 후보를 하나씩 인위로 만들었다. 응답하지 않는 서버는 TCP accept만 하고 아무것도 보내지 않는
로컬 리스너(127.0.0.1:16443)로 흉내 냈다.

- A: 빈 CRD 캐시 + `https_proxy`를 응답 없는 리스너로 (curl 경로)
- B: kubeconfig의 server를 응답 없는 리스너로 (kubectl 경로)
- C: kubeconfig server가 no route (192.0.2.1, TEST-NET-1)

## Command

```bash
S=<scratchpad>
# A (수정 전): curl
https_proxy=http://127.0.0.1:16443 XDG_CACHE_HOME=$S/emptycache timeout 60 bash scripts/airm-install.sh dry-run crd
# A (수정 후): API 서버는 프록시 제외
NO_PROXY=<apiserver> https_proxy=http://127.0.0.1:16443 XDG_CACHE_HOME=$S/emptycache AIRM_FETCH_TIMEOUT=20 \
  bash scripts/airm-install.sh dry-run all
# B
KUBECONFIG=$S/kc-silent AIRM_KUBECTL_TIMEOUT=15 bash scripts/airm-install.sh dry-run all
# 정상 경로, 빈 캐시
XDG_CACHE_HOME=$S/emptycache bash scripts/airm-install.sh dry-run all
```

## Results

| case | 수정 전 | 수정 후 |
|---|---|---|
| A: curl, 응답 없는 프록시 | **무한 대기** (timeout 60 s로 강제 종료, rc=124) | 33 s, rc=1, "failed to download the CRD (3 attempts, 20s each)" |
| A': 같은 프록시가 kubectl에도 적용 (NO_PROXY 없음) | 무한 대기 가능 | 60 s, rc=1, "kubectl get --raw /readyz did not finish within 60s" + "cannot reach the Kubernetes API server" |
| B: kubectl, 응답 없는 API 서버 | 매니페스트당 20 s(TLS handshake timeout) 후 실패 | 10 s, rc=1, "cannot reach the Kubernetes API server (x)" |
| C: no route | 0.1 s 실패 | 동일 |
| 정상, 빈 캐시 | 0.6 s | 1.0 s, CRD v0.1.1 `configured (server dry run)` |

## Conclusion

확실히 끝없이 기다리는 곳은 CRD 다운로드 `curl -fsSL`이다. 이 curl에는 타임아웃이 없어서, 캐시가 비어 있고
연결은 됐지만 응답이 없으면(프록시, 방화벽 중간 장비) 영원히 기다린다. 검증 환경에서 캐시가 비어 있었다면
이 경로일 가능성이 가장 높다. kubectl에도 상한이 없었다. `--request-timeout`이 없었고, exec credential
plugin이 대화형 로그인을 기다리거나 `delete`가 finalizer를 기다리면 멈출 수 있었다.

수정: curl에 `--connect-timeout 10 --max-time $AIRM_FETCH_TIMEOUT(60) --retry 2`를 넣고, 실패하면 수동으로 둘
경로를 안내하게 했다. kubectl은 모두 `kc()`(`timeout` + `--request-timeout`, 기본 60 s)로 감쌌다. 시작할 때
`/readyz` 사전 점검으로 API 서버 문제를 한 줄로 알린다. 검증 노드에서 실제로 멈춘 곳은 직접 확인하지 못했다.
이제는 어느 경우든 위 메시지 중 하나로 끝난다.
