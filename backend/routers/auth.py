import hashlib
from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel
from typing import Optional
from database import (create_user, authenticate_user, get_user_by_id, get_user_api_keys,
                       save_user_api_keys, check_rate_limit, create_session,
                       get_user_sessions, revoke_session, revoke_all_sessions, get_db)
from middleware.auth import get_current_user, create_access_token, decode_token
from config import RATE_LIMIT_LOGIN, RATE_LIMIT_REGISTER, RATE_LIMIT_WINDOW

router = APIRouter()

class RegisterRequest(BaseModel):
    username: str
    email: str
    password: str
    full_name: Optional[str] = ""

class LoginRequest(BaseModel):
    username: str
    password: str

class APIKeysUpdate(BaseModel):
    groq: Optional[str] = ""
    google_gemini: Optional[str] = ""
    deepseek: Optional[str] = ""
    mistral: Optional[str] = ""
    together: Optional[str] = ""
    openrouter: Optional[str] = ""
    huggingface: Optional[str] = ""
    cohere: Optional[str] = ""
    novita: Optional[str] = ""
    chutes: Optional[str] = ""
    siliconflow: Optional[str] = ""
    aiml: Optional[str] = ""
    cloudflare_workers_ai: Optional[str] = ""
    github_copilot: Optional[str] = ""
    perplexity: Optional[str] = ""

@router.post("/register")
def register(req: RegisterRequest, request: Request):
    ip = request.client.host if request.client else "unknown"
    if not check_rate_limit(ip, "register", RATE_LIMIT_REGISTER, RATE_LIMIT_WINDOW):
        raise HTTPException(429, "Muitas tentativas de registro. Aguarde 1 minuto.")
    if len(req.username) < 3:
        raise HTTPException(400, "Username deve ter pelo menos 3 caracteres")
    if len(req.password) < 6:
        raise HTTPException(400, "Senha deve ter pelo menos 6 caracteres")
    if "@" not in req.email or "." not in req.email:
        raise HTTPException(400, "Email inválido")
    if len(req.username) > 50:
        raise HTTPException(400, "Username muito longo (max 50)")
    if len(req.password) > 128:
        raise HTTPException(400, "Senha muito longa (max 128)")
    user = create_user(req.username, req.email, req.password, req.full_name)
    if not user:
        raise HTTPException(400, "Username ou email já existe")
    token = create_access_token({"sub": str(user["id"])})
    create_session(user["id"], token, ip)
    return {"access_token": token, "token_type": "bearer", "user": {"id": user["id"], "username": user["username"], "email": user["email"], "full_name": user["full_name"]}}

@router.post("/login")
def login(req: LoginRequest, request: Request):
    ip = request.client.host if request.client else "unknown"
    if not check_rate_limit(ip, "login", RATE_LIMIT_LOGIN, RATE_LIMIT_WINDOW):
        raise HTTPException(429, "Muitas tentativas de login. Aguarde 1 minuto.")
    user = authenticate_user(req.username, req.password)
    if not user:
        raise HTTPException(401, "Credenciais inválidas")
    token = create_access_token({"sub": str(user["id"])})
    ua = request.headers.get("User-Agent", "")
    create_session(user["id"], token, ip, ua)
    return {"access_token": token, "token_type": "bearer", "user": {"id": user["id"], "username": user["username"], "email": user["email"], "full_name": user["full_name"]}}

@router.get("/me")
def get_me(user=Depends(get_current_user)):
    keys = get_user_api_keys(user["id"])
    safe_keys = {k: ("***" + v[-4:] if len(v) > 4 else "Configurada") for k, v in keys.items() if v}
    return {"id": user["id"], "username": user["username"], "email": user["email"], "full_name": user["full_name"], "total_tasks": user["total_tasks"], "total_tokens_used": user["total_tokens_used"], "api_keys_configured": safe_keys, "created_at": user["created_at"]}

@router.put("/api-keys")
def update_api_keys(req: APIKeysUpdate, user=Depends(get_current_user)):
    keys = {k: v.strip() for k, v in req.dict().items() if v and v.strip()}
    save_user_api_keys(user["id"], keys)
    return {"message": "API keys atualizadas", "configured": list(keys.keys())}

@router.get("/api-keys")
def get_api_keys(user=Depends(get_current_user)):
    keys = get_user_api_keys(user["id"])
    safe_keys = {}
    for k, v in keys.items():
        if v and len(v) > 4:
            safe_keys[k] = v[:4] + "***" + v[-4:]
        elif v:
            safe_keys[k] = "Configurada"
    return {"keys": safe_keys}

@router.get("/sessions")
def list_sessions(user=Depends(get_current_user)):
    sessions = get_user_sessions(user["id"])
    return {"sessions": sessions}

@router.post("/sessions/{session_id}/revoke")
def revoke_user_session(session_id: int, user=Depends(get_current_user)):
    revoke_session(session_id, user["id"])
    return {"message": "Sessão revogada"}

@router.post("/sessions/revoke-all")
def revoke_all(user=Depends(get_current_user)):
    revoke_all_sessions(user["id"])
    return {"message": "Todas as sessões foram revogadas"}

@router.post("/change-password")
def change_password(req: LoginRequest, user=Depends(get_current_user)):
    from database import hash_password, get_db
    if len(req.password) < 6:
        raise HTTPException(400, "Nova senha deve ter pelo menos 6 caracteres")
    new_hash = hash_password(req.password)
    conn = get_db()
    try:
        conn.execute("UPDATE users SET password_hash = ? WHERE id = ?", (new_hash, user["id"]))
        conn.commit()
    finally:
        conn.close()
    revoke_all_sessions(user["id"])
    return {"message": "Senha alterada. Faça login novamente."}
