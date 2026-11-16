(function(){
  'use strict';
  const app=window.MatebotApp,$=s=>document.querySelector(s),dialog=$('#goalDialog');
  const canvas=$('#goalPreview'),ctx=canvas.getContext('2d');
  let target=null,heading=0,phase='draft',epoch=0,error='',pointer=null,runningAt=0,validation=null,validationTimer=null,validationSerial=0,hasStarted=false;
  const active=()=>phase==='preparing'||phase==='running';
  const key=()=>target?[...target,heading].join('/'):'none';
  function validateSoon(){
    const serial=++validationSerial;validation=null;clearTimeout(validationTimer);
    validationTimer=setTimeout(async()=>{
      if(!target)return;const current=key();
      try{const result=await app.api('goal-preview',{x:target[0],y:target[1],yaw:heading});if(serial===validationSerial&&current===key())validation={...result,key:current}}
      catch(e){if(serial===validationSerial)validation={valid:false,reason:e.message,key:current}}
      render();
    },180);
  }
  function validity(){
    const map=app.mapData();if(!target||!map)return 'Die Karte wird noch geladen';
    const a=map.origin[2],dx=target[0]-map.origin[0],dy=target[1]-map.origin[1];
    const x=Math.floor((dx*Math.cos(a)+dy*Math.sin(a))/map.resolution),y=Math.floor((-dx*Math.sin(a)+dy*Math.cos(a))/map.resolution);
    if(x<0||y<0||x>=map.width||y>=map.height)return 'Ziel liegt außerhalb der Karte';
    const cell=map.cells[y*map.width+x];
    if(cell<0)return 'Bitte eine bereits erkundete Fläche wählen';
    if(cell>=25)return 'Hier ist ein Hindernis – eine freie Fläche wählen';
    if(!validation||validation.key!==key())return 'Position und Blickrichtung werden geprüft …';
    return validation.valid?'':validation.reason;
  }
  function render(){
    if(!dialog.open)return;
    const state=app.state(),invalid=validity(),degrees=((Math.round(heading*180/Math.PI)%360)+360)%360;
    dialog.dataset.phase=phase;$('#goalHeading').value=String(degrees);$('#goalHeadingValue').textContent=degrees+'°';
    $('#goalHeading').disabled=$('#goalFaceRobot').disabled=active();
    $('#confirmGoal').disabled=active()||!!invalid||!state.localized||!state.calibrated||!window.MatebotCockpit?.frameFresh();
    $('#confirmGoal').textContent=phase==='preparing'?'Wird gestartet …':phase==='running'?'Unterwegs …':phase==='done'?'Erneut fahren →':'Losfahren →';
    $('#goalClose').setAttribute('aria-label',active()?'Schließen und Fahrt stoppen':'Zielansicht schließen');
    const pose=state.pose,distance=target&&pose?Math.hypot(target[0]-pose.x,target[1]-pose.y):null;
    let title=invalid||'Ziel gewählt'+(distance!=null?' · '+distance.toFixed(1)+' m entfernt':'');
    let detail='Pfeil ziehen oder Regler bewegen. Die Richtung gilt bei Ankunft.';
    if(!state.calibrated)detail='Für die Zielfahrt fehlen noch bestätigte Fahrprüfungen unter Einstellungen.';
    else if(!state.localized)detail=state.localization_status||'Position wird gesucht';
    else if(!state.navigation_ready)detail=state.navigation_status||'Navigation startet …';
    if(phase==='preparing'){title=state.navigation_ready?'Route wird geplant …':'Navigation wird gestartet …';detail='Die Fahrt beginnt, sobald Route und Steuerung bereit sind. STOPP bricht ab.'}
    if(phase==='running'){title='Matebot fährt zum Ziel'+(state.goal_distance!=null?' · '+state.goal_distance.toFixed(1)+' m verbleibend':'');detail='Ankunft mit der gewählten Blickrichtung. Schließen stoppt die Fahrt.'}
    if(phase==='running'&&state.manual_warning){title='Hindernis erkannt';detail='Matebot prüft eine freie Fahrtrichtung. STOPP bricht die Fahrt ab.'}
    if(phase==='done'){title='Ziel erreicht';detail='Matebot steht am Ziel. Du kannst eine neue Position auswählen.'}
    if(phase==='stopped'){title='Fahrt gestoppt';detail=error&&!/Gestoppt|Einstellungen/.test(error)?error+' · Ziel bleibt ausgewählt.':'Das Ziel bleibt ausgewählt. Mit Losfahren erneut starten.'}
    if(phase==='error'){title=hasStarted?'Fahrt angehalten':'Fahrt konnte nicht starten';detail=error}
    $('#goalMissionText').textContent=title;$('#goalNavigationStatus').textContent=detail;
    drawPreview();
  }
  function drawPreview(){
    if(!target||canvas.clientWidth<1)return;
    const w=canvas.clientWidth,h=canvas.clientHeight,d=devicePixelRatio||1;
    canvas.width=w*d;canvas.height=h*d;ctx.setTransform(d,0,0,d,0,0);
    ctx.fillStyle='#e4ebdb';ctx.fillRect(0,0,w,h);
    const scale=Math.min(w,h)/3.2,project=(x,y)=>[w/2+(x-target[0])*scale,h/2-(y-target[1])*scale];
    const map=app.mapData(),image=app.mapImage();
    if(map&&image){const p=project(...map.origin);ctx.save();ctx.translate(...p);ctx.rotate(-map.origin[2]);ctx.imageSmoothingEnabled=false;ctx.drawImage(image,0,-map.height*map.resolution*scale,map.width*map.resolution*scale,map.height*map.resolution*scale);ctx.restore()}
    const state=app.state(),grid=state.annotations?.grid_size||.25;
    ctx.fillStyle='#b14f4088';for(const [x,y] of state.annotations?.zones||[]){const p=project(x*grid,(y+1)*grid);ctx.fillRect(p[0],p[1],grid*scale,grid*scale)}
    if(state.path?.length){ctx.strokeStyle='#8caa58';ctx.lineWidth=3;ctx.beginPath();state.path.forEach((p,i)=>i?ctx.lineTo(...project(...p)):ctx.moveTo(...project(...p)));ctx.stroke()}
    if(state.pose&&state.localized){const p=project(state.pose.x,state.pose.y);ctx.fillStyle='#4d715b';ctx.beginPath();ctx.arc(...p,5,0,Math.PI*2);ctx.fill()}
    const cx=w/2,cy=h/2,length=Math.min(w,h)*.30;
    ctx.strokeStyle=!validation?'#b49b62':validity()?'#ad5546':'#a0773f';ctx.fillStyle=ctx.strokeStyle;ctx.lineWidth=3;
    const [bodyLength,bodyWidth]=state.geometry||[.41,.3];
    ctx.save();ctx.translate(cx,cy);ctx.rotate(-heading);ctx.lineWidth=1.2;
    ctx.fillStyle=validity()?'#ad554422':'#a0773f22';
    ctx.fillRect(-bodyLength*scale/2,-bodyWidth*scale/2,bodyLength*scale,bodyWidth*scale);
    ctx.strokeRect(-bodyLength*scale/2,-bodyWidth*scale/2,bodyLength*scale,bodyWidth*scale);
    ctx.setLineDash([3,3]);ctx.strokeRect(-(bodyLength+.20)*scale/2,-(bodyWidth+.20)*scale/2,(bodyLength+.20)*scale,(bodyWidth+.20)*scale);ctx.restore();
    ctx.fillStyle=ctx.strokeStyle;
    ctx.beginPath();ctx.arc(cx,cy,10,0,2*Math.PI);ctx.stroke();
    const tip=[cx+Math.cos(heading)*length,cy-Math.sin(heading)*length];ctx.beginPath();ctx.moveTo(cx,cy);ctx.lineTo(...tip);ctx.stroke();
    ctx.save();ctx.translate(...tip);ctx.rotate(-heading);ctx.beginPath();ctx.moveTo(8,0);ctx.lineTo(-8,-7);ctx.lineTo(-8,7);ctx.closePath();ctx.fill();ctx.restore();
    ctx.font='9px Segoe UI';ctx.fillStyle='#6e8064';ctx.fillText('KARTENRICHTUNG ↑',10,16);ctx.fillText('ZIEL · PFEIL = BLICKRICHTUNG',10,h-9);
  }
  function setDirection(event){
    if(active())return;const r=canvas.getBoundingClientRect(),dx=event.clientX-r.left-r.width/2,dy=event.clientY-r.top-r.height/2;
    if(Math.hypot(dx,dy)<12)return;heading=Math.atan2(-dy,dx);phase='draft';validateSoon();render();
  }
  canvas.onpointerdown=e=>{if(active())return;e.preventDefault();pointer=e.pointerId;canvas.setPointerCapture(pointer);setDirection(e)};
  canvas.onpointermove=e=>{if(e.pointerId===pointer)setDirection(e)};
  canvas.onpointerup=canvas.onpointercancel=canvas.onlostpointercapture=()=>pointer=null;
  $('#goalHeading').oninput=()=>{heading=Number($('#goalHeading').value)*Math.PI/180;phase='draft';validateSoon();render()};
  $('#goalFaceRobot').onclick=()=>{const p=app.state().pose;if(p&&target){heading=Math.atan2(p.y-target[1],p.x-target[0]);validateSoon();render()}};
  async function open(x,y,name='',angle){
    await app.stop();await app.ensureNavigation();
    epoch++;target=[x,y];error='';phase='draft';hasStarted=false;const pose=app.state().pose;
    heading=Number.isFinite(angle)?angle:pose?Math.atan2(y-pose.y,x-pose.x):0;
    app.selectGoal(x,y);$('#favoriteName').value=name;
    $('#goalText').textContent='Zielposition auf der Karte gewählt. Ziehe den Pfeil in die gewünschte Blickrichtung.';
    if(!dialog.open)dialog.showModal();document.dispatchEvent(new Event('goal-visibility'));validateSoon();render();
  }
  $('#confirmGoal').onclick=async()=>{
    if(active()||validity())return;
    const current=++epoch,goal={x:target[0],y:target[1],yaw:heading};phase='preparing';error='';render();
    try{
      const deadline=Date.now()+45000;
      while(!app.state().navigation_ready){
        if(current!==epoch||!dialog.open)return;
        if(Date.now()>deadline)throw Error('Navigation ist nicht startbereit. '+(app.state().error||'Bitte erneut versuchen.'));
        await new Promise(resolve=>setTimeout(resolve,200));
      }
      if(current!==epoch||!dialog.open)return;
      if(!await app.ensureControl('navigation'))return;
      if(current!==epoch||!dialog.open){await app.stop();return}
      await app.api('goal',goal);
      if(current===epoch){phase='running';hasStarted=true;runningAt=Date.now();render()}
    }catch(e){if(current===epoch){phase='error';error=e.message;render()}}
  };
  $('#goalStop').onclick=()=>app.stop().catch(e=>app.toast(e.message));
  $('#goalClose').onclick=()=>dialog.close();
  dialog.addEventListener('close',()=>{const wasActive=active();epoch++;if(wasActive)app.stop().catch(()=>{});document.dispatchEvent(new Event('goal-visibility'))});
  $('#saveFavorite').onclick=async()=>{try{if(target){await app.api('favorite',{name:$('#favoriteName').value,x:target[0],y:target[1],yaw:heading});app.toast('Ziel und Blickrichtung gespeichert')}}catch(e){app.toast(e.message)}};
  new ResizeObserver(()=>{if(dialog.open)drawPreview()}).observe(canvas);
  window.MatebotGoals={open,
    onStop:()=>{epoch++;if(dialog.open){phase='stopped';error='';render()}},
    onState:state=>{
      if(phase==='running'&&Date.now()-runningAt>1500){
        if(state.goal_status==='Ziel erreicht')phase='done';
        else if(['Abgebrochen','Kein sicherer Weg gefunden'].includes(state.goal_status)){phase='error';error=state.goal_error||state.goal_status}
        else if(state.estop){phase='stopped';error=state.blocked||''}
      }
      render();
    }};
})();
