const $=s=>document.querySelector(s);
let PID=null, SPEC=null, SEL=null, CAPS=null, ASSETS={}, PLAYING=false;
function toast(m){const t=$('#toast');t.textContent=m;t.classList.add('show');setTimeout(()=>t.classList.remove('show'),1700);}
function showTab(g,n){
  document.querySelectorAll(`.tabpane[data-group="${g}"]`).forEach(p=>p.classList.toggle('on',p.dataset.name===n));
  document.querySelectorAll(`.tabbtn[data-group="${g}"]`).forEach(b=>b.classList.toggle('on',b.dataset.name===n));
}
// mobile: switch which panel fills the screen (preview stays pinned on top)
function setMView(v){
  const app=document.querySelector('.app');if(app)app.dataset.mview=v;
  document.querySelectorAll('#mnav button').forEach(b=>b.classList.toggle('on',b.dataset.mv===v));
  if(v==='timeline')setTimeout(updatePlayhead,60);
}
const isMobile=()=>matchMedia('(max-width:860px)').matches;
async function api(method,path,body){
  const r=await fetch(path,{method,headers:{'Content-Type':'application/json'},
    body:body?JSON.stringify(body):undefined});
  if(!r.ok){const e=await r.json().catch(()=>({error:r.statusText}));throw new Error(e.error||r.statusText);}
  const ct=r.headers.get('Content-Type')||'';return ct.includes('json')?r.json():r;
}

async function boot(){
  CAPS=await api('GET','/api/capabilities');
  $('#fx').innerHTML=(CAPS.effects||[]).map(e=>`<option>${e}</option>`).join('');
  await refreshProjects();
  await loadAssets();
  chatStatus();
  window.addEventListener('resize',()=>{updatePlayhead();drawHandle();});
  setInterval(()=>{if($('#live').checked&&PID&&!PLAYING)softRefresh();},2500);
}
async function refreshProjects(){
  const {projects}=await api('GET','/api/projects');
  $('#proj').innerHTML=projects.length
    ? projects.map(p=>`<option value="${p.id}">${p.name} · ${(p.resolution||[]).join('×')}</option>`).join('')
    : '<option value="">프로젝트 없음</option>';
  if(projects.length){PID=$('#proj').value=projects[projects.length-1].id;await loadProject();}
  else{PID=null;}
}
$('#proj').onchange=async e=>{if(e.target.value){PID=e.target.value;await loadProject();}};
async function createProject(){
  const r=await api('POST','/api/projects',{width:1280,height:720,fps:24,name:'studio-'+Date.now()%10000});
  await refreshProjects();PID=r.project_id;$('#proj').value=PID;await loadProject();toast('프로젝트 생성됨');
}
async function renameProject(){
  if(!PID){toast('프로젝트를 먼저 선택하세요');return;}
  const name=prompt('새 프로젝트 이름:',(SPEC&&SPEC.name)||'');
  if(name==null||!name.trim())return;
  await api('POST','/api/projects/'+PID+'/rename',{name:name.trim()});
  await refreshProjects();$('#proj').value=PID;await loadProject();toast('이름 변경됨');
}
async function duplicateProject(){
  if(!PID){toast('프로젝트를 먼저 선택하세요');return;}
  const r=await api('POST','/api/projects/'+PID+'/duplicate',{});
  await refreshProjects();PID=r.project_id;$('#proj').value=PID;await loadProject();toast('복제됨');
}
async function deleteProject(){
  if(!PID){toast('프로젝트를 먼저 선택하세요');return;}
  if(!confirm('이 프로젝트를 삭제할까요?\n'+((SPEC&&SPEC.name)||PID)))return;
  await api('DELETE','/api/projects/'+PID);PID=null;
  await refreshProjects();
  if(!PID){SPEC=null;SEL=null;
    $('#stage').innerHTML='<div class="empty"><div class="big">프로젝트가 없습니다</div>+ 새 프로젝트로 시작하세요.</div>';
    $('#timelineTracks').innerHTML='';$('#durlabel').textContent='';updatePlayhead();}
  toast('삭제됨');
}
async function loadProject(){
  stopPlay();
  SPEC=await api('GET','/api/projects/'+PID);
  $('#store').textContent='store: '+(SPEC.name||PID);
  const dur=SPEC.duration||10;$('#time').max=dur;$('#durlabel').textContent='· '+dur+'s · '+(SPEC.width||'?')+'×'+(SPEC.height||'?');
  $('#rawspec').value=JSON.stringify(SPEC,null,2);
  await loadClips();refreshPreview();
}
async function softRefresh(){
  try{const s=await api('GET','/api/projects/'+PID);
    if(JSON.stringify(s)!==JSON.stringify(SPEC)){SPEC=s;$('#rawspec').value=JSON.stringify(s,null,2);
      await loadClips();refreshPreview();toast('에이전트 변경 반영됨');}}
  catch(e){PID=null;await refreshProjects();}
}
async function loadClips(){
  const {tracks}=await api('GET','/api/projects/'+PID+'/clips');
  renderTimeline(tracks);
}
function clipColor(t){return {video:'#2f6fe0',image:'#2f9fe0',text:'#3bbf8e',callout:'#d9a13a',
  solid:'#7b5cff',gradient:'#7b5cff'}[t]||'#4a90d9';}
