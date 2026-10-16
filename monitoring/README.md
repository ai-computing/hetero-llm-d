# monitoring

클러스터 관측 구성입니다. 기본은 k8s 클러스터의 모니터링 스택(Prometheus, Grafana, exporter 매니페스트는 `manifests/`)이고, 이 폴더는 그 보조 자료를 둡니다.

| 경로 | 내용 |
|---|---|
| `grafana-dashboards/` | Grafana 대시보드 JSON. `vllm_colon_min.json`은 vLLM colon 지표(TTFT/TPOT/E2E/TPS) 대시보드 |
| `standalone-compose/` | k8s 없이 GPU 노드 한 대에서 vLLM + Prometheus + Grafana + DCGM을 띄우는 docker-compose 스택 (개발·재현용) |

`ai-computing/rm_monitor@5d23892`에서 옮겨 왔습니다. 부하 생성·trace 재생 도구는 `ai-computing/rm-bench`, 운영 콘솔은 `ai-computing/lmd-top`입니다.
