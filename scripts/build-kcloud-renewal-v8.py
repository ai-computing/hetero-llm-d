"""Renewal from user's ETRI workshop template and kernel presentation evidence."""
from pathlib import Path
from PIL import Image
ROOT=Path(__file__).resolve().parents[1]
src=Path(__file__).with_name('build-kcloud-visual-v5.py').read_text().split('s=p.slides[0];base')[0]
src=src.replace('kcloud-etri-visual-v5','kcloud-etri-renewal-v8')
exec(compile(src,__file__,'exec'))
TEMPLATE=ROOT/'docs/presentations/example/251120 자원 관리 워크샵 발표 자료_v2.pptx'
p=Presentation(TEMPLATE)
logo_shape=next(sh for sh in p.slides[4].shapes if sh.shape_type==13 and sh.top<Inches(.6))
logo_file=assets/('etri-logo.'+logo_shape.image.ext);logo_file.write_bytes(logo_shape.image.blob)
ids=list(p.slides._sldIdLst);keep=[1,2,3,4,5,6,13,14]
for i,e in enumerate(ids):
    if i not in keep:p.slides._sldIdLst.remove(e);p.part.drop_rel(e.rId)
BLUE='005EB8';INK='172338';MUTED='576477';PALE='EAF3FC';GRAY='F2F4F7';PURPLE=BLUE
def text(s,v,x,y,w,h,size=20,bold=False,color=INK):return txt(s,v,x,y,w,h,size,bold,color)
def start(s,n,title,sub):
    # Retain the ETRI logo object and underlying source layout/master.
    for sh in list(s.shapes):
        if sh.shape_type==13 and sh.top<Inches(.6):continue
        sh._element.getparent().remove(sh._element)
    if not any(sh.shape_type==13 and sh.top<Inches(.6) for sh in s.shapes):
        s.shapes.add_picture(str(logo_file),Inches(11.7),Inches(.26),width=Inches(1.29),height=Inches(.22))
    text(s,title,.81,.61,11.9,.63,31,True,BLUE)
    text(s,sub,.81,1.45,11.8,.57,17,False,MUTED)
    text(s,'ETRI · 이종 NPU 실행 및 자원 관리',.64,7.15,9,.2,9,False,MUTED)
    text(s,str(n),12.35,7.1,.5,.3,10,False,MUTED)
def panel(s,x,y,w,h,title,body,own=True):
    box(s,x,y,w,h,PALE if own else GRAY);text(s,title,x+.22,y+.21,w-.44,.47,23,True,BLUE if own else INK)
    text(s,body,x+.22,y+.9,w-.44,h-1.03,18,False,INK)
def arr(s,x,y):
    sh=s.shapes.add_shape(MSO_SHAPE.CHEVRON,Inches(x),Inches(y),Inches(.33),Inches(.4));sh.fill.solid();sh.fill.fore_color.rgb=RGBColor.from_string(BLUE);sh.line.fill.background()
def conclusion(s,v):text(s,v,.83,6.55,11.8,.49,19,True,BLUE)
def pic(s,path,x,y,w,h,crop=None):
    iw,ih=Image.open(path).size;l,t,r,b=crop or (0,0,iw,ih);f=min(w/(r-l),h/(b-t));nw=(r-l)*f;nh=(b-t)*f
    sh=s.shapes.add_picture(str(path),Inches(x+(w-nw)/2),Inches(y+(h-nh)/2),width=Inches(nw),height=Inches(nh));sh.crop_left=l/iw;sh.crop_top=t/ih;sh.crop_right=(iw-r)/iw;sh.crop_bottom=(ih-b)/ih
def note(s,v):notes(s,v+'\n本資料는 제공된 발표자료와 연구 기록을 종합한 요약. 원시 실험을 재실행·독립 검증한 결과가 아니며, 계획·부분 검증·구현을 구분한다.'.replace('本資料','본 자료'))
old=ROOT/'docs/presentations/kcloud-etri-research-v7/assets'

