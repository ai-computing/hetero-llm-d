// Diagram-first technical briefing. Requires pptxgenjs.
// Run: NODE_PATH=/tmp/kcloud-ppt-tools/node_modules node scripts/build-kcloud-etri-architecture.cjs
const pptxgen = require('pptxgenjs');
const fs = require('fs');
const path = require('path');
const ROOT = path.resolve(__dirname, '..');
const OUT = path.join(ROOT, 'docs/presentations/kcloud-etri-architecture-v2');
fs.mkdirSync(OUT, {recursive:true});
const pptx = new pptxgen();
pptx.layout = 'LAYOUT_WIDE';
pptx.author = 'ETRI';
pptx.subject = 'K-Cloud 기술 미팅: 환경 구성과 ETRI 작업 계층';
pptx.title = 'ETRI 이종 가속기 서빙 환경 및 작업 계층';
pptx.company = 'ETRI';
pptx.lang = 'ko-KR';
pptx.theme = {headFontFace:'Noto Sans CJK KR', bodyFontFace:'Noto Sans CJK KR', lang:'ko-KR'};
const S = pptx.ShapeType;
const C = {ink:'18343A', muted:'65797E', teal:'087E83', mint:'51DBC0', pale:'E7F5F2',
  paper:'FFFFFF', bg:'F5F8F8', line:'CFDCDE', dark:'11292F', panel:'1C3A41',
  purple:'775DC3', purplePale:'EEE9FA', amber:'A76A20', amberPale:'FFF1DE'};
const audit = [];
function box(sl,x,y,w,h,fill,line=null,r=.13) {
  sl.addShape(r ? S.roundRect : S.rect,{x,y,w,h,rectRadius:r,radius:r,
    fill:{color:fill},line:{color:line||fill,width:line?1:0},radius:r});
  audit.push({slide:sl._slideNum,x,y,w,h,type:'shape'});
}
function txt(sl,t,x,y,w,h,size=16,color=C.ink,bold=false,align='left') {
  sl.addText(t,{x,y,w,h,fontFace:'Noto Sans CJK KR',fontSize:size,color,bold,align,
    margin:0,breakLine:false,paraSpaceAfter:0,valign:'mid',wrap:false,
    charSpacing:0,transparency:0});
  audit.push({slide:sl._slideNum,x,y,w,h,type:'text',text:t});
}
function arrow(sl,x1,y1,x2,y2,color=C.teal,dash=false,end=true) {
  sl.addShape(S.line,{x:Math.min(x1,x2),y:Math.min(y1,y2),w:Math.abs(x2-x1),h:Math.abs(y2-y1),
    flipH:x2<x1,flipV:y2<y1,line:{color,width:1.8,dashType:dash?'dash':'solid',
    beginArrowType:'none',endArrowType:end?'triangle':'none'}});
}
function node(sl,title,sub,x,y,w,h,fill=C.pale,color=C.ink) {
  box(sl,x,y,w,h,fill);
  txt(sl,title,x+.18,y+.13,w-.36,.37,18,color,true);
  if(sub)txt(sl,sub,x+.18,y+.57,w-.36,h-.65,12,color);
}
function tag(sl,t,x,y,w,color=C.teal,fill=C.pale) {
  box(sl,x,y,w,.35,fill,null,.1);txt(sl,t,x+.08,y+.04,w-.16,.26,10.5,color,true,'center');
}
function page(n,kicker,title,sub,dark=false) {
  let sl=pptx.addSlide();sl.background={color:dark?C.dark:C.paper};
  txt(sl,'K-CLOUD  /  ETRI     '+kicker,.55,.30,12.2,.30,11,dark?C.mint:C.teal,true);
  txt(sl,title,.55,.86,12.2,.63,34,dark?C.paper:C.ink,true);
  txt(sl,sub,.57,1.63,12.1,.35,14,dark?'B9CDCF':C.muted);
  txt(sl,'환경 및 작업 계층 · 기술 미팅 · 2026.09',.56,7.13,10,.20,9,dark?'91AAAF':C.muted);
  txt(sl,String(n).padStart(2,'0')+' / 04',12.0,7.08,.76,.28,10,dark?'91AAAF':C.muted,false,'right');
  return sl;
}

