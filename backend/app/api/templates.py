import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
import urllib.request

from app.storage.db import init_db, get_conn
from app.api.strategies import _build as build_legs_from_template  # internal builder (pure)

router = APIRouter(prefix="/api/templates", tags=["templates"])

def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

@router.on_event("startup")
def _startup():
    init_db()

class TemplateSaveRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    template_name: str = Field(..., min_length=1, max_length=80)
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
    legs: Any

class TemplatePriceRequest(BaseModel):
    underlying: float = Field(..., gt=0)
    curve: Optional[Dict[str, Any]] = None  # {steps, s_min?, s_max?}

# Keep it flexible so we don't crash on response shape changes
class TemplatePriceResponse(BaseModel):
    id: int
    name: str
    template_name: str
    params: Dict[str, Any]
    legs: Any
    pricing: Dict[str, Any]

def _load_template(template_id: int) -> TemplateDetail:
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

def _post_json(url: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = resp.read().decode("utf-8")
            return json.loads(data) if data else {}
    except urllib.error.HTTPError as e:
        try:
            detail = e.read().decode("utf-8")
        except Exception:
            detail = str(e)
        raise HTTPException(status_code=502, detail=f"Upstream error calling {url}: {detail}")
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Upstream connection error calling {url}: {e}")

@router.post("", response_model=TemplateSummary)
def save_template(req: TemplateSaveRequest):
    raw = json.dumps({"template_name": req.template_name, "params": req.params})
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
    return _load_template(template_id)

@router.post("/{template_id}/build", response_model=TemplateBuildResponse)
def build_from_template(template_id: int):
    detail = _load_template(template_id)
    legs_models = build_legs_from_template(detail.template_name, detail.params)
    legs = [l.model_dump() for l in legs_models]
    return TemplateBuildResponse(
        id=detail.id,
        name=detail.name,
        template_name=detail.template_name,
        params=detail.params,
        legs=legs,
    )

@router.post("/{template_id}/price", response_model=TemplatePriceResponse)
def price_template(template_id: int, req: TemplatePriceRequest):
    detail = _load_template(template_id)

    # 1) Build legs locally
    legs_models = build_legs_from_template(detail.template_name, detail.params)
    legs = [l.model_dump() for l in legs_models]

    # 2) Call the existing, proven pricer endpoint
    import os
    base_url = os.getenv("BASE_URL", "https://options-cockpit.onrender.com").rstrip("/")
    pricing_url = f"{base_url}/api/pl/portfolio"

    payload = {
        "underlying": req.underlying,
        "legs": legs,
        "curve": req.curve,  # can be None; pricer should handle it
    }
    pricing = _post_json(pricing_url, payload)

    return TemplatePriceResponse(
        id=detail.id,
        name=detail.name,
        template_name=detail.template_name,
        params=detail.params,
        legs=legs,
        pricing=pricing,
    )
