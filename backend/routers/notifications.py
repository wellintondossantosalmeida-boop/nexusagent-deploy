from fastapi import APIRouter, Depends
from database import get_db
from middleware.auth import get_current_user

router = APIRouter()

@router.get("")
def get_notifications(user=Depends(get_current_user)):
    conn = get_db()
    try:
        notifs = conn.execute("SELECT * FROM notifications WHERE user_id = ? ORDER BY created_at DESC LIMIT 50", (user["id"],)).fetchall()
        unread = conn.execute("SELECT COUNT(*) as c FROM notifications WHERE user_id = ? AND read = 0", (user["id"],)).fetchone()["c"]
        return {"notifications": [dict(n) for n in notifs], "unread": unread}
    finally:
        conn.close()

@router.post("/mark-read")
def mark_read(user=Depends(get_current_user)):
    conn = get_db()
    try:
        conn.execute("UPDATE notifications SET read = 1 WHERE user_id = ?", (user["id"],))
        conn.commit()
        return {"message": "Notificações marcadas como lidas"}
    finally:
        conn.close()

@router.post("/{notif_id}/read")
def mark_single_read(notif_id: int, user=Depends(get_current_user)):
    conn = get_db()
    try:
        conn.execute("UPDATE notifications SET read = 1 WHERE id = ? AND user_id = ?", (notif_id, user["id"]))
        conn.commit()
        return {"message": "Notificação marcada como lida"}
    finally:
        conn.close()
