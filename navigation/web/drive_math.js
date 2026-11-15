(function(root){
  'use strict';
  const clamp=(v,min=-1,max=1)=>Math.max(min,Math.min(max,v));
  function stickVector(nx,ny,deadZone=.13){
    const length=Math.hypot(nx,ny);if(!Number.isFinite(length)||length<=deadZone)return [0,0,0];
    const amount=clamp((Math.min(length,1)-deadZone)/(1-deadZone),0,1);
    return [-ny/length*amount,0,-nx/length*amount];
  }
  function combine(vectors,speed,rotationSpeed){
    let [x,y,z]=vectors.reduce((sum,v)=>sum.map((n,i)=>n+(Number.isFinite(v[i])?v[i]:0)),[0,0,0]);
    const norm=Math.max(1,Math.hypot(x,y));
    return [x/norm*speed,y/norm*speed,clamp(z)*rotationSpeed];
  }
  function cameraPoints(points,lidar,cameraYaw=0){
    const [lx,ly,la]=lidar,ca=Math.cos(cameraYaw),sa=Math.sin(cameraYaw),c=Math.cos(la),s=Math.sin(la);
    return points.filter(p=>p.length===2&&p.every(Number.isFinite)).map(([x,y])=>{
      const bx=lx+x*c-y*s,by=ly+x*s+y*c;return [bx*ca+by*sa,-bx*sa+by*ca];
    });
  }
  function projectPoint(point,cx,baseY,scale){return [cx-point[1]*scale,baseY-point[0]*scale]}
  function sectorDistance(points,angle,halfAngle=12){
    const values=points.filter(([x,y])=>x>0&&Math.abs(Math.atan2(y,x)*180/Math.PI-angle)<=halfAngle).map(p=>Math.hypot(...p));
    return values.length?Math.min(...values):null;
  }
  const api={stickVector,combine,cameraPoints,projectPoint,sectorDistance};
  if(typeof module==='object'&&module.exports)module.exports=api;else root.MatebotDrive=api;
})(globalThis);
