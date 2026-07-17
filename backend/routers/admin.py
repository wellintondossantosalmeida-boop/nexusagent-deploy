from fastapi import APIRouter, Depends, HTTPException
from middleware.admin import get_admin_user
from database import (
    get_all_users, ban_user, unban_user, delete_user,
    get_all_sessions, force_logout_user, force_logout_all,
    get_system_stats, get_all_tasks, execute_raw_sql,
    clear_all_data, set_admin_user, get_user_by_id,
    backup_database, create_notification
)
from pydantic import BaseModel
from typing import Optional
import subprocess
import os
import time

router = APIRouter()

class SQLQuery(BaseModel):
    sql: str

class UserID(BaseModel):
    user_id: int

class ForceLogout(BaseModel):
    user_id: int

class NotificationSend(BaseModel):
    title: str
    message: str
    user_id: Optional[int] = None

class TerminalCommand(BaseModel):
    command: str

class BypassMode(BaseModel):
    enabled: bool

# ============== PRIVILÉGIO 1: Ver Estatísticas Gerais ==============
@router.get("/stats")
async def admin_stats(user=Depends(get_admin_user)):
    stats = get_system_stats()
    return {"admin": True, "stats": stats}

# ============== PRIVILÉGIO 2: Listar Todos os Usuários ==============
@router.get("/users")
async def admin_list_users(user=Depends(get_admin_user)):
    users = get_all_users()
    return {"admin": True, "users": users, "total": len(users)}

# ============== PRIVILÉGIO 3: Banir/Desbanir Usuário ==============
@router.post("/ban")
async def admin_ban_user(data: UserID, user=Depends(get_admin_user)):
    if data.user_id == user["id"]:
        raise HTTPException(status_code=400, detail="Você não pode banir a si mesmo")
    target = get_user_by_id(data.user_id)
    if not target:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    if target.get("is_admin"):
        raise HTTPException(status_code=400, detail="Não é possível banir outro admin")
    ban_user(data.user_id)
    return {"admin": True, "message": f"Usuário {target['username']} banido com sucesso"}

@router.post("/unban")
async def admin_unban_user(data: UserID, user=Depends(get_admin_user)):
    target = get_user_by_id(data.user_id)
    if not target:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    unban_user(data.user_id)
    return {"admin": True, "message": f"Usuário {target['username']} desbanido com sucesso"}

# ============== PRIVILÉGIO 4: Deletar Usuário ==============
@router.post("/delete-user")
async def admin_delete_user(data: UserID, user=Depends(get_admin_user)):
    if data.user_id == user["id"]:
        raise HTTPException(status_code=400, detail="Você não pode deletar a si mesmo")
    target = get_user_by_id(data.user_id)
    if not target:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    if target.get("is_admin"):
        raise HTTPException(status_code=400, detail="Não é possível deletar outro admin")
    delete_user(data.user_id)
    return {"admin": True, "message": f"Usuário {target['username']} e todos os seus dados foram deletados"}

# ============== PRIVILÉGIO 5: Ver Todas as Sessões ==============
@router.get("/sessions")
async def admin_sessions(user=Depends(get_admin_user)):
    sessions = get_all_sessions()
    return {"admin": True, "sessions": sessions, "total": len(sessions)}

# ============== PRIVILÉGIO 6: Forçar Logout de Usuário ==============
@router.post("/force-logout")
async def admin_force_logout(data: ForceLogout, user=Depends(get_admin_user)):
    if data.user_id == user["id"]:
        raise HTTPException(status_code=400, detail="Você não pode fazer logout de si mesmo")
    target = get_user_by_id(data.user_id)
    if not target:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    force_logout_user(data.user_id)
    return {"admin": True, "message": f"Usuário {target['username']} foi forçado a fazer logout"}

@router.post("/force-logout-all")
async def admin_force_logout_all(user=Depends(get_admin_user)):
    force_logout_all()
    return {"admin": True, "message": "Todos os usuários foram forçados a fazer logout"}

# ============== PRIVILÉGIO 7: Ver Todas as Tarefas ==============
@router.get("/tasks")
async def admin_tasks(user=Depends(get_admin_user)):
    tasks = get_all_tasks()
    return {"admin": True, "tasks": tasks, "total": len(tasks)}

# ============== PRIVILÉGIO 8: Executar SQL Raw ==============
@router.post("/sql")
async def admin_execute_sql(data: SQLQuery, user=Depends(get_admin_user)):
    dangerous = ["DROP", "DELETE FROM users", "ALTER TABLE"]
    sql_upper = data.sql.upper()
    for d in dangerous:
        if d in sql_upper and "DELETE FROM users WHERE" not in sql_upper:
            raise HTTPException(status_code=400, detail=f"Operação perigosa bloqueada: {d}")
    result = execute_raw_sql(data.sql)
    return {"admin": True, "result": result}

