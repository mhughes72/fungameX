from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session, aliased, selectinload

from ..auth import require_user
from ..db import get_db
from ..jobs import enqueue
from ..models import Generation, Item, Source
from ..schemas import (DuplicateOut, FactsOut, GenerateIn, GenerationOut, InstructionIn, ItemDetailOut,
                       ItemListOut)
from ..services import pipeline
from ..services.ingest import process_item
from .errors import pipeline_errors

router = APIRouter(prefix="/api", tags=["items"], dependencies=[Depends(require_user)])


def _list_out(item: Item, dup_count: int = 0) -> ItemListOut:
    facts = item.latest_facts
    summary = facts.summary if facts else (item.feed_summary[:280] if item.feed_summary else None)
    return ItemListOut(id=item.id, source_id=item.source_id, source_title=item.source.title or item.source.url,
                       canonical_url=item.canonical_url, title=item.title, published_at=item.published_at,
                       status=item.status, error=item.error, summary=summary, created_at=item.created_at,
                       duplicate_count=dup_count)


@router.get("/items", response_model=list[ItemListOut])
def list_items(status: str | None = None, source_id: int | None = None, q: str | None = None,
               limit: int = 50, offset: int = 0, db: Session = Depends(get_db)):
    dup = aliased(Item)
    dup_counts = (db.query(dup.duplicate_of.label("orig"), func.count(dup.id).label("n"))
                  .filter(dup.duplicate_of.isnot(None)).group_by(dup.duplicate_of).subquery())
    query = (db.query(Item, func.coalesce(dup_counts.c.n, 0))
             .outerjoin(dup_counts, dup_counts.c.orig == Item.id)
             .options(selectinload(Item.source), selectinload(Item.facts))
             .filter(Item.duplicate_of.is_(None)))
    if status:
        query = query.filter(Item.status == status)
    else:
        query = query.filter(Item.status != "dismissed")
    if source_id:
        query = query.filter(Item.source_id == source_id)
    if q:
        query = query.filter(Item.title.ilike(f"%{q}%"))
    rows = (query.order_by(func.coalesce(Item.published_at, Item.created_at).desc(), Item.id.desc())
            .limit(min(limit, 200)).offset(offset).all())
    return [_list_out(item, n) for item, n in rows]


@router.get("/items/{item_id}", response_model=ItemDetailOut)
def get_item(item_id: int, db: Session = Depends(get_db)):
    item = db.get(Item, item_id)
    if item is None:
        raise HTTPException(404, "Item not found")
    dups = db.query(Item).filter(Item.duplicate_of == item.id).all()
    gens = (db.query(Generation).filter(Generation.item_id == item.id).options(selectinload(Generation.posts))
            .order_by(Generation.id.desc()).all())
    base = _list_out(item, len(dups))
    facts = item.latest_facts
    return ItemDetailOut(
        **base.model_dump(), author=item.author, raw_text=item.raw_text,
        facts=FactsOut.model_validate(facts) if facts else None,
        generations=[GenerationOut.model_validate(g) for g in gens],
        duplicates=[DuplicateOut(id=d.id, source_title=d.source.title or d.source.url,
                                 canonical_url=d.canonical_url, title=d.title) for d in dups],
    )


@router.post("/items/{item_id}/dismiss", response_model=ItemListOut)
def dismiss_item(item_id: int, db: Session = Depends(get_db)):
    item = db.get(Item, item_id)
    if item is None:
        raise HTTPException(404, "Item not found")
    item.status = "dismissed"
    db.commit()
    return _list_out(item)


@router.post("/items/{item_id}/restore", response_model=ItemListOut)
def restore_item(item_id: int, db: Session = Depends(get_db)):
    item = db.get(Item, item_id)
    if item is None:
        raise HTTPException(404, "Item not found")
    item.status = "extracted" if item.latest_facts and item.latest_facts.claims else "new"
    db.commit()
    return _list_out(item)


@router.post("/items/{item_id}/retry", status_code=202)
def retry_item(item_id: int, db: Session = Depends(get_db)):
    """Re-fetch and re-extract (e.g. after a fetch failure or once an API key is set)."""
    item = db.get(Item, item_id)
    if item is None:
        raise HTTPException(404, "Item not found")
    item.status, item.error = "new", None
    db.commit()
    enqueue(process_item, item.id)
    return {"queued": True}


@router.post("/items/{item_id}/generate", response_model=GenerationOut)
def generate(item_id: int, body: GenerateIn, db: Session = Depends(get_db)):
    opts = body.model_dump(exclude_none=True, exclude={"instruction"})
    with pipeline_errors():
        gen = pipeline.generate(db, item_id, opts, body.instruction)
    return GenerationOut.model_validate(gen)


@router.post("/generations/{generation_id}/regenerate", response_model=GenerationOut)
def regenerate_all(generation_id: int, body: InstructionIn, db: Session = Depends(get_db)):
    with pipeline_errors():
        gen = pipeline.regenerate_all(db, generation_id, body.instruction)
    return GenerationOut.model_validate(gen)