s=p.slides[0];start(s,1,'NPU 자원 관리 — 우리가 분석·구현한 범위','실행 조건을 이해하고, 실행 경로를 바꾸고, 모델 운영까지 연결')
for y,label,title,body in [(2.15,'분석','컴파일·저수준 실행 계층','입력 shape·병렬성 분석  /  DSL·Rust LIR·아티팩트 진입점 조사'),(3.56,'구현','커스텀 실행·PD 런타임','stage 교체 도구  /  직접 KV 소유·전달  /  동종·이종 NPU 실행'),(4.97,'구현','모델·자원 관리 도구','lmd-top  /  모델 준비·컴파일 작업·배포·관측·운영')]:
    box(s,.82,y,11.7,1.2,PALE);text(s,label,1.03,y+.22,1.0,.45,19,True,BLUE);text(s,title,2.26,y+.13,9.8,.48,24,True);text(s,body,2.26,y+.73,9.8,.34,17)
conclusion(s,'공통 목표: 모델·실행 단계·컴파일 조건을 함께 고려하는 자원 배치')
note(s,'작업 범위 개요. workshop slides7–15: 컴파일/병렬성 분석. custom kernel slides5,8,11,13,19: 저수준 진입점과 L8Swapper. PD history §§4–7: 실제 NPU PD. lmd-top README: 관리 도구. 자체 HW/벤더 컴파일러 개발 및 전체 통합 최적화기 완성은 주장하지 않음.')

s=p.slides[1];start(s,2,'이종 가속기 기반 실험·서빙 환경','활용한 하드웨어·기반 소프트웨어와 ETRI 개발 소프트웨어를 구분')
for x,file,title,sub,crop in [(.83,'spark.jpg','NVIDIA GPU','GB10 / DGX Spark',(1260,690,1710,955)),(4.89,'rngd.png','Furiosa NPU','RNGD',None),(8.96,'atom.png','Rebellions NPU','ATOM',None)]:
    pic(s,old/file,x,2.18,3.52,1.69,crop);text(s,title,x,4.03,3.63,.47,23,True);text(s,sub,x,4.59,3.6,.35,16,False,MUTED)
for x,name,label in [(.83,'kubernetes','배포·실행 관리'),(6.96,'prometheus','모델·장비 지표 수집')]:
    pic(s,ROOT/f'docs/presentations/kcloud-etri-visual-v6/assets/{name}.png',x,5.24,.59,.59);text(s,name.capitalize(),x+.84,5.2,4.8,.45,23,True);text(s,label,x+.84,5.77,4.8,.34,17)
conclusion(s,'ETRI 개발 영역: 커스텀 실행 경로·KV 전송 런타임·lmd-top')
note(s,'제조사 대표 제품 사진이며 설치 현장 사진/보드 리비전 확인 사진 아님. 원본 출처는 v7 README와 assets. Kubernetes/Prometheus CNCF 공식 로고. 환경은 논리 구성으로 모든 모델 동시 가동을 뜻하지 않음. docs/ENVIRONMENT-GUIDE.md.')

s=p.slides[2];start(s,3,'NPU 성능은 실행 전 설정에도 좌우됨','GPU/NPU의 일반적 우열보다, 사용한 NPU 경로의 설정과 비용을 분석')
for x,a,b in [(.83,'Model','모델·가중치 준비'),(4.89,'Compile','shape·병렬성 → 아티팩트'),(8.96,'Serve','로드·KV 관리·배치 실행')]:panel(s,x,2.21,3.53,1.49,a,b,False)
arr(s,4.46,2.76);arr(s,8.53,2.76)
panel(s,.83,4.13,5.53,1.96,'비교한 실행 조건','Prefill / Decode bucket · 입력 길이\nTP / PP / DP · 요청 동시성')
panel(s,6.73,4.13,5.78,1.96,'확인한 관리 비용','성능·전력뿐 아니라 컴파일 시간\n아티팩트 크기·padding 비용도 확인')
conclusion(s,'실행할 장비만 고르는 것이 아니라, 준비할 아티팩트와 설정도 선택해야 함')
note(s,'workshop slides4–5,7–13과 NPU 자원관리 PDF. 사전/자체 컴파일 비교와 후속 bucket 조건 정렬 실험을 단일 순위로 합치지 않음. 과거37배/33배 숫자는 본문에서 제외. RNGD 경로 특성이며 모든 NPU static/OOM 불가/항상 고전성비로 일반화하지 않는다.')

