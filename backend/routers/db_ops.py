from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel
from typing import Optional
from database import get_db
from middleware.auth import get_current_user
import json

router = APIRouter()

class QueryRequest(BaseModel):
    query: str
    params: list = []

class ExecuteRequest(BaseModel):
    statements: list

@router.get("/tables")
def list_tables(user=Depends(get_current_user)):
    conn = get_db()
    try:
        tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name").fetchall()
        result = []
        for t in tables:
            name = t["name"]
            count = conn.execute(f"SELECT COUNT(*) as c FROM [{name}]").fetchone()["c"]
            columns = [row[1] for row in conn.execute(f"PRAGMA table_info([{name}])").fetchall()]
            result.append({"name": name, "row_count": count, "columns": columns})
        return {"tables": result}
    finally:
        conn.close()

@router.post("/query")
def execute_query(req: QueryRequest, user=Depends(get_current_user)):
    query = req.query.strip()
    if not query:
        raise HTTPException(400, "Query vazia")
    upper = query.upper()
    forbidden = ["DROP", "DELETE", "TRUNCATE", "ALTER", "INSERT", "UPDATE", "ATTACH", "DETACH"]
    for word in forbidden:
        if word in upper:
            raise HTTPException(403, f"Operação '{word}' não permitida. Apenas SELECT é permitido.")
    if not upper.startswith("SELECT"):
        raise HTTPException(403, "Apenas consultas SELECT são permitidas")
    conn = get_db()
    try:
        try:
            rows = conn.execute(query, req.params).fetchall()
            return {"rows": [dict(r) for r in rows[:1000]], "count": len(rows)}
        except Exception as e:
            raise HTTPException(400, f"Erro na query: {str(e)}")
    finally:
        conn.close()

@router.get("/table/{table_name}")
def get_table_data(table_name: str, user=Depends(get_current_user), limit: int = 100, offset: int = 0):
    conn = get_db()
    try:
        tables = [t["name"] for t in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
        if table_name not in tables:
            raise HTTPException(404, "Tabela não encontrada")
        rows = conn.execute(f"SELECT * FROM [{table_name}] LIMIT ? OFFSET ?", (min(limit, 1000), offset)).fetchall()
        total = conn.execute(f"SELECT COUNT(*) as c FROM [{table_name}]").fetchone()["c"]
        columns = [row[1] for row in conn.execute(f"PRAGMA table_info([{table_name}])").fetchall()]
        return {"rows": [dict(r) for r in rows], "total": total, "columns": columns, "limit": limit, "offset": offset}
    finally:
        conn.close()