// 1. A stack map: distinguish existing platform integration from original runtime code.
{
const sl=page(1,'전체 계층','플랫폼에서 NPU 런타임까지','어디에 자원을 연결했고, 어느 계층을 직접 개발했는가?',true);
const x=2.10,w=6.95;
const rows=[
  {y:2.27,label:'서비스',title:'클라이언트 · OpenAI 호환 API',sub:'요청 진입',fill:C.panel,color:C.paper},
  {y:3.10,label:'요청 배치',title:'llm-d  /  Gateway · InferencePool · EPP',sub:'서빙 경로 구성 · 선택 점수 관측 확장',fill:'23575B',color:C.paper},
  {y:3.93,label:'모델 실행',title:'모델 서버  /  Prefill · Decode workers',sub:'벤더 엔진 배포 + 이기종 PD 실험',fill:'23575B',color:C.paper},
  {y:4.76,label:'NPU 런타임',title:'KVConnector · KV 이송 · 커널·배치 최적화',sub:'직접 KV를 소유하는 실험 런타임',fill:C.mint,color:C.dark},
  {y:5.59,label:'자원 기반',title:'Kubernetes · device-plugin  /  GPU · NPU · CPU',sub:'클러스터 · 공유 모델 스토어 · 가속기 연결',fill:C.panel,color:C.paper}
];
rows.forEach(r=>{
 txt(sl,r.label,.58,r.y+.18,1.3,.35,15,'B9CDCF',true);
 box(sl,x,r.y,w,.70,r.fill);
 txt(sl,r.title,x+.20,r.y+.08,w-.40,.29,16,r.color,true);
 txt(sl,r.sub,x+.20,r.y+.40,w-.40,.20,10.5,r.color);
});
for(let i=0;i<4;i++)arrow(sl,5.57,rows[i].y+.70,5.57,rows[i+1].y,'789D9F');
box(sl,9.75,3.10,3.00,3.19,C.panel,'527F83');
txt(sl,'lmd-top',10.00,3.37,2.5,.53,28,C.mint,true);
txt(sl,'통합 관측·운영',10.00,4.07,2.5,.36,18,C.paper,true);
txt(sl,'Prometheus + K8s API',10.00,4.70,2.5,.33,12,'B9CDCF');
txt(sl,'상태 · 점수 · 운영 액션',10.00,5.31,2.5,.33,12,'B9CDCF');
[3.45,4.28,5.94].forEach(y=>arrow(sl,9.05,y,9.75,y,'789D9F',true));
tag(sl,'기존 스택 연동·구축',2.10,6.56,2.04,C.paper,'23575B');
tag(sl,'직접 개발·확장',4.35,6.56,1.88,C.dark,C.mint);
txt(sl,'협업 접점: 요청 배치 · KV/배치 관리 · 자원 제어',6.64,6.56,6.1,.35,13,'B9CDCF');
sl.addNotes(`첫 장은 전체 작업 지도를 설명합니다. 기존 Kubernetes/llm-d/벤더 런타임을 모두 자체 개발했다는 뜻이 아닙니다. 짙은 청록은 기존 스택의 구성·연동, 민트는 직접 개발·확장 부분입니다. lmd-top 역시 직접 개발한 별도 관측·운영 도구이며 여러 계층의 데이터를 연결합니다. EPP에는 per-endpoint 점수 관측용 picker 확장 플러그인을 구현했습니다. 자체 PD 런타임은 기존 모든 모델 서버의 공통 런타임이 아니라 다른 서버에서 개발한 실험 경로입니다. 자동 폐루프 정책 제어 전체가 완성된 상태는 아닙니다.\n근거: README.md, lmd-top/README.ko.md, lmd-top/CHANGELOG.md v0.36.0, contrib/epp-score-observer/README.md, PD disaggregation_HISTORY.md §§4–8.\n설명 순서: 아래 기반 → 중간 서빙 → 직접 수정한 런타임 → 우측 관측 도구. 공동연구 범위는 이 지도에서 선택하도록 제안합니다.`);
}