s=p.slides[3];start(s,4,'저수준 분석 — 어느 계층에서 개입할 수 있는가','제공된 커스텀 커널 자료의 진입점을 자원 관리 관점으로 재정리')
for y,title,body in [(2.17,'연산·모듈 계층','Python DSL / CompileModule  —  단일 연산과 여러 연산의 묶음'),(3.5,'저수준 IR·메모리 계층','Rust LIR  —  HBM↔DM 이동, 연산 매핑, DMA·동시성 제어'),(4.83,'아티팩트·실행 계층','ArtifactBuilder / EDF swap  —  전체 모델 빌드와 특정 stage 교체')]:
    panel(s,.83,y,11.68,1.13,title,body)
    # Compact hierarchy uses explicit separate body position.
    last=s.shapes[-1];last.top=Inches(y+.67);last.height=Inches(.35);last.text_frame.paragraphs[0].font.size=Pt(17)
conclusion(s,'분석 대상: 코드 진입점 + 메모리 이동 + 실행 바이너리의 연결 관계')
note(s,'custom_kernel slides5,7–14,19. L1/L4/L5/L7/L8은 해당 가이드의 분류로 산업 표준 level 아님. Rust LIR/HBM/DM/tdma/main/sub 직접 제어 조사와 Rust 빌딩블록 기록을 반영. 벤더 내부 컴파일러 전체를 개발했다고 주장하지 않음. PD는 IR이 아니라 분리 실행 방식.')

s=p.slides[4];start(s,5,'자체 개발 — 커스텀 코드를 기존 실행 경로에 연결','L8Swapper: 직접 만든 모듈·바이너리로 vendor artifact의 특정 stage 교체')
for x,title,body,own in [(.83,'커스텀 코드','DSL / Rust 커널\nPyTorch 모듈',True),(4.89,'L8Swapper','I/O schema 확인\n컴파일·교체·저장',True),(8.96,'기존 LLM 엔진','수정된 artifact 로드\n해당 stage 실행',False)]:panel(s,x,2.4,3.53,2.08,title,body,own)
arr(s,4.46,3.17);arr(s,8.53,3.17)
box(s,.83,4.97,11.68,1.13,GRAY);text(s,'제공 자료의 검증 기록',1.08,5.16,4.7,.43,21,True);text(s,'tokenwise stage 교체  /  Rust binary의 runtime dispatch',1.08,5.7,10.9,.34,18)
conclusion(s,'전체 서빙 엔진을 다시 만들지 않고, 필요한 실행 부분을 바꿔보는 경로 확보')
note(s,'custom_kernel slides11,13,19. furiosa_l8.L8Swapper는 자료에서 자체 개발로 명시. schema 추출/dynamo permutation/orphan cleanup/validate invoke 및 stage2 tokenwise 교체. Rust binary→LLM runtime 검증은 passthrough dispatch로 실제 attention 알고리즘 교체 완료와 다름. 일부 dispatch 검증을 모든 custom kernel 정확도/성능 검증으로 확대하지 않음. 이전 파일에서 이 정보가 없었으나 사용자 추가 예시로 확인됨.')

s=p.slides[5];start(s,6,'PD 구현 — 실제 KV 전달과 실행 경로 최적화','초기의 가능성 검토에서, NPU 간 KV를 넘겨 decode를 잇는 구현으로 확장')
panel(s,.83,2.3,3.5,1.79,'Prefill worker','입력 문맥 처리\nKV 생성')
panel(s,4.91,2.3,3.5,1.79,'KVConnector','직접 KV 소유·전달\n공유 메모리 / TCP')
panel(s,8.99,2.3,3.5,1.79,'Decode worker','받은 KV를 로드\n이후 토큰 생성')
arr(s,4.45,2.98);arr(s,8.54,2.98)
text(s,'Furiosa ↔ Rebellions · 동종/이종 조합과 P/D 역할 교환',.83,4.44,11.6,.51,24,True,BLUE)
for x,title,body in [(.83,'KV 이동 축소','resident KV · streaming'),(4.89,'연산 배치 개선','lm_head NPU 배치 · batching'),(8.96,'컴파일 경로 조사','shape 제한 · 레이어 그룹')]:
    text(s,title,x,5.27,3.55,.45,21,True);text(s,body,x,5.87,3.55,.37,16)
