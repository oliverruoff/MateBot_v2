'use strict';
const $=s=>document.querySelector(s),canvas=$('#map'),ctx=canvas.getContext('2d');
let state={},map=null,mapLayer=null,mapVersion=null,annotationRevision=-1;
let scale=65,center=[0,0],fitNeeded=true,tool='mapping',brush='paint',positioning=false;
let selected=null,drag=null,token=null,armedAt=0,lastOK=0,manualTimer=null,sequence=0;
const keys=new Set();
const manualInputs=new Map();
const mapHome=canvas.parentElement;
let controlRequest=null,controlEpoch=0,manualFlight=null,controlAckAt=0,mapRequest=null;

function toast(text){$('#toast').textContent=text;$('#toast').hidden=false;clearTimeout(toast.timer);toast.timer=setTimeout(()=>$('#toast').hidden=true,5500)}
async function api(action,body={}){
  const headers={'Content-Type':'application/json','X-Matebot-Control':'1'};
  if(token)headers['X-Matebot-Lease']=token;
  const response=await fetch('/api/'+action,{method:'POST',headers,body:JSON.stringify(body),signal:AbortSignal.timeout(['manual','heartbeat','take-control','stop'].includes(action)?2200:35000)});
  let value;try{value=await response.json()}catch{throw Error('Keine gültige Antwort vom Roboter')}
  if(!response.ok){const error=Error(value.error||'Aktion fehlgeschlagen');error.status=response.status;throw error}
  if(['manual','heartbeat','take-control'].includes(action))controlAckAt=Date.now();
  return value;
}
const run=f=>async()=>{try{await f()}catch(e){toast(e.message)}};
function viewRotation(){return window.MatebotCockpit?.visible()?Math.PI/2-((state.localized?state.pose?.yaw:state.last_pose?.yaw)||0):0}
function viewCenter(){return window.MatebotCockpit?.followMap()&&state.localized&&state.pose?[state.pose.x,state.pose.y]:center}
function screen(x,y){const c=viewCenter(),p=MatebotDrive.rotatePoint(x-c[0],y-c[1],viewRotation());return [canvas.clientWidth/2+p[0]*scale,canvas.clientHeight/2-p[1]*scale]}
function world(x,y){const c=viewCenter(),p=MatebotDrive.rotatePoint((x-canvas.clientWidth/2)/scale,-(y-canvas.clientHeight/2)/scale,-viewRotation());return [c[0]+p[0],c[1]+p[1]]}
function pixel(e){const r=canvas.getBoundingClientRect();return [e.clientX-r.left,e.clientY-r.top]}
function canDrive(){return !state.manual_blocked&&state.manual_ready&&tool==='mapping'&&!positioning&&Date.now()-lastOK<2200&&(!window.MatebotCockpit?.visible()||window.MatebotCockpit.frameFresh())}
function fit(){
  const w=canvas.clientWidth,h=canvas.clientHeight;
  if(w<1||h<1){fitNeeded=true;return}
  if(!map){center=[0,0];scale=65}
  else{
    const a=map.origin[2],mx=map.width*map.resolution/2,my=map.height*map.resolution/2;
    center=[map.origin[0]+mx*Math.cos(a)-my*Math.sin(a),map.origin[1]+mx*Math.sin(a)+my*Math.cos(a)];
    const c=viewCenter(),r=viewRotation();
    const corners=[[0,0],[2*mx,0],[2*mx,2*my],[0,2*my]].map(p=>{const q=MatebotDrive.rotatePoint(...p,a);return MatebotDrive.rotatePoint(q[0]+map.origin[0]-c[0],q[1]+map.origin[1]-c[1],r)});
    scale=Math.min(w/(2*Math.max(...corners.map(p=>Math.abs(p[0])))+.7),h/(2*Math.max(...corners.map(p=>Math.abs(p[1])))+.7));
  }
  fitNeeded=false;draw();
}
function size(){if(canvas.clientWidth<1||canvas.clientHeight<1)return;const d=devicePixelRatio||1;canvas.width=canvas.clientWidth*d;canvas.height=canvas.clientHeight*d;ctx.setTransform(d,0,0,d,0,0);if(fitNeeded&&map)fit();draw()}
new ResizeObserver(size).observe(canvas);
function setMap(value){
  map=value;if(!map){mapLayer=null;$('#empty').hidden=false;draw();return}
  mapLayer=document.createElement('canvas');mapLayer.width=map.width;mapLayer.height=map.height;
  const c=mapLayer.getContext('2d'),img=c.createImageData(map.width,map.height);let free=0;
  for(let i=0;i<map.cells.length;i++){
    const v=map.cells[i],j=((map.height-1-Math.floor(i/map.width))*map.width+i%map.width)*4;
    img.data.set(v<0?[226,234,216,255]:v>=65?[63,86,62,255]:v<25?[253,254,249,255]:[166,181,151,255],j);
    if(v>=0&&v<25)free++;
  }
  c.putImageData(img,0,0);$('#empty').hidden=true;
  $('#mapStats').textContent=(free*map.resolution**2).toFixed(1)+' m² freie Fläche · '+Math.round(map.resolution*100)+' cm Kartenauflösung';
  if(fitNeeded||window.MatebotCockpit?.followMap())fit();draw();
}
function rasterCells(start,end){
  const size=state.annotations?.grid_size||.25;
  const left=Math.floor(Math.min(start[0],end[0])/size),right=Math.floor(Math.max(start[0],end[0])/size);
  const bottom=Math.floor(Math.min(start[1],end[1])/size),top=Math.floor(Math.max(start[1],end[1])/size);
  if((right-left+1)*(top-bottom+1)>4096)throw Error('Bitte kleinere Bereiche markieren (maximal 4096 Zellen).');
  const result=[];for(let x=left;x<=right;x++)for(let y=bottom;y<=top;y++)result.push([x,y]);return result;
}
function cellsDraw(cells,color){
  const g=state.annotations?.grid_size||.25;ctx.fillStyle=color;
  for(const [x,y] of cells){const corners=[[x,y],[x+1,y],[x+1,y+1],[x,y+1]].map(p=>screen(p[0]*g,p[1]*g));ctx.beginPath();corners.forEach((p,i)=>i?ctx.lineTo(...p):ctx.moveTo(...p));ctx.closePath();ctx.fill()}

}
function draw(){
  const w=canvas.clientWidth,h=canvas.clientHeight;if(w<1||h<1||!Number.isFinite(scale)||scale<=0)return;ctx.clearRect(0,0,w,h);
  if(mapLayer&&map){const p=screen(...map.origin);ctx.save();ctx.translate(...p);ctx.rotate(-map.origin[2]-viewRotation());ctx.imageSmoothingEnabled=false;ctx.drawImage(mapLayer,0,-map.height*map.resolution*scale,map.width*map.resolution*scale,map.height*map.resolution*scale);ctx.restore()}
  const g=state.annotations?.grid_size||.25;
  if($('#showGrid').checked){
    const step=g*Math.max(1,Math.ceil(8/(g*scale))),corners=[[0,0],[w,0],[w,h],[0,h]].map(p=>world(...p)),lo=[Math.min(...corners.map(p=>p[0])),Math.min(...corners.map(p=>p[1]))],hi=[Math.max(...corners.map(p=>p[0])),Math.max(...corners.map(p=>p[1]))];
    ctx.lineWidth=.6;ctx.strokeStyle='#69815324';ctx.beginPath();
    for(let x=Math.floor(lo[0]/step)*step;x<=hi[0];x+=step){ctx.moveTo(...screen(x,lo[1]));ctx.lineTo(...screen(x,hi[1]))}
    for(let y=Math.floor(lo[1]/step)*step;y<=hi[1];y+=step){ctx.moveTo(...screen(lo[0],y));ctx.lineTo(...screen(hi[0],y))}ctx.stroke();
  }
  cellsDraw(state.annotations?.zones||[],'#ba665c99');
  if(drag&&tool==='zones'&&!positioning){try{cellsDraw(rasterCells(drag.start,drag.current),brush==='paint'?'#b65049bb':'#d7eed1cc')}catch{}}
  if(state.localized&&state.path?.length){ctx.strokeStyle='#c6924d';ctx.lineWidth=3;ctx.setLineDash([6,5]);ctx.beginPath();state.path.forEach((p,i)=>{const s=screen(...p);i?ctx.lineTo(...s):ctx.moveTo(...s)});ctx.stroke();ctx.setLineDash([])}
  const pose=state.localized?state.pose:state.last_pose;
  if(pose){
    if(state.localized){const [lx,ly,la]=state.lidar_transform||[0,0,0];ctx.fillStyle='#729548a0';for(const [px,py] of state.points||[]){const x=lx+px*Math.cos(la)-py*Math.sin(la),y=ly+px*Math.sin(la)+py*Math.cos(la),p=screen(pose.x+x*Math.cos(pose.yaw)-y*Math.sin(pose.yaw),pose.y+x*Math.sin(pose.yaw)+y*Math.cos(pose.yaw));ctx.fillRect(p[0]-1,p[1]-1,2,2)}}
    const p=screen(pose.x,pose.y);ctx.save();ctx.translate(...p);ctx.rotate(-pose.yaw-viewRotation());ctx.globalAlpha=state.localized?1:.45;
    const dims=state.geometry||[.41,.3];ctx.strokeStyle='#bc965d';ctx.lineWidth=1;ctx.strokeRect(-dims[0]*scale/2,-dims[1]*scale/2,dims[0]*scale,dims[1]*scale);
    ctx.fillStyle='#d49e58';ctx.strokeStyle='white';ctx.lineWidth=2.5;ctx.beginPath();ctx.arc(0,0,8,0,Math.PI*2);ctx.fill();ctx.stroke();ctx.beginPath();ctx.moveTo(17,0);ctx.lineTo(5,-5);ctx.lineTo(5,5);ctx.closePath();ctx.fill();ctx.restore();
  }
  if(drag?.aim){const a=screen(...drag.start),b=screen(...drag.current);ctx.strokeStyle='#a57636';ctx.lineWidth=3;ctx.beginPath();ctx.moveTo(...a);ctx.lineTo(...b);ctx.stroke()}
  if(selected){const p=screen(...selected);ctx.strokeStyle='#b17d3b';ctx.lineWidth=2;ctx.beginPath();ctx.arc(...p,11,0,Math.PI*2);ctx.stroke()}
  if(positioning&&drag){const a=screen(...drag.start),b=screen(...drag.current);ctx.strokeStyle='#ba8b4b';ctx.lineWidth=3;ctx.beginPath();ctx.moveTo(...a);ctx.lineTo(...b);ctx.stroke()}
  const ruler=scale>150?.5:scale<30?2:1;$('#scale').textContent=ruler+' m';$('#scale').style.width=Math.max(15,ruler*scale)+'px';
}
function renderAnnotations(){
  const a=state.annotations;if(!a||annotationRevision===a.revision)return;annotationRevision=a.revision;
  $('#title').textContent=a.title;document.title='Matebot · '+a.title;$('#mapName').value=a.title;
  $('#gridSize').value=String(a.grid_size);$('#favoriteCount').textContent=a.favorites.length;
  document.querySelectorAll('[data-check]').forEach(c=>c.checked=!!a.calibration[c.dataset.check]);
  const list=$('#favorites');list.replaceChildren();
  for(const f of a.favorites){
    const row=document.createElement('div');row.className='favoriteRow';
    const button=document.createElement('button');button.textContent='⌖ '+f.name;button.onclick=()=>openGoal(f.x,f.y,f.name,f.yaw);
    const remove=document.createElement('button');remove.textContent='×';remove.setAttribute('aria-label',f.name+' entfernen');remove.onclick=run(async()=>{await api('favorite',{...f,delete:true});toast('Gespeichertes Ziel entfernt')});
    row.append(button,remove);list.append(row);
  }
  if(!a.favorites.length){const p=document.createElement('p');p.className='hint';p.textContent='Im Zielmodus einen Punkt wählen und benennen.';list.append(p)}
  if(tool!=='zones')tool=a.mode;renderMode();
}
function renderMode(){document.querySelectorAll('[data-mode]').forEach(b=>b.classList.toggle('active',b.dataset.mode===tool));$('#drivePanel').hidden=tool!=='mapping';$('#zoneTools').hidden=tool!=='zones'||positioning;$('#release').hidden=true;$('#positionHelp').hidden=!positioning;draw()}
function renderState(){
  $('#lidarBadge').classList.toggle('offline',state.lidar_age>.4);$('#imuBadge').classList.toggle('offline',state.imu_age>.4);
  const text=!state.localized&&state.saved_map?(state.localization_status||'Position wird automatisch gesucht'):(state.manual_blocked||(!state.estop?state.blocked:''))||(tool==='navigation'?'Freie Stelle als Ziel wählen. Sperrzonen und Hindernisse werden berücksichtigt.':'Bereit · Richtung gedrückt halten, Loslassen stoppt.');
  $('#banner').textContent=text;$('#banner').classList.toggle('ready',!state.blocked);
  $('#task').textContent=state.goal_status||'Gestoppt';$('#connection').style.color='#7fa35f';
  $('#saved').textContent=state.saved_at?'Gesichert: '+state.saved_at+' · Auto alle 30 s':'Automatische Sicherung alle 30 Sekunden';
  $('#floorNote').hidden=!state.initial_floor_test;
  $('#position').hidden=!state.saved_map;
  $('#backup').setAttribute('aria-disabled',String(!state.saved_map));
  $('#release').disabled=!state.estop||!state.manual_ready||positioning||!state.localized||!state.pose||state.pose.age>.5||(state.annotations?.mode==='navigation'&&!state.calibrated);
  $('#release').title=state.blocked||'Steuerung vor Ort freigeben';
  document.querySelectorAll('[data-v]').forEach(b=>b.disabled=!canDrive());

  $('#lastPosition').disabled=!state.last_pose;
  window.MatebotCockpit?.onState(state);
  window.MatebotGoals?.onState(state);
}
async function poll(){
  try{
    const response=await fetch('/api/state',{signal:AbortSignal.timeout(2500)});if(!response.ok)throw Error();
    state=await response.json();lastOK=Date.now();
    if(state.estop&&Date.now()-armedAt>1500&&token){token=null;endManual()}
    renderAnnotations();renderState();
    const v=String(state.map_version)+'/'+state.localized+'/'+state.annotations?.map_id;
    if(v!==mapVersion&&!mapRequest){mapRequest=fetch('/api/map',{signal:AbortSignal.timeout(5000)}).then(r=>{if(!r.ok)throw Error();return r.json()}).then(value=>{mapVersion=v;setMap(value)}).catch(()=>{}).finally(()=>mapRequest=null)}
    draw();
  }catch{
    $('#banner').textContent='Verbindung unterbrochen. Steuerung gesperrt; der Roboter stoppt bei ausbleibenden Befehlen.';
    $('#connection').style.color='#b5634c';state.blocked='Verbindung unterbrochen';token=null;endManual();
    document.querySelectorAll('[data-v]').forEach(b=>b.disabled=true);
    window.MatebotCockpit?.onDisconnect();
  }
  setTimeout(poll,400);
}
async function stop(){endManual();token=null;window.MatebotGoals?.onStop();await api('stop');if(!$('#goalDialog').open)selected=null;keys.clear();draw()}
async function ensureControl(mode='mapping'){
  if(token&&!state.estop)return true;
  if(controlRequest)return controlRequest;
  const epoch=controlEpoch;
  controlRequest=(async()=>{
    const value=await api('take-control',{mode});
    if(epoch!==controlEpoch){await api('stop');return false}
    token=value.token;sequence=0;armedAt=Date.now();state.estop=false;state.blocked='';return true;
  })().finally(()=>controlRequest=null);
  return controlRequest;
}
function inputVector(){return MatebotDrive.combine([...manualInputs.values()],Number($('#speed').value)/100,Math.min(.4,state.manual_limits?.[1]||.4))}
function sendManualInput(){
  const [vx,vy,wz]=inputVector(),moving=!!(vx||vy||wz);
  if(moving&&!canDrive()){endManual();return}
  if(!token||(moving&&manualFlight))return;
  const owner=token,epoch=controlEpoch;
  const request=api('manual',{vx,vy,wz,sequence:++sequence});
  if(moving)manualFlight=request;
  request.catch(e=>{
    if(moving&&token===owner&&controlEpoch===epoch&&(e.status===409||Date.now()-controlAckAt>2500)){
      token=null;endManual();api('stop').catch(()=>{});toast('Fahrt angehalten: '+e.message);
    }
  }).finally(()=>{if(manualFlight===request)manualFlight=null});
}
function syncManual(){
  const moving=inputVector().some(v=>Math.abs(v)>1e-6);
  if(!moving){clearInterval(manualTimer);manualTimer=null;sendManualInput();return}
  if(!manualTimer)manualTimer=setInterval(sendManualInput,100);
  sendManualInput();
}
function endManual(source=null){
  if(source)manualInputs.delete(source);
  else{controlEpoch++;manualInputs.clear();keys.clear();window.MatebotCockpit?.resetControls()}
  syncManual();
}
function startManual(vector,source='pad'){
  if(!canDrive())return;
  manualInputs.set(source,vector);
  if(token&&!state.estop){syncManual();return}
  ensureControl().then(acquired=>{if(acquired)syncManual()}).catch(e=>{endManual();toast(e.message)});
}
function openGoal(x,y,name='',heading){window.MatebotGoals.open(x,y,name,heading).catch(e=>toast(e.message))}
async function restore(pose){await api('restore',{x:pose.x,y:pose.y,yaw:pose.yaw});positioning=false;mapVersion=null;renderMode();toast('Karte an korrigierter Position fortgesetzt.')}
document.querySelectorAll('[data-close]').forEach(b=>b.onclick=()=>$('#'+b.dataset.close).close());
document.querySelectorAll('[data-mode]').forEach(b=>b.onclick=run(async()=>{await stop();positioning=false;tool=b.dataset.mode;if(tool!=='zones')await api('settings',{mode:tool});renderMode()}));
$('#release').onclick=()=>{$('#onSite').checked=false;$('#armDialog').showModal()};
$('#armNow').onclick=run(async()=>{const value=await api('release',{mode:state.annotations.mode,on_site:$('#onSite').checked});token=value.token;sequence=0;armedAt=Date.now();$('#armDialog').close();toast('Steuerung freigegeben. Loslassen oder STOPP hält an.')});
$('#stop').onclick=run(stop);
$('#quickStop').onclick=run(stop);
$('#save').onclick=run(async()=>{await api('save');toast('Karte, Position und Sperrzonen gespeichert')});
$('#position').onclick=run(async()=>{await stop();positioning=true;renderMode()});
$('#lastPosition').onclick=run(async()=>{if(state.last_pose)await restore(state.last_pose)});
$('#cancelPosition').onclick=()=>{positioning=false;renderMode()};
$('#newMap').onclick=run(async()=>{await stop();$('#newDialog').showModal()});
$('#newNow').onclick=run(async()=>{await stop();await api('new-map',{confirm:true});$('#newDialog').close();positioning=false;tool='mapping';mapVersion=null;fitNeeded=true;setMap(null);renderMode();toast('Neue Karte begonnen. Die bisherige Karte wurde archiviert.')});
$('#saveName').onclick=run(async()=>{await api('settings',{title:$('#mapName').value});toast('Kartenname gespeichert')});
$('#saveChecks').onclick=run(async()=>{await stop();$('#checksOnSite').checked=false;$('#checksDialog').showModal()});
$('#checksNow').onclick=run(async()=>{const checks={};document.querySelectorAll('[data-check]').forEach(c=>checks[c.dataset.check]=c.checked);await api('calibration',{checks,on_site:$('#checksOnSite').checked});$('#checksDialog').close();toast('Prüfstand gespeichert. Steuerung bleibt gestoppt.')});
$('#paint').onclick=()=>{brush='paint';$('#paint').classList.add('active');$('#erase').classList.remove('active')};
$('#erase').onclick=()=>{brush='erase';$('#erase').classList.add('active');$('#paint').classList.remove('active')};
$('#gridSize').onchange=run(async()=>{await api('zones',{paint:[],erase:[],grid_size:Number($('#gridSize').value),revision:state.annotations.revision});toast('Rastergröße gespeichert. Bestehende Sperrflächen bleiben gesperrt.')});
$('#speed').oninput=()=>{$('#speedValue').textContent=$('#speed').value+' cm/s'};
$('#panMap').onclick=()=>{const active=$('#panMap').classList.toggle('active');$('#panMap').setAttribute('aria-pressed',String(active))};
$('#showGrid').onchange=draw;$('#zoomIn').onclick=()=>{scale=Math.min(800,scale*1.25);draw()};$('#zoomOut').onclick=()=>{scale=Math.max(5,scale/1.25);draw()};$('#fit').onclick=fit;
canvas.onwheel=e=>{e.preventDefault();const p=pixel(e),before=world(...p);scale=Math.max(5,Math.min(800,scale*(e.deltaY<0?1.12:1/1.12)));const after=world(...p);center=[center[0]+before[0]-after[0],center[1]+before[1]-after[1]];draw()};
canvas.onpointerdown=e=>{const p=pixel(e);drag={pixel:p,start:world(...p),current:world(...p),center:[...center],revision:state.annotations?.revision,aim:tool==='navigation'&&!$('#panMap').classList.contains('active')&&!e.shiftKey};canvas.setPointerCapture(e.pointerId)};
canvas.onpointermove=e=>{if(!drag)return;const p=pixel(e);if(positioning||tool==='zones'||drag.aim)drag.current=world(...p);else{const delta=MatebotDrive.rotatePoint((p[0]-drag.pixel[0])/scale,-(p[1]-drag.pixel[1])/scale,-viewRotation());center=[drag.center[0]-delta[0],drag.center[1]-delta[1]]};draw()};
canvas.onpointercancel=()=>{drag=null;draw()};
canvas.onpointerup=async e=>{
  if(!drag)return;const d=drag,p=pixel(e);drag=null;
  try{
    if(positioning){const end=world(...p);if(Math.hypot(end[0]-d.start[0],end[1]-d.start[1])<.15)throw Error('Von der Position mindestens ein Stück in Blickrichtung ziehen.');await restore({x:d.start[0],y:d.start[1],yaw:Math.atan2(end[1]-d.start[1],end[0]-d.start[0])})}
    else if(tool==='zones'){
      const cells=rasterCells(d.start,world(...p));const body={paint:[],erase:[],grid_size:state.annotations.grid_size,revision:d.revision};body[brush]=cells;await api('zones',body);toast(cells.length+' Zellen '+(brush==='paint'?'gesperrt':'freigegeben')+' und gespeichert');
    }else if(d.aim){const end=world(...p),angle=Math.hypot(p[0]-d.pixel[0],p[1]-d.pixel[1])>8?Math.atan2(end[1]-d.start[1],end[0]-d.start[0]):undefined;openGoal(...d.start,'',angle)}
  }catch(error){toast(error.message)}draw();
};
document.querySelectorAll('[data-v]').forEach(b=>{
  b.onpointerdown=e=>{if(!canDrive())return;e.preventDefault();b.setPointerCapture(e.pointerId);startManual(b.dataset.v.split(',').map(Number))};
  b.onpointerup=()=>endManual('pad');b.onpointercancel=()=>endManual('pad');b.onlostpointercapture=()=>endManual('pad');
});
function keyboardVector(){return [(keys.has('w')?1:0)-(keys.has('s')?1:0),(keys.has('a')?1:0)-(keys.has('d')?1:0),(keys.has('q')?1:0)-(keys.has('e')?1:0)]}
window.addEventListener('keydown',e=>{
  if(['INPUT','TEXTAREA','SELECT'].includes(e.target.tagName))return;
  if(e.code==='Space'){e.preventDefault();stop().catch(()=>{});return}
  if(document.querySelector('dialog[open]'))return;
  const key=e.key.toLowerCase();if(!'wasdqe'.includes(key)||key.length!==1||!canDrive())return;
  e.preventDefault();if(!keys.has(key)){keys.add(key);startManual(keyboardVector(),'keyboard')}
});
window.addEventListener('keyup',e=>{const key=e.key.toLowerCase();if(!keys.has(key))return;keys.delete(key);const v=keyboardVector();if(v.some(Boolean))startManual(v,'keyboard');else endManual('keyboard')});
window.addEventListener('blur',()=>{endManual();if(token)stop().catch(()=>{})});
document.addEventListener('visibilitychange',()=>{if(document.hidden){endManual();if(token)stop().catch(()=>{})}});
setInterval(()=>{if(token&&!document.hidden){const owner=token;api('heartbeat').catch(()=>{if(token===owner&&Date.now()-controlAckAt>2500){token=null;endManual();toast('Verbindung unterbrochen – Joystick erneut betätigen')}})}},400);
window.MatebotApp={api,stop,ensureControl,startManual,endManual,canDrive,toast,state:()=>state,ownsControl:()=>!!token,
  setSpeed:value=>{const v=String(value);$('#speed').value=v;$('#speedValue').textContent=v+' cm/s'},
  selectGoal:(x,y)=>{selected=[x,y];draw()},mapData:()=>map,mapImage:()=>mapLayer,
  ensureNavigation:async()=>{if(state.annotations?.mode!=='navigation'){await stop();state.annotations=await api('settings',{mode:'navigation'});annotationRevision=-1;tool='navigation';renderAnnotations();renderState()}},
  ensureMapping:async()=>{if(state.annotations?.mode!=='mapping'){await stop();state.annotations=await api('settings',{mode:'mapping'});annotationRevision=-1;tool='mapping';renderAnnotations();renderState()}},
  openArm:()=>{$('#onSite').checked=false;$('#armDialog').showModal()},
  resume:async()=>{if(state.last_pose)await restore(state.last_pose)},
  selectPosition:()=>$('#position').click(),
  mountMap:container=>{(container||mapHome).prepend(canvas);fitNeeded=true;size()},
  freezeMap:()=>{if(state.localized&&state.pose)center=[state.pose.x,state.pose.y]},
  fitMap:fit,zoomMap:factor=>{scale=Math.max(5,Math.min(800,scale*factor));draw()},
  redraw:()=>{size();renderState()}};
poll();