// 2. Physical topology, with current registered capacity and explicit operational state.
{
const sl=page(2,'클러스터 환경','8개 노드에 GPU·NPU·CPU를 연결','Kubernetes v1.31 · Cilium   |   2026-09-08 읽기 전용 조회 기준');
node(sl,'R7525 · 관리 노드','Control-plane · 관리 UI',.55,2.32,3.28,1.02,C.bg);
node(sl,'단일 API 진입점','Envoy Gateway · 192.0.2.12',4.36,2.32,4.13,1.02,C.pale);
node(sl,'Prometheus / NAS','관측 지표 / 공유 model-store',9.02,2.32,3.76,1.02,C.bg);
// one horizontal worker connection bus; unobstructed below the top node row
arrow(sl,6.425,3.34,6.425,3.73,C.teal,false,false);
arrow(sl,2.19,3.34,2.19,3.73,C.muted,true,false);
arrow(sl,10.90,3.34,10.90,3.73,C.muted,true,false);
arrow(sl,1.98,3.73,11.34,3.73,C.line,false,false);
const groups=[
 {x:.55,w:2.87,name:'GPU 서버 ×2',hw:'GB10 ×2',sub:'dgx-spark0\ngx10-4744',foot:'GPU 서빙',col:C.teal,fill:C.pale},
 {x:3.67,w:2.87,name:'etri-001',hw:'ATOM ×4\nRNGD ×2',sub:'NPU 주력 워커',foot:'A100: K8s 등록 0',col:C.teal,fill:C.pale},
 {x:6.79,w:2.87,name:'ESC8000',hw:'RNGD ×4',sub:'Furiosa 워커',foot:'신규 스케줄 제한',col:C.amber,fill:C.amberPale},
 {x:9.91,w:2.87,name:'CPU 서버 ×3',hw:'CPU pool',sub:'cpu-1 / cpu-2 / cpu-3',foot:'cpu-3: NotReady',col:C.amber,fill:C.bg}
];
groups.forEach(g=>{
 arrow(sl,g.x+g.w/2,3.73,g.x+g.w/2,4.03);
 box(sl,g.x,4.03,g.w,2.32,g.fill);
 txt(sl,g.name,g.x+.18,4.20,g.w-.36,.35,18,C.ink,true);
 txt(sl,g.hw,g.x+.18,4.76,g.w-.36,.75,23,C.teal,true);
 txt(sl,g.sub,g.x+.18,5.56,g.w-.36,.38,11.5,C.muted);
 txt(sl,g.foot,g.x+.18,6.03,g.w-.36,.23,11,g.col,true);
});
tag(sl,'등록 자원',.57,6.65,1.12);
txt(sl,'GPU 2 · ATOM 4 · RNGD 6',1.87,6.63,4.18,.35,16,C.teal,true);
txt(sl,'관리·라우팅 가동 / 모델 워커 replica 0',7.1,6.63,5.67,.35,13,C.muted,false,'right');
sl.addNotes(`이 장은 물리/관리 환경입니다. 사용자 요청에 따라 2026-09-08 kubectl get nodes, deployments, gateway, httproute를 읽기 전용으로 조회했습니다. 등록 노드 8대: R7525 control-plane 1대, GB10 GPU 서버 2대, etri-001 1대, ESC8000 1대, CPU 3대입니다. Kubernetes allocatable 기준 GPU 2개(GB10 각1), ATOM 4개(etri-001), RNGD 6개(etri-001 2, ESC8000 4)입니다. ESC8000은 Ready,SchedulingDisabled, cpu-3은 NotReady이며 따라서 등록된 모든 자원이 지금 새 작업을 받을 수 있다는 뜻은 아닙니다. A100 물리 카드 보유 기록은 있지만 현재 etri-001의 nvidia.com/gpu는 0입니다.\nIP: control-plane 192.0.2.8; etri-001 .183; ESC8000 .126; CPU .178/.179/.186; GB10 192.0.2.5/.155. Gateway 192.0.2.12 Programmed=True. NAS 192.0.2.14 및 Prometheus 구성은 docs/ENVIRONMENT-GUIDE.md의 구성 기록이며 이번에 NAS 읽기/쓰기 검증은 하지 않았습니다.\n현재 EPP들, ds4-inject-proxy 2/2, hetero-pd-gateway 1/1은 가동하며 모델 워커 배포는 0/0입니다. Ready gateway만으로 모델 요청 성공을 주장하지 않습니다. 구성도를 단순화해 공통 네트워크 연결을 표현했으며 Gateway가 디바이스에 직접 요청한다는 의미는 아닙니다. 이전 문서의 RNGD 8장 수치보다 현재 조회값을 우선했습니다.`);
}

