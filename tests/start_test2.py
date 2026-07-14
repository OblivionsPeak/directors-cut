"""Reproduce the real updater condition: the batch's parent process DIES
immediately after spawning it. Also capture the relaunched app's exit code."""
import os
import subprocess
import sys
import tempfile

exe = os.path.join(os.environ['TEMP'], 'dc-selftest', 'DirectorsCut.exe')
log = os.path.join(tempfile.gettempdir(), 'dc-test2.log')
script = os.path.join(tempfile.gettempdir(), 'dc-test2.bat')
with open(script, 'w') as f:
    f.write(f'''@echo off
echo batch alive > "{log}"
timeout /t 3 /nobreak >nul
echo launching >> "{log}"
"{exe}"
echo app exited with %errorlevel% >> "{log}"
''')
subprocess.Popen(['cmd', '/c', script],
                 creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW,
                 close_fds=True)
os._exit(0)      # parent dies instantly, like the updating app does