conclusion(s,'“분리할 수 있는가”를 넘어, 연산·전송·컴파일 비용이 어디서 생기는지 분석')
note(s,'PD history §§4–7,12. 별도 개발 서버 실제 NPU PD 연구. shared /dev/shm 경로와 별도 TCP 검증, NIXL은 스텁. custom kernel slides15/17의 GPU prefill–RNGD decode는 2026-05 부분 가능성 검토이며 완료 사례로 혼용하지 않음. 실제 동종·이종 구현은 후속 history의 RNGD/ATOM 조합. resident KV/lm_head/shapegroup 개선 실험. lmd-top 자동 PD 제어 통합 아님.')

s=p.slides[6];start(s,7,'lmd-top — 모델 준비와 운영 상태를 연결','단순 지표 대시보드를 넘어 컴파일 작업·아티팩트·배포를 함께 관리')
for y,title,body in [(2.19,'준비·컴파일','원본 / 빌드 산출물 구분\n벤더 컴파일 Job 관리'),(3.61,'배포·작업 이력','타깃 노드·실행 옵션 선택\n진행·실패·로그 확인'),(5.03,'관측·운영','모델·요청·장비 상태 연결\n스케일·재시작·정지')]:text(s,title,.83,y,3.7,.44,23,True,BLUE);text(s,body,.83,y+.59,3.7,.77,17)
pic(s,old/'lmd-top-real.png',4.87,2.04,7.63,4.94)
note(s,'2026-09-08 실제 observe TUI ANSI 출력의 녹화 프레임. NO_COLOR 제거 후 soft theme, 실제 데이터이며 합성 없음. desktop 픽셀 캡처가 아니라 실제 PTY 출력 렌더. 캡처 중 메뉴 이동만 수행했고 외부 compile/deploy 실행 안함. lmd-top 자체가 compiler가 아니고 vendor Job 관리 도구. 현재 화면 과거 스냅샷, 현재 가동 상태 보장 아님.')

s=p.slides[7];start(s,8,'협업 방향 — 실행 조건과 자원 배치를 함께 최적화','현재 확보한 분석·구현 기반 위에서 정책과 비용 모델을 연결')
for x,title,body in [(.83,'컴파일 비용 모델','shape · 병렬성 · 그래프 구성\n성능 / 준비 비용 예측'),(4.89,'단계·메모리 배치','한 카드 실행 vs P/D 분리\nKV 이동 비용을 고려한 선택'),(8.96,'관측 기반 평가','모델·장비 상태와 실행 결과\n정책 실험의 평가 지표 연결')]:panel(s,x,2.35,3.53,2.45,title,body)
box(s,.83,5.28,11.68,.79,GRAY);text(s,'우리가 제공할 기반: 분석 자료 · 커스텀 실행 도구 · KV 전송 런타임 · lmd-top',1.07,5.48,11.2,.4,19,True)
conclusion(s,'다음 질문: 어떤 모델·부하를, 어떤 설정과 장비 조합으로 실행할 것인가?')
note(s,'협업 제안이며 자동 튜닝/폐루프 컨트롤러 완성 성과 아님. workshop future work slide14 성능/OOM 예측·후보 탐색 취지를 연결하되 새 미래 연구로 표시. 과제 총괄 소개는 다른 발표자가 제공하므로 생략.')
p.core_properties.title='ETRI NPU 실행·자원관리 — 예시자료 기반 리뉴얼'
p.core_properties.author='ETRI'
p.save(OUT/'ETRI_NPU실행과_자원관리_리뉴얼_v8.pptx')
print(OUT)
