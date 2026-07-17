#!/bin/bash
# NexusAgent AI - Start Script (robusto)

# Matar processos anteriores
pkill -f "uvicorn.*main:app" 2>/dev/null
pkill cloudflared 2>/dev/null
sleep 2

# Iniciar servidor
cd /root/agent/backend
setsid python3 -m uvicorn main:app --host 0.0.0.0 --port 8000 --log-level info > /tmp/nexus.log 2>&1 &
SERVER_PID=$!
disown

# Esperar servidor ficar pronto
for i in {1..10}; do
    if curl -s http://localhost:8000/api/health > /dev/null 2>&1; then
        break
    fi
    sleep 1
done

# Iniciar tunnel
setsid cloudflared tunnel --url http://localhost:8000 --no-autoupdate > /tmp/tunnel.log 2>&1 &
TUNNEL_PID=$!
disown

# Esperar tunnel ficar pronto
sleep 8

# Extrair URL
URL=$(grep -o 'https://[^ ]*trycloudflare.com' /tmp/tunnel.log | tail -1)

echo "========================================="
echo "NexusAgent AI - ONLINE!"
echo "Server PID: $SERVER_PID"
echo "Tunnel PID: $TUNNEL_PID"
echo "URL: $URL"
echo "========================================="
