"""Director's Cut — automatic highlight reels from iRacing replays.

Open a replay in iRacing, press Scan, review the detected highlights,
press Record — come back to highlights.mp4. Local only: sim SDK + OBS or
the sim's own recorder + bundled ffmpeg. No web APIs, no accounts.
"""
import os
import socket
import sys
import threading
import webbrowser

from flask import Flask, jsonify, render_template, request

from core.sdk import Sim
from core import scanner, events, director, cutter
from core.capture import ObsCapture, SimCapture

PORT = 4795
OUT_DIR = os.path.join(os.path.expanduser('~'), 'Videos', 'DirectorsCut')


def resource_path(rel):
    base = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, rel)


app = Flask(__name__, template_folder=resource_path('templates'),
            static_folder=resource_path('static'))

sim = Sim()
JOB = {'phase': 'idle', 'progress': 0.0, 'message': '', 'error': None,
       'highlights': [], 'clips': [], 'reel': None, 'stop': False, 'log': []}
TIMELINE = []
LOCK = threading.Lock()


def set_job(**kw):
    with LOCK:
        JOB.update(kw)


@app.get('/')
def index():
    return render_template('index.html')


@app.get('/api/status')
def status():
    connected = sim.connect()
    drivers = sim.drivers() if connected else []
    with LOCK:
        job = dict(JOB)
    return jsonify({'connected': connected, 'drivers': drivers,
                    'out_dir': OUT_DIR, 'job': job})


@app.post('/api/scan')
def scan():
    if JOB['phase'] in ('scanning', 'recording', 'cutting'):
        return jsonify({'error': 'A job is already running.'}), 409
    if not sim.connect():
        return jsonify({'error': 'iRacing is not running. Open your replay in the sim first.'}), 400
    speed = int(request.json.get('speed', 16))

    def run():
        global TIMELINE
        set_job(phase='scanning', progress=0.0, message='Scanning replay…',
                error=None, highlights=[], clips=[], reel=None, stop=False)
        try:
            TIMELINE = scanner.scan(sim, speed=speed,
                                    progress=lambda p: set_job(progress=p),
                                    stop_flag=lambda: JOB['stop'])
            hl = events.detect(TIMELINE)
            set_job(phase='scanned', progress=1.0, highlights=hl,
                    message=f'{len(hl)} highlights found across {len(TIMELINE)} samples.')
        except Exception as e:
            set_job(phase='idle', error=f'Scan failed: {e}')

    threading.Thread(target=run, daemon=True).start()
    return jsonify({'ok': True})


@app.post('/api/detect')
def redetect():
    if not TIMELINE:
        return jsonify({'error': 'Scan a replay first.'}), 400
    focus = request.json.get('focus')
    focus = int(focus) if focus not in (None, '', 'all') else None
    hl = events.detect(TIMELINE, focus_caridx=focus)
    set_job(highlights=hl, message=f'{len(hl)} highlights for this focus.')
    return jsonify({'highlights': hl})


@app.post('/api/record')
def record():
    if JOB['phase'] in ('scanning', 'recording', 'cutting'):
        return jsonify({'error': 'A job is already running.'}), 409
    if not TIMELINE:
        return jsonify({'error': 'Scan a replay first.'}), 400
    body = request.json
    picked = [JOB['highlights'][i] for i in body.get('selected', [])
              if 0 <= i < len(JOB['highlights'])]
    if not picked:
        return jsonify({'error': 'Select at least one highlight.'}), 400

    if body.get('capture') == 'obs':
        cap = ObsCapture(password=body.get('obs_password', ''))
    else:
        cap = SimCapture(sim)
    ok, reason = cap.available()
    if not ok:
        return jsonify({'error': reason}), 400

    def log_progress(i, n, msg):
        with LOCK:
            JOB['progress'] = i / max(n, 1)
            JOB['message'] = msg
            JOB['log'].append(msg)
            JOB['log'] = JOB['log'][-30:]

    def run():
        set_job(phase='recording', progress=0.0, message='Recording highlights…',
                error=None, clips=[], reel=None, stop=False, log=[])
        try:
            drivers = sim.drivers()
            clips = director.record_highlights(
                sim, TIMELINE, picked, cap, drivers,
                progress=log_progress,
                stop_flag=lambda: JOB['stop'])
            set_job(phase='cutting', message='Building the reel…', clips=clips)
            reel, err = cutter.build_reel(
                clips, OUT_DIR,
                progress=lambda i, n, msg: set_job(progress=i / max(n, 1), message=msg))
            if err:
                set_job(phase='scanned', error=err)
            else:
                set_job(phase='done', reel=reel, message=f'Reel ready: {reel}')
        except Exception as e:
            set_job(phase='scanned', error=f'Recording failed: {e}')

    threading.Thread(target=run, daemon=True).start()
    return jsonify({'ok': True})


@app.post('/api/capture-test')
def capture_test():
    """Record ~4 seconds right now and report exactly what happened."""
    body = request.json
    if body.get('capture') == 'obs':
        cap = ObsCapture(password=body.get('obs_password', ''))
    else:
        cap = SimCapture(sim)
    ok, reason = cap.available()
    if not ok:
        return jsonify({'ok': False, 'detail': reason})
    import time as _t
    try:
        cap.prepare()
        cap.start()
        _t.sleep(4)
        path = cap.stop()
        cap.cleanup()
    except Exception as e:
        try:
            cap.cleanup()
        except Exception:
            pass
        return jsonify({'ok': False, 'detail': f'Capture failed: {e}'})
    if path and os.path.exists(path):
        return jsonify({'ok': True,
                        'detail': f'Recorded {os.path.getsize(path) // 1024} KB to {path} — capture works.'})
    return jsonify({'ok': False,
                    'detail': 'Recording ran but no video file appeared. For the iRacing recorder, '
                              'confirm videoCaptureEnable=1 in app.ini and that the sim is running.'})


@app.post('/api/stop')
def stop():
    set_job(stop=True, message='Stopping…')
    return jsonify({'ok': True})


@app.post('/api/open-folder')
def open_folder():
    os.makedirs(OUT_DIR, exist_ok=True)
    os.startfile(OUT_DIR)
    return jsonify({'ok': True})


def already_running():
    s = socket.socket()
    s.settimeout(0.5)
    try:
        s.connect(('127.0.0.1', PORT))
        return True
    except OSError:
        return False
    finally:
        s.close()


def open_browser():
    webbrowser.open(f'http://localhost:{PORT}')


if __name__ == '__main__':
    if already_running():
        open_browser()
        sys.exit(0)
    threading.Timer(1.0, open_browser).start()
    app.run(host='127.0.0.1', port=PORT, debug=False)
