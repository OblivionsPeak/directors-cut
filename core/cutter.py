"""Cut pass: title cards + concat into highlights.mp4 with bundled ffmpeg."""
import os
import subprocess
import time


def ffmpeg_exe():
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return 'ffmpeg'   # PATH fallback


def _run(args):
    return subprocess.run([ffmpeg_exe(), '-y', '-hide_banner', '-loglevel', 'error'] + args,
                          capture_output=True, text=True, timeout=1800)


def build_reel(clips, out_dir, title='Race Highlights', progress=None):
    """clips: [{highlight, file}] -> path of highlights mp4 (or None + reason)."""
    if not clips:
        return None, 'No clips were recorded.'
    os.makedirs(out_dir, exist_ok=True)
    stamp = time.strftime('%Y%m%d-%H%M%S')
    work = os.path.join(out_dir, f'reel-{stamp}')
    os.makedirs(work, exist_ok=True)

    # normalize every clip (same codec/size/fps so concat is safe) + burn label
    norm = []
    for i, c in enumerate(clips):
        if progress:
            progress(i, len(clips) + 1, f"Cutting clip {i + 1}/{len(clips)}")
        h = c['highlight']
        label = f"Lap {h.get('lap', '?')} — {h['label']}".replace("'", '’').replace(':', r'\:')
        out = os.path.join(work, f'clip{i:02d}.mp4')
        r = _run(['-i', c['file'],
                  '-vf', (f"scale=1920:1080:force_original_aspect_ratio=decrease,"
                          f"pad=1920:1080:(ow-iw)/2:(oh-ih)/2,fps=60,"
                          f"drawtext=text='{label}':x=40:y=h-90:fontsize=42:"
                          f"fontcolor=white:box=1:boxcolor=black@0.55:boxborderw=14"),
                  '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '20',
                  '-c:a', 'aac', '-ar', '48000', out])
        if r.returncode == 0 and os.path.exists(out):
            norm.append(out)
    if not norm:
        return None, 'ffmpeg failed on every clip — raw clips are still in the output folder.'

    if progress:
        progress(len(clips), len(clips) + 1, 'Concatenating reel')
    lst = os.path.join(work, 'list.txt')
    with open(lst, 'w', encoding='utf-8') as f:
        for p in norm:
            f.write(f"file '{p}'\n")
    final = os.path.join(out_dir, f'highlights-{stamp}.mp4')
    r = _run(['-f', 'concat', '-safe', '0', '-i', lst, '-c', 'copy', final])
    if r.returncode != 0:
        return None, f'Concat failed: {r.stderr[:300]}'
    return final, None