# ============== PRIVILÉGIO 9: Limpar Todos os Dados ==============
@router.post("/clear-all")
async def admin_clear_all(user=Depends(get_admin_user)):
    clear_all_data()
    from database import create_user
    create_user("admin", "wellintondossantosalmeida@gmail.com", "admin123", "Admin Master")
    from database import get_db
    conn = get_db()
    conn.execute("UPDATE users SET is_admin = 1 WHERE username = 'admin'")
    conn.commit()
    conn.close()
    return {"admin": True, "message": "Todos os dados foram limpos. Usuário admin recriado."}

# ============== PRIVILÉGIO 10: Backup do Sistema ==============
@router.post("/backup")
async def admin_backup(user=Depends(get_admin_user)):
    success = backup_database()
    return {"admin": True, "success": success, "message": "Backup criado com sucesso" if success else "Erro ao criar backup"}

# ============== PROMOVER/REBAIXAR USUÁRIO ==============
@router.post("/promote")
async def admin_promote_user(data: UserID, user=Depends(get_admin_user)):
    target = get_user_by_id(data.user_id)
    if not target:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    set_admin_user(data.user_id, True)
    return {"admin": True, "message": f"Usuário {target['username']} promovido a admin"}

@router.post("/demote")
async def admin_demote_user(data: UserID, user=Depends(get_admin_user)):
    if data.user_id == user["id"]:
        raise HTTPException(status_code=400, detail="Você não pode rebaixar a si mesmo")
    target = get_user_by_id(data.user_id)
    if not target:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    set_admin_user(data.user_id, False)
    return {"admin": True, "message": f"Usuário {target['username']} rebaixado de admin"}

# ============== VERIFICAR STATUS ADMIN ==============
@router.get("/check")
async def admin_check(user=Depends(get_admin_user)):
    return {"admin": True, "user_id": user["id"], "username": user["username"], "email": user.get("email")}

# ============== STATUS: Admin tem restrições zeradas ==============
@router.get("/restrictions")
async def admin_restrictions(user=Depends(get_admin_user)):
    return {
        "admin": True,
        "restrictions": {
            "rate_limit_ai": "SEM LIMITE",
            "rate_limit_terminal": "SEM LIMITE",
            "max_tasks": "SEM LIMITE",
            "max_tokens": "SEM LIMITE",
            "all_providers": "LIBERADOS",
            "all_models": "LIBERADOS",
            "streaming": "LIBERADO",
            "sandbox": "LIBERADO",
            "terminal": "LIBERADO",
            "browser": "LIBERADO"
        },
        "message": "Admin tem todas as restrições desativadas para teste"
    }

# ============== NOVA FERRAMENTA: MONITOR DE RECURSOS ==============
@router.get("/resources")
async def admin_resources(user=Depends(get_admin_user)):
    resources = {}
    
    # CPU info
    try:
        with open('/proc/loadavg', 'r') as f:
            load = f.read().split()
        resources["cpu_load_1m"] = float(load[0])
        resources["cpu_load_5m"] = float(load[1])
        resources["cpu_load_15m"] = float(load[2])
    except:
        resources["cpu_load_1m"] = 0
        resources["cpu_load_5m"] = 0
        resources["cpu_load_15m"] = 0
    
    # Memory info
    try:
        with open('/proc/meminfo', 'r') as f:
            meminfo = f.read()
        for line in meminfo.split('\n'):
            if line.startswith('MemTotal:'):
                resources["mem_total_kb"] = int(line.split()[1])
            elif line.startswith('MemAvailable:'):
                resources["mem_available_kb"] = int(line.split()[1])
            elif line.startswith('MemFree:'):
                resources["mem_free_kb"] = int(line.split()[1])
        resources["mem_used_kb"] = resources["mem_total_kb"] - resources["mem_available_kb"]
        resources["mem_used_percent"] = round((resources["mem_used_kb"] / resources["mem_total_kb"]) * 100, 1)
    except:
        resources["mem_total_kb"] = 0
        resources["mem_used_kb"] = 0
        resources["mem_used_percent"] = 0
    
    # Disk info
    try:
        stat = os.statvfs('/')
        resources["disk_total_gb"] = round((stat.f_blocks * stat.f_frsize) / (1024**3), 2)
        resources["disk_free_gb"] = round((stat.f_bavail * stat.f_frsize) / (1024**3), 2)
        resources["disk_used_gb"] = round(resources["disk_total_gb"] - resources["disk_free_gb"], 2)
        resources["disk_used_percent"] = round((resources["disk_used_gb"] / resources["disk_total_gb"]) * 100, 1)
    except:
        resources["disk_total_gb"] = 0
        resources["disk_free_gb"] = 0
        resources["disk_used_percent"] = 0
    
    # Process info
    try:
        pid = os.getpid()
        with open(f'/proc/{pid}/status', 'r') as f:
            status = f.read()
        for line in status.split('\n'):
            if line.startswith('VmRSS:'):
                resources["process_memory_mb"] = int(line.split()[1]) // 1024
                break
    except:
        resources["process_memory_mb"] = 0
    
    resources["uptime_seconds"] = int(time.time() - os.path.getmtime('/proc/1/cmdline')) if os.path.exists('/proc/1/cmdline') else 0
    
    return {"admin": True, "resources": resources}

