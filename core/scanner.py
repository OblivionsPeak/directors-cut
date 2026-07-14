"""Scan pass: play the replay at high speed and sample all-car state.

Produces a timeline: list of samples {t (sim s), frame, pos[], pct[], lap[],
surf[]} — the pure-data input that events.py detects highlights in.
"""
import time

# irsdk_TrkLoc: -1 not in world, 0 off track, 1 pit stall, 2 approaching pits, 3 on track


def scan(sim, speed=16, sample_hz=8, progress=None, stop_flag=None):
    sim.freeze()
    end_frame = sim.frame_end() or 0
    sim.seek_frame(0)
    time.sleep(1.0)
    sim.set_speed(speed)

    timeline = []
    last_frame = -1
    stall = 0
    while True:
        if stop_flag is not None and stop_flag():
            break
        sim.freeze()
        frame = sim.frame_now()
        t = sim.session_time()
        pos = sim.get('CarIdxPosition')
        pct = sim.get('CarIdxLapDistPct')
        lap = sim.get('CarIdxLap')
        surf = sim.get('CarIdxTrackSurface')
        if frame is None or t is None or pos is None:
            time.sleep(0.25)
            continue
        timeline.append({
            't': float(t), 'frame': int(frame),
            'pos': list(pos), 'pct': list(pct), 'lap': list(lap), 'surf': list(surf),
        })
        if progress and end_frame:
            progress(min(0.999, frame / end_frame))
        # end detection: frame stops advancing near the end
        if frame == last_frame:
            stall += 1
            if stall > 3 * sample_hz and (not end_frame or frame >= end_frame * 0.98):
                break
            if stall > 15 * sample_hz:
                break
        else:
            stall = 0
        last_frame = frame
        time.sleep(1.0 / sample_hz)

    sim.set_speed(0)
    if progress:
        progress(1.0)
    return timeline
