"""Self-updater for the one-file EXE via GitHub Releases.

No framework: check the latest release tag, download the new EXE to temp,
then hand off to a detached batch script that waits for this process to
exit, swaps the files (rename-then-move — a running EXE can't be
overwritten in place), and relaunches. Stale .old files are cleaned on
the next start.
"""
import json
import os
import subprocess
import sys
import tempfile
import urllib.request

REPO = 'OblivionsPeak/directors-cut'
ASSET = 'DirectorsCut.exe'


def _frozen_exe():
    return sys.executable if getattr(sys, 'frozen', False) else None


def cleanup_old():
    exe = _frozen_exe()
    if exe:
        try:
            os.remove(exe + '.old')
        except OSError:
            pass


def check(current_version):
    """Returns {'version', 'url', 'notes'} when a newer release exists, else None."""
    if not _frozen_exe():
        return None                       # running from source — nothing to swap
    override = os.environ.get('DC_VERSION')       # test hook
    current = override or current_version
    try:
        req = urllib.request.Request(
            f'https://api.github.com/repos/{REPO}/releases/latest',
            headers={'Accept': 'application/vnd.github+json',
                     'User-Agent': 'DirectorsCut-updater'})
        with urllib.request.urlopen(req, timeout=5) as r:
            rel = json.load(r)
    except Exception:
        return None                       # offline / rate-limited — never block the app
    latest = rel.get('tag_name', '')
    if not latest or _ver_tuple(latest) <= _ver_tuple(current):
        return None
    url = next((a['browser_download_url'] for a in rel.get('assets', [])
                if a['name'] == ASSET), None)
    if not url:
        return None
    return {'version': latest, 'url': url, 'notes': (rel.get('body') or '')[:500]}


def _ver_tuple(tag):
    nums = ''.join(c if c.isdigit() or c == '.' else ' ' for c in tag).split()
    try:
        return tuple(int(x) for x in '.'.join(nums).split('.') if x != '')
    except ValueError:
        return (0,)


def apply(url):
    """Download the new EXE and hand off to the swap script. Raises on failure;
    on success the caller should exit the process shortly after responding."""
    exe = _frozen_exe()
    if not exe:
        raise RuntimeError('Not running as a frozen EXE.')
    fd, new_path = tempfile.mkstemp(suffix='.exe', prefix='DirectorsCut-update-')
    os.close(fd)
    req = urllib.request.Request(url, headers={'User-Agent': 'DirectorsCut-updater'})
    with urllib.request.urlopen(req, timeout=120) as r, open(new_path, 'wb') as f:
        while True:
            chunk = r.read(1 << 20)
            if not chunk:
                break
            f.write(chunk)
    if os.path.getsize(new_path) < 10 * 1024 * 1024:
        os.remove(new_path)
        raise RuntimeError('Downloaded file is too small to be the app — aborting update.')

    pid = os.getpid()
    script = os.path.join(tempfile.gettempdir(), 'directorscut-update.bat')
    log = os.path.join(tempfile.gettempdir(), 'directorscut-update.log')
    # DC_RELAUNCH tells the new instance to wait for the port instead of
    # treating a dying predecessor as "already running" and exiting
    with open(script, 'w', encoding='ascii') as f:
        f.write(f'''@echo off
echo %date% %time% updater started > "{log}"
:wait
tasklist /FI "PID eq {pid}" 2>nul | find "{pid}" >nul && (timeout /t 1 /nobreak >nul & goto wait)
timeout /t 2 /nobreak >nul
echo %date% %time% old process gone, swapping >> "{log}"
move /y "{exe}" "{exe}.old" >> "{log}" 2>&1
move /y "{new_path}" "{exe}" >> "{log}" 2>&1
set DC_RELAUNCH=1
start "" "{exe}"
echo %date% %time% relaunched, exit code %errorlevel% >> "{log}"
del "%~f0"
''')
    subprocess.Popen(['cmd', '/c', script],
                     creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
                     | getattr(subprocess, 'CREATE_NO_WINDOW', 0),
                     close_fds=True)
