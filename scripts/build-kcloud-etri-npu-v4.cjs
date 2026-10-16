// Editable technical meeting deck. npm dependency: pptxgenjs.
const Pptx=require('pptxgenjs'),fs=require('fs'),path=require('path');
const root=path.resolve(__dirname,'..'),out=path.join(root,'docs/presentations/kcloud-etri-npu-v4');fs.mkdirSync(out,{recursive:true});
const p=new Pptx();p.layout='LAYOUT_WIDE';p.author='ETRI';p.title='NPU 특성 분석에서 모델·자원 관리와 실행 단계 배치까지';p.lang='ko-KR';
p.theme={headFontFace:'Noto Sans CJK KR',bodyFontFace:'Noto Sans CJK KR',lang:'ko-KR'};
const C={ink:'16363C',muted:'62797E',teal:'087F83',mint:'50D9BE',pale:'E8F5F2',gray:'F2F5F5',line:'CCDADC',dark:'112C32',panel:'22434B',white:'FFFFFF',purple:'795BC2',vp:'EFEBF9',amber:'A16823',ap:'FFF2E0'};
const S=p.ShapeType,notes=[],audit=[];
function b(s,x,y,w,h,fill=C.pale,line){s.addShape(S.roundRect,{x,y,w,h,radius:.12,rectRadius:.12,fill:{color:fill},line:{color:line||fill,width:line?1:0}});audit.push({x,y,w,h});}
function t(s,text,x,y,w,h,size=17,color=C.ink,bold=false,align='left'){s.addText(text,{x,y,w,h,fontFace:'Noto Sans CJK KR',fontSize:size,color,bold,align,margin:0,wrap:false,valign:'mid',paraSpaceAfter:0});audit.push({x,y,w,h,text});}
function a(s,x1,y1,x2,y2,color=C.teal,dash=false,head=true){s.addShape(S.line,{x:Math.min(x1,x2),y:Math.min(y1,y2),w:Math.abs(x2-x1),h:Math.abs(y2-y1),flipH:x2<x1,flipV:y2<y1,line:{color,width:1.8,dashType:dash?'dash':'solid',beginArrowType:'none',endArrowType:head?'triangle':'none'}});}
function node(s,title,sub,x,y,w,h,fill=C.pale,color=C.ink){b(s,x,y,w,h,fill);t(s,title,x+.22,y+.17,w-.44,.43,21,color,true);if(sub)t(s,sub,x+.22,y+.77,w-.44,h-.94,14,color);}
function tag(s,text,x,y,w,color=C.teal,fill=C.pale){b(s,x,y,w,.37,fill);t(s,text,x+.08,y+.04,w-.16,.28,11,color,true,'center');}
function pg(label,title,sub,dark=false){let s=p.addSlide();s._dark=dark;s.background={color:dark?C.dark:C.white};t(s,'ETRI / K-CLOUD   '+label,.6,.28,12,.3,11,dark?C.mint:C.teal,true);t(s,title,.6,.91,12.1,.68,32,dark?C.white:C.ink,true);if(sub)t(s,sub,.62,1.75,12,.43,14,dark?'BAD0D2':C.muted);t(s,'NPU 특성 분석 · 모델·자원 관리 · 실행 방식 연구',.62,7.13,11,.20,9,dark?'91ACB0':C.muted);t(s,String(p._slides.length).padStart(2,'0'),12.14,7.10,.52,.26,10,dark?'91ACB0':C.muted,false,'right');return s;}
function end(s,text){t(s,text,.65,6.57,12,.38,19,s._dark?C.mint:C.teal,true);}
function nt(s,text,source){let q=text+'\n\n근거: '+source;s.addNotes(q);notes.push(q);}
function chip(s,name,sub,x,y,w,color=C.teal){b(s,x,y,w,1.34,C.gray);b(s,x+.20,y+.22,.75,.75,C.white,color);for(let i=0;i<4;i++){let q=.30+i*.15;a(s,x+.13,y+q,x+.20,y+q,color,false,false);a(s,x+.95,y+q,x+1.02,y+q,color,false,false);}t(s,'AI',x+.28,y+.40,.59,.33,17,color,true,'center');t(s,name,x+1.18,y+.19,w-1.38,.40,18,color,true);t(s,sub,x+1.18,y+.74,w-1.38,.32,12,C.muted);}
function chart(s,title,labels,values,x,y,w,h,colors){s.addChart(p.ChartType.bar,[{name:title,labels,values}],{x,y,w,h,barDir:'bar',showTitle:true,title,titleFontFace:'Noto Sans CJK KR',titleFontSize:16,showLegend:false,showValue:true,dataLabelPosition:'outEnd',dataLabelFormatCode:'0.00',dataLabelColor:C.ink,dataLabelBkgrdColor:C.white,catAxisLabelFontFace:'Noto Sans CJK KR',catAxisLabelFontSize:13,valAxisLabelFontSize:10,chartColors:colors||[C.teal],showCatName:false,valAxisMinVal:0,valGridLine:{color:'DFE7E8',width:.5},catGridLine:{style:'none'},showBorder:false,showCatName:false,showShadow:false,showPlotArea:false,showCatName:false,showCatName:false});}

