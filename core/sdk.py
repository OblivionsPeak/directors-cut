"""Thin wrapper over pyirsdk for replay control, cameras, and video capture.

Everything here talks to the LOCAL iRacing SDK (shared memory + window
broadcast messages). No web API, no login — unaffected by /data API status.
"""
import time

import irsdk


class Sim:
    def __init__(self):
        self.ir = irsdk.IRSDK()

    def connect(self):
        if not self.ir.is_initialized:
            self.ir.startup()
        return bool(self.ir.is_initialized and self.ir.is_connected)

    @property
    def connected(self):
        return bool(self.ir.is_initialized and self.ir.is_connected)

    def freeze(self):
        self.ir.freeze_var_buffer_latest()

    def get(self, name):
        try:
            return self.ir[name]
        except Exception:
            return None

    # ── session info ─────────────────────────────────────────────────────────
    def drivers(self):
        di = (self.ir['DriverInfo'] or {})
        out = []
        for d in di.get('Drivers', []):
            if d.get('IsSpectator') or d.get('CarIsPaceCar'):
                continue
            out.append({'idx': d['CarIdx'], 'name': d.get('UserName', f"Car {d.get('CarNumber')}"),
                        'number': str(d.get('CarNumber', '')), 'car': d.get('CarScreenNameShort', '')})
        return out

    def camera_groups(self):
        ci = (self.ir['CameraInfo'] or {})
        return [{'num': g['GroupNum'], 'name': g['GroupName']} for g in ci.get('Groups', [])]

    def pick_camera_group(self, preferences):
        """First camera group whose name contains any preferred token (in order)."""
        groups = self.camera_groups()
        for token in preferences:
            for g in groups:
                if token.lower() in g['name'].lower():
                    return g['num']
        return groups[0]['num'] if groups else 1

    # ── replay control ───────────────────────────────────────────────────────
    def set_speed(self, speed, slow_motion=False):
        self.ir.replay_set_play_speed(int(speed), int(slow_motion))

    def seek_frame(self, frame):
        self.ir.replay_set_play_position(irsdk.RpyPosMode.begin, int(frame))

    def frame_now(self):
        return self.get('ReplayFrameNum')

    def frame_end(self):
        return self.get('ReplayFrameNumEnd')

    def session_time(self):
        return self.get('ReplaySessionTime')

    # ── cameras ──────────────────────────────────────────────────────────────
    def watch(self, car_number, group):
        # cam_switch_num wants the car NUMBER string; falls back to position 1
        try:
            self.ir.cam_switch_num(str(car_number), int(group), 0)
        except Exception:
            self.ir.cam_switch_pos(1, int(group), 0)

    # ── video capture (built-in sim recorder) ────────────────────────────────
    def sim_capture_start(self):
        self.ir.video_capture(irsdk.VideoCaptureMode.start_video_capture)

    def sim_capture_stop(self):
        self.ir.video_capture(irsdk.VideoCaptureMode.end_video_capture)

    def wait_until_sim_time(self, target, timeout=600, poll=0.2):
        """Block until replay playback passes `target` sim seconds."""
        t0 = time.time()
        while time.time() - t0 < timeout:
            now = self.session_time()
            if now is not None and now >= target:
                return True
            time.sleep(poll)
        return False
