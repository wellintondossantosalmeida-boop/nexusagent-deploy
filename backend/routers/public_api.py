import hashlib
import time
from fastapi import APIRouter, HTTPException, Request, Depends
from pydantic import BaseModel
from typing import Optional
from database import get_db
from middleware.auth import get_current_user
from config import SECRET_KEY

router = APIRouter()

class PublicAPIKeyRequest(BaseModel):
    name: str
    permissions: str = "read"

def verify_public_api_key(key: str) -> Optional[dict]:
    key_hash = hashlib.sha256(key.encode()).hexdigest()[:32]
    conn = get_db()
    try:
        row = conn.execute("SELECT pak.*, u.username FROM public_api_keys pak JOIN users u ON pak.user_id = u.id WHERE pak.key_hash = ? AND pak.is_active = 1", (key_hash,)).fetchone()
        if row:
            conn.execute("UPDATE public_api_keys SET last_used = CURRENT_TIMESTAMP WHERE id = ?", (row["id"],))
            conn.commit()
            return dict(row)
        return None
    finally:
        conn.close()

@router.get("")
def list_api_keys(user=Depends(get_current_user)):
    conn = get_db()
    try:
        keys = conn.execute("SELECT id, name, permissions, last_used, created_at, is_active FROM public_api_keys WHERE user_id = ?", (user["id"],)).fetchall()
        return {"api_keys": [dict(k) for k in keys]}
    finally:
        conn.close()

@router.post("/create")
def create_api_key(req: PublicAPIKeyRequest, user=Depends(get_current_user)):
    import secrets
    raw_key = "nx_" + secrets.token_hex(24)
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()[:32]
    conn = get_db()
    try:
        conn.execute("INSERT INTO public_api_keys (user_id, key_hash, name, permissions) VALUES (?, ?, ?, ?)", (user["id"], key_hash, req.name, req.permissions))
        conn.commit()
    finally:
        conn.close()
    return {"key": raw_key, "name": req.name, "message": "Guarde esta chave. Ela não será mostrada novamente."}

@router.delete("/{key_id}")
def delete_api_key(key_id: int, user=Depends(get_current_user)):
    conn = get_db()
    try:
        conn.execute("DELETE FROM public_api_keys WHERE id = ? AND user_id = ?", (key_id, user["id"]))
        conn.commit()
    finally:
        conn.close()
    return {"message": "Chave removida"}
