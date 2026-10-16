# ETRI NPU 실행·자원관리 v9

## 제작 상태

승인된 7장 중 1장은 승인 샘플, 2–5장 및 7장은 생성·검수·결과 기록 완료. 6장은 실제 스크린샷 보존 검수 실패로 보류. 최종 PPT/PDF는 아직 조립하지 않았다.

codex-ppt 스킬의 built-in image tool 방식으로 제작했다. 6장 생성 및 수정 시도가 터미널 글자와 패널 비율을 바꾸므로 실제 화면으로 제시할 수 없다. 원본 스크린샷을 PPT에 직접 삽입하는 예외 방식을 사용자에게 확인해야 한다. 최종 이미지 생성에 로컬 합성은 사용하지 않았다.

## 작업 파일

- [승인된 구성](outline.md)
- [7장 발표자 노트](speech.md) — PPT 삽입은 조립 후 진행
- [슬라이드 이미지](origin_image/)
- [작업 및 생성 출처 기록](slide_jobs.json)
- [실행 상태](slide_run_state.json)
- [실제 lmd-top 화면](../kcloud-etri-research-v7/assets/lmd-top-real.png)

## 근거와 해석 범위

제공된 워크샵 자료, custom_kernel_in_furiosa_npu 자료, PD disaggregation_HISTORY.md 및 lmd-top 문서를 바탕으로 구성했다. 상세 근거 매핑은 outline.md와 deck_spec.json에 있다. 하드웨어는 제조사 대표 이미지이며 현장 사진이 아니다. 전체 계층도는 연구·개발 범위이며 단일 통합 자동 제어기의 구현을 뜻하지 않는다. PD 분리와 저수준 IR 분석은 별개 작업이며, 기존 엔진의 passthrough dispatch 검증을 완전한 attention 구현 검증으로 확대하지 않는다.

현재 방식은 전체 슬라이드가 이미지이므로 글자와 도형을 개별 편집할 수 없다.
