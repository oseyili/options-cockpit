import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.storage.db import init_db, get_conn

router = APIRouter(prefix="/api/saved", tags=["saved"])

Kind = Literal["strategy", "portfolio", "note"]

class SavedCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    kind: Kind = "strategy"
    payload: Dict[str, Any] = Field(default_factory=dict)

class SavedItemSummary(BaseModel):
    id: int
    name: str
    kind: Kind
    created_at: str

class SavedItemDetail(SavedItemSummary):
    payload: Dict[str, Any]

class ExportBundle(BaseModel):
    exported_at: str
    items: List[SavedItemDetail]

class ImportRequest(BaseModel):
    exported_at: Optional[str] = None
    items: List[SavedItemDetail] = Field(default_factory=list)

class ImportResponse(BaseModel):
    imported: int
    new_ids: List[int]

def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

@router.on_event("startup")
def _startup():
    init_db()

# -------------------------
# NEW: export/import/clear
# IMPORTANT: defined BEFORE /{item_id}
# -------------------------

@router.get("/export", response_model=ExportBundle)
def export_all():
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, name, kind, payload_json, created_at FROM saved_items ORDER BY id ASC"
        ).fetchall()

    items: List[SavedItemDetail] = []
    for r in rows:
        items.append(
            SavedItemDetail(
                id=int(r["id"]),
                name=r["name"],
                kind=r["kind"],
                created_at=r["created_at"],
                payload=json.loads(r["payload_json"]),
            )
        )

    return ExportBundle(exported_at=_utc_now_iso(), items=items)

@router.post("/import", response_model=ImportResponse)
def import_all(req: ImportRequest):
    new_ids: List[int] = []
    with get_conn() as conn:
        for item in req.items:
            raw = json.dumps(item.payload)
            if len(raw) > 200_000:
                raise HTTPException(status_code=413, detail=f"payload too large for item '{item.name}' (max 200KB)")
            created_at = item.created_at or _utc_now_iso()

            cur = conn.execute(
                "INSERT INTO saved_items (name, kind, payload_json, created_at) VALUES (?, ?, ?, ?)",
                (item.name, item.kind, raw, created_at),
            )
            new_ids.append(int(cur.lastrowid))
        conn.commit()

    return ImportResponse(imported=len(new_ids), new_ids=new_ids)

@router.delete("/clear")
def clear_all():
    with get_conn() as conn:
        conn.execute("DELETE FROM saved_items")
        conn.commit()
    return {"cleared": True}

# -------------------------
# Existing CRUD
# -------------------------

@router.post("", response_model=SavedItemSummary)
def create(req: SavedCreateRequest):
    raw = json.dumps(req.payload)
    if len(raw) > 200_000:
        raise HTTPException(status_code=413, detail="payload too large (max 200KB)")

    created_at = _utc_now_iso()
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO saved_items (name, kind, payload_json, created_at) VALUES (?, ?, ?, ?)",
            (req.name, req.kind, raw, created_at),
        )
        conn.commit()
        new_id = int(cur.lastrowid)

    return SavedItemSummary(id=new_id, name=req.name, kind=req.kind, created_at=created_at)

@router.get("", response_model=List[SavedItemSummary])
def list_items(limit: int = 50, offset: int = 0, kind: Optional[Kind] = None):
    if limit < 1 or limit > 200:
        raise HTTPException(status_code=400, detail="limit must be 1..200")
    if offset < 0:
        raise HTTPException(status_code=400, detail="offset must be >= 0")

    with get_conn() as conn:
        if kind is None:
            rows = conn.execute(
                "SELECT id, name, kind, created_at FROM saved_items ORDER BY id DESC LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT id, name, kind, created_at FROM saved_items WHERE kind=? ORDER BY id DESC LIMIT ? OFFSET ?",
                (kind, limit, offset),
            ).fetchall()

    return [SavedItemSummary(**dict(r)) for r in rows]

@router.get("/{item_id}", response_model=SavedItemDetail)
def get_item(item_id: int):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT id, name, kind, payload_json, created_at FROM saved_items WHERE id=?",
            (item_id,),
        ).fetchone()

    if row is None:
        raise HTTPException(status_code=404, detail="not found")

    payload = json.loads(row["payload_json"])
    return SavedItemDetail(
        id=row["id"],
        name=row["name"],
        kind=row["kind"],
        created_at=row["created_at"],
        payload=payload,
    )

@router.delete("/{item_id}")
def delete_item(item_id: int):
    with get_conn() as conn:
        cur = conn.execute("DELETE FROM saved_items WHERE id=?", (item_id,))
        conn.commit()

    if cur.rowcount == 0:
        raise HTTPException(status_code=404, detail="not found")

    return {"deleted": True, "id": item_id}
