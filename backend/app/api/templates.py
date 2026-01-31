import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.storage.db import init_db, get_conn
from app.api.strategies import build as strategies_build, BuildRequest  # reuse your builder endpoint function + model

router = APIRouter(prefix="/api/templates", tags=["templates"])

def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

@router.on_event("startup")
def _startup():
    init_db()

class TemplateSaveRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200, description="Friendly label, e.g. 'My weekly iron condor'")
    template_name: str = Field(..., min_length=1, max_length=80, description="Strategy template key, e.g. 'iron_condor'")
    params: Dict[str, Any] = Field(default_factory=dict)

class TemplateSummary(BaseModel):
    id: int
    name: str
    template_name: str
    created_at: str

class TemplateDetail(TemplateSummary):
    params: Dict[str, Any]

class TemplateBuildResponse(BaseModel):
    id: int
    name: str
    template_name: str
    params: Dict[str, Any]
    legs: Any  # legs list from strategies builder

@router.post("", response_model=TemplateSummary)
def save_template(req: TemplateSaveRequest):
    payload = {"template_name": req.template_name, "params": req.params}
    raw = json.dumps(payload)
    if len(raw) > 200_000:
        raise HTTPException(status_code=413, detail="template payload too large (max 200KB)")

    created_at = _utc_now_iso()
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO saved_items (name, kind, payload_json, created_at) VALUES (?, ?, ?, ?)",
            (req.name, "template", raw, created_at),
        )
        conn.commit()
        new_id = int(cur.lastrowid)

    return TemplateSummary(id=new_id, name=req.name, template_name=req.template_name, created_at=created_at)

@router.get("", response_model=List[TemplateSummary])
def list_templates(limit: int = 50, offset: int = 0):
    if limit < 1 or limit > 200:
        raise HTTPException(status_code=400, detail="limit must be 1..200")
    if offset < 0:
        raise HTTPException(status_code=400, detail="offset must be >= 0")

    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, name, payload_json, created_at FROM saved_items WHERE kind='template' ORDER BY id DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()

    out: List[TemplateSummary] = []
    for r in rows:
        payload = json.loads(r["payload_json"])
        out.append(
            TemplateSummary(
                id=int(r["id"]),
                name=r["name"],
                template_name=str(payload.get("template_name", "")),
                created_at=r["created_at"],
            )
        )
    return out

@router.get("/{template_id}", response_model=TemplateDetail)
def get_template(template_id: int):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT id, name, payload_json, created_at FROM saved_items WHERE kind='template' AND id=?",
            (template_id,),
        ).fetchone()

    if row is None:
        raise HTTPException(status_code=404, detail="not found")

    payload = json.loads(row["payload_json"])
    return TemplateDetail(
        id=int(row["id"]),
        name=row["name"],
        template_name=str(payload.get("template_name", "")),
        params=dict(payload.get("params", {})),
        created_at=row["created_at"],
    )

@router.post("/{template_id}/build", response_model=TemplateBuildResponse)
def build_from_template(template_id: int):
    # Load saved template+params
    detail = get_template(template_id)

    # Reuse your existing strategy builder (same logic as /api/strategies/build)
    built = strategies_build(BuildRequest(name=detail.template_name, params=detail.params))

    return TemplateBuildResponse(
        id=detail.id,
        name=detail.name,
        template_name=detail.template_name,
        params=detail.params,
        legs=built.legs,
    )
