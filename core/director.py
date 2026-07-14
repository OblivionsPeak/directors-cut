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
                      progress=None, stop_flag=None):
    """Play each highlight in real time while the capture backend records.
    Returns list of {highlight, file} clips."""
    num_by_idx = {d['idx']: d['number'] for d in drivers}
    clips = []
    for i, h in enumerate(highlights):
        if stop_flag is not None and stop_flag():
            break
        if progress:
            progress(i, len(highlights), f"Recording: {h['label']}")
        group = sim.pick_camera_group(CAM_PREFS.get(h['type'], ['TV', 'Chase']))
        frame = sim_time_to_frame(timeline, max(0, h['t_start']))

        sim.set_speed(0)
        sim.seek_frame(frame)
        time.sleep(1.5)                                  # let the sim load the frame
        sim.watch(num_by_idx.get(h['caridx'], '0'), group)
        time.sleep(0.8)

        capture.start()
        sim.set_speed(1)
        ok = sim.wait_until_sim_time(h['t_end'], timeout=(h['t_end'] - h['t_start']) + 60)
        sim.set_speed(0)
        path = capture.stop()
        if path and ok:
            clips.append({'highlight': h, 'file': path})
        time.sleep(1.0)
    if progress:
        progress(len(highlights), len(highlights), 'Recording complete')
    return clips
