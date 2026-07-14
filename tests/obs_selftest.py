"""Live OBS integration test: connect, record 5 s, report the file path."""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.capture import ObsCapture

password = sys.argv[1] if len(sys.argv) > 1 else ''

print('--- no password ---')
cap = ObsCapture(password='')
ok, reason = cap.available()
print('available:', ok, '|', reason[:160])

print('--- with password ---')
cap = ObsCapture(password=password)
ok, reason = cap.available()
print('available:', ok, '|', reason[:160])
if not ok:
    sys.exit(1)

print('starting record...')
cap.prepare()
cap.start()
time.sleep(5)
path = cap.stop()
cap.cleanup()
print('stop() returned:', repr(path))
if path and os.path.exists(path):
    print(f'FILE OK: {path} ({os.path.getsize(path)} bytes)')
else:
    print('NO FILE — investigating record directory...')
    try:
        rd = cap.client.get_record_directory().record_directory
        print('record dir:', rd)
        for f in sorted(os.listdir(rd))[-5:]:
            print('  ', f)
    except Exception as e:
        print('dir query failed:', e)
