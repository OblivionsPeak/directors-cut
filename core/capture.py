"""Video capture backends: OBS (websocket) and iRacing's built-in recorder.

Both expose: available() -> (ok, reason), start(), stop() -> newest file path.
"""
import glob
import os
import time


class ObsCapture:
    """Remote-controls OBS Studio via obs-websocket 5.x (Tools > WebSocket
    Server Settings in OBS — enable, default port 4455)."""

    def __init__(self, host='localhost', port=4455, password=''):
        self.host, self.port, self.password = host, port, password
        self.client = None

    def available(self):
        try:
            import obsws_python as obs
            self.client = obs.ReqClient(host=self.host, port=self.port,
                                        password=self.password or None, timeout=3)
            ver = self.client.get_version()
            return True, f'OBS {ver.obs_version} connected'
        except Exception as e:
            return False, ('Could not reach OBS. Open OBS, then Tools > WebSocket Server '
                           f'Settings > Enable. ({e})')

    def start(self):
        self.client.start_record()

    def stop(self):
        # returns the recorded file path (OBS 28+)
        try:
            resp = self.client.stop_record()
            path = getattr(resp, 'output_path', None)
        except Exception:
            path = None
        if path:
            return path
        # fallback: newest file in the OBS record directory
        try:
            rd = self.client.get_record_directory().record_directory
            files = sorted(glob.glob(os.path.join(rd, '*.*')), key=os.path.getmtime)
            return files[-1] if files else None
        except Exception:
            return None


class SimCapture:
    """iRacing's built-in video capture via SDK broadcast. Requires video
    capture enabled in iRacing (Options > Misc > video capture, or app.ini
    [Misc] videoCaptureEnable=1). Files land in Documents\\iRacing\\videos."""

    def __init__(self, sim):
        self.sim = sim
        self.video_dir = os.path.join(os.path.expanduser('~'), 'Documents', 'iRacing', 'videos')
        self._before = set()

    def available(self):
        if not self.sim.connected:
            return False, 'iRacing is not running.'
        if not os.path.isdir(self.video_dir):
            return False, (f'{self.video_dir} does not exist — enable video capture in '
                           'iRacing (Options > Misc) and record once manually to create it.')
        return True, 'iRacing built-in capture ready'

    def start(self):
        self._before = set(glob.glob(os.path.join(self.video_dir, '*.*')))
        self.sim.sim_capture_start()

    def stop(self):
        self.sim.sim_capture_stop()
        # the file appears asynchronously after capture ends
        for _ in range(40):
            time.sleep(0.5)
            new = set(glob.glob(os.path.join(self.video_dir, '*.*'))) - self._before
            done = [f for f in new if not f.endswith('.tmp')]
            if done:
                return max(done, key=os.path.getmtime)
        return None
