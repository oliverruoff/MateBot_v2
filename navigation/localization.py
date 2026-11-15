"""Stationary global scan-to-map matching. Never moves the robot to search."""
import math
import numpy as np


def angle_delta(a,b):return (a-b+math.pi)%(2*math.pi)-math.pi


class ScanMatcher:
    def __init__(self,grid):
        self.res=float(grid['resolution']);self.origin=grid['origin']
        self.cells=np.asarray(grid['cells'],dtype=np.int16).reshape(grid['height'],grid['width'])
        self.h,self.w=self.cells.shape
        occupied=self.cells>=65
        # Finite Gaussian wall likelihood, constructed without a scipy dependency.
        self.field=np.zeros_like(self.cells,dtype=float)
        radius=math.ceil(.30/self.res)
        for dy in range(-radius,radius+1):
            for dx in range(-radius,radius+1):
                weight=math.exp(-((dx*self.res)**2+(dy*self.res)**2)/(2*.10**2))
                if weight<.01:continue
                ya,yb=max(0,dy),min(self.h,self.h+dy);xa,xb=max(0,dx),min(self.w,self.w+dx)
                if ya>=yb or xa>=xb:continue
                self.field[ya:yb,xa:xb]=np.maximum(self.field[ya:yb,xa:xb],occupied[ya-dy:yb-dy,xa-dx:xb-dx]*weight)

    def indices(self,x,y):
        ox,oy,a=self.origin;dx=x-ox;dy=y-oy
        ix=np.floor((dx*math.cos(a)+dy*math.sin(a))/self.res).astype(int)
        iy=np.floor((-dx*math.sin(a)+dy*math.cos(a))/self.res).astype(int)
        valid=(ix>=0)&(iy>=0)&(ix<self.w)&(iy<self.h)
        return np.clip(ix,0,self.w-1),np.clip(iy,0,self.h-1),valid

    def metrics(self,poses,points):
        poses=np.asarray(poses,dtype=float);p=np.asarray(points,dtype=float)
        c=np.cos(poses[:,2,None]);s=np.sin(poses[:,2,None])
        rx=c*p[:,0]-s*p[:,1];ry=s*p[:,0]+c*p[:,1]
        ix,iy,valid=self.indices(poses[:,0,None]+rx,poses[:,1,None]+ry)
        wall=self.field[iy,ix]*valid
        score=wall.mean(axis=1);hits=(wall>=math.exp(-.15**2/(2*.1**2))).mean(axis=1)
        collision=np.zeros(len(poses));coverage=np.zeros(len(poses))
        for fraction in (.25,.5,.75):
            ix,iy,v=self.indices(poses[:,0,None]+rx*fraction,poses[:,1,None]+ry*fraction)
            collision+=((self.cells[iy,ix]>=65)&v).mean(axis=1)/3
            coverage+=((self.cells[iy,ix]>=0)&v).mean(axis=1)/3
        ix,iy,v=self.indices(poses[:,0],poses[:,1])
        free=v&(self.cells[iy,ix]>=0)&(self.cells[iy,ix]<25)
        return score-2*collision-(~free),hits,coverage,collision

    def rank(self,poses,points,count=32):
        ranked=[]
        for start in range(0,len(poses),256):
            batch=np.asarray(poses[start:start+256],dtype=float)
            metrics=self.metrics(batch,points)
            for i in np.argsort(metrics[0])[-count:]:
                ranked.append((float(metrics[0][i]),batch[i].tolist()))
        return sorted(ranked,key=lambda r:r[0],reverse=True)[:count]

    def match(self,points,prior=None):
        points=np.asarray(points,dtype=float)
        if points.ndim!=2 or points.shape[1]!=2 or len(points)<80:return None
        points=points[np.isfinite(points).all(axis=1)]
        points=points[(np.linalg.norm(points,axis=1)>.3)&(np.linalg.norm(points,axis=1)<10)]
        if len(points)<80:return None
        points=points[::max(1,len(points)//120)]
        stride=max(1,round(.20/self.res));free=(self.cells>=0)&(self.cells<25)
        yy,xx=np.where(free[::stride,::stride]);xx=xx*stride;yy=yy*stride
        if len(xx)>15000:return None  # Bound work on unexpectedly large maps.
        ox,oy,a=self.origin
        x=(xx+.5)*self.res;y=(yy+.5)*self.res
        world=np.column_stack((ox+x*math.cos(a)-y*math.sin(a),oy+x*math.sin(a)+y*math.cos(a)))
        poses=[[float(x),float(y),float(t)] for x,y in world for t in np.arange(-math.pi,math.pi,math.pi/18)]
        if prior:poses.append([prior['x'],prior['y'],prior['yaw']])
        if not poses:return None
        ranked=self.rank(poses,points)
        # Keep competing, separated hypotheses through refinement to detect ambiguity.
        seeds=[]
        for score,p in ranked:
            if all(math.hypot(p[0]-q[0],p[1]-q[1])>.35 or abs(angle_delta(p[2],q[2]))>.25 for q in seeds):seeds.append(p)
        for distance,angle in [(.10,math.pi/36),(.025,math.pi/180)]:
            poses=[[p[0]+dx,p[1]+dy,p[2]+dt] for p in seeds for dx in (-distance,0,distance) for dy in (-distance,0,distance) for dt in (-angle,0,angle)]
            ranked=self.rank(poses,points,64);seeds=[]
            for score,p in ranked:
                if all(math.hypot(p[0]-q[0],p[1]-q[1])>.25 or abs(angle_delta(p[2],q[2]))>.15 for q in seeds):seeds.append(p)
        score,best=ranked[0];_,hits,known,collision=self.metrics([best],points)
        rivals=[s for s,p in ranked if math.hypot(p[0]-best[0],p[1]-best[1])>.6 or abs(angle_delta(p[2],best[2]))>.35]
        margin=score-max(rivals) if rivals else 1.
        if score<.60 or hits[0]<.65 or known[0]<.65 or collision[0]>.08 or margin<.055:return None
        return dict(x=best[0],y=best[1],yaw=angle_delta(best[2],0),score=score,margin=margin)