{
let s=pg('01  실제 구축 환경','GPU와 두 종류의 NPU를 서빙 환경에 연결','아래는 구축한 환경의 논리 구성입니다. 모델은 필요에 따라 준비·배포합니다.');
node(s,'사용자 요청','공통 API',.65,2.50,2.39,1.25,C.gray);node(s,'통합 서빙 계층','모델 경로 · 실행 대상 연결',3.63,2.50,5.05,1.25);a(s,3.04,3.12,3.63,3.12);
node(s,'공유 모델 저장소','원본 · 컴파일 산출물',9.25,2.50,3.42,1.25,C.gray);
a(s,6.15,3.75,6.15,4.03,C.teal,false,false);a(s,2.59,4.03,10.74,4.03,C.teal,false,false);
[2.59,6.67,10.74].forEach(x=>a(s,x,4.03,x,4.31));
chip(s,'NVIDIA GPU','GPU 모델 서버',.65,4.31,3.88);chip(s,'Furiosa NPU','벤더별 실행 환경',4.73,4.31,3.88);chip(s,'Rebellions NPU','벤더별 실행 환경',8.81,4.31,3.88);
a(s,12.05,3.75,12.05,4.31,C.purple,true);t(s,'모델 로드',10.94,3.80,1.01,.20,9,C.purple);
a(s,6.67,5.65,6.67,5.94,C.purple,true);a(s,10.74,5.65,10.74,5.94,C.purple,true);
b(s,3.63,5.94,9.06,.45,C.vp);t(s,'lmd-top  |  모델 준비·배포·상태 확인·운영',3.85,6.02,8.62,.28,15,C.purple,true);
end(s,'이종 장비를 연결한 뒤, 모델을 어떻게 준비하고 관리할지가 과제가 됐습니다.');
nt(s,'과제 배경 설명 없이 실제 구축 환경에서 시작합니다. 아이콘은 특정 카드 외형을 복제한 제품 사진이 아니라 장비 종류를 구분하는 편집 가능한 도형입니다. 실제 환경에는 CPU 워커, 관리 노드, 모니터링, 공유 NAS가 있습니다. 여기서는 GPU·Furiosa·Rebellions와 모델 생애주기를 중심으로 추상화했습니다. Gateway가 디바이스에 직접 요청하는 것이 아니라 모델 서버에 연결합니다. 이 그림은 논리 구성이고 모두 현재 가동 중이라는 뜻이 아닙니다. lmd-top은 관측·운영 도구이며 트래픽 프록시가 아닙니다.','docs/ENVIRONMENT-GUIDE.md; manifests/README-model-store.md; lmd-top/README.ko.md; 2026-09-08 클러스터 조회');
}
{
let s=pg('02  GPU와 NPU: 사용한 실행 경로의 차이','NPU에서는 실행 전 준비 조건까지 관리','하드웨어 전체의 우열 비교가 아니라, 우리 소프트웨어 환경에서 경험한 차이입니다.');
tag(s,'GPU 경로',.65,2.72,1.55);tag(s,'NPU 경로',.65,4.56,1.55,C.purple,C.vp);
const xs=[2.70,6.14,9.58];
['모델 원본','런타임 로드','GPU 실행'].forEach((v,i)=>{b(s,xs[i],2.62,3.09,1.02,C.gray);t(s,v,xs[i]+.19,2.95,2.71,.38,21,C.ink,true);if(i<2)a(s,xs[i]+3.09,3.13,xs[i+1],3.13);});
[['모델 + 실행 조건','타깃 · 길이 · 배치 등'],['벤더별 컴파일','실행 산출물 준비'],['NPU 실행','호환 산출물 로드']].forEach((v,i)=>{node(s,v[0],v[1],xs[i],4.40,3.09,1.40,C.vp);if(i<2)a(s,xs[i]+3.09,5.10,xs[i+1],5.10,C.purple);});
end(s,'관리 단위가 “모델 파일”에서 “모델 + 가속기 + 실행 설정 + 산출물”로 넓어집니다.');
nt(s,'GPU도 JIT·그래프 컴파일 등을 사용할 수 있습니다. GPU에는 컴파일이 없고 모든 NPU가 동일한 사전 컴파일 방식이라는 뜻이 아닙니다. 여기서 GPU 경로는 사용한 vLLM 계열 일반 배포 흐름, NPU 경로는 사용한 RBLN/Furiosa 컴파일·아티팩트 기반 경로입니다. Furiosa는 사전 컴파일된 산출물을 가져오는 경우도 있습니다. 모델·타깃·길이·배치 등 조건은 엔진마다 다릅니다. 비교는 성능·가격·전력의 벤더 우열을 주장하지 않습니다.','manifests/README-model-store.md; manifests/compile-*.py; PD disaggregation_HISTORY.md §§3.1–3.2,5.4,8');
}
{
let s=pg('03  분석 ①  실행 조건','같은 모델·요청에서도 설정에 따라 지연이 달랐습니다','Furiosa 공식 엔진 · Llama-3.1-8B BF16 · 입력/출력 256토큰 · 동시성 1 · 요청 24개');
chart(s,'첫 토큰 지연 p50 (ms)',['coarse','fine','preset'],[88.12,27.85,22.08],.65,2.60,6.34,3.53);
node(s,'분석한 것','입력 길이 · 버킷 · 동시성\n지연 · 처리량 · 전력',7.59,2.73,5.08,1.59,C.gray);
node(s,'확인한 것','첫 토큰 지연은 크게 달라짐\n토큰 간 지연은 약 16.3–16.5 ms',7.59,4.65,5.08,1.48);
end(s,'장비 종류만으로 성능을 판단할 수 없어, 요청 조건과 실행 설정을 함께 봐야 합니다.');
nt(s,'버킷은 실행에 사용하는 입력/배치 크기 등의 미리 정해진 규격을 의미합니다. 제공 문서의 §3.2가 원본 JSONL을 확인해 요약한 값입니다. coarse TTFT88.12/TPOT16.48/output59.7, fine27.85/16.29/61.1, preset22.08/16.34/61.1. 세 조건 모두 shape_exact=true, 실패0. 이 PPT 제작에서 원시 JSONL이나 NPU 실험을 다시 실행하지 않았습니다. 특정 길이·동시성 조건의 비교이며 모든 길이에 일반화하지 않습니다. 전력/토큰당 에너지를 측정한 하니스도 있으나 GPU와 같은 조건의 우열 비교를 여기서 제시하지 않습니다.','PD disaggregation_HISTORY.md §§3.1–3.3,11');
}
{
let s=pg('04  분석 ②  실행 위치와 데이터 이동','호스트 왕복과 배치 구성도 성능을 좌우했습니다','자체 NPU 실행 경로에서 데이터 이동과 연산 위치를 바꾸어 측정했습니다.');
node(s,'NPU 계산','모델 연산',.65,2.85,3.44,1.41);node(s,'호스트 처리','중간 복사 · 일부 연산',4.95,2.85,3.44,1.41,C.ap);node(s,'NPU 계산','다음 단계 실행',9.25,2.85,3.44,1.41);a(s,4.09,3.55,4.95,3.55);a(s,8.39,3.55,9.25,3.55);
t(s,'개선한 부분',.70,4.85,3.35,.36,18,C.teal,true);t(s,'상태를 장치에 유지\n출력 연산을 장치로 이동\n여러 요청을 묶어 실행',.70,5.30,4.51,.93,17);
b(s,5.64,4.72,7.04,1.52,C.gray);t(s,'78.86 → 26.91 ms/step',5.90,4.98,6.52,.53,28,C.teal,true);t(s,'RNGD B=4 · 출력 연산을 호스트에서 장치로 이동',5.90,5.68,6.52,.28,13,C.muted);
end(s,'자원 상태 관측과 함께, 실행 내부의 병목을 바꾸는 연구도 진행했습니다.');
nt(s,'예시는 PD 문서 §5.3의 2026-08-19 기록: RNGD B=4 serving engine, lm_head를 host에서 device로 이동하여 78.86→26.91ms/step. lm_head는 다음 토큰 점수를 계산하는 출력 연산으로 설명합니다. 커널/엔진의 step 비용이며 API E2E latency 또는 배치로 나눈 token당 비용이 아닙니다. 다른 별도 기록으로 resident KV48.2→16.3ms/token 및 배치 디코드 B1/B4/B8 비교가 있습니다. 각 개선은 별도 조건이므로 합산하지 않습니다. 이런 데이터 이동·배치 민감성이 NPU에만 존재한다고 주장하지 않습니다.','PD disaggregation_HISTORY.md §§5.1,5.3,7,11');
}
{
let s=pg('05  분석에서 관리로','NPU 특성을 관리 기능으로 연결했습니다','모델을 실행 가능하게 만들고, 올린 뒤의 상태까지 이어서 관리합니다.');
const r=[['실행 산출물이 필요','모델·타깃·빌드를 함께 관리','모델 목록 · 공유 저장소'],['실행 조건의 영향','컴파일·배포 조건을 선택','작업 생성 · 진행 상태'],['배치·이동·부하의 영향','모델과 자원 상태를 함께 관측','실행 위치 · 지연 · 점유']];
t(s,'확인한 특성',.86,2.65,3.18,.3,15,C.muted,true);t(s,'필요한 관리',5.05,2.65,3.20,.3,15,C.teal,true);t(s,'lmd-top의 대응',9.25,2.65,3.15,.3,15,C.purple,true);
r.forEach((v,i)=>{let y=3.29+i*.88;b(s,.65,y,12.04,.67,i%2?C.white:C.gray);t(s,v[0],.86,y+.16,3.42,.32,17,C.ink,true);a(s,4.27,y+.34,4.76,y+.34);t(s,v[1],5.05,y+.16,3.85,.32,15);t(s,v[2],9.25,y+.16,3.15,.32,14,C.purple);});
end(s,'lmd-top은 컴파일러가 아니라, 모델 준비·배포·관측을 연결하는 관리 도구입니다.');
nt(s,'이 장은 기능과 요구의 논리적 대응이며, 이 PD 벤치가 lmd-top 개발 이전에 수행되어 제품 요구사항을 역사적으로 도출했다는 뜻은 아닙니다. lmd-top 개발(6~7월)과 PD/벤치 작업(8월)은 서로 다른 작업 흐름이었습니다. 이번 기술 소개에서 공통 자원관리 맥락으로 연결합니다. lmd-top이 세부 커널 병목을 자동 진단하거나 자동 최적화하는 것은 아닙니다. 구현된 모델 준비/배포 및 기존 exporter와 API 기반 관측 기능 범위로 설명합니다.','lmd-top/README.ko.md; lmd-top/CHANGELOG.md; PD disaggregation_HISTORY.md');
}
{
let s=pg('06  lmd-top ①  모델 준비·배포','모델 선택부터 컴파일·배포 작업까지 관리','벤더 도구가 실행하고, lmd-top이 작업과 결과를 연결해 보여줍니다.');
b(s,.65,2.69,12.04,1.62,C.vp);t(s,'lmd-top',.88,2.88,2.4,.37,21,C.purple,true);
['모델 선택','컴파일 조건','산출물 확인','배포 대상'].forEach((v,i)=>{let x=.89+i*3.0;t(s,v,x,3.57,2.57,.35,20,C.ink,true);if(i<3)a(s,x+2.34,3.75,x+2.79,3.75,C.purple);});
node(s,'벤더 컴파일 작업','Furiosa / Rebellions',.89,5.01,3.53,1.15,C.gray);node(s,'공유 모델 저장소','다운로드 · 컴파일 산출물',4.89,5.01,3.53,1.15,C.gray);node(s,'모델 서버 배포','타깃 장비 · 실행 옵션',8.89,5.01,3.53,1.15,C.gray);
a(s,3.92,4.31,3.92,5.01,C.purple);a(s,6.65,4.31,6.65,5.01,C.purple);a(s,10.65,4.31,10.65,5.01,C.purple);
end(s,'작업 진행률·성공·실패·로그를 확인하고, 준비된 모델을 장비에 배포합니다.');
nt(s,'실제 기능: Library/Model List에서 catalog 가능성 및 store builds 확인, Zoo에서 벤더 모델 탐색/prefetch, Compile 폼에서 RBLN/Furiosa 조건 선택 및 Job 생성, Activity에서 compile/prefetch/deploy 진행 상태 확인, Deploy에서 노드의 할당 기준 용량과 타깃 선택. 컴파일은 벤더 도구를 실행하는 작업이며 lmd-top 자체가 compiler가 아닙니다. apply/운영 액션은 권한 모드 및 확인 흐름을 따릅니다. 모든 모델/파라미터 조합이 지원된다는 뜻은 아닙니다.','lmd-top/README.ko.md; lmd-top/CHANGELOG.md v0.34–0.36; manifests/README-model-store.md');
}
{
let s=pg('07  lmd-top ②  관측·운영','모델·요청·장비 상태를 한 화면에서 연결','어떤 모델이 어디서 실행되고, 요청이 어디로 향하며, 어느 자원이 사용되는가?');
t(s,'Serving',.67,2.81,3.70,.41,22,C.purple,true);t(s,'모델 상태 · 실행 위치\n스케일 · 재시작 · 롤백',.67,3.34,3.70,.65,16);
t(s,'Traffic',.67,4.27,3.70,.41,22,C.purple,true);t(s,'요청 경로 · 선택 점수\n큐 · KV 상태',.67,4.80,3.70,.65,16);
t(s,'Infra',.67,5.73,3.70,.41,22,C.purple,true);t(s,'장비 점유 · 메모리 · 전력',.67,6.26,3.90,.33,15);
s.addImage({path:path.join(root,'docs/images/lmd-top-ppt.gif'),x:4.81,y:2.65,w:7.28,h:7.28*1075/1806});
t(s,'UI 데모 · 수치 변화는 합성',8.47,2.31,4.14,.20,10,C.muted,false,'right');
nt(s,'GIF는 실제 구성 스냅샷을 바탕으로 수치 변화와 선택을 합성한 UI 데모입니다. 성능 자료가 아닙니다. 기존 전체 뷰 순환 녹화라 발표자는 주요 화면에서 Serving/Traffic/Infra의 의미만 짚습니다. EPP endpoint score는 별도 개발한 score observer 플러그인이 제공하고 lmd-top은 pod 단위로 연결합니다. exporter·트래픽·권한에 따라 표시 가능한 지표가 다릅니다. 현재 데이터가 없는 칸은 자동적으로 추론한 값이 아닙니다.','lmd-top/README.ko.md; contrib/epp-score-observer/README.md; docs/images/lmd-top-ppt.gif');
}
{
let s=pg('08  실행 방식 연구','모델 배치에서, 실행 단계 배치로 확장','입력 처리(Prefill)와 답변 생성(Decode)을 다른 가속기에 맡겼습니다.',true);
b(s,.65,2.68,12.04,1.0,C.panel);t(s,'한 가속기에서 실행',.88,2.96,4.1,.38,20,C.white,true);t(s,'입력 처리 → 답변 생성',6.06,2.96,6.14,.38,23,C.white,true);
node(s,'NPU A','입력 문맥 처리',.65,4.52,3.43,1.57,C.panel,C.white);node(s,'중간 상태 전달','실제 KV cache 이송',4.98,4.52,3.43,1.57,C.mint,C.dark);node(s,'NPU B','상태를 이어 답변 생성',9.28,4.52,3.43,1.57,C.panel,C.white);a(s,4.08,5.30,4.98,5.30,C.mint);a(s,8.41,5.30,9.28,5.30,C.mint);
end(s,'자체 런타임에서 KV를 소유·전달하여, 다른 NPU에서도 실행을 이어갔습니다.');
nt(s,'다른 서버에서 수행한 연구 기록을 근거로 합니다. 공식 엔진에서 당시 KV export/import 훅이 없던 제약을 우회하려고 자체 KV 입출력 런타임을 구성했습니다. 실제 전달받은 KV로 decode를 이어가는 구현이며 초기 재프리필/캐시 에뮬레이션과 구분합니다. 기본 서빙 경로는 shared /dev/shm이고 별도 TCP 전송 테스트 기록이 있습니다. NPU A/B는 카드 역할로, 서로 다른 서버 간 직접 전송을 단정하지 않습니다. 자체 런타임 전체를 lmd-top이 자동 제어하는 통합 제품을 완성했다는 뜻은 아닙니다.','PD disaggregation_HISTORY.md §§4,6.1,12');
}
{
let s=pg('09  PD 실험과 자원 효율','전체 처리량과 카드당 효율은 다른 문제','동일 배치 조건 대조 실험 · 출력 100–160토큰 · 동시 요청 8개 · 후속 최적화 전');
chart(s,'전체 출력 처리량 (tok/s)',['한 카드 실행','두 카드 PD'],[106.6,143.7],.65,2.71,6.32,3.32);
node(s,'실제로 비교한 것','Furiosa ↔ Rebellions 역할 교환\n동종·이종 네 조합 · 한 카드 대조군',7.54,2.71,5.13,1.59,C.gray);
b(s,7.54,4.68,5.13,1.44,C.ap);t(s,'카드당 106.6 vs 71.85',7.77,4.94,4.67,.44,23,C.amber,true);t(s,'한 카드 실행 / 두 카드 PD · tok/s/장',7.77,5.58,4.67,.28,13,C.muted);
end(s,'입력·출력·부하·전송 비용을 보고, 언제 나눌지 결정하는 정책이 필요합니다.');
nt(s,'원문 §6.5의 384310c 재측정 기록. solo1card106.6 vs PD2card143.7tok/s, 출력100~160, in-flightN8, 동일 배치/closed-loop 조건. 카드당 PD71.85=143.7/2이며 solo가 약1.48배. 네 벤더 조합 스윕과 이 solo 비교는 별도 실험으로, 그래프가 네 벤더 조합의 비교라는 뜻은 아닙니다. 최신8/25최적화 전 기록. 모든 PD나 모든 요청에서 solo가 유리하다는 일반화 금지. 처음 불공정 비교는 철회됐고 이 값은 후속 동일 배치 대조군 기록입니다. 원문 commit 기록을 인용했고 PPT 제작 중 원시데이터를 재검증하지 않았습니다.','PD disaggregation_HISTORY.md §§6.2,6.5,11');
}
{
let s=pg('10  전체 작업의 연결','특성 분석·관리 도구·런타임을 같은 문제로 연결','분석은 실행 조건을 드러내고, 관리는 운영을 지원하며, 런타임 연구는 선택지를 넓힙니다.');
const r=[['NPU 특성 분석','조건에 따른 지연·처리량·이동 비용','벤치·비교 자료'],['모델·자원 관리','모델 준비 → 배포 → 관측·운영','lmd-top'],['실행 방식 확장','한 카드 실행 ↔ 이종 NPU 단계 분리','실제 KV 이송 런타임']];
r.forEach((v,i)=>{let y=2.71+i*1.03;b(s,.65,y,12.02,.80,i===1?C.vp:C.gray);t(s,v[0],.90,y+.20,3.24,.39,21,i===1?C.purple:C.teal,true);t(s,v[1],4.56,y+.25,5.41,.30,15);t(s,v[2],10.16,y+.26,2.31,.29,12,C.muted);});
end(s,'공통 질문: 어떤 모델을, 어떤 자원에, 어떤 실행 방식으로 배치할 것인가?');
nt(s,'세 작업의 논리적 관계를 나타냅니다. 모든 작업이 하나의 자동화 시스템으로 end-to-end 통합됐거나 분석→도구→런타임의 순서로 개발됐다는 뜻은 아닙니다. 직접 완료 근거가 있는 벤치·관측/운영도구·실제KV이송실험을 하나의 자원관리 논의로 묶습니다.','lmd-top/README.ko.md; PD disaggregation_HISTORY.md §§1,12');
}
{
let s=pg('11  협업 접점','구현된 환경 위에서 배치·제어 정책을 공동 연구','ETRI의 환경·도구·실험 경로에 연결할 후보입니다.');
[['모델 배치','어떤 실행 산출물을\n어느 자원에 올릴까?'],['단계 배치','언제 나누고\n어떤 NPU에 맡길까?'],['상태 기반 제어','관측값을 보고\n배치·규모를 어떻게 바꿀까?']].forEach((v,i)=>node(s,v[0],v[1],.65+i*4.15,2.83,3.72,2.20,i===2?C.vp:C.pale));
b(s,.65,5.58,12.02,.58,C.gray);t(s,'첫 공동 실험',.90,5.72,2.8,.3,17,C.teal,true);t(s,'같은 모델·요청 조건에서 정책을 바꾸고 지연·처리량·자원 효율 비교',3.89,5.72,8.42,.3,14);
end(s,'정할 것: 함께 바꿔볼 결정 지점과, 비교할 기준선');
nt(s,'공동연구 제안이며 역할 분담이나 시스템 제공을 확약하지 않습니다. 현재 구현에 연구 정책을 연결하려면 최신 설정 통합 스윕, 메타데이터 정합, 운영 상태 재확인 등이 필요합니다. 관측 기반 자동 제어 전체는 앞으로의 연구 후보로 구분합니다.','PD disaggregation_HISTORY.md §§11,12; lmd-top/README.ko.md');
}
{
let s=pg('부록 A  현황','설치된 자원과 현재 가동 상태','2026-09-08 기존 읽기 전용 조회 기준 · 등록 자원과 즉시 사용 가능한 자원은 다릅니다.');
node(s,'클러스터','등록 노드 8대\nGPU 2 · ATOM 4 · RNGD 6',.65,2.75,5.80,1.80,C.gray);node(s,'운영 상태','Gateway · EPP · proxy 가동\n모델 워커 replica 0',6.88,2.75,5.80,1.80,C.gray);
node(s,'확인된 구현 범위','컴파일·배포 관리 · 통합 관측\n실제 KV 이송 · 역할 조합 실험',.65,4.94,5.80,1.63);node(s,'별도 검증·연구 대상','장시간 운영 · 최신 통합 비교\n직접 전송 · 자동 정책 제어',6.88,4.94,5.80,1.63,C.vp);
nt(s,'기존 조회: GPU GB10 2서버각1; etri-001 ATOM4 RNGD2 GPU0; ESC8000 RNGD4 SchedulingDisabled; cpu-3NotReady. Gateway Programmed=True. 모델워커0/0이며 gateway 가동을 추론 성공과 혼동하지 않습니다. NAS·공유저장소는 환경 가이드 기록이며 이번 새로 검증하지 않았습니다.','2026-09-08 kubectl 조회; docs/ENVIRONMENT-GUIDE.md; PD disaggregation_HISTORY.md §12');
}
{
let s=pg('부록 B  자료와 해석 범위','분석 수치와 구현 상태의 근거','상세 조건과 원문 위치는 각 슬라이드의 발표자 노트에 포함했습니다.');
const r=[['환경·모델 관리','환경 가이드 · 모델 스토어 문서 · lmd-top README/CHANGELOG'],['버킷 비교','제공 작업 이력 §3.2 — 문서에서 원본 JSONL 확인한 값'],['장치 내 출력 연산','제공 작업 이력 §5.3 — 2026-08-19 측정 기록'],['한 카드 / PD 비교','제공 작업 이력 §6.5 — 동일 배치 재측정 기록'],['이번 자료의 범위','원격 실험 재실행 없음 · GPU/NPU 성능 우열 주장 없음']];
r.forEach((v,i)=>{let y=2.74+i*.66;b(s,.65,y,12.02,.57,i%2?C.white:C.gray);t(s,v[0],.88,y+.12,3.22,.31,16,C.teal,true);t(s,v[1],4.60,y+.13,7.78,.30,14);});
nt(s,'NPU 문서: PD disaggregation_HISTORY.md는 사용자가 다른 서버에서 수행한 내용을 정리해 제공했습니다. 이 문서의 인용 수치는 원격 raw files를 이번 턴에서 다시 열어 검증한 값이 아닙니다. 과거 설정별 측정과 최신 코드, 커널/엔진/HTTP 지표를 구별하고 A/B 개선을 합산하지 않습니다. GPU와 NPU의 동일조건 비교 실험이 이 슬라이드에 없으므로 처리량·전력·가격의 우열을 주장하지 않습니다. GIF는합성 UI demo.','PD disaggregation_HISTORY.md §§2,11,12; lmd-top/src/cast.rs');
}
audit.forEach(q=>{if(q.x<0||q.y<0||q.x+q.w>13.334||q.y+q.h>7.5)throw Error(JSON.stringify(q));});
let f=path.join(out,'ETRI_NPU특성과_모델자원관리_v4.pptx');p.writeFile({fileName:f}).then(()=>{fs.writeFileSync(path.join(out,'발표노트_근거.md'),'# ETRI NPU 특성과 모델·자원 관리\n\n본문 11장 + 부록 2장.\n\n'+notes.map((n,i)=>'## '+(i+1)+'장\n\n'+n).join('\n\n'));console.log(f);});
