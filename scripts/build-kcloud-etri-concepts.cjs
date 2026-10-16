// Concept-led technical introduction. NODE_PATH must expose pptxgenjs.
const Pptx=require('pptxgenjs'), fs=require('fs'), path=require('path');
const root=path.resolve(__dirname,'..');
const out=path.join(root,'docs/presentations/kcloud-etri-concepts-v3');
fs.mkdirSync(out,{recursive:true});
const p=new Pptx(); p.layout='LAYOUT_WIDE'; p.author='ETRI';p.company='ETRI';
p.title='K-Cloud | 이종 가속기 서빙 환경과 ETRI 작업 범위';p.lang='ko-KR';
p.theme={headFontFace:'Noto Sans CJK KR',bodyFontFace:'Noto Sans CJK KR',lang:'ko-KR'};
const C={ink:'17363B',muted:'60787D',teal:'087F83',mint:'50D9BE',pale:'E8F5F2',gray:'F1F5F5',line:'CBDBDD',dark:'112B31',panel:'21434A',white:'FFFFFF',violet:'795BC2',vp:'F0ECF9',amber:'A0681E',ap:'FFF2DF'};
const S=p.ShapeType, checks=[], notes=[];
function box(s,x,y,w,h,fill=C.pale,border){s.addShape(S.roundRect,{x,y,w,h,radius:.12,rectRadius:.12,fill:{color:fill},line:{color:border||fill,width:border?1:0}});checks.push({x,y,w,h});}
function t(s,text,x,y,w,h,size=18,color=C.ink,bold=false,align='left'){s.addText(text,{x,y,w,h,fontFace:'Noto Sans CJK KR',fontSize:size,color,bold,align,margin:0,wrap:false,valign:'mid',paraSpaceAfter:0});checks.push({x,y,w,h,text});}
function a(s,x1,y1,x2,y2,color=C.teal,dash=false,head=true){s.addShape(S.line,{x:Math.min(x1,x2),y:Math.min(y1,y2),w:Math.abs(x2-x1),h:Math.abs(y2-y1),flipH:x2<x1,flipV:y2<y1,line:{color,width:2,dashType:dash?'dash':'solid',beginArrowType:'none',endArrowType:head?'triangle':'none'}});}
function n(s,title,sub,x,y,w,h,fill=C.pale,color=C.ink){box(s,x,y,w,h,fill);t(s,title,x+.23,y+.18,w-.46,.47,23,color,true);if(sub)t(s,sub,x+.23,y+.80,w-.46,h-.96,15,color);}
function pill(s,text,x,y,w,color=C.teal,fill=C.pale){box(s,x,y,w,.38,fill);t(s,text,x+.1,y+.04,w-.2,.3,11,color,true,'center');}
function page(ch,title,sub='',dark=false){const s=p.addSlide();s.background={color:dark?C.dark:C.white};s._dark=dark;
t(s,'K-CLOUD / ETRI   '+ch,.6,.3,12.1,.3,11,dark?C.mint:C.teal,true);
t(s,title,.6,.92,12.1,.67,34,dark?C.white:C.ink,true);
if(sub)t(s,sub,.62,1.78,12,.36,15,dark?'B8CDCF':C.muted);
t(s,'이종 가속기 서빙 환경 · 기술 미팅',.62,7.13,10,.2,9,dark?'92ADB1':C.muted);
t(s,String(p._slides.length).padStart(2,'0'),12.1,7.1,.6,.25,10,dark?'92ADB1':C.muted,false,'right');return s;}
function note(s,text,source){const full=text+'\n\n근거: '+source; s.addNotes(full);notes.push(full);}
function takeaway(s,text){t(s,text,.65,6.57,12.0,.40,20,s._dark?C.mint:C.teal,true);}
// The same conceptual map is reused for orientation, not as an implementation diagram.
function map(s,focus='all'){
 const hi=(id)=>focus==='all'||focus===id;
 n(s,'사용자 요청','질문 · 문서 · 대화',.65,3.00,2.40,1.65,C.gray);
 n(s,'통합 서빙','요청을 실행할 곳에 연결',3.64,3.00,3.20,1.65,hi('serve')?C.pale:C.gray);
 n(s,'AI 자원 풀','GPU · 서로 다른 NPU · CPU',7.43,3.00,5.20,1.65,hi('run')?C.pale:C.gray);
 a(s,3.05,3.82,3.64,3.82);a(s,6.84,3.82,7.43,3.82);
 box(s,3.64,5.24,8.99,.74,hi('observe')?C.vp:C.gray);
 t(s,'통합 관측·운영',3.89,5.40,3.2,.35,20,C.violet,true);
 t(s,'요청 상태 + 모델 상태 + 자원 상태',7.2,5.42,5.15,.32,15,C.muted);
 a(s,5.24,4.65,5.24,5.24,C.violet,true);a(s,10.03,4.65,10.03,5.24,C.violet,true);
}

