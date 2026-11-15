"""Shared raster geometry for planner overlays, manual guard and UI validation."""
import math


def zone_collision(x,y,radius,cells,size):
    for cx in range(math.floor((x-radius)/size),math.floor((x+radius)/size)+1):
        for cy in range(math.floor((y-radius)/size),math.floor((y+radius)/size)+1):
            if (cx,cy) not in cells:continue
            dx=max(cx*size-x,0.,x-(cx+1)*size)
            dy=max(cy*size-y,0.,y-(cy+1)*size)
            if dx*dx+dy*dy<=radius*radius:return True
    return False


def overlay_indices(width,height,resolution,origin,cells,size):
    """Cover all intersecting occupancy cells, including raster boundaries."""
    ox,oy,angle=origin
    c,s=math.cos(angle),math.sin(angle)
    result=set()
    half=resolution*math.sqrt(2)/2
    for cx,cy in cells:
        corners=[((x-ox)*c+(y-oy)*s, -(x-ox)*s+(y-oy)*c)
                 for x in (cx*size,(cx+1)*size) for y in (cy*size,(cy+1)*size)]
        left=max(0,math.floor(min(x for x,_ in corners)/resolution))
        right=min(width-1,math.ceil(max(x for x,_ in corners)/resolution)-1)
        bottom=max(0,math.floor(min(y for _,y in corners)/resolution))
        top=min(height-1,math.ceil(max(y for _,y in corners)/resolution)-1)
        for row in range(bottom,top+1):
            for col in range(left,right+1):
                x=ox+(col+.5)*resolution*c-(row+.5)*resolution*s
                y=oy+(col+.5)*resolution*s+(row+.5)*resolution*c
                # Circumscribed cell circle is conservative for rotated map grids.
                dx=max(cx*size-x,0.,x-(cx+1)*size)
                dy=max(cy*size-y,0.,y-(cy+1)*size)
                if dx*dx+dy*dy<=half*half:result.add(row*width+col)
    return result


def laser_to_base(x,y,cfg):
    a=cfg['lidar_yaw']
    return cfg['lidar_x']+x*math.cos(a)-y*math.sin(a),cfg['lidar_y']+x*math.sin(a)+y*math.cos(a)


def self_return(x,y,cfg):
    # Never clear a ray behind the chassis; these returns become NaN, not infinity.
    padding=cfg.get('self_filter_padding',0.)
    return abs(x)<=cfg['footprint_length']/2+padding and abs(y)<=cfg['footprint_width']/2+padding


def rectangle_clearance(x,y,length,width):
    dx=max(abs(x)-length/2,0.)
    dy=max(abs(y)-width/2,0.)
    return math.hypot(dx,dy)


def obstacle_risk(points,cfg,cmd):
    """Conservative swept body check; permit reversing away from a close obstacle."""
    vx,vy,wz=cmd
    if max(abs(vx),abs(vy),abs(wz))<1e-5:return False
    length,width=cfg['footprint_length'],cfg['footprint_width']
    margin=.07
    for x,y in points:
        before=rectangle_clearance(x,y,length,width)
        for dt in (.10,.25,.50,.75):
            a=wz*dt
            px=(x-vx*dt)*math.cos(a)+(y-vy*dt)*math.sin(a)
            py=-(x-vx*dt)*math.sin(a)+(y-vy*dt)*math.cos(a)
            after=rectangle_clearance(px,py,length,width)
            if after<margin and after<before-1e-5:return True
    return False


def sweep_hits_zones(pose,cmd,cfg,cells,size):
    if not cells:return False
    if pose is None or pose.get('age',99)>.5:return True
    radius=math.hypot(cfg['footprint_length'],cfg['footprint_width'])/2+.05
    a=pose['yaw']
    vx,vy,_=cmd
    for dt in (0.,.15,.35,.75,1.):
        x=pose['x']+(vx*math.cos(a)-vy*math.sin(a))*dt
        y=pose['y']+(vx*math.sin(a)+vy*math.cos(a))*dt
        if zone_collision(x,y,radius,cells,size):return True
    return False
