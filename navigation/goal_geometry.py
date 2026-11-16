"""Validate the robot's entire arrival footprint, including its chosen heading."""
import math


def arrival_error(grid,x,y,heading,cfg,obstacles=()):
    if grid is None:return 'Die Karte wird noch geladen'
    if not all(math.isfinite(v) for v in (x,y,heading)):return 'Ungültige Zielposition'
    hx=cfg['footprint_length']/2+cfg.get('obstacle_margin',.04)+cfg.get('goal_position_tolerance',0.)
    hy=cfg['footprint_width']/2+cfg.get('obstacle_margin',.04)+cfg.get('goal_position_tolerance',0.)
    c,s=math.cos(heading),math.sin(heading)
    def inside(px,py,pad=0.):
        dx,dy=px-x,py-y
        return abs(dx*c+dy*s)<=hx+pad and abs(-dx*s+dy*c)<=hy+pad
    for px,py in obstacles:
        if inside(px,py):return 'In dieser Blickrichtung ist das Ziel zu nah an einem aktuellen Hindernis'
    resolution=grid['resolution'];ox,oy,a=grid['origin'];ca,sa=math.cos(a),math.sin(a)
    corners=[(x+dx*c-dy*s,y+dx*s+dy*c) for dx in (-hx,hx) for dy in (-hy,hy)]
    cells=[(((px-ox)*ca+(py-oy)*sa)/resolution,(-(px-ox)*sa+(py-oy)*ca)/resolution) for px,py in corners]
    left=math.floor(min(p[0] for p in cells));right=math.floor(max(p[0] for p in cells))
    bottom=math.floor(min(p[1] for p in cells));top=math.floor(max(p[1] for p in cells))
    if left<0 or bottom<0 or right>=grid['width'] or top>=grid['height']:return 'Der Roboter würde über den Kartenrand ragen'
    for row in range(bottom,top+1):
        for col in range(left,right+1):
            px=ox+(col+.5)*resolution*ca-(row+.5)*resolution*sa
            py=oy+(col+.5)*resolution*sa+(row+.5)*resolution*ca
            if not inside(px,py,resolution*math.sqrt(2)/2):continue
            cell=grid['cells'][row*grid['width']+col]
            if cell<0:return 'Der Roboter würde in eine noch unbekannte Fläche ragen'
            if cell>=25:return 'Position oder Blickrichtung liegt zu nah an einer Wand – Ziel etwas versetzen'
    return ''