{
let s=page('01  출발점','서로 다른 가속기를 어떻게 함께 쓸 것인가?','장비마다 특성이 다르고, 요청마다 필요한 자원도 다릅니다.',true);
n(s,'짧은 대화','빠른 첫 응답',.65,2.66,3.72,1.42,C.panel,C.white);
n(s,'긴 문서 질문','많은 입력 문맥 처리',4.80,2.66,3.72,1.42,C.panel,C.white);
n(s,'동시 요청 증가','처리량과 응답 지연 관리',8.95,2.66,3.72,1.42,C.panel,C.white);
t(s,'어디서, 어떤 방식으로 실행할까?',2.0,4.37,9.3,.65,29,C.mint,true,'center');
for(let i=0;i<3;i++)a(s,2.51+i*4.15,5.05,2.51+i*4.15,5.45,C.mint);
['GPU 자원','NPU 자원 A','NPU 자원 B'].forEach((v,i)=>{box(s,.65+i*4.15,5.48,3.72,.69,C.panel);t(s,v,.86+i*4.15,5.64,3.3,.34,21,C.white,true,'center');});
takeaway(s,'ETRI는 이 배치 문제를 실제 시스템에서 실험할 기반을 구축했습니다.');
note(s,'서로 다른 요청과 서로 다른 장비를 연결하는 자원관리 문제가 출발점입니다. 상단과 하단의 세 열은 예시이며 특정 요청 종류가 특정 하드웨어에 항상 대응한다는 뜻이 아닙니다. 가운데 질문은 선택 정책이 필요한 지점을 나타냅니다. 최적 배치 정책 전체를 이미 완성했다고 주장하지 않습니다.','README.md; PD disaggregation_HISTORY.md §§1,6,12');
}
{
let s=page('02  전체 환경','여러 장비를 하나의 서빙 환경으로 연결','사용자는 공통된 방식으로 요청하고, 내부에서는 서로 다른 자원이 실행합니다.');map(s);
takeaway(s,'연결된 자원 위에, 요청 처리와 관측·운영 체계를 구성했습니다.');
note(s,'이 그림은 논리 구조이며 서버별 물리 토폴로지가 아닙니다. 통합 서빙 계층은 모델 경로와 실행 대상 연결을 담당하고, GPU·NPU·CPU에는 각 엔진이 배포됩니다. 관측 도구는 요청 트래픽 자체를 중계하지 않고 기존 메트릭과 Kubernetes 상태를 수집·연결합니다. 모델 파일 공유 저장소도 구성했습니다. 모든 모델이 항상 실행되거나 동일 모델이 모든 가속기에서 실행된다는 뜻은 아닙니다.','docs/ENVIRONMENT-GUIDE.md; manifests/epp/README.md; lmd-top/README.ko.md');
}
{
let s=page('03  요청 하나의 여정','질문 하나가 답변이 되기까지','아래 네 단계가 연결되어야 하나의 서빙 서비스가 됩니다.');
const vals=[['요청 수신','사용자가 질문'],['실행 위치 선택','모델과 실행 대상을 연결'],['모델 실행','가속기에서 추론'],['결과 반환','생성된 답변을 전달']];
vals.forEach((v,i)=>{const x=.65+i*3.10;pill(s,String(i+1).padStart(2,'0'),x,2.72,.57);n(s,v[0],v[1],x,3.42,2.72,1.68,i===1||i===2?C.pale:C.gray);if(i<3)a(s,x+2.72,4.24,x+3.10,4.24);});
box(s,3.75,5.56,5.82,.48,C.vp);t(s,'자원관리 정책이 개입할 수 있는 지점',3.96,5.65,5.4,.29,15,C.violet,true,'center');
takeaway(s,'우리는 “어디서 실행할지”와 “어떻게 실행할지”를 다룹니다.');
note(s,'실제 구현의 응답은 역방향 또는 streaming으로 반환되지만 여기서는 개념적 순서를 그렸습니다. 실행 위치 선택은 경로 분기와 모델 풀 내 endpoint 선택 등을 포함합니다. 요청마다 자동으로 최적 가속기를 고르는 알고리즘이 완료됐다는 뜻은 아닙니다. 다음 장부터 구축·개발한 영역을 강조합니다.','manifests/epp/README.md; PD disaggregation_HISTORY.md §6.1');
}
{
let s=page('04  ETRI 작업 범위','연결하고, 관측하고, 실행 방식을 확장','세 작업은 서로 다른 계층에 있지만 같은 자원관리 문제를 향합니다.');
const cards=[['01','환경 연결','이종 자원에서 모델 서빙','기존 기술 구성·연동',C.teal,C.pale],['02','관측·운영','요청과 자원 상태를 함께 확인','통합 도구 직접 개발',C.violet,C.vp],['03','실행 단계 분리','다른 가속기로 역할과 상태 전달','실험 런타임 직접 개발',C.teal,C.pale]];
cards.forEach((r,i)=>{let x=.65+i*4.15;box(s,x,2.69,3.72,3.28,r[5]);t(s,r[0],x+.24,2.92,3.24,.4,15,r[4],true);t(s,r[1],x+.24,3.58,3.24,.55,28,r[4],true);t(s,r[2],x+.24,4.47,3.24,.54,16);t(s,r[3],x+.24,5.37,3.24,.3,12,C.muted);});
takeaway(s,'기존 플랫폼을 활용한 구축과, ETRI가 직접 개발한 영역을 구분합니다.');
note(s,'기존 Kubernetes/llm-d/벤더 엔진은 기반으로 활용했습니다. lmd-top과 EPP 점수 관측 확장은 직접 개발했고, 다른 서버에서 자체 KV 소유·이송 런타임과 PD 실험을 수행했습니다. 세 작업이 완전한 자동 제어 루프로 통합되었다고 설명하지 않습니다.','README.md; lmd-top/CHANGELOG.md; PD disaggregation_HISTORY.md §§4–8');
}
{
let s=page('05  환경 연결','모델을 준비해서, 여러 자원에서 실행','장비를 묶는 것에서 모델을 올리고 운영하는 흐름까지 구성했습니다.');
n(s,'모델 준비','다운로드 · 필요 시 컴파일',.65,3.00,3.28,1.63);
n(s,'공유 저장','원본과 실행 산출물 보관',5.03,3.00,3.28,1.63,C.gray);
n(s,'자원에 배포','가속기에 맞는 모델 서버',9.41,3.00,3.28,1.63);
a(s,3.93,3.82,5.03,3.82);a(s,8.31,3.82,9.41,3.82);
box(s,.65,5.25,12.04,.74,C.gray);t(s,'통합 서빙 기반',.90,5.45,3.2,.31,19,C.teal,true);t(s,'공통 요청 경로  ·  모델별 실행 환경  ·  배포·운영 작업',4.32,5.45,8.07,.31,17);
takeaway(s,'이 기반 위에 배치·라우팅 정책을 적용할 수 있습니다.');
note(s,'모델 준비에는 NPU용 사전 컴파일이 포함됩니다. 모든 모델을 모든 장비에 그대로 이식하는 시스템은 아니며 엔진·모델·컴파일 지원 조건을 따릅니다. 공유 모델 스토어와 inventory discovery를 구현했고 lmd-top의 모델 다운로드/컴파일/배포 흐름과 연결했습니다. 구현 이름: Kubernetes, llm-d, model-store PVC, compile Job.','manifests/README-model-store.md; lmd-top/README.ko.md; lmd-top/CHANGELOG.md v0.35.0');
}
{
let s=page('06  관측·운영','“어떤 모델이 어디에서 실행되고 있나?”','하나의 운영 질문에서 출발해 모델과 자원 상태를 연결해 봅니다.');
t(s,'통합 관측 도구',.67,2.65,3.6,.4,22,C.violet,true);t(s,'lmd-top',.67,3.20,3.6,.59,33,C.ink,true);
[['모델 상태','실행 중인가?'],['실행 위치','어느 자원을 쓰는가?'],['부하 상태','어디가 혼잡한가?']].forEach((r,i)=>{t(s,r[0],.67,4.08+i*.64,1.1,.30,14,C.violet,true);t(s,r[1],1.90,4.08+i*.64,2.55,.30,14);});
s.addImage({path:path.join(root,'docs/images/lmd-top-ppt.gif'),x:4.79,y:2.61,w:7.32,h:7.32*1075/1806});
t(s,'UI 데모 · 수치 변화는 합성',.67,6.63,3.9,.25,11,C.muted);
note(s,'시연할 때 화면의 모든 열과 단축키를 설명하지 않습니다. 먼저 어떤 모델이 어디서 실행되는지 질문하고, Serving 화면의 상태/실행 노드를 보여준 뒤 Infra의 장비 상태로 이어갑니다. 이 녹화는 전체 UI를 순환하는 기존 데모이며 현재 live 트래픽 녹화가 아닙니다. 실제 구성 스냅샷을 바탕으로 --cast가 사용률과 성능 수치를 합성했습니다. 화면 숫자를 실측 성능으로 설명하지 않습니다. 원본 GIF는 25.14초 157프레임 무한 반복. lmd-top은 상태 조회와 모드별 운영 액션을 제공하지만 자동 최적화 정책 엔진은 아닙니다.','lmd-top/README.ko.md; lmd-top/src/cast.rs; docs/images/lmd-top-ppt.gif');
}
{
let s=page('07  실행 방식의 개념','모델의 실행은 두 단계로 나눌 수 있습니다','입력 문맥을 처리한 뒤, 그 상태를 활용해 답변을 생성합니다.');
n(s,'입력 처리','질문·문서의 문맥을 계산',1.05,3.02,4.50,1.90);
n(s,'답변 생성','다음 토큰을 반복해서 생성',7.80,3.02,4.50,1.90);
a(s,5.55,3.97,7.80,3.97);
t(s,'중간 계산 상태',5.67,3.14,2.02,.40,14,C.teal,true,'center');
t(s,'KV cache',5.67,4.27,2.02,.35,13,C.muted,false,'center');
t(s,'Prefill',1.29,5.21,4.02,.40,16,C.muted);t(s,'Decode',8.04,5.21,4.02,.40,16,C.muted);
takeaway(s,'두 단계의 역할이 다르다면, 서로 다른 가속기에 맡길 수 있을까?');
note(s,'LLM 추론의 prefill/decode를 역할로 먼저 설명하고 명칭은 아래에 보조 표기합니다. KV cache는 앞서 계산한 문맥 상태이며 완성된 답변 파일이 아닙니다. 실제 첫 토큰 경계 등의 세부는 생략한 개념도입니다. 이 설명에서 특정 벤더가 항상 입력 처리 또는 답변 생성에 유리하다고 단정하지 않습니다.','PD disaggregation_HISTORY.md §§1,4,6');
}
{
let s=page('08  실행 방식 확장','두 가속기에 역할을 나누고, 상태를 전달','ETRI는 실제 중간 상태를 넘겨 실행을 이어가는 실험 경로를 구현했습니다.',true);
box(s,.65,2.76,12.00,1.13,C.panel);t(s,'한 가속기에서 실행',.91,2.97,3.6,.35,18,C.white,true);t(s,'입력 처리  →  답변 생성',5.02,3.02,6.96,.35,22,C.white,true);
n(s,'가속기 A','입력 처리',.65,4.55,3.40,1.38,C.panel,C.white);
n(s,'상태 전달','실제 KV 이송',4.97,4.55,3.40,1.38,C.mint,C.dark);
n(s,'가속기 B','답변 생성',9.29,4.55,3.40,1.38,C.panel,C.white);
a(s,4.05,5.24,4.97,5.24,C.mint);a(s,8.37,5.24,9.29,5.24,C.mint);
takeaway(s,'서로 다른 NPU 벤더 사이에서도 역할을 교환하며 실험했습니다.');
note(s,'사용자가 제공한 다른 서버의 PD disaggregation_HISTORY.md를 근거로 작성했습니다. 자체 런타임이 KV를 명시적 입출력으로 소유하고, prefill이 만든 KV를 decode에 전달합니다. 초기 재프리필 모사나 prefix-cache 상한 실험과 구분합니다. RNGD→RNGD, RNGD→ATOM, ATOM→RNGD, ATOM→ATOM 네 조합의 기록이 있습니다. 가속기 A/B는 물리 카드 역할이며 별도 서버 간 네트워크 전송을 주장하는 그림이 아닙니다. 현재 서빙 이송 경로는 공유 메모리이고 별도 TCP 커넥터 검증 기록도 있습니다. NIXL/장치 직접 전송은 미완료. 출력 정합 검증 및 llm-d 게이트웨이 배포·측정 기록은 있으나 이번 PPT 제작에서 원격 원시 결과나 추론을 재검증하지 않았습니다.','PD disaggregation_HISTORY.md §§4,6.1–6.3,12');
}
{
let s=page('09  실험에서 얻은 질문','분리하는 것만으로 효율이 좋아지지는 않습니다','부하와 전송 비용에 따라 유리한 실행 방식이 달라집니다.');
const rows=[['역할 분리','두 단계를 겹쳐 처리할 가능성','추가 자원과 상태 전달 비용'],['여러 요청 묶기','자원을 함께 써 처리량 확대','배치 대기와 상태 관리 비용'],['전송·계산 겹치기','중간 상태 전달 지연 완화','계산·복사·배치의 조정 필요']];
t(s,'실행 방식',.88,2.62,3,.36,16,C.muted,true);t(s,'기대하는 효과',4.48,2.62,3.6,.36,16,C.teal,true);t(s,'함께 고려할 비용',8.85,2.62,3.6,.36,16,C.amber,true);
rows.forEach((r,i)=>{let y=3.26+i*.87;box(s,.65,y,12.03,.70,i%2?C.white:C.gray);t(s,r[0],.88,y+.15,3.25,.35,19,C.ink,true);t(s,r[1],4.48,y+.17,3.97,.32,15);t(s,r[2],8.85,y+.17,3.59,.32,15);});
takeaway(s,'실험은 “무조건 분리”가 아니라 “언제 분리할지”를 묻는 근거가 됩니다.');
note(s,'이 장은 정량 성과 자랑이 아니라 수행한 비교에서 생긴 자원관리 질문을 설명합니다. 동일 배치 대조군에서 PD 전체 처리량이 높더라도 카드당 효율은 solo가 높았던 조건이 있습니다. continuous batching은 구현했지만 당시 static보다 느렸고 KV 재구성과 호스트 왕복이 원인이었습니다. 후속 스트리밍/프리패치 최적화는 특정 조건에서 지연을 줄였습니다. 단계별 실험은 설정과 버전이 달라 수치를 합산하지 않습니다. 모든 환경에 적용되는 순위나 일반 성능 결론은 아닙니다.','PD disaggregation_HISTORY.md §§6.4,6.5,7,11');
}
{
let s=page('10  공동연구 접점','만들어진 환경 위에서, 선택 정책을 함께 연구','ETRI의 실행·관측 기반에 배치·스케줄링·제어 연구를 연결할 수 있습니다.');
const labels=[['어디에 배치할까?','요청·모델 → 자원 선택'],['언제 나눌까?','한 장비 실행 ↔ 단계 분리'],['어떻게 조절할까?','관측 결과 → 운영 제어']];
labels.forEach((r,i)=>{let x=.65+i*4.15;n(s,r[0],r[1],x,2.77,3.72,1.72,i===2?C.vp:C.pale);});
box(s,.65,5.15,12.02,.79,C.gray);t(s,'공동 실험',.91,5.37,2.03,.33,19,C.teal,true);t(s,'같은 요청 조건에서 정책을 바꾸고, 지연·처리량·자원 효율을 비교',3.14,5.39,9.21,.31,16);
takeaway(s,'논의할 것: 어떤 결정 지점을 공동연구 대상으로 잡을 것인가?');
note(s,'협업 후보이며 이미 구현한 자동 정책이나 합의된 역할 분담을 뜻하지 않습니다. ETRI는 이종 서빙 구성, 관측·운영 도구, 실제 KV 이송 실험 런타임과 벤치 자료를 기반으로 논의할 수 있습니다. 교수님의 전문 분야에 따라 요청 배치, 단계 분리 기준, 배치 스케줄링, 지연 목표 기반 제어 중 우선 범위를 정합니다. 첫 공동 실험은 모델·버전·입출력·배치·카드 수를 맞추고 latency/throughput/card-efficiency/energy를 비교하는 것으로 제안합니다. 운영 상태와 최신 통합 스윕은 후속 확인 필요합니다.','lmd-top/README.ko.md; PD disaggregation_HISTORY.md §§11,12');
}
{
let s=page('부록 A  용어 연결','본문의 개념은 어떤 구현과 연결되는가?','세부 용어는 질의응답에서 필요한 만큼만 설명합니다.');
const rows=[['통합 서빙','Kubernetes · llm-d · Gateway / EPP'],['관측·운영','Prometheus · lmd-top · Kubernetes API'],['모델 준비·배포','공유 모델 스토어 · NPU 컴파일 · 배포 작업'],['입력 처리 / 답변 생성','Prefill / Decode'],['중간 상태 전달','KV cache · KVConnector · 공유 메모리'],['이종 NPU 실험','Furiosa RNGD · Rebellions ATOM']];
rows.forEach((r,i)=>{let y=2.62+i*.57;box(s,.65,y,12.0,.51,i%2?C.white:C.gray);t(s,r[0],.87,y+.1,3.62,.30,16,C.teal,true);t(s,r[1],4.90,y+.1,7.5,.30,15);});
note(s,'본문에서는 개념을 먼저 설명하고 이 표에서만 구현 명칭을 연결합니다. 기존 기술과 자체 개발을 구별합니다. 모든 벤더 엔진을 수정한 것이 아니라 특정 실험 런타임을 직접 구현했습니다.','README.md; lmd-top/README.ko.md; PD disaggregation_HISTORY.md');
}
{
let s=page('부록 B  현황과 근거','구축 이력과 현재 가동 상태를 구분합니다','아래 상태는 2026-09-08 클러스터 조회 및 제공 문서 기준입니다.');
n(s,'클러스터 구성','등록 노드 8대\nGPU 2 · ATOM 4 · RNGD 6',.65,2.68,5.81,1.75,C.gray);
n(s,'현재 운영 상태','관리·라우팅 구성 가동\n모델 워커 replica 0',6.88,2.68,5.81,1.75,C.gray);
n(s,'구현·측정 기록','통합 서빙 · 관측 도구\n실제 KV 이송 · 이종 NPU 실험',.65,4.80,5.81,1.75);
n(s,'추가 검증이 필요한 부분','최신 설정 통합 비교 · 장시간 운영\n전송·배치 개선 · 자동 제어 정책',6.88,4.80,5.81,1.75,C.vp);
note(s,'2026-09-08 이전 턴의 read-only kubectl 조회: 8노드. GB10 각1 GPU 두 서버, etri-001 ATOM4/RNGD2/nvidiaGPU0, ESC8000 RNGD4 SchedulingDisabled, cpu-3 NotReady. 등록 자원 수는 즉시 스케줄 가능한 자원 수와 다릅니다. Gateway Programmed=True, EPP/hetero-pd-gateway/ds4-inject-proxy 가동, 모델 workers 0/0. 동작 중인 Gateway만으로 추론 성공을 주장하지 않습니다. 새로 제공된 PD 문서는 다른 서버의 작업 기록 요약이며 원격 원시 코드/결과를 이 PPT 제작에서 재검증하지 않았습니다. 실험 수치와 상세 한계는 원문과 발표 노트 참조.','2026-09-08 kubectl 조회; docs/ENVIRONMENT-GUIDE.md; lmd-top/CHANGELOG.md; PD disaggregation_HISTORY.md §§11,12');
}
for(const q of checks){if(q.x<0||q.y<0||q.x+q.w>13.334||q.y+q.h>7.5)throw Error(JSON.stringify(q));}
const file=path.join(out,'K-Cloud_ETRI_개념중심_기술소개_v3.pptx');
p.writeFile({fileName:file}).then(()=>{
 fs.writeFileSync(path.join(out,'발표노트.md'),'# ETRI 기술 소개 — 본문 10장 + 부록 2장\n\n'+notes.map((x,i)=>'## '+(i+1)+'장\n\n'+x).join('\n\n'));
 console.log(file);
});
