"""Isolate the update-script relaunch: does `start` from a hidden cmd work?"""
import os
import subprocess
import tempfile
import time
import urllib.request

exe = os.path.join(os.environ['TEMP'], 'dc-selftest', 'DirectorsCut.exe')
script = os.path.join(tempfile.gettempdir(), 'dc-test-start.bat')
with open(script, 'w') as f:
    f.write(f'@echo off\nstart "" "{exe}"\n')
subprocess.Popen(['cmd', '/c', script],
                 creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW,
                 close_fds=True)
time.sleep(8)
try:
    r = urllib.request.urlopen('http://localhost:4795/api/status', timeout=3)
    print('app responds:', r.status)
except Exception as e:
    print('app NOT running:', e)
