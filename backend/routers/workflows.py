import json
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from database import get_db
from middleware.auth import get_current_user
from services.ai_orchestrator import ai_orchestrator

router = APIRouter()

class WorkflowRequest(BaseModel):
    name: str
    steps: list

@router.get("")
def list_workflows(user=Depends(get_current_user)):
    conn = get_db()
    try:
        ws = conn.execute("SELECT * FROM workflows WHERE user_id = ? ORDER BY created_at DESC", (user["id"],)).fetchall()
        return {"workflows": [dict(w) for w in ws]}
    finally:
        conn.close()

@router.post("/create")
def create_workflow(req: WorkflowRequest, user=Depends(get_current_user)):
    if not req.name or len(req.name) > 100:
        raise HTTPException(400, "Nome inválido (1-100 caracteres)")
    if not req.steps or not isinstance(req.steps, list):
        raise HTTPException(400, "Steps deve ser uma lista não-vazia")
    conn = get_db()
    try:
        cursor = conn.execute("INSERT INTO workflows (user_id, name, steps_json) VALUES (?, ?, ?)", (user["id"], req.name, json.dumps(req.steps)))
        conn.commit()
        wf = conn.execute("SELECT * FROM workflows WHERE id = ?", (cursor.lastrowid,)).fetchone()
        return {"workflow": dict(wf)}
    finally:
        conn.close()

@router.post("/execute/{workflow_id}")
async def execute_workflow(workflow_id: int, user=Depends(get_current_user)):
    conn = get_db()
    try:
        wf = conn.execute("SELECT * FROM workflows WHERE id = ? AND user_id = ?", (workflow_id, user["id"])).fetchone()
        if not wf:
            raise HTTPException(404, "Workflow não encontrado")
        try:
            steps = json.loads(wf["steps_json"])
        except (json.JSONDecodeError, TypeError):
            raise HTTPException(400, "Steps inválidos no workflow")
    finally:
        conn.close()

    from database import get_user_api_keys
    api_keys = get_user_api_keys(user["id"])
    results = []
    for i, step in enumerate(steps):
        prompt = step.get("prompt", step.get("description", ""))
        task_type = step.get("task_type", "general_task")
        if not prompt:
            results.append({"step": i + 1, "status": "skipped", "error": "Sem prompt"})
            continue
        try:
            result = await ai_orchestrator.execute_task(task_type, [{"role": "system", "content": "Você é NexusAgent."}, {"role": "user", "content": prompt}], api_keys)
            results.append({"step": i + 1, "status": "completed" if result.get("success") else "failed", "content": result.get("content", "")[:2000], "error": result.get("error")})
        except Exception as e:
            results.append({"step": i + 1, "status": "failed", "error": str(e)})

    conn = get_db()
    try:
        conn.execute("UPDATE workflows SET status = 'completed', last_run = CURRENT_TIMESTAMP WHERE id = ?", (workflow_id,))
        conn.commit()
    finally:
        conn.close()
    return {"results": results, "status": "completed", "total_steps": len(steps)}

@router.delete("/{workflow_id}")
def delete_workflow(workflow_id: int, user=Depends(get_current_user)):
    conn = get_db()
    try:
        conn.execute("DELETE FROM workflows WHERE id = ? AND user_id = ?", (workflow_id, user["id"]))
        conn.commit()
    finally:
        conn.close()
    return {"message": "Workflow removido"}
