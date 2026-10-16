# ETRI 저수준 NPU 연구와 자원관리 — v7

7장: 개발 범위 → 하드웨어·기반 환경 → DSL/계산 그래프 → PD/KVConnector → 런타임 최적화 → lmd-top → 협업 질문.

lmd-top 전용 설명은 1장, 저수준 그래프·PD·최적화는 3장으로 재균형. 기존 템플릿 파생 디자인 유지. 근거와 한계는 발표자 노트에 수록.

## 저수준 분석의 범위

PD disaggregation은 IR이 아니라 실행 분리 방식이다. 로컬 연구 기록에서 확인되는 furiosa-torch/DSL 계산 그래프 구성, KV 입출력, 컴파일 shape/레이어 그룹 탐색, 메모리 경로를 소개했다. LLVM/MLIR 패스 직접 수정이나 벤더 내부 컴파일러 개발을 완료했다고 주장하지 않는다. PD 런타임과 lmd-top은 별도 구현이며 자동 통합 제어기로 표현하지 않는다.

## 실제 컬러 TUI

`scripts/capture-lmd-color.py`가 실제 lmd-top을 observe 모드 PTY에서 실행하고 ANSI 출력 전체를 기록한다. 색상을 끄는 `NO_COLOR` 환경 변수만 제거하고 soft 테마를 선택했다. 4번 Deploy 탭으로 이동했으며 클러스터 변경 액션을 실행하지 않았다.

- `assets/lmd-top-real.cast`: 실제 데이터/색상 녹화 원본
- `assets/lmd-top-real.gif`: agg 렌더 (시간 압축)
- `assets/lmd-top-real.png`: 마지막 프레임. 본문에 삽입

이전의 --render 문자 추출 재구성이 아니다. 다만 데스크톱 픽셀 캡처는 아니며 실제 터미널 ANSI 출력을 렌더링한 것이다. 값 합성 없음. 실패·정지·지표 없음 상태는 캡처 당시 값을 그대로 유지했다.

## 제조사 제품 이미지

- NVIDIA DGX Spark / GB10: https://nvidianews.nvidia.com/news/nvidia-announces-dgx-spark-and-dgx-station-personal-ai-computers
  - https://iprsoftwaremedia.com/219/files/20252/nvidia-dgx-spark.jpg
- Furiosa RNGD: https://furiosa.ai/rngd
  - https://cdn.prod.website-files.com/69289524195a1f9e06ade49b/696e5f723fd519b667a96192_redcard_cropped_greyBG.avif
- Rebellions ATOM: 공식 media API의 ATOM 이미지
  - https://rebellions.ai/wp-content/uploads/2025/05/atom.png
- Kubernetes/Prometheus 로고: https://github.com/cncf/artwork

제조사 대표 이미지로 보유 장비 현장 사진이 아니며 카드 리비전 외형 일치를 보장하지 않는다. NVIDIA 이미지에서는 DGX Spark 본체 영역만 PPT에서 잘라 표시. 제품 이미지 원래 비율 유지. 로고·사진은 식별용이며 제조사 후원·인증 의미 없음.
