"""Extend v5 visual language with live UI captures and official project logos."""
from pathlib import Path
from pptx.util import Inches, Pt
from PIL import Image
import cairosvg

source=Path(__file__).with_name('build-kcloud-visual-v5.py').read_text()
source=source.replace("kcloud-etri-visual-v5", "kcloud-etri-visual-v6")
source=source.replace("p.save(OUT/'ETRI_NPU_모델자원관리_5slides_v5.pptx')", "# save after v6 edits")
exec(compile(source,__file__,'exec'))

for f in assets.glob('*.svg'):cairosvg.svg2png(url=str(f),write_to=str(f.with_suffix('.png')))
for f in (assets/'live').glob('*.svg'):cairosvg.svg2png(url=str(f),write_to=str(f.with_suffix('.png')))

# Retain v5's animation as an optional demo, then add two UI explanation pages.
arch,analysis,lifecycle,demo,runtime=list(p.slides)
from pptx.opc.packuri import PackURI
for i,s in enumerate(p.slides,1):s.part._partname=PackURI(f'/ppt/slides/slide{i}.xml')
deploy=p.slides.add_slide(p.slide_layouts[0])
operations=p.slides.add_slide(p.slide_layouts[0])
observe=p.slides.add_slide(p.slide_layouts[0])
order=[arch,analysis,lifecycle,deploy,operations,observe,runtime,demo]
rels={id(p.part.related_slide(e.rId)):e for e in p.slides._sldIdLst}
for e in list(p.slides._sldIdLst):p.slides._sldIdLst.remove(e)
for s in order:p.slides._sldIdLst.append(rels[id(s)])

def logo(s,name,x,y,size=.62):
    s.shapes.add_picture(str(assets/(name+'.png')),Inches(x),Inches(y),width=Inches(size))
def screenshot(s,name,x,y,w,region=None):
    path=assets/'live'/('lmd-top-'+name+'.png')
    iw,ih=Image.open(path).size
    l,t,r,b=region or (0,0,iw,ih)
    h=w*(b-t)/(r-l)
    sh=s.shapes.add_picture(str(path),Inches(x),Inches(y),width=Inches(w),height=Inches(h))
    sh.crop_left=l/iw;sh.crop_right=(iw-r)/iw;sh.crop_top=t/ih;sh.crop_bottom=(ih-b)/ih
    return sh
def badge(s,n,x,y):
    box(s,x,y,.35,.35,PURPLE);txt(s,str(n),x+.09,y+.025,.25,.25,13,True,'FFFFFF')
def callout(s,n,title,body,x,y,w=3.0):
    badge(s,n,x,y);txt(s,title,x+.52,y-.035,w-.52,.47,21,True)
    txt(s,body,x+.52,y+.53,w-.52,.85,16,False,MUTED)
def outline(s,x,y,w,h):
    sh=s.shapes.add_shape(MSO_SHAPE.RECTANGLE,Inches(x),Inches(y),Inches(w),Inches(h))
    sh.fill.background();sh.line.color.rgb=RGBColor.from_string('A994FF');sh.line.width=Pt(1.5)
def live_note(s):txt(s,'실제 클러스터 조회 화면 · 2026-09-08 · 핵심 영역 확대',.58,6.79,11,.2,9,False,MUTED)

base(arch,1,'Infrastructure / serving & management','이종 가속기 위에 서빙을 구성하고,\n상태 수집과 운영 도구를 연결했습니다')
# Native diagram: service path in cluster; separate management/metrics path.
box(arch,.58,2.57,7.4,3.9,GRAY)
logo(arch,'kubernetes',.84,2.83,.59);txt(arch,'Kubernetes',1.58,2.84,3.3,.43,24,True)
txt(arch,'배포 · 스케줄링 · 실행 상태 관리',1.58,3.35,5.9,.4,17,False,MUTED)
box(arch,.9,4.01,6.76,.67,'FFFFFF');txt(arch,'요청  →  Gateway / 라우팅  →  모델 서버',1.14,4.18,6.32,.35,20,True)
for x,name in [(1.0,'NVIDIA GPU'),(3.22,'Furiosa NPU'),(5.46,'Rebellions NPU')]:
    icon(arch,'LuCpu',x,5.0,.59);txt(arch,name,x,5.79,2.3,.39,16,True)