function renderTimeline(tracks){
  const dur=parseFloat($('#time').max)||10;const host=$('#timelineTracks');
  if(!tracks||!tracks.length){host.innerHTML='<div class="tl-empty">클립이 없습니다 — 왼쪽 도구에서 배경·텍스트·미디어를 추가하세요</div>';updatePlayhead();return;}
  host.innerHTML=rulerHTML(dur)+tracks.map(tr=>{
    const pk=packLanes(tr.clips);const laneH=pk.rows*28+2;
    return `<div class="tl-row">
      <div class="tl-label" title="${tr.track}"><span class="tl-tname">${tr.track}</span><button class="tl-del" data-track="${tr.track}" title="트랙 삭제">×</button></div>
      <div class="tl-lane" data-track="${tr.track}" style="height:${laneH}px">${tr.clips.map((c,ci)=>{
        const left=Math.min(98,Math.max(0,(c.start||0)/dur*100));
        const w=Math.min(100-left,Math.max(3,((c.duration||0)/dur)*100));
        const top=pk.row[ci]*28+2;
        const sel=SEL&&SEL.track===tr.track&&SEL.index===c.index;
        const lbl=`#${c.index} ${c.type||''}`;
        return `<div class="tl-clip${sel?' sel':''}" data-track="${tr.track}" data-index="${c.index}"
          data-start="${c.start||0}" data-dur="${c.duration||0}"
          style="left:${left}%;width:${w}%;top:${top}px;background:${clipColor(c.type)}"
          title="${(c.preview||lbl).replace(/"/g,'&quot;')}">
          <div class="tl-grip l"></div><span>${lbl}</span><div class="tl-grip r"></div></div>`;
      }).join('')}</div>
    </div>`;}).join('');
  wireTimeline();updatePlayhead();
}
// greedy interval packing: overlapping clips get stacked onto separate sub-rows
function packLanes(clips){
  const order=clips.map((c,ci)=>({ci,s:c.start||0,e:(c.start||0)+(c.duration||0)}))
    .sort((a,b)=>a.s-b.s||a.e-b.e);
  const rowEnds=[],row={};
  order.forEach(o=>{let r=rowEnds.findIndex(end=>end<=o.s+1e-6);
    if(r<0){r=rowEnds.length;rowEnds.push(o.e);}else rowEnds[r]=o.e;row[o.ci]=r;});
  return {row,rows:Math.max(1,rowEnds.length)};
}
function rulerHTML(dur){
  const step=dur<=6?1:dur<=15?2:dur<=40?5:10;let m='';
  for(let t=0;t<=dur+1e-6;t+=step){const left=Math.min(99.5,t/dur*100);
    m+=`<span class="tick" style="left:${left}%">${+t.toFixed(2)}s</span>`;}
  return `<div class="tl-row tl-rulerrow"><div class="tl-label"></div><div class="tl-ruler" id="tlRuler">${m}</div></div>`;
}
function renderTimelineFromSpec(){
  if(!SPEC)return;
  renderTimeline(SPEC.tracks.map(t=>({track:t.name,clips:t.clips.map((c,i)=>(
    {index:i,type:(c.element||{}).type,start:c.start,duration:c.duration,preview:(c.element||{}).text}))})));
}
// ---- timeline: drag to move, edge-grip to resize, with snapping ----
let TLD=null;
function wireTimeline(){
  document.querySelectorAll('.tl-clip').forEach(el=>{
    const track=el.dataset.track,index=+el.dataset.index;
    el.querySelector('.tl-grip.l').addEventListener('pointerdown',e=>startClipDrag(e,el,'l'));
    el.querySelector('.tl-grip.r').addEventListener('pointerdown',e=>startClipDrag(e,el,'r'));
    el.addEventListener('pointerdown',e=>{if(e.target.classList.contains('tl-grip'))return;startClipDrag(e,el,'move');});
    el.addEventListener('contextmenu',e=>showCtx(e,track,index));
  });
  document.querySelectorAll('.tl-del').forEach(b=>b.addEventListener('click',e=>{e.stopPropagation();deleteTrack(b.dataset.track);}));
}
async function addTrack(kind){
  const base=kind==='audio'?'audio':'video';
  const names=new Set((SPEC.tracks||[]).map(t=>t.name));
  let n=1,name;do{name=base+(n++);}while(names.has(name));
  SPEC.tracks.push({kind:base,name,clips:[]});
  await putSpec();toast('트랙 추가: '+name);
}
async function deleteTrack(name){
  const tr=trackOf(name);if(!tr)return;
  if((SPEC.tracks||[]).length<=1){toast('트랙이 하나뿐이라 삭제할 수 없습니다');return;}
  if(tr.clips.length&&!confirm(`'${name}' 트랙에 클립 ${tr.clips.length}개가 있습니다.\n트랙과 클립을 모두 삭제할까요?`))return;
  SPEC.tracks=SPEC.tracks.filter(t=>t.name!==name);
  if(SEL&&SEL.track===name){SEL=null;$('#inspectorBody').innerHTML='<div class="empty-i">타임라인에서 클립을 선택하면<br>여기서 편집할 수 있습니다.</div>';}
  await putSpec();toast('트랙 삭제: '+name);
}
function collectEdges(track,skip){
  const dur=parseFloat($('#time').max)||10;const out=[0,dur,parseFloat($('#time').value)||0];
  (SPEC.tracks||[]).forEach(tr=>tr.clips.forEach((c,i)=>{
    if(tr.name===track&&i===skip)return;out.push(c.start||0,(c.start||0)+(c.duration||0));}));
  return out;
}
function snapSec(v,edges,thr){let best=v,bd=thr;edges.forEach(e=>{const d=Math.abs(v-e);if(d<bd){bd=d;best=e;}});return best;}
function startClipDrag(e,el,mode){
  e.preventDefault();e.stopPropagation();
  const track=el.dataset.track,index=+el.dataset.index;
  SEL={track,index};showInspector();
  document.querySelectorAll('.tl-clip').forEach(c=>c.classList.toggle('sel',c===el));
  const lr=el.parentElement.getBoundingClientRect();
  const dur=parseFloat($('#time').max)||10;
  // overlap is allowed: text/callout/etc. coexist in time and stack on sub-rows
  TLD={el,mode,track,index,lanePx:lr.width,dur,startX:e.clientX,
       origStart:+el.dataset.start,origDur:+el.dataset.dur,moved:false,
       edges:collectEdges(track,index),srcTrack:track,curTrack:track};
  window.addEventListener('pointermove',onClipDrag);window.addEventListener('pointerup',endClipDrag);
}
function trackKind(name){const t=SPEC&&SPEC.tracks.find(x=>x.name===name);return t?(t.kind||'video'):'video';}
function onClipDrag(e){
  if(!TLD)return;if(Math.abs(e.clientX-TLD.startX)>2)TLD.moved=true;
  if(TLD.mode==='move'){                          // detect target track under cursor
    let hov=null;document.querySelectorAll('.tl-lane').forEach(l=>{const b=l.getBoundingClientRect();
      if(e.clientY>=b.top&&e.clientY<=b.bottom&&trackKind(l.dataset.track)===trackKind(TLD.srcTrack))hov=l.dataset.track;});
    const tgt=hov||TLD.srcTrack;
    if(tgt!==TLD.curTrack){
      TLD.curTrack=tgt;TLD.moved=true;
      document.querySelectorAll('.tl-lane').forEach(l=>l.classList.toggle('drophover',l.dataset.track===tgt&&tgt!==TLD.srcTrack));
    }
  }
  const sPerPx=TLD.dur/TLD.lanePx,thr=8*sPerPx,min=0.1;
  const delta=(e.clientX-TLD.startX)*sPerPx;
  let start=TLD.origStart,d=TLD.origDur;
  if(TLD.mode==='move'){start=snapSec(TLD.origStart+delta,TLD.edges,thr);start=Math.max(0,Math.min(TLD.dur-d,start));}
  else if(TLD.mode==='r'){let end=snapSec(TLD.origStart+TLD.origDur+delta,TLD.edges,thr);end=Math.min(TLD.dur,end);d=Math.max(min,end-TLD.origStart);}
  else{let ns=snapSec(TLD.origStart+delta,TLD.edges,thr);ns=Math.max(0,Math.min(TLD.origStart+TLD.origDur-min,ns));d=TLD.origStart+TLD.origDur-ns;start=ns;}
  TLD.curStart=Math.round(start*100)/100;TLD.curDur=Math.round(d*100)/100;
  const left=Math.min(98,Math.max(0,TLD.curStart/TLD.dur*100));
  const w=Math.min(100-left,Math.max(1,TLD.curDur/TLD.dur*100));
  TLD.el.style.left=left+'%';TLD.el.style.width=w+'%';
  const cross=TLD.mode==='move'&&TLD.curTrack!==TLD.srcTrack;
  const b=$('#badge');if(b)b.textContent=(cross?`→ ${TLD.curTrack} · `:'')+`${TLD.curStart.toFixed(2)}s · 길이 ${TLD.curDur.toFixed(2)}s`;
}
async function endClipDrag(){
  window.removeEventListener('pointermove',onClipDrag);window.removeEventListener('pointerup',endClipDrag);
  document.querySelectorAll('.tl-lane.drophover').forEach(l=>l.classList.remove('drophover'));
  const d=TLD;TLD=null;if(!d)return;
  if(!d.moved){selectClip(d.track,d.index);if(isMobile())setMView('inspect');return;}
  // moved to a different track? relocate the clip object via spec PUT (undo-able)
  if(d.mode==='move'&&d.curTrack&&d.curTrack!==d.srcTrack){
    const src=trackOf(d.srcTrack),tgt=trackOf(d.curTrack);
    if(src&&tgt){
      const clip=src.clips.splice(d.index,1)[0];clip.start=d.curStart;tgt.clips.push(clip);
      const ni=tgt.clips.length-1;SEL={track:d.curTrack,index:ni};
      try{await putSpec();selectClip(d.curTrack,ni);toast(`'${d.curTrack}' 트랙으로 이동`);}
      catch(err){toast('이동 오류: '+err.message);}
      return;
    }
  }
  try{await api('PATCH',`/api/projects/${PID}/clips/${d.track}/${d.index}`,{patch:{start:d.curStart,duration:d.curDur}});
    await loadProject();selectClip(d.track,d.index);toast(`클립: ${d.curStart.toFixed(2)}s +${d.curDur.toFixed(2)}s`);
  }catch(err){toast('오류: '+err.message);}
}
// ---- clip context menu (right-click) — edits spec + PUT (undo-able) ----
async function putSpec(){await api('PUT','/api/projects/'+PID,{spec:SPEC});await loadProject();}
function trackOf(name){return SPEC.tracks.find(t=>t.name===name);}
function showCtx(e,track,index){
  e.preventDefault();const m=$('#ctxmenu');
  const tr=trackOf(track),n=tr?tr.clips.length:0;
  const item=(l,fn,cls='')=>`<div class="ctxitem ${cls}" onclick="hideCtx();${fn}">${l}</div>`;
  m.innerHTML=item('복제',`ctxDuplicate('${track}',${index})`)
    +(index<n-1?item('위로 (앞 레이어)',`ctxMove('${track}',${index},1)`):'')
    +(index>0?item('아래로 (뒤 레이어)',`ctxMove('${track}',${index},-1)`):'')
    +'<div class="ctxsep"></div>'+item('삭제',`ctxDelete('${track}',${index})`,'dz');
  m.style.display='block';
  const w=m.offsetWidth,h=m.offsetHeight;
  m.style.left=Math.min(e.clientX,innerWidth-w-6)+'px';
  m.style.top=Math.min(e.clientY,innerHeight-h-6)+'px';
}
function hideCtx(){const m=$('#ctxmenu');if(m)m.style.display='none';}
async function ctxDuplicate(track,index){
  const tr=trackOf(track);if(!tr)return;
  tr.clips.splice(index+1,0,JSON.parse(JSON.stringify(tr.clips[index])));
  SEL={track,index:index+1};await putSpec();selectClip(track,index+1);toast('클립 복제됨');
}
async function ctxDelete(track,index){
  const tr=trackOf(track);if(!tr)return;tr.clips.splice(index,1);SEL=null;
  await putSpec();$('#inspectorBody').innerHTML='<div class="empty-i">타임라인에서 클립을 선택하면<br>여기서 편집할 수 있습니다.</div>';
  toast('클립 삭제됨');
}
async function ctxMove(track,index,dir){
  const tr=trackOf(track);if(!tr)return;const j=index+dir;if(j<0||j>=tr.clips.length)return;
  [tr.clips[index],tr.clips[j]]=[tr.clips[j],tr.clips[index]];
  SEL={track,index:j};await putSpec();selectClip(track,j);toast(dir>0?'앞 레이어로':'뒤 레이어로');
}
document.addEventListener('click',hideCtx);
document.addEventListener('keydown',e=>{
  if((e.ctrlKey||e.metaKey)&&String(e.key).toLowerCase()==='z'){
    const t=(e.target.tagName||'');if(t==='INPUT'||t==='TEXTAREA')return;
    e.preventDefault();undoEdit();
  }
  if(e.key==='Escape')hideCtx();
});
function selectClip(track,index){SEL={track,index};showInspector();renderTimelineFromSpec();}
function showInspector(){
  const clip=selectedClip();if(!clip){return;}
  const el=clip.element||{};const type=el.type;
  const pos=(clip.transform&&clip.transform.position)||['',''];
  const opt=(arr,cur)=>arr.map(a=>`<option ${a===cur?'selected':''}>${a}</option>`).join('');
  let extra='';
  if(type==='text'){
    extra=`
      <div class="row"><div><label>크기</label><input id="e_size" type="number" value="${el.size??''}"></div>
        <div><label>정렬</label><select id="e_align">${opt(['left','center','right'],el.align)}</select></div></div>
      <div class="field"><label>폰트</label><select id="e_font">${opt(['sans','sans-bold','display','serif','mono','kr-bold'],el.font)}</select></div>
      <div class="field"><label>색</label><input id="e_color" value="${el.color||'#ffffff'}"></div>`;
  }else if(type==='callout'){
    extra=`
      <div class="row"><div><label>글자크기</label><input id="e_font_size" type="number" value="${el.font_size??''}"></div>
        <div><label>꼬리</label><select id="e_tail_side">${opt(['bottom','top','left','right'],el.tail_side)}</select></div></div>
      <div class="row"><div><label>배경</label><input id="e_fill" value="${el.fill||'#ffffff'}"></div>
        <div><label>글자색</label><input id="e_color" value="${el.color||'#0b0e16'}"></div></div>`;
  }else if(type==='video'||type==='image'){
    const cr=el.crop||['','','',''];
    extra=(type==='video'?`
      <div class="row"><div><label>속도 (0.5=슬로모, 2=배속)</label><input id="e_speed" type="number" step="0.1" value="${el.speed??1}"></div>
        <div><label>소스 시작(s)</label><input id="e_source_start" type="number" step="0.1" value="${el.start??0}"></div></div>
      <label style="display:flex;align-items:center;gap:6px;margin-top:8px"><input type="checkbox" id="e_loop" ${el.loop?'checked':''} style="width:auto"> 루프(소스 반복)</label>`:'')
      +`<label>크롭 (비율 0~1: x · y · 너비 · 높이)</label>
      <div class="row"><input id="e_crop_x" type="number" step="0.01" placeholder="x" value="${cr[0]}">
        <input id="e_crop_y" type="number" step="0.01" placeholder="y" value="${cr[1]}">
        <input id="e_crop_w" type="number" step="0.01" placeholder="w" value="${cr[2]}">
        <input id="e_crop_h" type="number" step="0.01" placeholder="h" value="${cr[3]}"></div>`;
  }
  $('#inspectorBody').innerHTML=`
    <div class="clip-meta">${SEL.track} · #${SEL.index} · ${type||''}</div>
    ${el.text!==undefined?`<div class="field"><label>텍스트</label><textarea id="e_text">${(el.text||'').replace(/</g,'&lt;')}</textarea></div>`:''}
    ${extra}
    <div class="row"><div><label>시작(s)</label><input id="e_start" type="number" step="0.1" value="${clip.start??0}"></div>
      <div><label>길이(s)</label><input id="e_dur" type="number" step="0.1" value="${clip.duration??0}"></div></div>
    <div class="row" style="margin-top:8px"><div><label>X</label><input id="e_x" type="number" value="${pos[0]}"></div>
      <div><label>Y</label><input id="e_y" type="number" value="${pos[1]}"></div></div>
    ${['solid','gradient'].includes(type)?'':'<p class="hint" style="margin:8px 0 0">💡 미리보기에서 <b>◯ 핸들</b> 드래그 · 타임라인에서 <b>클립/가장자리 드래그</b>로 위치·길이 조절</p>'}
    <div class="row" style="margin-top:12px">
      <button class="btn primary" style="flex:2" onclick="applyClip()">적용</button>
      <button class="btn danger" onclick="delClip()">삭제</button></div>
    <div class="row" style="margin-top:8px">
      <button class="btn sm ghost" onclick="ctxDuplicate(SEL.track,SEL.index)">복제</button>
      <button class="btn sm ghost" onclick="ctxMove(SEL.track,SEL.index,1)">▲ 앞</button>
      <button class="btn sm ghost" onclick="ctxMove(SEL.track,SEL.index,-1)">▼ 뒤</button></div>`;
  showTab('insp','props');drawHandle();
}
async function applyClip(){
  const g=k=>{const n=$('#e_'+k);return n?n.value:undefined;};
  const patch={},el={};
  ['text','color','align','font','fill','tail_side'].forEach(k=>{const v=g(k);if(v!==undefined)el[k]=v;});
  ['size','font_size','speed'].forEach(k=>{const v=g(k);if(v!==undefined&&v!=='')el[k]=parseFloat(v);});
  const ss=g('source_start');if(ss!==undefined&&ss!=='')el.start=parseFloat(ss);
  const lp=$('#e_loop');if(lp)el.loop=lp.checked;
  const cx=g('crop_x');
  if(cx!==undefined){const v=[cx,g('crop_y'),g('crop_w'),g('crop_h')];
    el.crop=v.every(x=>x!==''&&x!==undefined)?v.map(parseFloat):null;}
  if(Object.keys(el).length)patch.element=el;
  const s=g('start'),d=g('dur'),x=g('x'),y=g('y');
  if(s!==undefined&&s!=='')patch.start=parseFloat(s);
  if(d!==undefined&&d!=='')patch.duration=parseFloat(d);
  if(x!==undefined&&x!==''&&y!==undefined&&y!=='')patch.transform={position:[parseFloat(x),parseFloat(y)]};
  await api('PATCH',`/api/projects/${PID}/clips/${SEL.track}/${SEL.index}`,{patch});
  await loadProject();selectClip(SEL.track,SEL.index);toast('클립 수정됨');
}
async function delClip(){
  await api('DELETE',`/api/projects/${PID}/clips/${SEL.track}/${SEL.index}`);SEL=null;
  $('#inspectorBody').innerHTML='<div class="empty-i">타임라인에서 클립을 선택하면<br>여기서 편집할 수 있습니다.</div>';
  await loadProject();toast('클립 삭제됨');
}
async function addBackground(){
  await api('POST','/api/projects/'+PID+'/background',
    {gradient:{stops:[[0,$('#bg1').value],[1,$('#bg2').value]],kind:'radial'},duration:SPEC.duration||10});
  await loadProject();toast('배경 추가됨');
}
async function addText(){
  await api('POST','/api/projects/'+PID+'/text',
    {text:$('#txt').value,size:+$('#txtSize').value,color:$('#txtColor').value,font:'kr-bold',duration:4,
     transition_in:{type:'fade',duration:0.4}});
  await loadProject();toast('텍스트 추가됨');
}
async function addCallout(){
  await api('POST','/api/projects/'+PID+'/callout',
    {text:$('#coTxt').value,position:[+$('#coX').value,+$('#coY').value],tail_side:$('#coSide').value,
     font:'kr-bold',duration:3,transition_in:{type:'zoom',duration:0.4}});
  await loadProject();toast('콜아웃 추가됨');
}
async function addEffect(){
  await api('POST','/api/projects/'+PID+'/effect',{effect:{type:$('#fx').value}});
  await loadProject();toast('이펙트 추가: '+$('#fx').value);
}
async function loadAssets(){
  try{
    const {assets}=await api('GET','/api/assets');
    const media=(assets||[]).filter(a=>a.kind==='video'||a.kind==='image');
    ASSETS={};media.forEach(a=>ASSETS[a.id]=a);
    $('#mediaSel').innerHTML = media.length
      ? media.map(a=>{const d=(a.media&&a.media.duration)?' · '+a.media.duration+'s':'';
          return `<option value="${a.id}">${a.kind==='video'?'🎬':'🖼'} ${a.id.slice(0,12)} · ${a.role||''}${d}</option>`;}).join('')
      : '<option value="">등록된 미디어 없음 — 먼저 발행/업로드</option>';
  }catch(e){$('#mediaSel').innerHTML='<option value="">에셋을 불러올 수 없음</option>';}
}
async function addMedia(){
  if(!PID){toast('프로젝트를 먼저 선택하세요');return;}
  const a=ASSETS[$('#mediaSel').value];
  if(!a){toast('추가할 미디어를 선택하세요');return;}
  const start=parseFloat($('#medStart').value)||0;
  const duration=parseFloat($('#medDur').value)||(a.media&&a.media.duration)||5;
  await api('POST','/api/projects/'+PID+'/media',{path:a.path,kind:a.kind,start,duration,fit:'cover'});
  await loadProject();toast('미디어 추가: '+a.id.slice(0,8));
}
async function saveSpec(){
  try{const spec=JSON.parse($('#rawspec').value);await api('PUT','/api/projects/'+PID,{spec});
    await loadProject();toast('스펙 저장됨');}catch(e){toast('JSON 오류: '+e.message);}
}
function onScrub(){stopPlay();$('#tlabel').textContent=(+$('#time').value).toFixed(1)+'s';
  clearTimeout(window._sc);window._sc=setTimeout(refreshPreview,160);updatePlayhead();}
function ensureStage(){
  if(!$('#frame')){$('#stage').innerHTML='<img id="frame"/><div id="ovl"></div><span class="badge" id="badge"></span>';}
}
function refreshPreview(){
  if(!PID)return;
  ensureStage();const t=$('#time').value;const f=$('#frame');
  f.onload=()=>{updatePlayhead();drawHandle();};
  f.src=`/api/projects/${PID}/preview?t=${t}&_=${Date.now()}`;
  $('#badge').textContent=(+t).toFixed(1)+'s · 미리보기';
}
// ---- drag-to-position: handle over the preview for the selected clip ----
let DRAG=null;
function selectedClip(){
  if(!SEL||!SPEC)return null;
  const tr=SPEC.tracks.find(t=>t.name===SEL.track);
  return tr?(tr.clips[SEL.index]||null):null;
}
function clipPos(clip){
  const p=clip&&clip.transform&&clip.transform.position;
  if(p&&p.length===2&&p[0]!==''&&p[1]!=='')return [Number(p[0]),Number(p[1])];
  return [(SPEC.width||1280)/2,(SPEC.height||720)/2];
}
function drawHandle(){
  const ovl=$('#ovl');if(!ovl)return;
  const clip=selectedClip(),f=$('#frame');
  const type=clip&&(clip.element||{}).type;
  if(!clip||!f||!SPEC||['solid','gradient'].includes(type)||type===undefined){ovl.innerHTML='';return;}
  const r=f.getBoundingClientRect(),s=$('#stage').getBoundingClientRect();
  if(!r.width){ovl.innerHTML='';return;}
  const [x,y]=clipPos(clip);
  const hx=(r.left-s.left)+x/(SPEC.width||1280)*r.width;
  const hy=(r.top-s.top)+y/(SPEC.height||720)*r.height;
  const txt=(clip.element||{}).text;
  ovl.innerHTML=`<div class="handle" id="handle" style="left:${hx}px;top:${hy}px" title="드래그해서 위치 이동">✛${txt?`<span class="lbl">${String(txt).replace(/</g,'&lt;').slice(0,12)}</span>`:''}</div>`;
  $('#handle').onpointerdown=startDrag;
}
function hideHandle(){const o=$('#ovl');if(o)o.innerHTML='';}
function startDrag(e){
  e.preventDefault();if(!selectedClip())return;
  DRAG={x:null,y:null};
  window.addEventListener('pointermove',onDrag);
  window.addEventListener('pointerup',endDrag);
}
function onDrag(e){
  if(!DRAG)return;const f=$('#frame');if(!f)return;
  const r=f.getBoundingClientRect(),s=$('#stage').getBoundingClientRect();
  const W=SPEC.width||1280,H=SPEC.height||720;
  let x=(e.clientX-r.left)/r.width*W,y=(e.clientY-r.top)/r.height*H;
  let snapX=null,snapY=null;
  [W/2,0,W].forEach(t=>{if(Math.abs(x-t)<W*0.022){x=t;snapX=t;}});
  [H/2,0,H].forEach(t=>{if(Math.abs(y-t)<H*0.022){y=t;snapY=t;}});
  x=Math.max(0,Math.min(W,Math.round(x)));y=Math.max(0,Math.min(H,Math.round(y)));
  DRAG.x=x;DRAG.y=y;
  const h=$('#handle');
  if(h){h.style.left=((r.left-s.left)+x/W*r.width)+'px';h.style.top=((r.top-s.top)+y/H*r.height)+'px';}
  drawGuides(snapX,snapY,r,s,W,H);
  const X=$('#e_x'),Y=$('#e_y');if(X)X.value=x;if(Y)Y.value=y;
  $('#badge').textContent=`위치 ${x}, ${y}`;
}
function drawGuides(sx,sy,r,s,W,H){
  const ovl=$('#ovl');if(!ovl)return;
  let g=ovl.querySelector('.guides');if(!g){g=document.createElement('div');g.className='guides';ovl.appendChild(g);}
  let html='';
  if(sx!=null)html+=`<div class="guide v" style="left:${(r.left-s.left)+sx/W*r.width}px;top:${r.top-s.top}px;height:${r.height}px"></div>`;
  if(sy!=null)html+=`<div class="guide h" style="top:${(r.top-s.top)+sy/H*r.height}px;left:${r.left-s.left}px;width:${r.width}px"></div>`;
  g.innerHTML=html;
}
function clearGuides(){const ovl=$('#ovl'),g=ovl&&ovl.querySelector('.guides');if(g)g.innerHTML='';}
async function endDrag(){
  window.removeEventListener('pointermove',onDrag);window.removeEventListener('pointerup',endDrag);clearGuides();
  if(!DRAG||DRAG.x==null){DRAG=null;return;}
  const x=DRAG.x,y=DRAG.y;DRAG=null;
  try{await api('PATCH',`/api/projects/${PID}/clips/${SEL.track}/${SEL.index}`,{patch:{transform:{position:[x,y]}}});
    await loadProject();selectClip(SEL.track,SEL.index);toast('위치 이동: '+x+', '+y);
  }catch(err){toast('이동 오류: '+err.message);}
}
function updatePlayhead(){
  const ph=$('#playhead');if(!ph)return;
  const lane=document.querySelector('.tl-lane');const body=$('#tlBody');
  if(!lane||!body){ph.style.display='none';return;}
  const dur=parseFloat($('#time').max)||10,t=parseFloat($('#time').value)||0;
  const lr=lane.getBoundingClientRect(),br=body.getBoundingClientRect();
  ph.style.display='block';
  ph.style.left=(lr.left-br.left+(t/dur)*lr.width)+'px';
  ph.style.height=body.scrollHeight+'px';
}
// ---- lightweight play: step the scrubber, re-rendering preview frames ----
function playToggle(){
  if(PLAYING){stopPlay();return;}
  if(!PID){toast('프로젝트를 먼저 선택하세요');return;}
  PLAYING=true;$('#playBtn').textContent='⏸';hideHandle();ensureStage();
  const step=0.2,max=parseFloat($('#time').max)||10;
  const tick=()=>{
    if(!PLAYING)return;
    let t=parseFloat($('#time').value)+step;if(t>max)t=0;
    $('#time').value=t;$('#tlabel').textContent=t.toFixed(1)+'s';
    const f=$('#frame');if(!f){PLAYING=false;return;}
    f.onload=()=>{if(!PLAYING)return;$('#badge').textContent=t.toFixed(1)+'s · 재생';updatePlayhead();setTimeout(tick,30);};
    f.onerror=()=>{if(PLAYING)setTimeout(tick,150);};
    f.src=`/api/projects/${PID}/preview?t=${t}&_=${Date.now()}`;
  };
  tick();
}
function stopPlay(){PLAYING=false;const b=$('#playBtn');if(b)b.textContent='▶';drawHandle();}
async function doRender(){
  if(!PID){toast('프로젝트를 먼저 선택하세요');return;}
  stopPlay();
  $('#renderBtn').disabled=true;$('#renderBtn').textContent='렌더 중…';$('#renderInfo').textContent='렌더링 중입니다…';
  try{const r=await api('POST','/api/projects/'+PID+'/render',{});
    $('#stage').innerHTML=`<video src="${r.url}?_=${Date.now()}" controls autoplay loop></video><span class="badge">렌더 결과</span>`;
    $('#renderInfo').textContent=`완료 · ${r.frames}프레임 · ${r.render_seconds}s · ${(r.bytes/1e6).toFixed(1)}MB`;
  }catch(e){$('#renderInfo').textContent='오류: '+e.message;toast('렌더 오류');}
  $('#renderBtn').disabled=false;$('#renderBtn').textContent='▶ 렌더';
}
function chatBubble(role,text){
  const d=document.createElement('div');d.className='bub '+(role==='user'?'u':'a');
  d.textContent=text;$('#chatLog').appendChild(d);$('#chatLog').scrollTop=1e9;return d;
}
async function chatStatus(){
  try{const s=await api('GET','/api/chat/status');
    const mcp=s.mcp_connected?('MCP '+s.mcp_tools+'개 도구'):'MCP 미연결';
    $('#chatStatus').textContent=s.available?('● '+mcp+' · '+s.provider+' '+(s.model||'')):('○ '+mcp+' · LLM 미설정');
    $('#chatStatus').style.color=s.available?'var(--ok)':'var(--mut)';
    $('#chatStatus').title=s.hint||'';}catch(e){}
}
async function undoEdit(){
  if(!PID)return;const r=await api('POST','/api/projects/'+PID+'/undo',{});
  if(r.ok){await loadProject();toast('되돌림 ('+r.remaining+' 남음)');}else{toast('되돌릴 항목 없음');}
}
async function sendChat(){
  const inp=$('#chatIn');const msg=inp.value.trim();if(!msg||!PID)return;
  inp.value='';chatBubble('user',msg);
  const thinking=chatBubble('assistant','…편집 중');$('#chatBtn').disabled=true;
  try{const r=await api('POST','/api/projects/'+PID+'/chat',{message:msg});
    thinking.textContent=r.reply+(r.actions&&r.actions.length?`  [${r.actions.map(a=>a.name).join(', ')}]`:'');
    await loadProject();
  }catch(e){thinking.textContent='오류: '+e.message;}
  $('#chatBtn').disabled=false;inp.focus();
}
boot();
