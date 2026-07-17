import os
import json
import uuid
import re
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, List
from database import (create_task, update_task, get_user_tasks, get_user_api_keys, log_ai_usage,
                       get_db, check_rate_limit, create_task_version, get_task_versions,
                       create_notification, is_admin_user)
from middleware.auth import get_current_user
from services.task_executor import task_executor
from services.ai_orchestrator import ai_orchestrator
from config import RATE_LIMIT_AI, RATE_LIMIT_WINDOW, UPLOAD_DIR

router = APIRouter()

def sanitize_filename(name: str) -> str:
    name = os.path.basename(name)
    name = re.sub(r'[/\\:*?"<>|]', '', name)
    name = name.strip('. ')
    if not name:
        name = "upload"
    return name[:200]

class TaskRequest(BaseModel):
    title: str
    description: str
    task_type: str = "general_task"
    priority: int = 5
    preferred_model: Optional[str] = None
    context: Optional[dict] = None
    system_prompt_id: Optional[int] = None

class QuickTaskRequest(BaseModel):
    prompt: str
    task_type: str = "general_task"
    preferred_model: Optional[str] = None
    force_provider: Optional[str] = None
    system_prompt_id: Optional[int] = None

@router.post("/create")
async def create_new_task(req: TaskRequest, user=Depends(get_current_user)):
    task = create_task(user["id"], req.title, req.description, req.task_type, json.dumps(req.context or {}), req.priority)
    if not task:
        raise HTTPException(500, "Erro ao criar tarefa")
    return {"task": task, "message": "Tarefa criada. Use /execute/{task_id} para executar."}

@router.post("/execute/{task_id}")
async def execute_task_endpoint(task_id: int, user=Depends(get_current_user)):
    conn = get_db()
    try:
        task_row = conn.execute("SELECT * FROM tasks WHERE id = ? AND user_id = ?", (task_id, user["id"])).fetchone()
    finally:
        conn.close()
    if not task_row:
        raise HTTPException(404, "Tarefa não encontrada")
    task = dict(task_row)
    api_keys = get_user_api_keys(user["id"])
    try:
        files = json.loads(task.get("files_json", "[]"))
    except (json.JSONDecodeError, TypeError):
        files = []
    try:
        context = json.loads(task["input_data"]) if task.get("input_data") else {}
    except (json.JSONDecodeError, TypeError):
        context = {}
    update_task(task_id, status="running", progress=0)
    result = await task_executor.execute(
        task_type=task["task_type"], description=task["description"],
        user_id=user["id"], user_api_keys=api_keys, files=files, context=context
    )
    if result["success"]:
        update_task(task_id, status="completed", output_data=result.get("content", ""), ai_provider_used=result.get("provider"), ai_model_used=result.get("model"), tokens_used=result.get("tokens_input", 0) + result.get("tokens_output", 0), execution_time_ms=result.get("execution_time_ms", 0), completed_at=datetime.now(timezone.utc).isoformat(), progress=100)
        log_ai_usage(user["id"], result.get("provider", ""), result.get("model", ""), result.get("tokens_input", 0), result.get("tokens_output", 0), result.get("execution_time_ms", 0), True, None, task_id)
        create_task_version(task_id, result.get("content", ""))
        conn = get_db()
        try:
            conn.execute("UPDATE users SET total_tasks = total_tasks + 1 WHERE id = ?", (user["id"],))
            conn.commit()
        finally:
            conn.close()
        create_notification(user["id"], "Tarefa concluída", f"Tarefa '{task['title']}' executada com sucesso via {result.get('provider', 'N/A')}", "success")
    else:
        update_task(task_id, status="failed", error_message=result.get("error", "Erro desconhecido"))
        log_ai_usage(user["id"], result.get("provider", ""), result.get("model", ""), 0, 0, result.get("execution_time_ms", 0), False, result.get("error"), task_id)
        create_notification(user["id"], "Tarefa falhou", f"Erro: {result.get('error', 'Desconhecido')}", "error")
    return result

@router.post("/quick")
async def quick_task(req: QuickTaskRequest, request: Request, user=Depends(get_current_user)):
    ip = request.client.host if request.client else "unknown"
    if not is_admin_user(user["id"]):
        if not check_rate_limit(f"ai:{user['id']}", "quick", RATE_LIMIT_AI, RATE_LIMIT_WINDOW):
            raise HTTPException(429, "Muitas requisições. Aguarde 1 minuto.")
    api_keys = get_user_api_keys(user["id"])
    system_prompt = task_executor._build_system_prompt(req.task_type)
    messages = task_executor._build_messages(system_prompt, req.prompt)
    result = await ai_orchestrator.execute_task(req.task_type, messages, api_keys, req.preferred_model, req.force_provider)
    result["execution_time_ms"] = result.get("latency_ms", 0)
    if result["success"]:
        conn = get_db()
        try:
            conn.execute("UPDATE users SET total_tasks = total_tasks + 1 WHERE id = ?", (user["id"],))
            conn.commit()
        finally:
            conn.close()
        log_ai_usage(user["id"], result.get("provider", ""), result.get("model", ""), result.get("tokens_input", 0), result.get("tokens_output", 0), result.get("execution_time_ms", 0), True)
    return result