// 3. Request path beside the animated UI; dashed observation edges, native shapes.
{
const sl=page(3,'서빙·관측 계층','요청 경로를 연결하고, lmd-top으로 관측','llm-d 구성·EPP 점수 확장  +  자체 관측·운영 도구');
tag(sl,'요청 흐름',.56,2.22,1.2);
node(sl,'API 요청','/atom/* · /rngd/* 등',.56,2.78,3.20,.83,C.bg);
node(sl,'Gateway / HTTPRoute','모델 경로 선택',.56,3.93,3.20,.83,C.bg);
node(sl,'InferencePool + EPP','큐·KV 기반 endpoint 선택',.56,5.08,3.20,.83,C.pale);
box(sl,.56,6.25,3.20,.46,C.bg);
txt(sl,'모델 Pod → 가속기',.74,6.31,2.84,.30,16,C.ink,true);
arrow(sl,2.16,3.61,2.16,3.93);
arrow(sl,2.16,4.76,2.16,5.08);
arrow(sl,2.16,5.91,2.16,6.25);
// Branch beside EPP shows the existing Service route without obscuring labels.
arrow(sl,.56,4.35,.34,4.35,C.muted,true,false);
arrow(sl,.34,4.35,.34,6.48,C.muted,true,false);
arrow(sl,.34,6.48,.56,6.48,C.muted,true);
// Read-side sources represented as a narrow bridge between flow and UI.
tag(sl,'관측·운영',5.19,2.22,1.35);
txt(sl,'Prometheus + Kubernetes API',7.09,2.22,5.69,.35,13,C.muted,false,'right');
arrow(sl,3.76,5.51,4.84,5.51,C.purple,true);
txt(sl,'메트릭\n상태',3.93,4.90,.94,.50,11,C.purple,false,'center');
const gif=path.join(ROOT,'docs/images/lmd-top-ppt.gif');
sl.addImage({path:gif,x:5.19,y:2.78,w:6.94,h:6.94*1075/1806});
txt(sl,'UI 시연용 · 수치 변화는 합성',8.73,6.98,4.05,.20,9,C.muted,false,'right');
sl.addNotes(`요청 경로와 관측 경로를 나눠 설명합니다. 실선은 클라이언트 요청: HTTPRoute → InferencePool/EPP → 모델 Pod. 좌측 회색 점선은 EPP를 통하지 않는 Service 직접 연결 경로입니다. 실제 openai-route에는 /atom/gemma, /rngd/exaone 등이 InferencePool을 사용하고 /atom/koni, /gpu/qwen, /cpu/ollama 등은 Service를 사용하는 구성이 있습니다. 모든 요청이 EPP를 거친다고 설명하지 않습니다.\nEPP는 모델 메트릭을 사용하며 자체 점수 관측 picker 확장은 실제 composite score를 노출합니다. lmd-top은 Prometheus와 K8s API 결과를 조인하여 모델·디바이스·라우팅 상태를 보여주고 모드에 따라 compile/deploy/scale/restart/rollback 등 운영 액션을 제공합니다. 그림의 메트릭 화살표는 관측 관계를 단순화한 것이며 lmd-top이 요청 트래픽을 프록시하지 않습니다.\nGIF는 원본 25초 무한 반복 UI 데모를 내장했습니다. 구성은 실제 스냅샷을 사용하지만 수치 변화는 합성으로, 성능 증거가 아닙니다. 실시간 트래픽 부하 실험을 하지 않았습니다.\n근거: lmd-top/README.ko.md, CHANGELOG.md, contrib/epp-score-observer/README.md; 2026-09-08 HTTPRoute 조회. 협업 논의: 어떤 배치/라우팅 정책을 이 계층에서 구현하고 어떤 관측값으로 평가할 것인가?`);
}

