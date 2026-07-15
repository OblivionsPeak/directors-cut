"""Director pass: seek to each highlight, aim a camera, record it."""
import time

# camera preference by highlight type — matched against the replay's own
# camera group names (every car/track ships different sets)
CAM_PREFS = {
    'overtake': ['TV1', 'TV', 'Chase'],
    'incident': ['TV2', 'TV', 'Chopper', 'Chase'],
    'battle': ['Chase', 'TV1', 'TV'],
    'finish': ['TV1', 'TV', 'Blimp'],
}


def sim_time_to_frame(timeline, t):
    """Interpolate replay frame from sampled (t, frame) pairs."""
    prev = timeline[0]
    for s in timeline:
        if s['t'] >= t:
            if s['t'] == prev['t']:
                return s['frame']
            w = (t - prev['t']) / (s['t'] - prev['t'])
            return int(prev['frame'] + (s['frame'] - prev['frame']) * w)
        prev = s
    return timeline[-1]['frame']


def record_highlights(sim, timeline, highlights, capture, drivers,
                      progress=None, stop_flag=None, hide_ui=True, game_audio_only=True):
    """Play each highlight in real time while the capture backend records.
    Returns list of {highlight, file} clips. A highlight may carry
    'cam_group' (int) to override the automatic type-based camera pick."""
    num_by_idx = {d['idx']: d['number'] for d in drivers}
    replay_end_t = timeline[-1]['t']
    clips = []
    capture.prepare(game_audio_only=game_audio_only)
    for note_attr in ('mic_warning', 'audio_note'):
        note = getattr(capture, note_attr, None)
        if note and progress:
            progress(0, len(highlights), note)
    # always pin the camera (disables the sim's auto-director so it can't
    # wander off the target car mid-clip); optionally hide the UI too
    prior_cam = sim.pin_camera(hide_ui)
    for i, h in enumerate(highlights):
        if stop_flag is not None and stop_flag():
            break
        if progress:
            progress(i, len(highlights), f"Recording: {h['label']}")
        group = h.get('cam_group') or sim.pick_camera_group(CAM_PREFS.get(h['type'], ['TV', 'Chase']))
        frame = sim_time_to_frame(timeline, max(0, h['t_start']))

        sim.set_speed(0)
        sim.seek_frame(frame)
        sim.wait_until_frame(frame)                      # seek is asynchronous
        time.sleep(0.5)
        aimed = sim.watch(num_by_idx.get(h['caridx'], '0'), group,
                          expect_caridx=h['caridx'])
        if not aimed and progress:
            progress(i, len(highlights),
                     f"Camera may not be on the right car for: {h['label']}")
        time.sleep(0.5)

        # never wait for a target past the end of the replay — playback
        # stops there and the wait would only time out
        target = min(h['t_end'], replay_end_t - 0.5)
        capture.start()
        sim.set_speed(1)
        ok = sim.wait_until_sim_time(target, timeout=(target - h['t_start']) + 60)
        sim.set_speed(0)
        path = capture.stop()
        # keep the clip whenever a file exists — a wait timeout just means
        # the clip may run long, which the cutter tolerates
        if path:
            clips.append({'highlight': h, 'file': path, 'timed_out': not ok})
        elif progress:
            progress(i + 1, len(highlights), f"No video file for: {h['label']} — check the capture backend")
        time.sleep(1.0)
    sim.restore_camera(prior_cam)
    capture.cleanup()
    if progress:
        progress(len(highlights), len(highlights), 'Recording complete')
    return clips
