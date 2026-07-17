from fastapi import APIRouter, Depends
from database import get_db, log_monitoring
from middleware.auth import get_current_user

router = APIRouter()

@router.get("/health")
def health_check():
    return {"status": "ok", "version": "3.0.0"}

@router.get("/stats")
def get_stats(user=Depends(get_current_user)):
    conn = get_db()
    try:
        tasks = conn.execute("SELECT COUNT(*) as c FROM tasks WHERE user_id = ?", (user["id"],)).fetchone()["c"]
        completed = conn.execute("SELECT COUNT(*) as c FROM tasks WHERE user_id = ? AND status = 'completed'", (user["id"],)).fetchone()["c"]
        failed = conn.execute("SELECT COUNT(*) as c FROM tasks WHERE user_id = ? AND status = 'failed'", (user["id"],)).fetchone()["c"]
        tokens = conn.execute("SELECT COALESCE(SUM(total_tokens_used), 0) as t FROM users WHERE id = ?", (user["id"],)).fetchone()["t"]
        projects = conn.execute("SELECT COUNT(*) as c FROM projects WHERE user_id = ?", (user["id"],)).fetchone()["c"]
        files = conn.execute("SELECT COUNT(*) as c FROM file_uploads WHERE user_id = ?", (user["id"],)).fetchone()["c"]
        providers_used = conn.execute("SELECT COUNT(DISTINCT provider) as c FROM ai_usage_log WHERE user_id = ?", (user["id"],)).fetchone()["c"]
        return {"tasks": tasks, "completed": completed, "failed": failed, "tokens": tokens, "projects": projects, "files": files, "providers_used": providers_used}
    finally:
        conn.close()

@router.get("/monitoring")
def get_monitoring(user=Depends(get_current_user)):
    conn = get_db()
    try:
        events = conn.execute("SELECT * FROM monitoring ORDER BY created_at DESC LIMIT 100").fetchall()
        return {"events": [dict(e) for e in events]}
    finally:
        conn.close()
