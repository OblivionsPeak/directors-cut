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

    MIC_KINDS = ('wasapi_input_capture', 'dshow_input', 'coreaudio_input_capture',
                 'pulse_input_capture')

    def prepare(self, game_audio_only=False):
        """Session setup, restored by cleanup():
        - drop OBS output to 1080p (big/triple canvases exceed NVENC H264's max
          frame size — StartRecord is accepted but the encoder never starts)
        - optionally mute microphone inputs so clips carry no voice audio."""
        try:
            v = self.client.get_video_settings()
            self._saved_video = v
            if v.output_width > 1920 or v.output_height > 1080:
                self.client.set_video_settings(
                    numerator=v.fps_numerator, denominator=v.fps_denominator,
                    base_width=v.base_width, base_height=v.base_height,
                    out_width=1920, out_height=1080)
        except Exception:
            self._saved_video = None
        self._muted = []
        if game_audio_only:
            try:
                for inp in self.client.get_input_list().inputs:
                    if inp.get('inputKind') in self.MIC_KINDS:
                        name = inp['inputName']
                        was = self.client.get_input_mute(name).input_muted
                        if not was:
                            self.client.set_input_mute(name, True)
                            self._muted.append(name)
            except Exception:
                pass

    def cleanup(self):
        v = getattr(self, '_saved_video', None)
        if v is not None:
            try:
                self.client.set_video_settings(
                    numerator=v.fps_numerator, denominator=v.fps_denominator,
                    base_width=v.base_width, base_height=v.base_height,
                    out_width=v.output_width, out_height=v.output_height)
            except Exception:
                pass
        for name in getattr(self, '_muted', []):
            try:
                self.client.set_input_mute(name, False)
            except Exception:
                pass

    def start(self):
        self._t_start = time.time()
        self.client.start_record()
        # verify the output actually went active — StartRecord can accept the
        # request yet fail to start (no encoder, disk error, bad settings)
        for _ in range(12):
            time.sleep(0.25)
            try:
                if self.client.get_record_status().output_active:
                    return
            except Exception:
                pass
        raise RuntimeError(
            'OBS accepted the record request but recording never started. Most common '
            'cause on big/triple-monitor canvases: the H.264 encoder rejects frames wider '
            'than 4096px. Fix in OBS: Settings > Video > Output (Scaled) Resolution = '
            '1920x1080, or Settings > Output > Recording > Video Encoder = NVENC HEVC/AV1. '
            'Then use the Test capture button to confirm.')

    VIDEO_EXTS = ('.mp4', '.mkv', '.mov', '.flv', '.ts', '.m4v')

    def stop(self):
        path = None
        try:
            resp = self.client.stop_record()
            path = getattr(resp, 'output_path', None)
        except Exception:
            path = None
        if path and os.path.exists(path):
            return path
        # fallback: newest VIDEO file created after start() in the record dir
        try:
            rd = self.client.get_record_directory().record_directory
            vids = [f for f in glob.glob(os.path.join(rd, '*.*'))
                    if f.lower().endswith(self.VIDEO_EXTS)
                    and os.path.getmtime(f) >= getattr(self, '_t_start', 0)]
            return max(vids, key=os.path.getmtime) if vids else None
        except Exception:
            return None


class SimCapture:
    """iRacing's built-in video capture via SDK broadcast. Requires video
    capture enabled in iRacing (Options > Misc > video capture, or app.ini
    [Misc] videoCaptureEnable=1). Files land in Documents\\iRacing\\videos."""

    def __init__(self, sim):
        self.sim = sim
        docs = os.path.join(os.path.expanduser('~'), 'Documents', 'iRacing')
        self.video_dir = os.path.join(docs, 'videos')
        self.app_ini = os.path.join(docs, 'app.ini')
        self._before = set()

    def _capture_enabled(self):
        """iRacing silently ignores the record broadcast unless
        [Misc] videoCaptureEnable=1 is set in app.ini."""
        try:
            with open(self.app_ini, encoding='utf-8', errors='replace') as f:
                for line in f:
                    key = line.split(';')[0].strip()
                    if key.lower().startswith('videocaptureenable'):
                        return key.split('=')[1].strip() == '1'
        except OSError:
            return None
        return False    # key absent = disabled

    def available(self):
        if not self.sim.connected:
            return False, 'iRacing is not running.'
        enabled = self._capture_enabled()
        if enabled is False:
            return False, ('iRacing video capture is DISABLED — the sim silently ignores '
                           'record commands. Fix: close iRacing, open Documents\\iRacing\\app.ini, '
                           'set videoCaptureEnable=1 under [Misc] (add the line if missing), '
                           'restart the sim. Or switch to the OBS option above.')
        if not os.path.isdir(self.video_dir):
            os.makedirs(self.video_dir, exist_ok=True)
        return True, 'iRacing built-in capture ready'

    def prepare(self, game_audio_only=False):
        # the sim recorder mixes mic audio only when videoCaptureMic=1; warn if
        # the user asked for game-only audio but the sim will record the mic
        self.mic_warning = None
        if game_audio_only:
            try:
                with open(self.app_ini, encoding='utf-8', errors='replace') as f:
                    for line in f:
                        key = line.split(';')[0].strip()
                        if key.lower().startswith('videocapturemic') and key.split('=')[1].strip() == '1':
                            self.mic_warning = ('iRacing has videoCaptureMic=1 — clips will include '
                                                'your microphone. Set it to 0 in app.ini (sim closed).')
            except OSError:
                pass

    def cleanup(self):
        pass

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
