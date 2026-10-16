# v14 — 슬라이드 6·7 재녹화

기존 v13의 1–5, 8–9장은 유지한다. 6·7장만 교체한다.

- 실제 터미널을 176열 × 44행으로 넓혀 다시 캡처했다.
- 6장: Library 선택 이동, Model Zoo에서 여러 모델 탐색, Library 복귀.
- 7장: 컴파일 폼에서 여러 필드·값 이동, 취소, 배포 폼에서 여러 필드·값 이동, 취소.
- 6·7장 모두 원본 전체 GIF를 크롭 없이 비율 유지하여 삽입했다. 왼쪽 설명 영역을 줄여 화면을 확보했다.
- GIF 원본 바이트가 PPT에 그대로 포함되는지 빌드 시 검사한다. PDF는 첫 프레임만 보여준다.

캡처 중 실제 Job/배포는 실행하지 않았다. admin 모드는 옵션 폼 표시를 위해서만 사용했다. Enter, apply, 저장 키는 전송하지 않았다. UI가 긴 문자열을 자체 생략하는 경우는 남을 수 있지만 PPT 크롭으로 글자를 자르지 않는다.

원본 PTY 기록: assets/dynamic.cast(목록), assets/forms.cast(옵션). 캡처 스크립트: scripts/capture-lmd-dynamic.py, scripts/capture-lmd-dynamic-forms.py. 빌드: scripts/build-kcloud-editable-v14.py.

발표자 노트 없음. 텍스트·도형 편집 가능. GIF 내부는 이미지다. PowerPoint 슬라이드 쇼의 실제 재생은 이 환경에서 검증하지 못했다.
