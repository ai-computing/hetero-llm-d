# 실제 UI 설명 보강판 v6

본문 7장 + GIF 데모 부록 1장. v5 원본은 변경하지 않았다.

실제 환경 → NPU 특성 분석 → 모델 생애주기 → Deploy 화면 → Serving 화면 → Flow/Devices 화면 → 실행 단계 분리 순서.

## 캡처

`assets/live`는 2026-09-08 클러스터를 `lmd-top --render`로 읽기 전용 조회한 TestBackend UI 렌더이다. `scripts/capture-lmd-top.sh`로 SVG를 생성하고 PNG로 렌더링했다. OS 스크린샷이 아닌 실제 데이터 기반 헤드리스 화면이며 값은 합성하지 않았다. PPT에서는 핵심 부분을 확대하고 설명 번호를 덧붙였다. 일부 글리프는 헤드리스 폰트에서 지원되지 않을 수 있다.

Running/Failed/Degraded/Scaled-0 및 누락 지표를 유지했다. 캡처 과정에서 배포·컴파일·스케일 등 클러스터 변경은 실행하지 않았다. 순간 지표는 벤더 성능 비교 자료가 아니다. 부록 GIF만 수치 변화가 합성된 UI 데모이며 본문 실조회 화면과 구분한다.

## 로고·디자인

- Simple Light Mode PPT 템플릿에서 파생한 v5 디자인 계승.
- Kubernetes: https://raw.githubusercontent.com/cncf/artwork/main/projects/kubernetes/icon/color/kubernetes-icon-color.svg
- Prometheus: https://raw.githubusercontent.com/cncf/artwork/main/projects/prometheus/icon/color/prometheus-icon-color.svg
- 정책: https://github.com/cncf/artwork/blob/main/LICENSE.md
- 공식 로고는 원래 색을 유지한 식별용이며 후원·인증을 의미하지 않는다.
- lmd-top은 공식 로고를 새로 만들지 않고 이름·기능 아이콘과 실제 화면으로 표현.
- 개념 아이콘: Lucide (React Icons).

상세 근거와 한계는 발표자 노트에 포함. 재생성: `scripts/build-kcloud-visual-v6.py`.
