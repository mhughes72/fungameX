from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from ..auth import check_password, clear_session, require_user, set_session
from ..config import get_settings
from ..db import get_db
from ..models import Generation, Item, Source
from ..schemas import LoginIn, SettingsIn
from ..services import settings_store
from ..services.pipeline import month_spend

router = APIRouter(prefix="/api", tags=["misc"])


@router.get("/health")
def health():
    return {"ok": True}


@router.post("/auth/login")
def login(body: LoginIn, response: Response):
    if not check_password(body.password):
        raise HTTPException(401, "Wrong password")
    set_session(response)
    return {"ok": True}


@router.post("/auth/logout")
def logout(response: Response):
    clear_session(response)
    return {"ok": True}


@router.get("/auth/me", dependencies=[Depends(require_user)])
def me():
    return {"user": "owner"}


@router.get("/settings", dependencies=[Depends(require_user)])
def get_settings_route(db: Session = Depends(get_db)):
    return settings_store.get_all(db)


@router.put("/settings", dependencies=[Depends(require_user)])
def put_settings(body: SettingsIn, db: Session = Depends(get_db)):
    return settings_store.update(db, body.model_dump(exclude_none=True))


@router.get("/admin/status", dependencies=[Depends(require_user)])
def admin_status(db: Session = Depends(get_db)):
    s = get_settings()
    cap = float(settings_store.get_all(db).get("monthly_budget_usd") or 0)
    source_errors = db.query(Source).filter(Source.last_error.isnot(None)).order_by(Source.last_polled_at.desc()) \
        .limit(20).all()
    item_errors = db.query(Item).filter(Item.status == "extract_failed").order_by(Item.created_at.desc()) \
        .limit(20).all()
    recent_gens = db.query(Generation).order_by(Generation.created_at.desc()).limit(10).all()
    prices_set = any([s.openai_price_fast_input, s.openai_price_fast_output, s.openai_price_writer_input,
                      s.openai_price_writer_output])
    return {
        "openai_key_set": bool(s.openai_api_key),
        "models": {"fast": s.openai_model_fast, "writer": s.openai_model_writer},
        "prices_configured": prices_set,
        "jobs_mode": s.jobs_mode,
        "month_spend_usd": round(month_spend(db), 4),
        "monthly_budget_usd": cap,
        "source_errors": [{"id": x.id, "title": x.title or x.url, "error": x.last_error,
                           "at": x.last_polled_at} for x in source_errors],
        "item_errors": [{"id": x.id, "title": x.title, "error": x.error, "at": x.created_at} for x in item_errors],
        "recent_generations": [{"id": g.id, "item_id": g.item_id, "angle": g.angle, "model": g.model,
                                "cost_usd": g.cost_usd, "at": g.created_at} for g in recent_gens],
    }