logo(arch,'prometheus',8.66,2.72,.66);txt(arch,'Prometheus',9.52,2.75,3.2,.48,24,True)
txt(arch,'모델·장비 지표 수집',9.52,3.36,3.2,.48,16,False,MUTED)
line(arch,7.98,3.91,8.98,3.91);txt(arch,'exporter 지표',8.05,4.01,1.95,.3,11,False,MUTED)
line(arch,10.75,3.92,10.75,4.31);arrow(arch,10.52,4.15);arch.shapes[-1].rotation=90
box(arch,8.65,4.66,4.08,1.81,PALE);icon(arch,'LuActivity',8.96,4.99,.58)
txt(arch,'lmd-top',9.78,4.99,2.58,.48,27,True)
txt(arch,'지표 + K8s 상태를 연결\n컴파일·배포·운영 작업 관리',8.96,5.7,3.58,.68,16,False,MUTED)
line(arch,7.98,5.31,8.65,5.31);txt(arch,'K8s API',7.98,5.43,.8,.3,9,False,MUTED)
notes(arch,'논리 구성. 실선은 구성 간 연계이며 모든 선이 사용자 트래픽을 의미하지 않는다. 사용자 요청은 Gateway/라우팅과 모델 서버를 거친다. lmd-top은 Prometheus 지표 및 Kubernetes API 상태를 읽어 연결하며, 승인된 운영 작업은 K8s를 통해 수행한다. lmd-top은 요청 프록시나 컴파일러 자체가 아니다. Kubernetes와 Prometheus는 CNCF 공식 artwork의 원본 색 로고. lmd-top의 아이콘은 개념 아이콘으로 공식 로고를 주장하지 않으며 4–6장에 실제 UI를 제시한다. 공유 모델 저장소는 3–4장에서 다룬다. 근거: docs/ENVIRONMENT-GUIDE.md; lmd-top/README.ko.md. 로고: https://github.com/cncf/artwork')

# Add one concrete action to each workstream, without reintroducing benchmark tables.
for x,text in [(.58,'조건별 모델 빌드와 실행 가능 범위 확인'),(4.87,'부하 조건을 바꿔 성능·효율 비교'),(9.05,'호스트 복사·KV 유지 경로 개선')]:
    txt(analysis,text,x,5.59,3.65,.5,14,False,INK)
for x,text in [(.58,'GPU/NPU 호환 목록 탐색'),(3.71,'조건 선택 → 컴파일 Job'),(6.84,'공유 저장소의 빌드 확인'),(9.97,'노드 후보와 자원 확인')]:
    txt(lifecycle,text,x,5.59,2.9,.38,13,False,INK)

base(deploy,4,'lmd-top / prepare & deploy','준비된 모델과 컴파일 작업을\n분리해서 보고, 배포로 이어갑니다')
screenshot(deploy,'deploy',.58,2.49,8.53,(18,100,1376,698))
outline(deploy,.63,2.52,8.34,1.96);badge(deploy,1,.74,2.7)
outline(deploy,.63,5.18,8.34,1.00);badge(deploy,3,.74,5.83)
callout(deploy,1,'모델 목록','GPU/NPU 타깃과\n컴파일 필요 여부 확인',9.51,2.56,3.24)
callout(deploy,2,'빌드 산출물','동일 모델의 실행 조건별\n컴파일 결과를 구분',9.51,3.94,3.24)
badge(deploy,2,7.98,3.97)
callout(deploy,3,'작업 이력','컴파일 진행·실패와\n배포 상태·로그 확인',9.51,5.31,3.24)
live_note(deploy)
notes(deploy,'2026-09-08 lmd-top --render로 실제 클러스터를 읽기 전용 조회한 TestBackend 화면을 SVG/PNG 렌더링하고 확대했다. 데이터 합성 없음. Model List는 원본/카탈로그와 스토어의 compiled 빌드를 표시. 화면의 네 빌드는 실제 목록이고 수치를 성능 지표로 해석하지 않는다. Activity에는 당시 Running/Failed compile과 Degraded/Serving deploy가 존재. 발표자는 실패를 숨기지 않고 작업 상태·로그를 관리한다는 기능으로 설명. 컴파일 실행은 벤더 도구 Job이며 자체 컴파일러 아님. 배포/컴파일 액션은 이번 캡처 과정에서 수행하지 않음. 근거: assets/live/lmd-top-deploy.svg; lmd-top/README.ko.md.')

