from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional
from database import get_system_prompts, create_system_prompt, delete_system_prompt
from middleware.auth import get_current_user

router = APIRouter()

class PromptRequest(BaseModel):
    name: str
    prompt: str
    task_type: str = "general"

@router.get("")
def list_prompts(user=Depends(get_current_user)):
    prompts = get_system_prompts(user["id"])
    return {"prompts": prompts}

@router.post("/create")
def create_prompt(req: PromptRequest, user=Depends(get_current_user)):
    if not req.name or len(req.name) > 100:
        raise HTTPException(400, "Nome inválido")
    if not req.prompt or len(req.prompt) > 10000:
        raise HTTPException(400, "Prompt inválido (max 10000 caracteres)")
    prompt_id = create_system_prompt(user["id"], req.name, req.prompt, req.task_type)
    return {"id": prompt_id, "message": "Prompt criado"}

@router.delete("/{prompt_id}")
def remove_prompt(prompt_id: int, user=Depends(get_current_user)):
    delete_system_prompt(prompt_id, user["id"])
    return {"message": "Prompt removido"}
