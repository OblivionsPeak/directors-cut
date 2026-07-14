"""Highlight detection over a scanned timeline. Pure data → pure data:
no sim, no I/O — fully unit-testable.

Timeline sample: {t, frame, pos[caridx], pct[caridx], lap[caridx], surf[caridx]}
Highlight: {type, label, t_start, t_end, caridx, lap, score}
"""

ON_TRACK = 3
OFF_TRACK = 0

PRE_ROLL = 6.0     # seconds of context before the moment
POST_ROLL = 5.0


def _cars_in(timeline):
    n = max(len(s['pos']) for s in timeline)
    return [i for i in range(n)
            if any(s['pos'][i] > 0 and s['surf'][i] != -1 for s in timeline if i < len(s['pos']))]


def detect(timeline, focus_caridx=None, max_highlights=12):
    """focus_caridx: None = whole field; else only moments involving that car."""
    if len(timeline) < 10:
        return []
    cars = _cars_in(timeline)
    events = []
    events += _overtakes(timeline, cars)
    events += _incidents(timeline, cars)
    events += _battles(timeline, cars)
    events += _finish(timeline, cars)

    if focus_caridx is not None:
        events = [e for e in events
                  if e['caridx'] == focus_caridx or focus_caridx in e.get('involved', [])]

    events = _merge_overlaps(events)
    events.sort(key=lambda e: -e['score'])
    events = events[:max_highlights]
    events.sort(key=lambda e: e['t_start'])
    return events


def _overtakes(timeline, cars):
    """Position swap that sticks for 10+ s, on track, not a pit cycle."""
    out = []
    hold = 10.0
    for ci in cars:
        prev_pos = None
        for k, s in enumerate(timeline):
            p = s['pos'][ci]
            if p <= 0:
                continue
            if prev_pos is not None and p < prev_pos and s['surf'][ci] == ON_TRACK:
                # find who was passed: car now exactly one position behind
                victim = next((cj for cj in cars if cj != ci
                               and s['pos'][cj] == p + 1), None)
                # sticky? position still ≤ p after `hold` seconds
                t_check = s['t'] + hold
                later = next((x for x in timeline[k:] if x['t'] >= t_check), None)
                # pit-cycle filter: victim in/near pits at the swap
                pit = victim is not None and s['surf'][victim] in (1, 2)
                if later and later['pos'][ci] <= p and not pit:
                    out.append({
                        'type': 'overtake',
                        'label': f'Pass for P{p}' + (f' on car {victim}' if victim is not None else ''),
                        't_start': s['t'] - PRE_ROLL, 't_end': s['t'] + POST_ROLL,
                        'caridx': ci, 'involved': [v for v in [victim] if v is not None],
                        'lap': s['lap'][ci], 'score': 10 - min(p, 8) + 4,  # front matters more
                    })
            prev_pos = p
    return out


def _incidents(timeline, cars):
    """Off-track excursions at racing speed (spin/crash proxy from surface)."""
    out = []
    for ci in cars:
        was_on = False
        for k, s in enumerate(timeline):
            surf = s['surf'][ci]
            if surf == ON_TRACK:
                was_on = True
                continue
            if surf == OFF_TRACK and was_on and s['pos'][ci] > 0:
                # position damage = more dramatic
                pos_before = s['pos'][ci]
                t_check = s['t'] + 15
                later = next((x for x in timeline[k:] if x['t'] >= t_check), None)
                lost = (later['pos'][ci] - pos_before) if later else 0
                out.append({
                    'type': 'incident',
                    'label': f'Off at lap {s["lap"][ci]}' + (f' — loses {lost} places' if lost > 0 else ''),
                    't_start': s['t'] - PRE_ROLL, 't_end': s['t'] + POST_ROLL + 3,
                    'caridx': ci, 'involved': [],
                    'lap': s['lap'][ci], 'score': 8 + min(lost, 6) + (4 if pos_before <= 5 else 0),
                })
                was_on = False
    return out


def _battles(timeline, cars):
    """Sustained nose-to-tail running: gap < ~0.6% of a lap for 30+ s."""
    out = []
    GAP = 0.006
    MIN_S = 30.0
    pairs = set()
    for k in range(0, len(timeline), 4):
        s = timeline[k]
        for ci in cars:
            if s['pos'][ci] <= 0 or s['surf'][ci] != ON_TRACK:
                continue
            for cj in cars:
                if cj <= ci or s['pos'][cj] != s['pos'][ci] + 1:
                    continue
                d = abs(s['pct'][ci] - s['pct'][cj])
                d = min(d, 1 - d)
                if d < GAP:
                    pairs.add((ci, cj, k))
    # group consecutive windows per pair
    bypair = {}
    for ci, cj, k in sorted(pairs):
        bypair.setdefault((ci, cj), []).append(k)
    for (ci, cj), ks in bypair.items():
        run_start = ks[0]
        prev = ks[0]
        for k in ks[1:] + [None]:
            if k is not None and k - prev <= 8:
                prev = k
                continue
            t0, t1 = timeline[run_start]['t'], timeline[prev]['t']
            if t1 - t0 >= MIN_S:
                pos = timeline[run_start]['pos'][ci]
                out.append({
                    'type': 'battle',
                    'label': f'P{pos} battle, {t1 - t0:.0f}s nose-to-tail',
                    't_start': max(t0, t1 - 25) - PRE_ROLL, 't_end': t1 + POST_ROLL,
                    'caridx': ci, 'involved': [cj],
                    'lap': timeline[prev]['lap'][ci],
                    'score': 6 + (6 if pos <= 3 else 2) + min((t1 - t0) / 30, 4),
                })
            if k is not None:
                run_start = prev = k
    return out


def _finish(timeline, cars):
    """The last ~40 s of the leader's race, always worth having."""
    leader = None
    for s in reversed(timeline):
        for ci in cars:
            if s['pos'][ci] == 1:
                leader = ci
                break
        if leader is not None:
            break
    if leader is None:
        return []
    t_end = timeline[-1]['t']
    return [{
        'type': 'finish', 'label': 'The finish',
        't_start': t_end - 40, 't_end': t_end,
        'caridx': leader, 'involved': [],
        'lap': timeline[-1]['lap'][leader], 'score': 9,
    }]


def _merge_overlaps(events):
    """Overlapping windows collapse into the higher-scoring one (label kept)."""
    events = sorted(events, key=lambda e: e['t_start'])
    out = []
    for e in events:
        if out and e['t_start'] < out[-1]['t_end'] and e['caridx'] == out[-1]['caridx']:
            keep = e if e['score'] > out[-1]['score'] else out[-1]
            keep = dict(keep)
            keep['t_start'] = min(e['t_start'], out[-1]['t_start'])
            keep['t_end'] = max(e['t_end'], out[-1]['t_end'])
            out[-1] = keep
        else:
            out.append(dict(e))
    return out
