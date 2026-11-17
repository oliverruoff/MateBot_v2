"""Validated, independently saved motor experiments; no GPIO on import."""
import math
from session import atomic_json
from core import twist

BOUNDS=dict(frequency=(10,8000),acceleration=(0,100000),duty=(5,95),
            start_frequency=(10,8000),warmup=(0,2),enable_delay=(0,500))
DIRECTIONS=dict(forward=[1,1,1,1],backward=[-1,-1,-1,-1],
                left=[-1,1,1,-1],right=[1,-1,-1,1],
                turn_left=[-1,1,-1,1],turn_right=[1,-1,1,-1])
WHEELS=('FL','FR','BL','BR')


def validate_profile(value):
    if not isinstance(value,dict) or set(value)!=set(BOUNDS):
        raise ValueError('Motorprofil ist unvollständig')
    result={}
    for key,(low,high) in BOUNDS.items():
        v=value[key]
        if isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or not low<=v<=high:
            raise ValueError(f'{key}: erlaubt sind {low} bis {high}')
        result[key]=float(v)
    if result['start_frequency']>result['frequency']:
        raise ValueError('Anlauftakt darf nicht höher als Zieltakt sein')
    return result


def driver_config(cfg,profile):
    p=validate_profile(profile)
    return dict(cfg,motor_max_frequency=p['frequency'],motor_start_frequency=p['start_frequency'],
                motor_start_seconds=p['warmup'],motor_duty_percent=p['duty'],
                motor_acceleration_hz_s=p['acceleration'],motor_enable_delay_ms=p['enable_delay'])


def test_rates(direction,profile,wheel='all'):
    p=validate_profile(profile)
    if direction not in DIRECTIONS:raise ValueError('Unbekannte Testrichtung')
    if wheel!='all' and wheel not in WHEELS:raise ValueError('Unbekanntes Testrad')
    if wheel!='all' and direction not in ('forward','backward'):
        raise ValueError('Einzelradprüfung: Vorwärts oder Rückwärts wählen')
    return [s*p['frequency'] if wheel=='all' or wheel==WHEELS[i] else 0.
            for i,s in enumerate(DIRECTIONS[direction])]


def test_command(direction,profile,cfg,duration,wheel='all'):
    hz=test_rates(direction,profile,wheel)
    if isinstance(duration,bool) or not isinstance(duration,(int,float)) or not math.isfinite(duration) or not .1<=duration<=3:
        raise ValueError('Testdauer: 0,1 bis 3 Sekunden')
    steps_m=cfg['steps_per_revolution']*cfg['microsteps']/(math.pi*cfg['wheel_diameter'])
    return list(twist([h/steps_m for h in hz],cfg['wheelbase'],cfg['track_width']))


class MotorProfiles:
    def __init__(self,path,cfg):
        self.path=path
        self.default=dict(frequency=cfg.get('motor_max_frequency',8000),acceleration=cfg.get('motor_acceleration_hz_s',0),
                          duty=cfg.get('motor_duty_percent',50),start_frequency=min(40,cfg.get('motor_max_frequency',8000)),
                          warmup=cfg.get('motor_start_seconds',0),enable_delay=cfg.get('motor_enable_delay_ms',10))
        self.draft=validate_profile(self.default);self.active=None
        if path.exists():
            import json
            data=json.loads(path.read_text())
            self.draft=validate_profile(data['draft'])
            if data.get('active') is not None:self.active=validate_profile(data['active'])

    def save(self,profile,apply=False):
        p=validate_profile(profile)
        active=p if apply else self.active
        atomic_json(self.path,dict(schema=1,draft=p,active=active))
        self.draft=p;self.active=active

    def state(self):return dict(draft=self.draft,active=self.active,default=self.default)
