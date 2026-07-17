from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from middleware.auth import get_current_user

router = APIRouter()

class CodeExecRequest(BaseModel):
    code: str
    language: str = "python"
    timeout: int = 15

@router.post("/execute")
async def execute_code(req: CodeExecRequest, user=Depends(get_current_user)):
    from services.code_sandbox import code_sandbox
    result = await code_sandbox.execute(req.code, req.language, min(req.timeout, 30))
    return result

@router.get("/languages")
def get_languages():
    from services.code_sandbox import code_sandbox
    return {"languages": code_sandbox.get_languages()}
