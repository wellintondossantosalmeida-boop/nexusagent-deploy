from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel
from middleware.auth import get_current_user
from database import check_rate_limit, is_admin_user
from config import RATE_LIMIT_TERMINAL, RATE_LIMIT_WINDOW

router = APIRouter()

class TerminalRequest(BaseModel):
    command: str
    timeout: int = 15

class FileRequest(BaseModel):
    path: str = "."

class FileReadRequest(BaseModel):
    path: str

class FileWriteRequest(BaseModel):
    path: str
    content: str

@router.post("/execute")
async def execute_command(req: TerminalRequest, request: Request, user=Depends(get_current_user)):
    ip = request.client.host if request.client else "unknown"
    if not is_admin_user(user["id"]):
        if not check_rate_limit(f"terminal:{user['id']}", "execute", RATE_LIMIT_TERMINAL, RATE_LIMIT_WINDOW):
            raise HTTPException(429, "Muitas requisições ao terminal. Aguarde 1 minuto.")
    from services.terminal import terminal
    result = await terminal.execute(req.command, min(req.timeout, 30))
    return result

@router.post("/files")
async def list_files(req: FileRequest, user=Depends(get_current_user)):
    from services.terminal import terminal
    files = terminal.list_files(req.path)
    return {"files": files, "path": req.path}

@router.post("/read")
async def read_file(req: FileReadRequest, user=Depends(get_current_user)):
    from services.terminal import terminal
    result = terminal.read_file(req.path)
    return result

@router.post("/write")
async def write_file(req: FileWriteRequest, user=Depends(get_current_user)):
    from services.terminal import terminal
    result = terminal.write_file(req.path, req.content)
    return result
