from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..auth import require_user
from ..db import get_db
from ..jobs import enqueue
from ..models import Item, Source
from ..schemas import PreviewIn, SourceIn, SourceOut, SourcePatch
from ..services.fetch import FetchError
from ..services.ingest import create_url_item, poll_source, preview_feed, process_item
from ..services.urls import canonicalize, is_http_url

router = APIRouter(prefix="/api/sources", tags=["sources"], dependencies=[Depends(require_user)])


def _out(source: Source, count: int) -> SourceOut:
    out = SourceOut.model_validate(source)
    out.item_count = count
    return out


def _counts(db: Session) -> dict[int, int]:
    rows = db.query(Item.source_id, func.count(Item.id)).filter(Item.duplicate_of.is_(None)) \
        .group_by(Item.source_id).all()
    return dict(rows)


@router.get("", response_model=list[SourceOut])
def list_sources(type: str | None = None, db: Session = Depends(get_db)):
    q = db.query(Source)
    if type:
        q = q.filter(Source.type == type)
    counts = _counts(db)
    return [_out(s, counts.get(s.id, 0)) for s in q.order_by(Source.created_at.desc()).all()]


@router.post("/preview")
def preview(body: PreviewIn):
    if not is_http_url(body.url):
        raise HTTPException(400, "Enter a full URL starting with http:// or https://")
    try:
        return preview_feed(body.url.strip())
    except FetchError as e:
        raise HTTPException(400, f"Couldn't read that feed: {e}")


@router.post("", response_model=SourceOut, status_code=201)
def create_source(body: SourceIn, db: Session = Depends(get_db)):
    url = body.url.strip()
    if not is_http_url(url):
        raise HTTPException(400, "Enter a full URL starting with http:// or https://")
    if body.type == "rss":
        if db.query(Source).filter(Source.type == "rss", Source.url == url).first():
            raise HTTPException(409, "That feed is already a source.")
        title = body.title
        if not title:
            try:
                title = preview_feed(url)["title"]
            except FetchError as e:
                raise HTTPException(400, f"Couldn't read that feed: {e}")
        source = Source(type="rss", url=url, title=title, tags=body.tags, poll_interval_min=body.poll_interval_min)
        db.add(source)
        db.commit()
        enqueue(poll_source, source.id)
        return _out(source, 0)

    existing = db.query(Item).filter(Item.canonical_url == canonicalize(url)).first()
    if existing:
        raise HTTPException(409, f"That article is already in your inbox (item {existing.id}).")
    source = Source(type="url", url=url, title=body.title or "", tags=body.tags, active=False)
    db.add(source)
    db.flush()
    item = create_url_item(db, source)
    db.commit()
    enqueue(process_item, item.id)
    return _out(source, 1)


@router.patch("/{source_id}", response_model=SourceOut)
def update_source(source_id: int, body: SourcePatch, db: Session = Depends(get_db)):
    source = db.get(Source, source_id)
    if source is None:
        raise HTTPException(404, "Source not found")
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(source, field, value)
    db.commit()
    return _out(source, _counts(db).get(source.id, 0))


@router.delete("/{source_id}", status_code=204)
def delete_source(source_id: int, db: Session = Depends(get_db)):
    source = db.get(Source, source_id)
    if source is None:
        raise HTTPException(404, "Source not found")
    db.delete(source)
    db.commit()


@router.post("/{source_id}/refresh", status_code=202)
def refresh_source(source_id: int, db: Session = Depends(get_db)):
    source = db.get(Source, source_id)
    if source is None:
        raise HTTPException(404, "Source not found")
    if source.type != "rss":
        raise HTTPException(400, "Only feeds can be refreshed")
    enqueue(poll_source, source.id)
    return {"queued": True}
