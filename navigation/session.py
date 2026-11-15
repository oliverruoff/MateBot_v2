"""Durable map annotations. Coordinates are meters in the persistent map frame."""
import copy
import json
import math
import os
from pathlib import Path
import threading
import time
import uuid

LEASE_TIMEOUT=2.5

GRID_SIZES=(0.1,0.25,0.5,1.0)
MAX_CELLS=30000


def atomic_json(path, value):
    path=Path(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_name(path.name+'.next')
    with temporary.open('w',encoding='utf-8') as stream:
        json.dump(value,stream,ensure_ascii=False,allow_nan=False,separators=(',',':'))
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary,path)
    try:
        descriptor=os.open(str(path.parent),os.O_RDONLY)
        try: os.fsync(descriptor)
        finally: os.close(descriptor)
    except OSError:
        # Windows does not support directory fsync; file data is still flushed.
        if os.name!='nt': raise


def checked_cells(values):
    if not isinstance(values,list) or len(values)>MAX_CELLS:
        raise ValueError('Zu viele Rasterzellen')
    result=set()
    for value in values:
        if (not isinstance(value,list) or len(value)!=2 or
            any(type(n) is not int or abs(n)>5000 for n in value)):
            raise ValueError('Ungültige Rasterzelle')
        result.add(tuple(value))
    return result


def validate(doc):
    if (doc.get('schema')!=1 or not isinstance(doc.get('map_id'),str) or
        len(doc['map_id'])!=32 or any(c not in '0123456789abcdef' for c in doc['map_id'])):
        raise ValueError('Ungültiges Sitzungsformat')
    if type(doc.get('grid_size')) not in (float,int) or doc.get('grid_size') not in GRID_SIZES:
        raise ValueError('Ungültige Rastergröße')
    checked_cells(doc.get('zones'))
    if doc.get('mode') not in ('mapping','navigation'):
        raise ValueError('Ungültiger Modus')
    if type(doc.get('revision')) is not int or doc['revision']<0:
        raise ValueError('Ungültige Revision')
    if 'fresh' in doc and type(doc['fresh']) is not bool:
        raise ValueError('Ungültiger Kartenzustand')
    if not isinstance(doc.get('calibration'),dict):
        raise ValueError('Kalibrierstand fehlt')
    for value in doc['calibration'].values():
        if type(value) is not bool:
            raise ValueError('Ungültiger Kalibrierstand')
    if not isinstance(doc.get('favorites'),list) or len(doc['favorites'])>100:
        raise ValueError('Ungültige Favoriten')
    for favorite in doc['favorites']:
        if not isinstance(favorite.get('name'),str) or not 1<=len(favorite['name'])<=40:
            raise ValueError('Ungültiger Zielname')
        if any(type(favorite.get(k)) not in (float,int) or not math.isfinite(favorite[k])
               or abs(favorite[k])>500 for k in ('x','y')):
            raise ValueError('Ungültige Zielkoordinaten')
    return doc


class Session:
    def __init__(self,directory):
        self.directory=Path(directory)
        self.path=self.directory/'session.json'
        self.lock=threading.RLock()
        if self.path.exists():
            # Corruption must never silently remove no-go zones.
            self.doc=validate(json.loads(self.path.read_text(encoding='utf-8')))
            if 'fresh' not in self.doc:
                self.doc['fresh']=not (self.directory/'current/house.posegraph').exists()
                atomic_json(self.path,self.doc)
        else:
            self.doc=dict(schema=1,map_id=uuid.uuid4().hex,title='Erdgeschoss',revision=0,fresh=True,
                          grid_size=.25,zones=[],favorites=[],mode='mapping',
                          calibration=dict(translation=False,lateral=False,rotation=False,stopping=False),
                          updated_at=time.time())
            atomic_json(self.path,self.doc)

    def get(self):
        with self.lock:return copy.deepcopy(self.doc)

    def commit(self,doc):
        validate(doc)
        doc['revision']=self.doc['revision']+1
        doc['updated_at']=time.time()
        atomic_json(self.path,doc)
        self.doc=doc
        return self.get()

    def edit_zones(self,paint,erase,grid_size,revision):
        with self.lock:
            if type(revision) is not int or revision!=self.doc['revision']:
                raise ValueError('Karte wurde geändert. Ansicht wird aktualisiert; bitte erneut zeichnen.')
            if type(grid_size) not in (int,float) or grid_size not in GRID_SIZES:
                raise ValueError('Rastergröße muss 10, 25, 50 oder 100 cm sein')
            old=self.doc['grid_size']
            zones=checked_cells(self.doc['zones'])
            if grid_size!=old:
                # Conservatively cover every part of the old forbidden area.
                resampled=set()
                for x,y in zones:
                    for nx in range(math.floor(x*old/grid_size+1e-9),math.ceil((x+1)*old/grid_size-1e-9)):
                        for ny in range(math.floor(y*old/grid_size+1e-9),math.ceil((y+1)*old/grid_size-1e-9)):
                            resampled.add((nx,ny))
                zones=resampled
            zones.update(checked_cells(paint))
            zones.difference_update(checked_cells(erase))
            if len(zones)>MAX_CELLS:
                raise ValueError('Maximal 30.000 Sperrzellen erlaubt')
            doc=self.get()
            doc.update(grid_size=grid_size,zones=[list(c) for c in sorted(zones)])
            return self.commit(doc)

    def settings(self,mode=None,calibration=None,title=None):
        with self.lock:
            doc=self.get()
            if mode is not None:doc['mode']=mode
            if title is not None:
                if not isinstance(title,str) or not 1<=len(title.strip())<=60:
                    raise ValueError('Kartenname muss 1–60 Zeichen haben')
                doc['title']=title.strip()
            if calibration is not None:
                if set(calibration)!=set(doc['calibration']):
                    raise ValueError('Alle vier Fahrprüfungen müssen angegeben sein')
                doc['calibration']=calibration
            return self.commit(doc)

    def favorite(self,name,x,y,delete=False):
        with self.lock:
            doc=self.get()
            doc['favorites']=[f for f in doc['favorites'] if f['name']!=name]
            if not delete:doc['favorites'].append(dict(name=name,x=x,y=y))
            return self.commit(doc)

    def new_map(self):
        with self.lock:
            old=self.get()
            atomic_json(self.directory/'archives'/('session-'+old['map_id']+'.json'),old)
            doc=self.get()
            doc.update(map_id=uuid.uuid4().hex,zones=[],favorites=[],mode='mapping',fresh=True)
            return self.commit(doc)

    def mark_saved(self):
        with self.lock:
            if self.doc.get('fresh',True):
                doc=self.get();doc['fresh']=False
                return self.commit(doc)
            return self.get()


class ControlLease:
    """One browser owns motion; read-only status polling cannot extend a lease."""
    def __init__(self):
        self.token=None
        self.at=0.

    def acquire(self,now):
        if self.token and now-self.at<LEASE_TIMEOUT:
            raise ValueError('Eine andere Steuerung ist noch aktiv. Erst stoppen.')
        self.token=uuid.uuid4().hex
        self.at=now
        return self.token

    def check(self,token,now,refresh=False):
        if not token or token!=self.token or now-self.at>LEASE_TIMEOUT:
            raise ValueError('Steuerung abgelaufen. Bitte erneut freigeben.')
        if refresh:self.at=now

    def clear(self):
        self.token=None
        self.at=0.
