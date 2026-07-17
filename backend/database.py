import sqlite3
import hashlib
import os
import shutil
import time
import secrets
from datetime import datetime, timezone
from pathlib import Path
from config import DB_PATH

ALLOWED_TASK_COLUMNS = {
    "title", "description", "task_type", "status", "priority", "input_data",
    "output_data", "files_json", "ai_provider_used", "ai_model_used",
    "tokens_used", "execution_time_ms", "error_message", "completed_at"
}

def get_db():
    conn = sqlite3.connect(str(DB_PATH), timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn

def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            full_name TEXT DEFAULT '',
            api_keys_json TEXT DEFAULT '{}',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_login TIMESTAMP,
            is_active BOOLEAN DEFAULT 1,
            is_admin BOOLEAN DEFAULT 0,
            total_tasks INTEGER DEFAULT 0,
            total_tokens_used INTEGER DEFAULT 0,
            system_prompt_id INTEGER DEFAULT NULL
        );

        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            description TEXT,
            task_type TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            priority INTEGER DEFAULT 5,
            input_data TEXT,
            output_data TEXT,
            files_json TEXT DEFAULT '[]',
            ai_provider_used TEXT,
            ai_model_used TEXT,
            tokens_used INTEGER DEFAULT 0,
            execution_time_ms INTEGER DEFAULT 0,
            error_message TEXT,
            progress INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            description TEXT,
            project_type TEXT NOT NULL,
            status TEXT DEFAULT 'created',
            config_json TEXT DEFAULT '{}',
            output_path TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS ai_usage_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            task_id INTEGER,
            provider TEXT NOT NULL,
            model TEXT NOT NULL,
            tokens_input INTEGER DEFAULT 0,
            tokens_output INTEGER DEFAULT 0,
            latency_ms INTEGER DEFAULT 0,
            success BOOLEAN DEFAULT 1,
            error TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS file_uploads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            task_id INTEGER,
            filename TEXT NOT NULL,
            original_name TEXT NOT NULL,
            file_size INTEGER DEFAULT 0,
            mime_type TEXT DEFAULT '',
            upload_path TEXT NOT NULL,
            processed BOOLEAN DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS task_versions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id INTEGER NOT NULL,
            version_number INTEGER DEFAULT 1,
            content TEXT,
            diff_from_previous TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (task_id) REFERENCES tasks(id)
        );

        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            message TEXT DEFAULT '',
            type TEXT DEFAULT 'info',
            read INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS workflows (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            steps_json TEXT DEFAULT '[]',
            status TEXT DEFAULT 'created',
            last_run TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS system_prompts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            prompt TEXT NOT NULL,
            task_type TEXT DEFAULT 'general',
            is_default INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS deployments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            project_id INTEGER,
            platform TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            url TEXT DEFAULT '',
            deploy_log TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS user_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            token_hash TEXT NOT NULL,
            ip_address TEXT DEFAULT '',
            user_agent TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP NOT NULL,
            is_active INTEGER DEFAULT 1,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS rate_limits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            identifier TEXT NOT NULL,
            action TEXT NOT NULL,
            count INTEGER DEFAULT 1,
            window_start TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS public_api_keys (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            key_hash TEXT NOT NULL,
            name TEXT DEFAULT '',
            permissions TEXT DEFAULT 'read',
            last_used TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_active INTEGER DEFAULT 1,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS monitoring (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type TEXT NOT NULL,
            message TEXT DEFAULT '',
            metadata TEXT DEFAULT '{}',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_tasks_user ON tasks(user_id);
        CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
        CREATE INDEX IF NOT EXISTS idx_notifications_user ON notifications(user_id);
        CREATE INDEX IF NOT EXISTS idx_rate_limits_id ON rate_limits(identifier, action);
        CREATE INDEX IF NOT EXISTS idx_sessions_user ON user_sessions(user_id);
        CREATE INDEX IF NOT EXISTS idx_monitoring_type ON monitoring(event_type);
    """)
    conn.commit()
    conn.close()

def hash_password(password: str) -> str:
    salt = secrets.token_hex(32)
    key = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100000).hex()
    return f"{salt}:{key}"

def verify_password(password: str, stored: str) -> bool:
    try:
        parts = stored.split(":")
        if len(parts) != 2:
            return False
        salt, key = parts
        new_key = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100000).hex()
        return new_key == key
    except Exception:
        return False

def create_user(username: str, email: str, password: str, full_name: str = ""):
    conn = get_db()
    try:
        password_hash = hash_password(password)
        conn.execute(
            "INSERT INTO users (username, email, password_hash, full_name) VALUES (?, ?, ?, ?)",
            (username, email, password_hash, full_name)
        )
        conn.commit()
        user = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        return dict(user) if user else None
    except sqlite3.IntegrityError:
        return None
    finally:
        conn.close()

def authenticate_user(username: str, password: str):
    conn = get_db()
    try:
        user = conn.execute("SELECT * FROM users WHERE username = ? OR email = ?", (username, username)).fetchone()
        if user and verify_password(password, user["password_hash"]):
            conn.execute("UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = ?", (user["id"],))
            conn.commit()
            return dict(user)
        return None
    finally:
        conn.close()

def get_user_by_id(user_id: int):
    conn = get_db()
    try:
        user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return dict(user) if user else None
    finally:
        conn.close()

def create_task(user_id: int, title: str, description: str, task_type: str, input_data: str = "", priority: int = 5):
    conn = get_db()
    try:
        cursor = conn.execute(
            "INSERT INTO tasks (user_id, title, description, task_type, input_data, priority) VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, title, description, task_type, input_data, priority)
        )
        task_id = cursor.lastrowid
        conn.commit()
        task = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        return dict(task) if task else None
    finally:
        conn.close()

def update_task(task_id: int, **kwargs):
    invalid_keys = set(kwargs.keys()) - ALLOWED_TASK_COLUMNS
    if invalid_keys:
        raise ValueError(f"Colunas não permitidas: {invalid_keys}")
    conn = get_db()
    try:
        sets = ", ".join(f"{k} = ?" for k in kwargs)
        values = list(kwargs.values()) + [task_id]
        conn.execute(f"UPDATE tasks SET {sets} WHERE id = ?", values)
        conn.commit()
    finally:
        conn.close()

def get_user_tasks(user_id: int, limit: int = 50):
    conn = get_db()
    try:
        tasks = conn.execute(
            "SELECT * FROM tasks WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
            (user_id, limit)
        ).fetchall()
        return [dict(t) for t in tasks]
    finally:
        conn.close()

def create_project(user_id: int, name: str, description: str, project_type: str, config_json: str = "{}"):
    conn = get_db()
    try:
        cursor = conn.execute(
            "INSERT INTO projects (user_id, name, description, project_type, config_json) VALUES (?, ?, ?, ?, ?)",
            (user_id, name, description, project_type, config_json)
        )
        project_id = cursor.lastrowid
        conn.commit()
        project = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
        return dict(project) if project else None
    finally:
        conn.close()

def get_user_projects(user_id: int):
    conn = get_db()
    try:
        projects = conn.execute(
            "SELECT * FROM projects WHERE user_id = ? ORDER BY updated_at DESC", (user_id,)
        ).fetchall()
        return [dict(p) for p in projects]
    finally:
        conn.close()

def log_ai_usage(user_id: int, provider: str, model: str, tokens_input: int, tokens_output: int, latency_ms: int, success: bool = True, error: str = None, task_id: int = None):
    conn = get_db()
    try:
        provider = provider or "none"
        model = model or "none"
        conn.execute(
            "INSERT INTO ai_usage_log (user_id, task_id, provider, model, tokens_input, tokens_output, latency_ms, success, error) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (user_id, task_id, provider, model, tokens_input, tokens_output, latency_ms, success, error)
        )
        conn.execute("UPDATE users SET total_tokens_used = total_tokens_used + ? WHERE id = ?", (tokens_input + tokens_output, user_id))
        conn.commit()
    finally:
        conn.close()

def get_user_api_keys(user_id: int):
    user = get_user_by_id(user_id)
    if user:
        import json
        return json.loads(user.get("api_keys_json", "{}"))
    return {}

def save_user_api_keys(user_id: int, keys: dict):
    import json
    conn = get_db()
    try:
        conn.execute("UPDATE users SET api_keys_json = ? WHERE id = ?", (json.dumps(keys), user_id))
        conn.commit()
    finally:
        conn.close()

def backup_database():
    db_path = str(DB_PATH)
    bak_path = db_path + ".bak"
    if os.path.exists(db_path):
        shutil.copy2(db_path, bak_path)
        return True
    return False

def check_rate_limit(identifier: str, action: str, limit: int, window: int = 60) -> bool:
    conn = get_db()
    try:
        now = time.time()
        cutoff = now - window
        conn.execute("DELETE FROM rate_limits WHERE window_start < datetime(?, 'unixepoch')", (int(cutoff),))
        row = conn.execute(
            "SELECT COUNT(*) as c FROM rate_limits WHERE identifier = ? AND action = ? AND window_start > datetime(?, 'unixepoch')",
            (identifier, action, int(cutoff))
        ).fetchone()
        if row["c"] >= limit:
            return False
        conn.execute(
            "INSERT INTO rate_limits (identifier, action, count, window_start) VALUES (?, ?, 1, datetime('now'))",
            (identifier, action)
        )
        conn.commit()
        return True
    finally:
        conn.close()

def create_session(user_id: int, token: str, ip: str = "", ua: str = "", expires_in: int = 86400):
    conn = get_db()
    try:
        token_hash = hashlib.sha256(token.encode()).hexdigest()[:32]
        conn.execute(
            "INSERT INTO user_sessions (user_id, token_hash, ip_address, user_agent, expires_at) VALUES (?, ?, ?, ?, datetime('now', '+' || ? || ' seconds'))",
            (user_id, token_hash, ip, ua, expires_in)
        )
        conn.commit()
    finally:
        conn.close()

def get_user_sessions(user_id: int):
    conn = get_db()
    try:
        sessions = conn.execute(
            "SELECT * FROM user_sessions WHERE user_id = ? AND is_active = 1 ORDER BY created_at DESC",
            (user_id,)
        ).fetchall()
        return [dict(s) for s in sessions]
    finally:
        conn.close()

def revoke_session(session_id: int, user_id: int):
    conn = get_db()
    try:
        conn.execute("UPDATE user_sessions SET is_active = 0 WHERE id = ? AND user_id = ?", (session_id, user_id))
        conn.commit()
    finally:
        conn.close()

def revoke_all_sessions(user_id: int):
    conn = get_db()
    try:
        conn.execute("UPDATE user_sessions SET is_active = 0 WHERE user_id = ?", (user_id,))
        conn.commit()
    finally:
        conn.close()

def log_monitoring(event_type: str, message: str = "", metadata: str = "{}"):
    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO monitoring (event_type, message, metadata) VALUES (?, ?, ?)",
            (event_type, message, metadata)
        )
        conn.commit()
    finally:
        conn.close()

def get_task_versions(task_id: int):
    conn = get_db()
    try:
        versions = conn.execute(
            "SELECT * FROM task_versions WHERE task_id = ? ORDER BY version_number DESC",
            (task_id,)
        ).fetchall()
        return [dict(v) for v in versions]
    finally:
        conn.close()

def create_task_version(task_id: int, content: str, diff_from_previous: str = ""):
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT COALESCE(MAX(version_number), 0) as max_v FROM task_versions WHERE task_id = ?",
            (task_id,)
        ).fetchone()
        next_version = row["max_v"] + 1
        conn.execute(
            "INSERT INTO task_versions (task_id, version_number, content, diff_from_previous) VALUES (?, ?, ?, ?)",
            (task_id, next_version, content, diff_from_previous)
        )
        conn.commit()
        return next_version
    finally:
        conn.close()

def create_notification(user_id: int, title: str, message: str = "", notif_type: str = "info"):
    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO notifications (user_id, title, message, type) VALUES (?, ?, ?, ?)",
            (user_id, title, message, notif_type)
        )
        conn.commit()
    finally:
        conn.close()

def get_system_prompts(user_id: int):
    conn = get_db()
    try:
        prompts = conn.execute(
            "SELECT * FROM system_prompts WHERE user_id = ? ORDER BY created_at DESC",
            (user_id,)
        ).fetchall()
        return [dict(p) for p in prompts]
    finally:
        conn.close()

def create_system_prompt(user_id: int, name: str, prompt: str, task_type: str = "general"):
    conn = get_db()
    try:
        cursor = conn.execute(
            "INSERT INTO system_prompts (user_id, name, prompt, task_type) VALUES (?, ?, ?, ?)",
            (user_id, name, prompt, task_type)
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()

def delete_system_prompt(prompt_id: int, user_id: int):
    conn = get_db()
    try:
        conn.execute("DELETE FROM system_prompts WHERE id = ? AND user_id = ?", (prompt_id, user_id))
        conn.commit()
    finally:
        conn.close()

# ============== ADMIN FUNCTIONS ==============

ADMIN_USERNAME = "admin"
ADMIN_EMAIL = "wellintondossantosalmeida@gmail.com"

def is_admin_user(user_id: int) -> bool:
    conn = get_db()
    try:
        user = conn.execute("SELECT is_admin FROM users WHERE id = ?", (user_id,)).fetchone()
        return bool(user["is_admin"]) if user else False
    finally:
        conn.close()

def set_admin_user(user_id: int, is_admin: bool = True):
    conn = get_db()
    try:
        conn.execute("UPDATE users SET is_admin = ? WHERE id = ?", (int(is_admin), user_id))
        conn.commit()
    finally:
        conn.close()

def get_all_users():
    conn = get_db()
    try:
        users = conn.execute("SELECT id, username, email, full_name, is_active, is_admin, total_tasks, total_tokens_used, created_at, last_login FROM users ORDER BY id").fetchall()
        return [dict(u) for u in users]
    finally:
        conn.close()

def ban_user(user_id: int):
    conn = get_db()
    try:
        conn.execute("UPDATE users SET is_active = 0 WHERE id = ?", (user_id,))
        conn.execute("UPDATE user_sessions SET is_active = 0 WHERE user_id = ?", (user_id,))
        conn.commit()
    finally:
        conn.close()

def unban_user(user_id: int):
    conn = get_db()
    try:
        conn.execute("UPDATE users SET is_active = 1 WHERE id = ?", (user_id,))
        conn.commit()
    finally:
        conn.close()

def delete_user(user_id: int):
    conn = get_db()
    try:
        conn.execute("DELETE FROM user_sessions WHERE user_id = ?", (user_id,))
        conn.execute("DELETE FROM notifications WHERE user_id = ?", (user_id,))
        conn.execute("DELETE FROM tasks WHERE user_id = ?", (user_id,))
        conn.execute("DELETE FROM projects WHERE user_id = ?", (user_id,))
        conn.execute("DELETE FROM workflows WHERE user_id = ?", (user_id,))
        conn.execute("DELETE FROM system_prompts WHERE user_id = ?", (user_id,))
        conn.execute("DELETE FROM deployments WHERE user_id = ?", (user_id,))
        conn.execute("DELETE FROM public_api_keys WHERE user_id = ?", (user_id,))
        conn.execute("DELETE FROM file_uploads WHERE user_id = ?", (user_id,))
        conn.execute("DELETE FROM ai_usage_log WHERE user_id = ?", (user_id,))
        conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
        conn.commit()
    finally:
        conn.close()

def get_all_sessions():
    conn = get_db()
    try:
        sessions = conn.execute("""
            SELECT s.*, u.username FROM user_sessions s 
            JOIN users u ON s.user_id = u.id 
            WHERE s.is_active = 1 
            ORDER BY s.created_at DESC
        """).fetchall()
        return [dict(s) for s in sessions]
    finally:
        conn.close()

def force_logout_user(user_id: int):
    conn = get_db()
    try:
        conn.execute("UPDATE user_sessions SET is_active = 0 WHERE user_id = ?", (user_id,))
        conn.commit()
    finally:
        conn.close()

def force_logout_all():
    conn = get_db()
    try:
        conn.execute("UPDATE user_sessions SET is_active = 0 WHERE is_active = 1")
        conn.commit()
    finally:
        conn.close()

def get_system_stats():
    conn = get_db()
    try:
        stats = {}
        stats["total_users"] = conn.execute("SELECT COUNT(*) as c FROM users").fetchone()["c"]
        stats["active_users"] = conn.execute("SELECT COUNT(*) as c FROM users WHERE is_active = 1").fetchone()["c"]
        stats["admin_users"] = conn.execute("SELECT COUNT(*) as c FROM users WHERE is_admin = 1").fetchone()["c"]
        stats["total_tasks"] = conn.execute("SELECT COUNT(*) as c FROM tasks").fetchone()["c"]
        stats["completed_tasks"] = conn.execute("SELECT COUNT(*) as c FROM tasks WHERE status = 'completed'").fetchone()["c"]
        stats["pending_tasks"] = conn.execute("SELECT COUNT(*) as c FROM tasks WHERE status = 'pending'").fetchone()["c"]
        stats["failed_tasks"] = conn.execute("SELECT COUNT(*) as c FROM tasks WHERE status = 'failed'").fetchone()["c"]
        stats["total_projects"] = conn.execute("SELECT COUNT(*) as c FROM projects").fetchone()["c"]
        stats["total_tokens_used"] = conn.execute("SELECT COALESCE(SUM(total_tokens_used), 0) as t FROM users").fetchone()["t"]
        stats["active_sessions"] = conn.execute("SELECT COUNT(*) as c FROM user_sessions WHERE is_active = 1").fetchone()["c"]
        stats["total_notifications"] = conn.execute("SELECT COUNT(*) as c FROM notifications").fetchone()["c"]
        stats["total_workflows"] = conn.execute("SELECT COUNT(*) as c FROM workflows").fetchone()["c"]
        stats["total_api_keys"] = conn.execute("SELECT COUNT(*) as c FROM public_api_keys WHERE is_active = 1").fetchone()["c"]
        stats["total_monitoring_events"] = conn.execute("SELECT COUNT(*) as c FROM monitoring").fetchone()["c"]
        stats["db_size_bytes"] = os.path.getsize(str(DB_PATH)) if os.path.exists(str(DB_PATH)) else 0
        return stats
    finally:
        conn.close()

def get_all_tasks():
    conn = get_db()
    try:
        tasks = conn.execute("""
            SELECT t.*, u.username FROM tasks t 
            JOIN users u ON t.user_id = u.id 
            ORDER BY t.created_at DESC LIMIT 200
        """).fetchall()
        return [dict(t) for t in tasks]
    finally:
        conn.close()

def execute_raw_sql(sql: str):
    conn = get_db()
    try:
        cursor = conn.execute(sql)
        if cursor.description:
            rows = cursor.fetchall()
            return [dict(r) for r in rows]
        conn.commit()
        return {"affected_rows": cursor.rowcount}
    except Exception as e:
        return {"error": str(e)}
    finally:
        conn.close()

def clear_all_data():
    conn = get_db()
    try:
        conn.execute("DELETE FROM monitoring")
        conn.execute("DELETE FROM rate_limits")
        conn.execute("DELETE FROM task_versions")
        conn.execute("DELETE FROM file_uploads")
        conn.execute("DELETE FROM ai_usage_log")
        conn.execute("DELETE FROM public_api_keys")
        conn.execute("DELETE FROM deployments")
        conn.execute("DELETE FROM workflows")
        conn.execute("DELETE FROM system_prompts")
        conn.execute("DELETE FROM notifications")
        conn.execute("DELETE FROM user_sessions")
        conn.execute("DELETE FROM tasks")
        conn.execute("DELETE FROM projects")
        conn.execute("DELETE FROM users")
        conn.commit()
        return True
    except Exception as e:
        return False
    finally:
        conn.close()