// 4. Zoom into the custom runtime and KV ownership; no benchmark sales pitch.
{
const sl=page(4,'런타임 계층 확대','NPU 간 Prefill / Decode 분리 구현','다른 서버에서 개발한 실험 경로 · llm-d 배포 연동 기록',true);
node(sl,'llm-d Gateway · EPP','HTTP router → worker 선택',.55,2.35,3.20,1.00,C.panel,C.paper);
arrow(sl,2.15,3.35,2.15,3.85,C.mint);
box(sl,4.48,2.35,8.30,1.00,C.panel);
txt(sl,'검증한 역할 조합',4.70,2.48,2.15,.27,12,'B9CDCF',true);
txt(sl,'RNGD → RNGD    RNGD → ATOM    ATOM → RNGD    ATOM → ATOM',4.70,2.91,7.80,.25,12,C.paper,true);

box(sl,.55,3.85,3.65,2.18,'23575B');
txt(sl,'Prefill worker',.79,4.07,3.17,.43,24,C.paper,true);
txt(sl,'입력 문맥 처리',.79,4.67,3.17,.35,16,'B9CDCF');
tag(sl,'RNGD 또는 ATOM',.79,5.35,2.55,C.dark,C.mint);

box(sl,4.85,3.85,3.63,2.18,C.panel,'527F83');
txt(sl,'KV cache 이송',5.08,4.07,3.17,.43,23,C.mint,true);
txt(sl,'KVConnector + /dev/shm',5.08,4.67,3.17,.35,14,C.paper);
txt(sl,'레이어 그룹 스트리밍\ndecode 카드 프리패치',5.08,5.26,3.17,.55,12,'B9CDCF');

box(sl,9.13,3.85,3.65,2.18,'23575B');
txt(sl,'Decode worker',9.37,4.07,3.17,.43,24,C.paper,true);
txt(sl,'전달받은 KV로 토큰 생성',9.37,4.67,3.17,.35,15,'B9CDCF');
tag(sl,'RNGD 또는 ATOM',9.37,5.35,2.55,C.dark,C.mint);
arrow(sl,4.20,4.92,4.85,4.92,C.mint);
arrow(sl,8.48,4.92,9.13,4.92,C.mint);

txt(sl,'직접 작업',.57,6.43,1.20,.32,13,C.mint,true);
txt(sl,'KV 소유·전송     resident KV     배치 디코드     커널·컴파일 최적화',1.96,6.41,10.80,.36,16,C.paper);
txt(sl,'협업 접점: 역할 배치 · KV 전송/중첩 · 배치 스케줄링',.57,6.94,10.7,.22,11,'B9CDCF');
sl.addNotes(`다른 서버의 작업 이력 PD disaggregation_HISTORY.md를 바탕으로 런타임 내부를 확대한 그림입니다. 이 작업은 공식 엔진에서 당시 KV export/import 훅이 없던 제약을 우회하기 위해 KV를 명시적 입출력으로 소유하는 자체 런타임을 구성한 것입니다. prefill이 생성한 실제 KV를 decode에 전달하여 계산을 이어갑니다. 초기의 재프리필/캐시 에뮬레이션과 구분합니다.\n최신 문서의 서빙 구조는 HTTP router → prefill worker → KVConnector + 공유 /dev/shm → decode worker이며 RNGD/ATOM의 네 역할 조합을 기록합니다. 일반 전송 계층에는 InProc/Shm/TCP 구현이 있지만 이 그림의 현재 서빙 경로는 공유 메모리입니다. 다른 서버에서 개발했다는 사용자 설명이 서버 간 네트워크 KV 전송을 뜻하지 않습니다. NIXL은 스텁이며 장치 직접 전송은 미완료입니다.\n하단은 직접 손댄 범위: resident KV, 배치 디코드, 카드 내 lm_head, 호스트 복사 축소, 레이어 그룹 스트리밍, 카드 prefetch, shape 탐색 제한과 사전 컴파일 캐시. continuous batching은 구현·측정했으나 기존 측정에서 static보다 느려 기본값은 static입니다.\n모델/범위: Llama-3.1-8B 중심, S=256/512 기록; 임의 모델·대규모 context·모든 backend 일반화를 주장하지 않습니다. 현재 이 클러스터에 hetero-pd-gateway 및 sw-rngd/sw-atom 배포 리소스도 확인되지만 모델 워커 replica는 0입니다. 이번에 PD 엔드투엔드 추론 또는 원격 소스/결과 재검증은 하지 않았습니다.\n근거: PD disaggregation_HISTORY.md §§4,5,6.1–6.4,7,8,12. 마지막 질문: 공동연구에서 바꿀 지점을 역할 배치, KV 구조/전송, 배치 스케줄러 중 어느 계층으로 잡을 것인가?`);
}

for (const a of audit) {
  if(a.x<0 || a.y<0 || a.x+a.w>13.334 || a.y+a.h>7.501) throw new Error('Off-slide: '+JSON.stringify(a));
}
const filename=path.join(OUT,'K-Cloud_ETRI_환경과_작업계층_v2.pptx');
pptx.writeFile({fileName:filename}).then(()=>{
  fs.writeFileSync(path.join(OUT,'layout-audit.json'),JSON.stringify(audit,null,2));
  console.log(filename);
});
