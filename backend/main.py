import os
import sys
import shutil
import json as _json
from datetime import datetime
from contextlib import asynccontextmanager
sys.path.insert(0, os.path.dirname(__file__))

def _load_default_keys():
    env_json = os.environ.get("DEFAULT_API_KEYS_JSON", "")
    if env_json:
        try:
            return _json.loads(env_json)
        except Exception:
            pass
    data_file = os.path.join(os.path.dirname(__file__), "keydata.json")
    if os.path.exists(data_file):
        try:
            with open(data_file) as f:
                return _json.load(f)
        except Exception:
            pass
    return {}

DEFAULT_API_KEYS = _load_default_keys()

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from database import init_db, backup_database, log_monitoring

def _ensure_admin_keys():
    import json
    from database import get_db, create_user, hash_password
    try:
        conn = get_db()
        user = conn.execute("SELECT api_keys_json FROM users WHERE username = 'admin'").fetchone()
        if not user:
            create_user("admin", "wellintondossantosalmeida@gmail.com", "admin123", "Admin Master")
            conn = get_db()
            conn.execute("UPDATE users SET is_admin = 1 WHERE username = 'admin'")
            conn.commit()
            print("✅ Admin user created: admin / admin123")
        else:
            new_hash = hash_password("admin123")
            conn.execute("UPDATE users SET is_admin = 1, password_hash = ? WHERE username = 'admin'", (new_hash,))
            conn.commit()
            print("✅ Admin password reset: admin / admin123")
        existing_keys = json.loads(user[0] if user and user[0] else "{}")
        if not existing_keys or all(not v for v in existing_keys.values()):
            conn.execute("UPDATE users SET api_keys_json = ? WHERE username = 'admin'",
                         (json.dumps(DEFAULT_API_KEYS),))
            conn.commit()
            print("✅ API keys restored: " + ", ".join(DEFAULT_API_KEYS.keys()))
        conn.close()
    except Exception as e:
        print(f"⚠️ Admin setup error: {e}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    backup_database()
    _ensure_admin_keys()
    log_monitoring("startup", "NexusAgent AI v3.0 iniciado")
    print("🚀 NexusAgent AI v3.0 iniciado!")
    print("📚 Docs: http://0.0.0.0:8000/docs")
    print("🌐 Frontend: http://0.0.0.0:8000")
    yield
    from services.ai_orchestrator import ai_orchestrator
    await ai_orchestrator.close()
    log_monitoring("shutdown", "NexusAgent AI desligado")
    print("👋 Servidor desligado")

app = FastAPI(
    title="NexusAgent AI",
    description="Agente Autônomo de Programação com Todas as IAs Gratuitas do Mundo",
    version="3.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://leaf-zip-elementary-publish.trycloudflare.com", "http://localhost:8000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from routers import (auth, tasks, projects, terminal, sandbox, browser_routes,
                      notifications, workflows, system_prompts, deployments,
                      db_ops, monitoring, public_api, export, admin)

app.include_router(auth.router, prefix="/api/auth", tags=["Autenticação"])
app.include_router(admin.router, prefix="/api/admin", tags=["Admin"])
app.include_router(tasks.router, prefix="/api/tasks", tags=["Tarefas"])
app.include_router(projects.router, prefix="/api/projects", tags=["Projetos"])
app.include_router(terminal.router, prefix="/api/terminal", tags=["Terminal"])
app.include_router(sandbox.router, prefix="/api/sandbox", tags=["Sandbox"])
app.include_router(browser_routes.router, prefix="/api/browser", tags=["Browser"])
app.include_router(notifications.router, prefix="/api/notifications", tags=["Notificações"])
app.include_router(workflows.router, prefix="/api/workflows", tags=["Workflows"])
app.include_router(system_prompts.router, prefix="/api/system-prompts", tags=["System Prompts"])
app.include_router(deployments.router, prefix="/api/deployments", tags=["Deployments"])
app.include_router(db_ops.router, prefix="/api/db", tags=["Database"])
app.include_router(monitoring.router, prefix="/api/monitoring", tags=["Monitoramento"])
app.include_router(public_api.router, prefix="/api/public-api-keys", tags=["API Keys Públicas"])
app.include_router(export.router, prefix="/api/export", tags=["Exportar"])

@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    path = request.url.path
    if path.endswith((".js", ".css", ".png", ".jpg", ".svg", ".woff2")):
        response.headers["Cache-Control"] = "public, max-age=86400"
    elif path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    return response

@app.get("/download/projeto-000")
def download_projeto():
    from config import BASE_DIR
    zip_path = BASE_DIR / "PROJETO-000.zip"
    if zip_path.exists():
        return FileResponse(str(zip_path), media_type="application/zip", filename="PROJETO-000.zip")
    return JSONResponse({"error": "Arquivo não encontrado"}, status_code=404)

@app.get("/download/nexus-zip")
def download_nexus_zip():
    from config import BASE_DIR
    zip_path = BASE_DIR / "frontend" / "NexusAgent-v3-Completo.zip"
    if zip_path.exists():
        return FileResponse(str(zip_path), media_type="application/zip", filename="NexusAgent-v3-Completo.zip")
    return JSONResponse({"error": "Arquivo não encontrado"}, status_code=404)

@app.get("/download/nexus-txt")
def download_nexus_txt():
    from config import BASE_DIR
    txt_path = BASE_DIR / "frontend" / "NexusAgent-v3-Instrucoes.txt"
    if txt_path.exists():
        return FileResponse(str(txt_path), media_type="text/plain", filename="NexusAgent-v3-Instrucoes.txt")
    return JSONResponse({"error": "Arquivo não encontrado"}, status_code=404)

@app.get("/download/nexus-apk")
def download_nexus_apk():
    from config import BASE_DIR
    apk_path = BASE_DIR / "frontend" / "NexusAgent-v3.apk"
    if apk_path.exists():
        return FileResponse(str(apk_path), media_type="application/vnd.android.package-archive", filename="NexusAgent-v3.apk")
    return JSONResponse({"error": "Arquivo não encontrado"}, status_code=404)

@app.get("/download/nexus-backup-txt")
def download_nexus_backup_txt():
    import subprocess
    from config import BASE_DIR
    txt_path = BASE_DIR / "frontend" / "NexusAgent-Backup-Projeto-Completo.txt"
    if not txt_path.exists():
        try:
            result = subprocess.run(
                ["python3", "-c", """
import sqlite3, json, os

DB = os.path.join(os.path.dirname(__file__), 'backend', 'agent.db')
if not os.path.exists(DB):
    DB = '/tmp/nexusagent/agent.db'

conn = sqlite3.connect(DB)

# Get admin keys
user = conn.execute("SELECT api_keys_json FROM users WHERE username='admin'").fetchone()
keys = json.loads(user[0]) if user and user[0] else {}

# Get providers
providers = {}
try:
    import sys; sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))
    from config import FREE_AI_PROVIDERS
    for k,v in FREE_AI_PROVIDERS.items():
        providers[k] = {'name': v['name'], 'url': v['url'], 'models': v['models'], 'api_type': v.get('api_type','openai')}
except: pass

# Get stats
stats = {}
try:
    stats['users'] = conn.execute('SELECT COUNT(*) FROM users').fetchone()[0]
    stats['tasks'] = conn.execute('SELECT COUNT(*) FROM tasks').fetchone()[0]
except: pass

conn.close()

print(json.dumps({'keys': keys, 'providers': providers, 'stats': stats}))
"""],
                capture_output=True, text=True, timeout=10,
                cwd=str(BASE_DIR)
            )
            data = json.loads(result.stdout.strip()) if result.stdout.strip() else {}
        except Exception:
            data = {}

        keys = data.get('keys', {})
        providers = data.get('providers', {})
        stats = data.get('stats', {})

        lines = [
            "================================================================================",
            "                    NEXUSAGENT AI - BACKUP DO PROJETO",
            "                    Data: 2026 | Versao: 3.0.0",
            "================================================================================",
            "",
            "URL: https://nexusagent-ai-vv60.onrender.com",
            "GitHub: https://github.com/wellintondossantosalmeida-boop/nexusagent-deploy",
            "Login: admin / admin123",
            "Email: wellintondossantosalmeida@gmail.com",
            "",
            "=== API KEYS ===",
        ]
        for name, key in keys.items():
            lines.append(f"  {name}: {key}")

        lines.extend(["", f"=== PROVEDORES ({len(providers)}) ==="])
        for pid, p in providers.items():
            lines.append(f"  {pid}: {p.get('name','')} | {p.get('api_type','openai')} | modelos: {', '.join(p.get('models',[]))}")

        lines.extend(["", f"=== ESTATISTICAS ===", f"  Usuarios: {stats.get('users',0)}", f"  Tarefas: {stats.get('tasks',0)}"])

        lines.extend(["", "=== TABELAS DB ==="])
        lines.append("  users, tasks, projects, ai_usage_log, file_uploads, task_versions,")
        lines.append("  notifications, workflows, system_prompts, deployments,")
        lines.append("  user_sessions, rate_limits, public_api_keys, monitoring")

        lines.extend(["", "=== COMO RECRIAR ===", "  1. Copie a estrutura de pastas do repo GitHub", "  2. Deploy no Render com Dockerfile", "  3. Acesse como admin e salve as API keys em Configuracoes", "", "Para restaurar este chat: opencode import chat-nexusagent-historico.json", "", "================================================================================"])

        with open(str(txt_path), 'w') as f:
            f.write('\n'.join(lines))

    if txt_path.exists():
        return FileResponse(str(txt_path), media_type="text/plain", filename="NexusAgent-Backup.txt")
    return JSONResponse({"error": "Erro ao gerar backup"}, status_code=500)

@app.get("/", response_class=HTMLResponse)
@app.get("/app", response_class=HTMLResponse)
@app.get("/app/{path:path}", response_class=HTMLResponse)
@app.get("/download/{path:path}", response_class=HTMLResponse)
def root():
    frontend_path = os.path.join(os.path.dirname(__file__), "..", "frontend", "index.html")
    if not os.path.exists(frontend_path):
        frontend_path = os.path.join(os.path.dirname(__file__), "..", "static", "index.html")
    if os.path.exists(frontend_path):
        with open(frontend_path, "r") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse(content="<h1>NexusAgent AI</h1><p>Frontend não encontrado</p>")

@app.get("/api/health")
def health():
    return {"status": "ok", "name": "NexusAgent AI", "version": "3.0.0", "providers": 15, "features": ["streaming", "sandbox", "terminal", "browser", "workflows", "notifications", "system_prompts", "deployments", "db_ops", "export", "monitoring", "public_api", "rate_limiting", "sessions"]}

@app.get("/api/stats")
def stats():
    try:
        from database import get_db
        conn = get_db()
        try:
            users = conn.execute("SELECT COUNT(*) as c FROM users").fetchone()["c"]
            tasks = conn.execute("SELECT COUNT(*) as c FROM tasks").fetchone()["c"]
            completed = conn.execute("SELECT COUNT(*) as c FROM tasks WHERE status = 'completed'").fetchone()["c"]
            tokens = conn.execute("SELECT COALESCE(SUM(total_tokens_used), 0) as t FROM users").fetchone()["t"]
            return {"users": users, "total_tasks": tasks, "completed_tasks": completed, "total_tokens": tokens}
        finally:
            conn.close()
    except Exception as e:
        return {"error": str(e)}

@app.post("/api/auth/validate")
def validate_token(user=None):
    from middleware.auth import get_current_user
    return {"valid": True}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
