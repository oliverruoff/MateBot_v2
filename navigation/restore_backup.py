"""Restore a downloaded backup while the navigation container is stopped."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile
import time
import uuid
from session import atomic_json,validate

FILES={'house.posegraph','house.data','house.pgm','house.yaml','map.json','session.json','pose.json','manifest.json'}


def restore_archive(source,destination):
    destination=Path(destination).resolve()
    destination.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.restore-',dir=destination) as staging:
        stage=Path(staging)
        with tarfile.open(source,mode='r:gz') as archive:
            members=archive.getmembers()
            allowed={'session.json'}|{'snapshot/'+name for name in FILES}
            seen=set();total=0
            for member in members:
                if member.name not in allowed or member.name in seen or not member.isfile() or member.issym() or member.islnk():
                    raise ValueError('Unzulässiger Inhalt im Sicherungsarchiv')
                seen.add(member.name);total+=member.size
                if member.size>256*1024**2 or total>512*1024**2:
                    raise ValueError('Sicherungsarchiv zu groß')
            if not {'session.json','snapshot/house.posegraph','snapshot/house.data',
                    'snapshot/house.pgm','snapshot/house.yaml','snapshot/session.json'}<=seen:
                raise ValueError('Sicherungsarchiv unvollständig')
            for member in members:
                target=stage/member.name;target.parent.mkdir(parents=True,exist_ok=True)
                with archive.extractfile(member) as incoming,target.open('wb') as outgoing:
                    shutil.copyfileobj(incoming,outgoing,1024*1024)
                    outgoing.flush();os.fsync(outgoing.fileno())
        session=validate(json.loads((stage/'session.json').read_text(encoding='utf-8')))
        snapshot=stage/'snapshot'
        old_session=validate(json.loads((snapshot/'session.json').read_text(encoding='utf-8')))
        if session['map_id']!=old_session['map_id']:raise ValueError('Karte und Sperrzonen passen nicht zusammen')
        manifest_path=snapshot/'manifest.json'
        if manifest_path.exists():
            manifest=json.loads(manifest_path.read_text(encoding='utf-8'))
            for name,digest in manifest['sha256'].items():
                if name not in FILES or hashlib.sha256((snapshot/name).read_bytes()).hexdigest()!=digest:
                    raise ValueError('Prüfsumme der Sicherung stimmt nicht')
        else:manifest=dict(schema=1,map_id=session['map_id'],saved_at=time.time(),sha256={})
        session['fresh']=False
        atomic_json(snapshot/'session.json',session)
        manifest['sha256']['session.json']=hashlib.sha256((snapshot/'session.json').read_bytes()).hexdigest()
        atomic_json(manifest_path,manifest)
        for suffix in ('posegraph','data'):
            alias=destination/('current.'+suffix)
            if alias.exists() and not alias.is_symlink():raise ValueError('Vorhandene reguläre Kartendatei wird nicht überschrieben')
        old=destination/'session.json'
        if old.exists():atomic_json(destination/'archives'/('before-restore-'+uuid.uuid4().hex+'.json'),
                                   dict(session=json.loads(old.read_text(encoding='utf-8')),
                                        snapshot=(destination/'current').resolve().name))
        name='map-restored-'+time.strftime('%Y%m%d-%H%M%S')+'-'+uuid.uuid4().hex[:8]
        target=destination/name
        os.replace(snapshot,target)
        pending=destination/'current.restore-next';pending.unlink(missing_ok=True);pending.symlink_to(name,target_is_directory=True)
        os.replace(pending,destination/'current')
        for suffix in ('posegraph','data'):
            alias=destination/('current.'+suffix)
            if not alias.is_symlink():alias.symlink_to('current/house.'+suffix)
        atomic_json(destination/'session.json',session)
        pose=None
        if (target/'pose.json').exists():pose=json.loads((target/'pose.json').read_text(encoding='utf-8'))
        atomic_json(destination/'runtime.json',dict(map_id=session['map_id'],pose=pose,saved_at='Sicherung wiederhergestellt'))
        atomic_json(destination/'latest.json',dict(map_id=session['map_id'],snapshot=name))
        return name


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive',type=Path)
    parser.add_argument('--directory',type=Path,default=Path(__file__).parent/'data')
    parser.add_argument('--confirm',action='store_true')
    args=parser.parse_args()
    if not args.confirm:parser.error('Container stoppen und Wiederherstellung mit --confirm wählen')
    status=subprocess.run(['sudo','-n','docker','inspect','-f','{{.State.Running}}','matebot-navigation'],capture_output=True,text=True)
    if status.returncode==0 and status.stdout.strip()=='true':raise SystemExit('Navigation zuerst stoppen')
    print('Restored:',restore_archive(args.archive,args.directory))
