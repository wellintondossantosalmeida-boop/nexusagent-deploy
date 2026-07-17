from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional
from database import get_db
from middleware.auth import get_current_user

router = APIRouter()

class DeployRequest(BaseModel):
    project_id: int
    platform: str

SUPPORTED_PLATFORMS = ["vercel", "netlify", "render", "cloudflare_pages"]

@router.get("")
def list_deployments(user=Depends(get_current_user)):
    conn = get_db()
    try:
        deps = conn.execute("SELECT d.*, p.name as project_name FROM deployments d LEFT JOIN projects p ON d.project_id = p.id WHERE d.user_id = ? ORDER BY d.created_at DESC", (user["id"],)).fetchall()
        return {"deployments": [dict(d) for d in deps]}
    finally:
        conn.close()

@router.post("/create")
def create_deployment(req: DeployRequest, user=Depends(get_current_user)):
    if req.platform not in SUPPORTED_PLATFORMS:
        raise HTTPException(400, f"Plataforma não suportada. Use: {SUPPORTED_PLATFORMS}")
    conn = get_db()
    try:
        project = conn.execute("SELECT * FROM projects WHERE id = ? AND user_id = ?", (req.project_id, user["id"])).fetchone()
        if not project:
            raise HTTPException(404, "Projeto não encontrado")
        cursor = conn.execute("INSERT INTO deployments (user_id, project_id, platform, status) VALUES (?, ?, ?, 'pending')", (user["id"], req.project_id, req.platform))
        conn.commit()
        dep_id = cursor.lastrowid
        deploy = conn.execute("SELECT * FROM deployments WHERE id = ?", (dep_id,)).fetchone()
        return {"deployment": dict(deploy), "message": f"Deploy para {req.platform} criado. Configure as credenciais da plataforma em Configurações."}
    finally:
        conn.close()

@router.get("/{deploy_id}")
def get_deployment(deploy_id: int, user=Depends(get_current_user)):
    conn = get_db()
    try:
        dep = conn.execute("SELECT * FROM deployments WHERE id = ? AND user_id = ?", (deploy_id, user["id"])).fetchone()
    finally:
        conn.close()
    if not dep:
        raise HTTPException(404, "Deploy não encontrado")
    return {"deployment": dict(dep)}
