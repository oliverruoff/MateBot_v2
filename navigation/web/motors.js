'use strict';
const $=s=>document.querySelector(s);
const fields=[
 ['frequency','Zieltakt',10,8000,10,'Hz','Takt pro Rad. Der tatsächlich verfügbare Wert steht oben.'],
 ['acceleration','Beschleunigung',0,100000,500,'Hz/s','Früher V2-Anlauf: 20.000 Hz/s. 0 = sofort.'],
 ['duty','Pulsanteil',5,95,1,'%','Früher: 50 %. Verändert die Länge der HIGH-Pulse.'],
 ['enable_delay','Wartezeit nach Einschalten',0,500,10,'ms','Motoren einschalten, dann erst Pulse ausgeben.'],
 ['start_frequency','Anlauftakt',10,8000,10,'Hz','Takt während der Anlaufphase, höchstens der Zieltakt.'],
 ['warmup','Anlaufphase',0,2,.1,'s','0 = keine zusätzliche Anlaufphase.']
];
let profile=null,token=null,held=false,generation=0,timer=null,busy=false,ready=false,baseline=0,lastYaw=0,lastDelta=0,currentTrial=null,stopping=false;
let savedState=null;
const format=(v,d=0)=>Number(v).toLocaleString('de-DE',{maximumFractionDigits:d});
function message(text,error=false){$('#message').textContent=text;$('#message').classList.toggle('error',error)}
async function post(action,body={},lease=token){
 const headers={'Content-Type':'application/json','X-Matebot-Control':'1'};
 if(lease)headers['X-Matebot-Lease']=lease;
 const r=await fetch('/api/'+action,{method:'POST',headers,body:JSON.stringify(body),signal:AbortSignal.timeout(5000)});
 const data=await r.json();if(!r.ok)throw Error(data.error||'Aktion fehlgeschlagen');return data;
}
function lock(value){
 document.querySelectorAll('#sliders input,#quickFrequency input,#preset,#save,#apply,#duration,#testWheel,#testReverse').forEach(el=>el.disabled=value);
}
function values(){
 const p={};fields.forEach(([key])=>p[key]=Number($(`#n-${key}`).value));
 if(p.start_frequency>p.frequency)throw Error('Anlauftakt darf nicht höher als Zieltakt sein.');
 return p;
}
function fill(p){
 profile={...p};fields.forEach(([key])=>{$(`#n-${key}`).value=p[key];$(`#r-${key}`).value=p[key]});
}
for(const [key,label,min,max,step,unit,hint] of fields){
 const el=document.createElement('div');el.className='setting';
 el.innerHTML=`<div class="settingHead"><label for="r-${key}">${label}</label><span class="value"><input aria-label="${label}, genauer Wert" id="n-${key}" type="number" min="${min}" max="${max}" step="${step}" required> ${unit}</span></div><input id="r-${key}" type="range" min="${min}" max="${max}" step="${step}" aria-label="${label}"><small>${hint}</small>`;
 (key==='frequency'?$('#quickFrequency'):$('#sliders')).append(el);
 for(const prefix of ['n','r'])$(`#${prefix}-${key}`).addEventListener('input',e=>{
  $(`#${prefix==='n'?'r':'n'}-${key}`).value=e.target.value;
  if(key==='frequency'&&Number($('#n-start_frequency').value)>Number(e.target.value)){
   $('#n-start_frequency').value=$('#r-start_frequency').value=e.target.value;
  }
  $('#preset').value='';
 });
}
async function stop(note){
 held=false;generation++;stopping=true;clearInterval(timer);timer=null;
 document.querySelectorAll('.pressed').forEach(b=>b.classList.remove('pressed'));lock(false);
 const trial=currentTrial;currentTrial=null;
 try{await post('stop',{},null);if(note)message(note)}catch(e){message('Stopp nicht bestätigt: '+e.message,true)}
 token=null;
 if(trial){
  try{const r=await fetch('/api/motor-tuning',{signal:AbortSignal.timeout(1000)});if(r.ok)lastYaw=(await r.json()).gyro_yaw_deg||0}catch{}
  lastDelta=(lastYaw-baseline+540)%360-180;
  $('#yaw').textContent=lastDelta.toFixed(1)+'°';
  const list=$('#history');if(!list.dataset.used){list.replaceChildren();list.dataset.used='1'}
  const li=document.createElement('li');li.textContent=`${trial.label} · ${trial.wheel} · ${trial.reverse?'umgekehrt':'normale Reihenfolge'} · ${format(trial.p.frequency)} Hz · ${format(trial.p.duty)} % · Rampe ${format(trial.p.acceleration)} Hz/s · ${lastDelta.toFixed(1)}° Drehänderung`;
  list.prepend(li);while(list.children.length>8)list.lastElementChild.remove();
 }
 stopping=false;
}
async function begin(button){
 if(!ready||held||stopping)return;
 let p;try{p=values();for(const [key,,low,high] of fields)if(!Number.isFinite(p[key])||p[key]<low||p[key]>high)throw Error('Bitte gültige Werte eintragen.')}catch(e){message(e.message,true);return}
 held=true;const epoch=++generation;lock(true);button.classList.add('pressed');baseline=lastYaw;
 const duration=Number($('#duration').value);message('Test wird vorbereitet …');
 try{
  const control=await post('motor-test-arm',{},null);
  if(!held||epoch!==generation){await post('stop',{},null);return}
  token=control.token;
  const wheel=$('#testWheel').value,reverse=$('#testReverse').checked;
  const result=await post('motor-test-start',{profile:p,direction:button.dataset.direction,duration,wheel,reverse});
  if(!held||epoch!==generation){await post('stop',{},null);return}
  token=result.token;currentTrial={p,label:button.textContent.trim(),started:performance.now(),wheel,reverse};
  message(`Test läuft · höchstens ${format(duration,2)} s. Loslassen stoppt.`);
  timer=setInterval(async()=>{
   if(busy||!held)return;busy=true;
   try{await post('motor-test-refresh')}catch(e){if(held)await stop(e.message)}finally{busy=false}
  },100);
  setTimeout(()=>{if(epoch===generation)stop('Testdauer erreicht · gestoppt')},duration*1000+100);
 }catch(e){if(epoch===generation)await stop(e.message);else await post('stop',{},null).catch(()=>{})}
}
for(const button of document.querySelectorAll('[data-direction]')){
 button.disabled=true;
 button.addEventListener('pointerdown',e=>{if(e.button!==0)return;e.preventDefault();button.setPointerCapture(e.pointerId);begin(button)});
 for(const name of ['pointerup','pointercancel','lostpointercapture'])button.addEventListener(name,()=>{if(held)stop('Losgelassen · gestoppt')});
 button.addEventListener('contextmenu',e=>e.preventDefault());
 button.addEventListener('keydown',e=>{if(['Enter',' '].includes(e.key)){e.preventDefault();if(!e.repeat)begin(button)}});
 button.addEventListener('keyup',e=>{if(['Enter',' '].includes(e.key)){e.preventDefault();if(held)stop('Losgelassen · gestoppt')}});
}
$('#stop').onclick=()=>stop('Gestoppt');
function channelView(){
 const single=$('#testWheel').value!=='all';
 document.querySelectorAll('[data-direction]').forEach(b=>b.disabled=!ready||(single&&!['forward','backward'].includes(b.dataset.direction)));
 $('#channelHint').textContent=single?'Einzelradprüfung: Vorwärts/Rückwärts wirkt nur auf das gewählte Rad. Der Roboter kann sich dabei drehen.':$('#testReverse').checked?'Reihenfolge: hinten rechts → hinten links → vorne rechts → vorne links.':'Reihenfolge normal: vorne links → vorne rechts → hinten links → hinten rechts.';
}
$('#testWheel').onchange=channelView;$('#testReverse').onchange=channelView;
$('#preset').onchange=()=>{
 const key=$('#preset').value;
 if(key==='draft'&&savedState)fill(savedState.draft);
 if(key==='crawl')fill({frequency:100,acceleration:0,duty:50,start_frequency:40,warmup:1,enable_delay:10});
 if(key==='old'||key==='medium')fill({frequency:key==='old'?8000:1000,acceleration:20000,duty:50,start_frequency:40,warmup:0,enable_delay:100});
 message('Vorlage geladen. Es bewegt sich erst etwas, wenn du eine Richtung hältst.');
};
for(const [id,apply] of [['save',false],['apply',true]])$('#'+id).onclick=async()=>{
 try{
  await stop();savedState=await post('motor-profile',{profile:values(),apply},null);
  render(savedState);message(apply?'Fahrprofil übernommen und dauerhaft gespeichert. Der normale Joystick nutzt jetzt diese Grenzen und den Anlauf.':'Entwurf gespeichert. Das normale Fahrprofil bleibt unverändert.');
 }catch(e){message(e.message,true)}
};
function render(s,pollStarted=Infinity){
 lastYaw=s.gyro_yaw_deg||0;
 $('#actual').textContent=(s.actual_hz||[0,0,0,0]).map(v=>format(v)).join(' · ')+' Hz';
 const delta=(lastYaw-baseline+540)%360-180;$('#yaw').textContent=(held?delta:lastDelta).toFixed(1)+'°';
 $('#front').textContent=s.front_distance==null?'—':format(s.front_distance*100)+' cm';
 $('#remaining').textContent=s.running?format(s.remaining,1)+' s':'HALTEN';
 $('#active').textContent=s.active?`Fahrprofil: maximal ${format(s.active.frequency)} Hz · ${format(s.active.duty)} % Pulsanteil. Bleibt nach Neustart erhalten.`:'Fahrprofil: bisherige Einstellungen. Entwürfe ändern den normalen Joystick erst nach „Übernehmen“. ';
 $('#live').textContent=s.running?'● TEST LÄUFT':'● verbunden';
 if(s.pins){
  const container=$('#pinStates');container.replaceChildren();
  for(const pin of s.pins){const row=document.createElement('div');row.className='pinRow';row.textContent=pin.error?`${pin.wheel}: ${pin.error}`:`${pin.wheel} · STEP ${pin.step} / DIR ${pin.direction} · ${format(pin.frequency)} Hz · PWM ${pin.duty}/255 · ${pin.mode===1?'Ausgang':'Modus '+pin.mode}`;container.append(row);}
 }
 if(held&&token&&!s.running&&currentTrial&&pollStarted>currentTrial.started)stop(s.stop_reason==='Gestoppt'?'Test beendet · gestoppt':s.stop_reason||'Test beendet');
 if(held&&currentTrial&&s.running&&s.stop_reason&&pollStarted>currentTrial.started)stop(s.stop_reason);
}
let polling=false;
async function poll(){
 if(polling)return;polling=true;const pollStarted=performance.now();
 try{
  const r=await fetch('/api/motor-tuning',{signal:AbortSignal.timeout(2000)});if(!r.ok)throw Error('Roboter nicht bereit');const s=await r.json();
  if(!ready){savedState=s;fill(s.draft);ready=true;channelView();message('Bereit. Werte wählen und eine Richtung gedrückt halten.');}
  render(s,pollStarted);
 }catch(e){$('#live').textContent='● offline';if(held)await stop('Verbindung unterbrochen · gestoppt');else message('Keine Verbindung zum Roboter.',true)}finally{polling=false}
}
window.addEventListener('pagehide',()=>{held=false;generation++;fetch('/api/stop',{method:'POST',headers:{'Content-Type':'application/json','X-Matebot-Control':'1'},body:'{}',keepalive:true}).catch(()=>{})});
window.addEventListener('blur',()=>{if(held)stop('Fenster verlassen · gestoppt')});
document.addEventListener('visibilitychange',()=>{if(document.hidden&&held)stop('Ansicht verlassen · gestoppt')});
document.addEventListener('keydown',e=>{if(e.key==='Escape'){e.preventDefault();stop('Gestoppt')}});
let frameBusy=false;
setInterval(async()=>{
 if(frameBusy||document.hidden)return;frameBusy=true;
 try{const r=await fetch('/api/camera/frame.jpg',{signal:AbortSignal.timeout(1800)});if(!r.ok)throw Error();const url=URL.createObjectURL(await r.blob());const previous=$('#camera').dataset.url;$('#camera').src=url;$('#camera').dataset.url=url;if(previous)URL.revokeObjectURL(previous);$('#cameraState').textContent='LIVE · vorne'}catch{$('#cameraState').textContent='Kamera momentan nicht verfügbar'}finally{frameBusy=false}
},400);
poll();setInterval(poll,500);