base(operations,5,'lmd-top / serving','배포 목록에서 실제 실행 상태와\n운영할 대상을 확인합니다')
screenshot(operations,'serving',.58,2.56,12.16,(20,100,1375,357))
outline(operations,.64,2.64,1.04,2.13);badge(operations,1,.78,4.45)
outline(operations,7.52,2.64,4.32,2.13);badge(operations,2,11.21,4.45)
for x,n,title,body in [(.58,1,'상태를 구분','Serving / Degraded / Scaled-0\n배포 존재와 실제 실행은 별개'),(4.87,2,'실행 위치 확인','엔진 · replica · 실행 노드\n모델과 자원 배치를 함께 확인'),(9.05,3,'선택 후 운영','스케일 · 재시작 · 정지\n권한과 확인 절차를 거쳐 수행')]:
    callout(operations,n,title,body,x,5.18,3.73)
badge(operations,3,6.66,2.66)
live_note(operations)
notes(operations,'실제 Serving 화면의 상단 행을 확대. 목록 일부만 보인다. Scaled-0는 정지/0 replica 상태이며 성능 데이터가 아니다. 캡처 당시 일부 게이트웨이/프록시만 동작했으므로 전 모델이 서빙 중이라고 설명하지 않는다. Degraded는 lmd-top이 pod/deployment 상태를 교차 판정한 결과이며 이 PPT에서 원인을 진단한 것은 아니다. t/s —는 수치가 없는 상태다. 운영 액션은 observe 기본에서 차단되고 admin 등 모드와 확인 절차에 따른다. 근거: assets/live/lmd-top-serving.svg; lmd-top/README.ko.md.')

base(observe,6,'lmd-top / traffic & infrastructure','요청의 목적지와 장비 상태를\n같은 도구에서 추적합니다')
screenshot(observe,'flow',.58,2.54,7.4,(20,100,1200,480))
txt(observe,'요청 → 라우트 → 모델 → 실행 노드',.58,5.16,7.35,.47,22,True)
txt(observe,'EPP를 거치는 경로와 직접 연결 경로를 구분',.58,5.77,7.35,.45,17,False,MUTED)
screenshot(observe,'devices',8.31,2.54,4.43,(20,102,790,380))
txt(observe,'GPU·NPU를 나란히 관측',8.31,4.62,4.43,.5,22,True)
txt(observe,'장비별 사용률 · 메모리\n온도 · 전력 확인',8.31,5.27,4.43,.8,18,False,MUTED)
live_note(observe)
notes(observe,'Flow와 Devices의 실제 조회 화면을 각각 핵심 열·행만 확대했다. Flow는 Gateway/HTTPRoute/backend/Pod 관계를 표시하고 EPP 연결 경로와 Service 직접 경로를 구분한다. Devices는 exporter가 제공하는 GPU/RBLN/RNGD 지표를 표시. 지표가 없거나 0인 항목을 정상 측정으로 간주하지 않는다. 사용률은 K8s 할당/스케줄 가능 용량과 다르다. 화면 값은 순간 스냅샷으로 벤더 성능 비교 자료가 아니다. 근거: assets/live/lmd-top-flow.svg, lmd-top-devices.svg; README.ko.md.')

# Keep conceptual P/D diagram; add implemented runtime details and correct page id.
for sh in runtime.shapes:
    if sh.has_text_frame and sh.text=='05':
        for r in sh.text_frame.paragraphs[0].runs:r.text='07'
txt(runtime,'구현: 실제 KV 전달 · 자체 런타임 · 입력/생성 역할 교환',.6,5.42,11.5,.32,15,False,PURPLE)
for sh in demo.shapes:
    if sh.has_text_frame and sh.text=='04':
        for r in sh.text_frame.paragraphs[0].runs:r.text='08'
    if sh.has_text_frame and sh.text=='OPERATIONS / LMD-TOP':
        for r in sh.text_frame.paragraphs[0].runs:r.text='APPENDIX / ANIMATED UI DEMO'
p.core_properties.title='ETRI — NPU·자원관리: 환경 구성과 실제 lmd-top 화면'
p.save(OUT/'ETRI_NPU_자원관리_실제화면_v6.pptx')
print('Saved v6: 7 main slides + animated demo appendix')
