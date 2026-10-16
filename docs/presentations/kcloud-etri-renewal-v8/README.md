# 예시 발표자료 기반 리뉴얼 v8

기존 v7 및 example 파일은 보존. 본문 8장, lmd-top 전용 1장.

## 참고한 예시와 반영

| 예시 | 반영한 부분 |
|---|---|
| 251120 자원 관리 워크샵 발표 자료_v2.pptx | 실제 템플릿·마스터·ETRI 로고, 파란색 제목, Model→Compile→Serve, 설정·준비 비용 분석 |
| LLM 추론 효율화를 위한 NPU 자원 관리.pdf | 컴파일·병렬성·bucket의 자원관리 의미, 후보 탐색과 예측의 연구 방향 |
| custom_kernel_in_furiosa_npu.pptx | 진입 계층 구분, DSL/Rust LIR/모듈/아티팩트 경로, 자체 L8Swapper, stage 교체와 dispatch 검증 |

## 8장 구성과 근거

1. 분석·구현 범위: 예시 전체와 PD history, lmd-top README
2. 구축 환경: ENVIRONMENT-GUIDE, 제조사 사진·공식 로고 (v7 출처 계승)
3. 실행 전 설정: 워크샵 4–5, 7–13장
4. 저수준 개입 계층: 커스텀 커널 5, 7–14, 19장
5. L8Swapper: 커스텀 커널 11, 13, 19장
6. 실제 NPU PD와 최적화: PD disaggregation_HISTORY.md §§4–7
7. lmd-top: README, 실제 컬러 PTY 녹화 프레임
8. 협업 방향: 워크샵 14장의 후보 탐색/예측과 현재 구현을 연결한 제안

## 사실 구분

- L1/L4/L5/L7/L8은 제공된 가이드의 분류이지 표준 단계명이 아니다.
- Rust binary→runtime은 passthrough dispatch 검증을 포함. 완성된 attention 교체 검증이라고 확대하지 않는다.
- 2026-05 자료의 GPU–RNGD PD는 부분 가능성 검토. 이후 RNGD–ATOM 실제 KV 전송 구현과 구분한다.
- 사용자 제공 발표자료의 검증 기록을 인용한 것이며 해당 별도 서버 원시 코드·측정을 독립 재검증하지 않았다.
- GPU/NPU 우열, NPU의 OOM 불가능, 일률적 성능 향상 등 예시의 일반화는 계승하지 않았다.
- 자체 개발 도구와 벤더 컴파일러·엔진을 구분. 자동 통합 자원관리 제어기 완성을 주장하지 않는다.
- 하드웨어는 제조사 대표 사진이며 보유 장비 실물 사진이 아니다.

상세 한계와 출처는 발표자 노트에 포함. Python 생성기: `scripts/build-kcloud-renewal-v8.py`.
