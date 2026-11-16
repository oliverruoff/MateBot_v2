(function(){
  'use strict';
  const app=window.MatebotApp,math=window.MatebotDrive,$=s=>document.querySelector(s);
  const radar=$('#frontLidar'),context=radar.getContext('2d'),stick=$('#joystick'),knob=$('#joystickKnob');
  let latest={},range=4,view='map',cameraEnabled=true,cameraTimer=null,cameraRequest=null,cameraBusy=false;
  let frameAt=0,lastSequence=-1,frameURL=null,framesShown=0,rateAt=performance.now(),displayFPS=0,stoppingForVideo=false;
  let followMap=true;
  let stickPointer=null,stickVector=[0,0,0];const sidePointers=new Map();
  const cameraWanted=()=>visible()||$('#goalDialog').open;
  const visible=()=>view==='drive',frameFresh=()=>cameraEnabled&&performance.now()-frameAt<1200&&frameAt>0;
  const guarded=f=>async()=>{try{await f()}catch(e){app.toast(e.message)}};

  function setView(next,persist=true){
    if(view!==next){app.endManual();if(app.ownsControl())app.stop().catch(()=>{})}
    view=next;document.body.classList.toggle('drive-view',visible());
    if(persist){try{localStorage.setItem('matebot.view',next)}catch{}}
    try{history.replaceState(null,'',visible()?'/drive':'/')}catch{}
    app.mountMap(visible()?$('#driveMapStage'):null);
    if(visible()){startCamera();resizeRadar()}
    else{if(!cameraWanted()){clearTimeout(cameraTimer);cameraRequest?.abort()}app.redraw()}
    renderStatus();
  }
  function resizeRadar(){
    if(!visible()||radar.clientWidth<1||radar.clientHeight<1)return;
    const d=devicePixelRatio||1;radar.width=radar.clientWidth*d;radar.height=radar.clientHeight*d;
    context.setTransform(d,0,0,d,0,0);drawRadar();
  }
  new ResizeObserver(resizeRadar).observe(radar);
  function points(){return math.cameraPoints(latest.points||[],latest.lidar_transform||[0,0,0],latest.camera_view?.yaw||0)}
  function distance(id,value){const element=$(id);element.textContent=value==null?'—':value.toFixed(2)+' m';element.style.color=value!=null&&value<.35?'#e8ae78':''}
  function drawRadar(){
    if(!visible())return;
    const scan=points();
    distance('#distanceLeft',math.sectorDistance(scan,45,15));distance('#distanceFront',math.sectorDistance(scan,0,12));distance('#distanceRight',math.sectorDistance(scan,-45,15));
    $('#lidarStale').hidden=latest.lidar_age<.5;
    $('#driveMapStatus').textContent=latest.localized?'LIVE · VORNE ↑':'ORTUNG LÄUFT';
  }
  function renderStatus(){
    const fresh=frameFresh(),s=latest,ready=app.canDrive();
    $('#driveStatusDot').style.background=ready?'#c2dc94':'#d2a35b';
    $('#driveFloorHint').hidden=!s.initial_floor_test;
    let message=s.manual_blocked||s.manual_warning||'Bereit · Joystick halten, Loslassen stoppt';
    if(!s.localized&&s.saved_map)message=s.manual_blocked||'Ortung im Hintergrund · manuelles Fahren bereit';
    else if(!fresh)message=cameraEnabled?'Kamera wird verbunden':'Kamera pausiert – Fahren gesperrt';
    else if(s.annotations?.mode==='navigation')message='Karte antippen: Ziel wählen · Joystick: selbst fahren';
    if(!$('#zoneTools').hidden)message='Sperrzonen bearbeiten · zum Fahren „Zonen fertig“ wählen';
    $('#driveNoticeText').textContent=message;
    $('#driveResume').hidden=$('#drivePosition').hidden=$('#driveArm').hidden=true;
    stick.setAttribute('aria-disabled',String(!ready));
    $('#strafeLeft').disabled=$('#strafeRight').disabled=!ready;
    $('#cameraStatus').textContent=fresh?'LIVE · '+(displayFPS||'…')+' FPS':cameraEnabled?'VERBINDET':'PAUSIERT';
    $('#cameraOverlay').hidden=fresh;
    if(!fresh)$('#cameraOverlay').textContent=cameraEnabled?(frameAt?'Kamerabild nicht aktuell. Steuerung angehalten.':'Kamera wird verbunden …'):'Livebild pausiert';
    $('#cameraFrame').style.opacity=fresh?'1':'.2';
    $('#goalCamera').style.opacity=fresh?'1':'.2';
    $('#goalCameraStatus').textContent=$('#cameraStatus').textContent;
    $('#goalCameraOverlay').hidden=fresh;
    $('#goalCameraOverlay').textContent=fresh?'':'Kamerabild nicht aktuell · Verbindung wird erneuert';
  }
  function stopForStaleVideo(){
    if(cameraWanted()&&!frameFresh()&&app.ownsControl()&&!stoppingForVideo){
      stoppingForVideo=true;app.stop().catch(()=>{}).finally(()=>stoppingForVideo=false);
      app.toast('Kamerabild nicht aktuell – Roboter gestoppt');
    }
  }
  async function nextFrame(){
    if(cameraBusy||!cameraWanted()||!cameraEnabled||document.hidden)return;
    cameraBusy=true;let delay=65,url=null;
    try{
      cameraRequest=new AbortController();const timer=setTimeout(()=>cameraRequest?.abort(),3200);
      let response;try{response=await fetch('/api/camera/frame.jpg',{cache:'no-store',signal:cameraRequest.signal})}finally{clearTimeout(timer)}
      if(!response.ok)throw Error('Kamera nicht bereit');
      const sequence=Number(response.headers.get('X-Frame-Sequence')),age=Number(response.headers.get('X-Frame-Age-Ms'));
      if(!Number.isFinite(sequence)||!Number.isFinite(age)||age>=700)throw Error('Bild veraltet');
      const blob=await response.blob();
      if(!cameraWanted()||!cameraEnabled||document.hidden)return;
      url=URL.createObjectURL(blob);const image=$('#goalDialog').open?$('#goalCamera'):$('#cameraFrame');$('#cameraFrame').src=url;$('#goalCamera').src=url;await image.decode();
      const old=frameURL;frameURL=url;url=null;if(old)URL.revokeObjectURL(old);
      if(sequence!==lastSequence){lastSequence=sequence;frameAt=performance.now();framesShown++}
      const now=performance.now();if(now-rateAt>=1000){displayFPS=Math.round(framesShown*1000/(now-rateAt));framesShown=0;rateAt=now}
    }catch{delay=500}
    finally{
      if(url)URL.revokeObjectURL(url);
      cameraRequest=null;cameraBusy=false;renderStatus();stopForStaleVideo();
      if(cameraWanted()&&cameraEnabled&&!document.hidden)cameraTimer=setTimeout(nextFrame,delay);
    }
  }
  function startCamera(){clearTimeout(cameraTimer);if(cameraEnabled&&!document.hidden)nextFrame()}
  function setKnob(x=0,y=0){knob.style.transform='translate('+x+'px,'+y+'px)'}
  function resetControls(){
    stickPointer=null;stickVector=[0,0,0];sidePointers.clear();stick.classList.remove('active');
    $('#strafeLeft').classList.remove('active');$('#strafeRight').classList.remove('active');
    setKnob();$('#driveInputLabel').textContent='Loslassen stoppt';
  }
  function inputLabel(){
    const v=math.combine([stickVector,...[...sidePointers.keys()].map(id=>id==='strafeLeft'?[0,1,0]:[0,-1,0])],1,1);
    const labels=[];if(v[0]>.05)labels.push('vorwärts');if(v[0]<-.05)labels.push('rückwärts');
    if(v[1]>.05)labels.push('links versetzen');if(v[1]<-.05)labels.push('rechts versetzen');
    if(v[2]>.05)labels.push('links drehen');if(v[2]<-.05)labels.push('rechts drehen');
    $('#driveInputLabel').textContent=labels.length?labels.join(' · '):'Loslassen stoppt';
  }
  function moveStick(e){
    if(e.pointerId!==stickPointer)return;
    const rect=stick.getBoundingClientRect(),radius=rect.width*.31;
    const dx=e.clientX-rect.left-rect.width/2,dy=e.clientY-rect.top-rect.height/2;
    const length=Math.hypot(dx,dy),factor=length>radius?radius/length:1;
    setKnob(dx*factor,dy*factor);stickVector=math.stickVector(dx/radius,dy/radius);
    if(stickVector.some(Boolean))app.startManual(stickVector,'joystick');else app.endManual('joystick');
    inputLabel();
  }
  stick.onpointerdown=e=>{
    if(!app.canDrive()){app.toast($('#driveNoticeText').textContent);return}
    if(stickPointer!==null)return;e.preventDefault();stickPointer=e.pointerId;stick.setPointerCapture(e.pointerId);stick.classList.add('active');moveStick(e);
  };
  stick.onpointermove=moveStick;
  function releaseStick(e){if(e.pointerId!==stickPointer)return;stickPointer=null;stickVector=[0,0,0];stick.classList.remove('active');setKnob();app.endManual('joystick');inputLabel()}
  stick.onpointerup=releaseStick;stick.onpointercancel=releaseStick;stick.onlostpointercapture=releaseStick;
  for(const [id,vector] of [['strafeLeft',[0,1,0]],['strafeRight',[0,-1,0]]]){
    const button=$('#'+id);
    button.onpointerdown=e=>{if(!app.canDrive()||sidePointers.has(id))return;e.preventDefault();sidePointers.set(id,e.pointerId);button.setPointerCapture(e.pointerId);button.classList.add('active');app.startManual(vector,id);inputLabel()};
    const release=e=>{if(sidePointers.get(id)!==e.pointerId)return;sidePointers.delete(id);button.classList.remove('active');app.endManual(id);inputLabel()};
    button.onpointerup=release;button.onpointercancel=release;button.onlostpointercapture=release;
  }
  $('#driveSpeed').oninput=()=>{app.setSpeed($('#driveSpeed').value);$('#driveSpeedValue').textContent=$('#driveSpeed').value+' cm/s'};
  $('#driveStop').onclick=guarded(app.stop);
  const menu=$('#menuDialog');menu.append(document.querySelector('aside'));
  $('#menuClose').onclick=()=>menu.close();
  $('#driveMap').onclick=()=>menu.showModal();
  $('#mapPan').onclick=()=>{$('#panMap').click();$('#mapPan').classList.toggle('active',$('#panMap').classList.contains('active'));$('#mapPan').textContent=$('#panMap').classList.contains('active')?'⌖ Ziel wählen':'↔ Karte verschieben';$('#mapHint').textContent=$('#panMap').classList.contains('active')?'Ziehen verschiebt die Karte · Zielwahl zum Fahren wählen':'Freie Fläche antippen → Richtung wählen → Losfahren'};
  $('#mapZones').onclick=guarded(async()=>{const zones=$('#zoneTools').hidden;await app.setMapTool(zones?'zones':'goals');$('#mapPan').disabled=zones;$('#mapZones').textContent=zones?'✓ Zonen fertig':'Sperrzonen';$('#mapHint').textContent=zones?'Rasterzellen antippen oder Rechteck ziehen · automatisch gespeichert':'Freie Fläche antippen → Richtung wählen → Losfahren'});
  $('#driveMapStage').append($('#zoneTools'),$('#positionHelp'));
  for(const id of ['position','newMap'])$('#'+id).addEventListener('click',()=>menu.close());
  for(const id of ['openDrive','openDriveNav'])$('#'+id).onclick=guarded(async()=>{setView('drive');await app.ensureMapping()});
  $('#driveArm').onclick=guarded(async()=>{await app.ensureMapping();app.openArm()});
  $('#driveResume').onclick=guarded(app.resume);
  $('#drivePosition').onclick=()=>{setView('map');app.selectPosition()};
  $('#cameraToggle').onclick=()=>{cameraEnabled=!cameraEnabled;$('#cameraToggle').textContent=cameraEnabled?'Pause':'Verbinden';if(!cameraEnabled){cameraRequest?.abort();clearTimeout(cameraTimer);if(app.ownsControl())app.stop().catch(()=>{})}else{lastSequence=-1;frameAt=0;startCamera()}renderStatus()};
  $('#driveFit').onclick=()=>{followMap=true;app.fitMap()};
  $('#driveZoomIn').onclick=()=>{if(followMap)app.freezeMap();followMap=false;app.zoomMap(1.3)};
  $('#driveZoomOut').onclick=()=>{if(followMap)app.freezeMap();followMap=false;app.zoomMap(1/1.3)};
  $('#driveMapStage').addEventListener('pointerdown',()=>{if(followMap)app.freezeMap();followMap=false},true);
  document.addEventListener('goal-visibility',()=>{if(cameraWanted()){cameraEnabled=true;startCamera()}else{clearTimeout(cameraTimer);cameraRequest?.abort()}});
  document.addEventListener('visibilitychange',()=>{if(document.hidden){cameraRequest?.abort();clearTimeout(cameraTimer)}else startCamera()});
  window.addEventListener('pagehide',()=>{cameraRequest?.abort();clearTimeout(cameraTimer)});
  window.MatebotCockpit={visible,frameFresh,resetControls,followMap:()=>visible()&&followMap,
    onState:s=>{latest=s;renderStatus();drawRadar();if(!app.canDrive()&&(stickPointer!==null||sidePointers.size))app.endManual()},
    onDisconnect:()=>{latest={...latest,blocked:'Verbindung unterbrochen',estop:true};renderStatus()}};
  setInterval(()=>{if(cameraWanted()){renderStatus();stopForStaleVideo()}},150);
  setView('drive',false);
})();