# ============== NOVA FERRAMENTA: LOGS EM TEMPO REAL ==============
@router.get("/logs")
async def admin_logs(user=Depends(get_admin_user), limit: int = 100):
    from database import get_db
    conn = get_db()
    try:
        events = conn.execute(
            "SELECT * FROM monitoring ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return {"admin": True, "logs": [dict(e) for e in events], "total": len(events)}
    finally:
        conn.close()

@router.get("/logs/file")
async def admin_logs_file(user=Depends(get_admin_user), lines: int = 100):
    log_content = ""
    for logfile in ["/tmp/nexus_final.log", "/tmp/nexus.log", "/root/agent/server.pid"]:
        try:
            if os.path.exists(logfile):
                with open(logfile, 'r') as f:
                    all_lines = f.readlines()
                    log_content = "".join(all_lines[-lines:])
                break
        except:
            continue
    return {"admin": True, "content": log_content, "lines": lines}

# ============== NOVA FERRAMENTA: ENVIAR NOTIFICAÇÕES ==============
@router.post("/send-notification")
async def admin_send_notification(data: NotificationSend, user=Depends(get_admin_user)):
    if data.user_id:
        target = get_user_by_id(data.user_id)
        if not target:
            raise HTTPException(status_code=404, detail="Usuário não encontrado")
        create_notification(data.user_id, data.title, data.message, "info")
        return {"admin": True, "message": f"Notificação enviada para {target['username']}"}
    else:
        users = get_all_users()
        sent = 0
        for u in users:
            try:
                create_notification(u["id"], data.title, data.message, "info")
                sent += 1
            except:
                pass
        return {"admin": True, "message": f"Notificação enviada para {sent} usuários"}

@router.get("/notifications-all")
async def admin_notifications_all(user=Depends(get_admin_user)):
    from database import get_db
    conn = get_db()
    try:
        notifs = conn.execute("""
            SELECT n.*, u.username FROM notifications n 
            JOIN users u ON n.user_id = u.id 
            ORDER BY n.created_at DESC LIMIT 200
        """).fetchall()
        return {"admin": True, "notifications": [dict(n) for n in notifs], "total": len(notifs)}
    finally:
        conn.close()

# ============== NOVA FERRAMENTA: TERMINAL DO SERVIDOR ==============
@router.post("/terminal")
async def admin_terminal(data: TerminalCommand, user=Depends(get_admin_user)):
    cmd = data.command
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=30,
            cwd="/root/agent"
        )
        output = result.stdout
        error = result.stderr
        return {
            "admin": True,
            "command": cmd,
            "output": output,
            "error": error,
            "exit_code": result.returncode,
            "success": result.returncode == 0
        }
    except subprocess.TimeoutExpired:
        return {"admin": True, "command": cmd, "error": "Comando excedeu 30 segundos", "exit_code": -1, "success": False}
    except Exception as e:
        return {"admin": True, "command": cmd, "error": str(e), "exit_code": -1, "success": False}


@router.post("/restore-default-keys")
async def restore_default_keys(admin=Depends(get_admin_user)):
    import json
    from database import get_db
    from main import DEFAULT_API_KEYS
    if not DEFAULT_API_KEYS:
        return {"success": False, "error": "Nenhuma key padrão configurada no servidor"}
    conn = get_db()
    conn.execute("UPDATE users SET api_keys_json = ? WHERE username = 'admin'",
                 (json.dumps(DEFAULT_API_KEYS),))
    conn.commit()
    conn.close()
    return {"success": True, "restored": list(DEFAULT_API_KEYS.keys())}
