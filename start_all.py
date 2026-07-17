#!/usr/bin/env python3
"""NexusAgent - Servidor + Tunnel permanente"""
import subprocess, time, sys, os, signal, threading

def run_server():
    proc = subprocess.Popen(
        [sys.executable, '-m', 'uvicorn', 'main:app', '--host', '0.0.0.0', '--port', '8000'],
        cwd='/root/agent/backend',
        stdout=open('/root/agent/server.log', 'w'),
        stderr=subprocess.STDOUT,
        start_new_session=True
    )
    with open('/root/agent/server.pid', 'w') as f:
        f.write(str(proc.pid))
    print(f'Servidor PID: {proc.pid}', flush=True)
    return proc

def run_tunnel():
    proc = subprocess.Popen(
        ['cloudflared', 'tunnel', '--url', 'http://localhost:8000', '--no-autoupdate'],
        stdout=open('/root/agent/tunnel.log', 'w'),
        stderr=subprocess.STDOUT,
        start_new_session=True
    )
    with open('/root/agent/tunnel.pid', 'w') as f:
        f.write(str(proc.pid))
    print(f'Tunnel PID: {proc.pid}', flush=True)
    return proc

def get_tunnel_url():
    for _ in range(30):
        try:
            with open('/root/agent/tunnel.log') as f:
                for line in f:
                    if 'trycloudflare.com' in line and 'https://' in line:
                        url = line.split('https://')[1].split()[0].strip().rstrip('|').strip()
                        return f'https://{url}'
        except:
            pass
        time.sleep(1)
    return None

def main():
    print('=== NexusAgent AI ===', flush=True)
    print('Iniciando servidor...', flush=True)
    server = run_server()
    time.sleep(3)
    
    print('Iniciando tunnel...', flush=True)
    tunnel = run_tunnel()
    
    url = get_tunnel_url()
    if url:
        print('', flush=True)
        print('=' * 50, flush=True)
        print(f'  SITE: {url}', flush=True)
        print(f'  DOWNLOAD: {url}/download/projeto-000', flush=True)
        print(f'  DOCS: {url}/docs', flush=True)
        print(f'  LOGIN: admin / admin123', flush=True)
        print('=' * 50, flush=True)
    else:
        print('Nao foi possivel obter URL do tunnel', flush=True)
    
    # Manter vivo
    while True:
        if server.poll() is not None:
            print('Servidor morreu, reiniciando...', flush=True)
            server = run_server()
        if tunnel.poll() is not None:
            print('Tunnel morreu, reiniciando...', flush=True)
            tunnel = run_tunnel()
            url = get_tunnel_url()
            if url:
                print(f'NOVA URL: {url}', flush=True)
        time.sleep(10)

if __name__ == '__main__':
    main()