@router.post("/execute-raw")
async def execute_raw(prompt: str = Form(...), task_type: str = Form("general_task"), force_provider: str = Form(""), files: List[UploadFile] = File(default=[]), user=Depends(get_current_user)):
    api_keys = get_user_api_keys(user["id"])
    saved_files = []
    for upload_file in files:
        if upload_file.size and upload_file.size > 500 * 1024 * 1024:
            continue
        safe_name = sanitize_filename(upload_file.filename or "upload")
        safe_name = uuid.uuid4().hex[:8] + "_" + safe_name
        upload_path = str(UPLOAD_DIR / f"{user['id']}_{safe_name}")
        try:
            content = await upload_file.read()
            with open(upload_path, "wb") as f:
                f.write(content)
            saved_files.append(upload_path)
            conn = get_db()
            try:
                conn.execute("INSERT INTO file_uploads (user_id, filename, original_name, file_size, upload_path) VALUES (?, ?, ?, ?, ?)", (user["id"], safe_name, upload_file.filename or "upload", len(content), upload_path))
                conn.commit()
            finally:
                conn.close()
        except Exception:
            continue
    system_prompt = task_executor._build_system_prompt(task_type)
    messages = task_executor._build_messages(system_prompt, prompt)
    result = await ai_orchestrator.execute_task(task_type, messages, api_keys, force_provider=force_provider or None)
    result["execution_time_ms"] = result.get("latency_ms", 0)
    if result["success"]:
        conn = get_db()
        try:
            conn.execute("UPDATE users SET total_tasks = total_tasks + 1 WHERE id = ?", (user["id"],))
            conn.commit()
        finally:
            conn.close()
        log_ai_usage(user["id"], result.get("provider", ""), result.get("model", ""), result.get("tokens_input", 0), result.get("tokens_output", 0), result.get("execution_time_ms", 0), True)
    return result

@router.post("/execute-stream")
async def execute_stream(req: QuickTaskRequest, request: Request, user=Depends(get_current_user)):
    ip = request.client.host if request.client else "unknown"
    if not is_admin_user(user["id"]):
        if not check_rate_limit(f"ai:{user['id']}", "stream", RATE_LIMIT_AI, RATE_LIMIT_WINDOW):
            raise HTTPException(429, "Muitas requisições. Aguarde 1 minuto.")
    api_keys = get_user_api_keys(user["id"])

    async def event_generator():
        system = task_executor._build_system_prompt(req.task_type)
        messages = task_executor._build_messages(system, req.prompt)
        async for chunk in ai_orchestrator.execute_task_stream(req.task_type, messages, api_keys, req.preferred_model, req.force_provider):
            yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"})

@router.get("/history")
def task_history(user=Depends(get_current_user), limit: int = 50):
    tasks = get_user_tasks(user["id"], min(limit, 200))
    return {"tasks": tasks, "count": len(tasks)}

@router.get("/{task_id}/versions")
def task_versions(task_id: int, user=Depends(get_current_user)):
    conn = get_db()
    try:
        task = conn.execute("SELECT id FROM tasks WHERE id = ? AND user_id = ?", (task_id, user["id"])).fetchone()
    finally:
        conn.close()
    if not task:
        raise HTTPException(404, "Tarefa não encontrada")
    versions = get_task_versions(task_id)
    return {"versions": versions}

@router.get("/providers")
def list_providers(user=Depends(get_current_user)):
    api_keys = get_user_api_keys(user["id"])
    status = ai_orchestrator.get_provider_status(api_keys)
    return {"providers": status, "total": len(status)}

@router.get("/task-types")
def get_task_types():
    return {"types": [
        {"id": "code_generation", "name": "Geração de Código", "icon": "code"},
        {"id": "code_review", "name": "Revisão de Código", "icon": "search"},
        {"id": "website_creation", "name": "Criar Website", "icon": "globe"},
        {"id": "app_creation", "name": "Criar App", "icon": "smartphone"},
        {"id": "apk_creation", "name": "Criar APK Android", "icon": "android"},
        {"id": "file_analysis", "name": "Analisar Arquivo", "icon": "file"},
        {"id": "data_processing", "name": "Processar Dados", "icon": "database"},
        {"id": "code_refactor", "name": "Refatorar Código", "icon": "refresh"},
        {"id": "bug_fix", "name": "Corrigir Bug", "icon": "bug"},
        {"id": "api_design", "name": "Projetar API", "icon": "link"},
        {"id": "database_design", "name": "Projetar Banco", "icon": "server"},
        {"id": "documentation", "name": "Documentação", "icon": "book"},
        {"id": "testing", "name": "Criar Testes", "icon": "check"},
        {"id": "deployment", "name": "Deploy/DevOps", "icon": "cloud"},
        {"id": "optimization", "name": "Otimizar", "icon": "zap"},
        {"id": "security_review", "name": "Review Segurança", "icon": "shield"},
        {"id": "ui_design", "name": "Design UI/UX", "icon": "palette"},
        {"id": "general_task", "name": "Tarefa Geral", "icon": "cpu"},
    ]}
