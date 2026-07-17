#!/usr/bin/env python3
import subprocess, sys, os

proc = subprocess.Popen(
    [sys.executable, '-m', 'uvicorn', 'main:app', '--host', '0.0.0.0', '--port', '8000'],
    cwd='/root/agent/backend',
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
    start_new_session=True
)

with open('/root/agent/server.pid', 'w') as f:
    f.write(str(proc.pid))

print(f'NexusAgent server started on PID {proc.pid}')
print(f'URL: http://0.0.0.0:8000')
print(f'Docs: http://0.0.0.0:8000/docs')
