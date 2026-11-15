"""HTTP API kept separate from ROS so authorization and persistence can be tested."""
import io
import json
import math
from pathlib import Path
import tarfile
from flask import Flask, jsonify, request, send_file, send_from_directory, Response
from camera_client import CameraClient


def numbers(data,fields):
    values=[float(data[f]) for f in fields]
    if not all(math.isfinite(v) and abs(v)<500 for v in values):
        raise ValueError('Ungültige Koordinaten oder Geschwindigkeiten')
    return values


def create_app(robot,web_root=None,camera=None):
    root=Path(web_root or Path(__file__).parent/'web')
    app=Flask(__name__,static_folder=str(root),static_url_path='/assets')
    app.config['MAX_CONTENT_LENGTH']=256*1024
    camera=camera or CameraClient()

    @app.after_request
    def headers(response):
        response.headers['X-Content-Type-Options']='nosniff'
        response.headers['Referrer-Policy']='same-origin'
        response.headers['Cache-Control']='no-store'
        return response

    @app.errorhandler(413)
    def too_large(_):return jsonify(error='Anfrage zu groß'),413

    @app.get('/')
    def index():return send_from_directory(root,'index.html')

    @app.get('/drive')
    def drive():return send_from_directory(root,'index.html')

    @app.get('/api/camera/frame.jpg')
    def camera_frame():
        try:
            image,sequence,age=camera.frame()
            return Response(image,mimetype='image/jpeg',headers={
                'X-Frame-Sequence':str(sequence),'X-Frame-Age-Ms':str(round(age))})
        except Exception:
            return jsonify(error='Kamera nicht verfügbar – Verbindung wird erneut versucht'),503

    @app.get('/api/camera/status')
    def camera_status():
        try:return jsonify(camera.status())
        except Exception:return jsonify(active=False,ready=False,error='Kameradienst nicht erreichbar'),503

    @app.get('/api/state')
    def state():return jsonify(robot.state())

    @app.get('/api/map')
    def map_data():return jsonify(robot.map_json())

    @app.get('/api/saved-map')
    def saved_map():return jsonify(robot.saved_map_json())

    @app.get('/api/backup')
    def backup():
        folder=robot.active_snapshot()
        if folder is None:return jsonify(error='Noch keine gespeicherte Karte vorhanden'),409
        buffer=io.BytesIO()
        with tarfile.open(fileobj=buffer,mode='w:gz') as archive:
            for name in ('house.posegraph','house.data','house.pgm','house.yaml','map.json',
                         'session.json','pose.json','manifest.json'):
                path=folder/name
                if path.is_file():archive.add(path,arcname='snapshot/'+name,recursive=False)
            annotations=json.dumps(robot.session.get(),ensure_ascii=False).encode('utf-8')
            info=tarfile.TarInfo('session.json')
            info.size=len(annotations)
            archive.addfile(info,io.BytesIO(annotations))
        buffer.seek(0)
        return send_file(buffer,mimetype='application/gzip',as_attachment=True,
                         download_name='matebot-'+robot.annotations['map_id'][:8]+'.tar.gz')

    @app.post('/api/<action>')
    def command(action):
        if request.headers.get('X-Matebot-Control')!='1':
            return jsonify(error='Steuerungsheader fehlt'),403
        try:
            data=request.get_json(silent=True) or {}
            if not isinstance(data,dict):raise ValueError('Ungültige Anfrage')
            token=request.headers.get('X-Matebot-Lease')
            if action=='stop':
                robot.stop()
                return jsonify(stopped=True)
            if action=='release':return jsonify(robot.arm(data.get('mode'),data.get('on_site')))
            if action=='heartbeat':
                robot.heartbeat(token)
                return jsonify(ok=True)
            if action=='manual':
                robot.manual(token,*numbers(data,['vx','vy','wz']),sequence=data.get('sequence'))
                return jsonify(ok=True)
            if action=='goal':return jsonify(robot.goal(*numbers(data,['x','y']),token=token))
            if action=='restore':return jsonify(robot.restore(*numbers(data,['x','y','yaw'])))
            if action=='save':return jsonify(robot.save_map())
            if action=='zones':return jsonify(robot.edit_zones(data.get('paint',[]),data.get('erase',[]),
                                                data['grid_size'],data['revision']))
            if action=='settings':return jsonify(robot.settings(mode=data.get('mode'),title=data.get('title')))
            if action=='calibration':
                if data.get('on_site') is not True:raise ValueError('Fahrprüfungen müssen vor Ort erfolgen')
                return jsonify(robot.settings(calibration=data['checks']))
            if action=='favorite':
                name=data.get('name')
                if not isinstance(name,str) or not name.strip():raise ValueError('Bitte einen Zielnamen eingeben')
                x,y=numbers(data,['x','y'])
                return jsonify(robot.favorite(name.strip(),x,y,delete=data.get('delete') is True))
            if action=='new-map':
                if data.get('confirm') is not True:raise ValueError('Neue Karte muss ausdrücklich gewählt werden')
                robot.new_map()
                return jsonify(ok=True)
            return jsonify(error='Unbekannte Aktion'),404
        except (ValueError,KeyError,TypeError,RuntimeError,OSError) as exc:
            return jsonify(error=str(exc)),409

    return app
