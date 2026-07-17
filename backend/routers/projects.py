import os
import json
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, List
from database import create_project, get_user_projects, get_db
from middleware.auth import get_current_user
from engines.code_generator import code_generator

router = APIRouter()

class ProjectRequest(BaseModel):
    name: str
    description: str
    project_type: str = "vanilla_html"
    features: List[str] = []

@router.post("/create")
async def create_new_project(req: ProjectRequest, user=Depends(get_current_user)):
    if len(req.name) > 100:
        raise HTTPException(400, "Nome do projeto muito longo")
    if len(req.description) > 2000:
        raise HTTPException(400, "Descrição muito longa")
    project = create_project(user["id"], req.name, req.description, req.project_type, json.dumps({"features": req.features}))
    if not project:
        raise HTTPException(500, "Erro ao criar projeto")
    try:
        result = await code_generator.generate_project(req.project_type, req.name, req.description, req.features, None)
    except Exception as e:
        conn = get_db()
        try:
            conn.execute("UPDATE projects SET status = 'failed' WHERE id = ?", (project["id"],))
            conn.commit()
        finally:
            conn.close()
        return {"project": project, "generation": {"success": False, "error": str(e)}}
    conn = get_db()
    try:
        conn.execute("UPDATE projects SET output_path = ?, status = ? WHERE id = ?", (result.get("project_dir", ""), "completed" if result["success"] else "failed", project["id"]))
        conn.commit()
    finally:
        conn.close()
    return {"project": project, "generation": result}

@router.get("/list")
def list_projects(user=Depends(get_current_user)):
    projects = get_user_projects(user["id"])
    return {"projects": projects, "count": len(projects)}

@router.get("/templates/list")
def get_templates():
    return {"templates": [
        {"id": "react", "name": "React + Vite", "description": "App React moderno com Vite"},
        {"id": "nextjs", "name": "Next.js", "description": "Framework React full-stack"},
        {"id": "vue", "name": "Vue.js", "description": "Framework reativo progressivo"},
        {"id": "svelte", "name": "Svelte", "description": "Framework ultracompilado"},
        {"id": "vanilla_html", "name": "HTML/CSS/JS", "description": "Site vanilla puro"},
        {"id": "flask", "name": "Flask (Python)", "description": "Backend Python leve"},
        {"id": "fastapi", "name": "FastAPI (Python)", "description": "API Python assíncrona"},
        {"id": "node_express", "name": "Node.js Express", "description": "Backend JavaScript"},
        {"id": "android_kotlin", "name": "Android Kotlin", "description": "App Android nativo"},
        {"id": "python_cli", "name": "Python CLI", "description": "Ferramenta de linha de comando"},
    ]}

@router.get("/{project_id}")
def get_project(project_id: int, user=Depends(get_current_user)):
    conn = get_db()
    try:
        project = conn.execute("SELECT * FROM projects WHERE id = ? AND user_id = ?", (project_id, user["id"])).fetchone()
    finally:
        conn.close()
    if not project:
        raise HTTPException(404, "Projeto não encontrado")
    return {"project": dict(project)}
