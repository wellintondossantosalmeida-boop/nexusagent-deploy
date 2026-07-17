#!/usr/bin/env python3
import subprocess
import sys
import os

os.chdir('/root/agent/backend')

proc = subprocess.Popen(
    [sys.executable, '-m', 'uvicorn', 'main:app', '--host', '0.0.0.0', '--port', '8000'],
    stdout=open('/tmp/nexus_final.log', 'w'),
    stderr=subprocess.STDOUT,
    start_new_session=True
)

with open('/root/agent/server.pid', 'w') as f:
    f.write(str(proc.pid))

print(f'Server PID: {proc.pid}')
