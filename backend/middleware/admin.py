from fastapi import Depends, HTTPException, status
from middleware.auth import get_current_user
from database import is_admin_user

async def get_admin_user(user=Depends(get_current_user)):
    if not is_admin_user(user["id"]):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso negado. Apenas administradores podem acessar este recurso."
        )
    return user
