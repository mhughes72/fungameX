from datetime import date, datetime, time, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..auth import require_user
from ..db import get_db
from ..models import Generation, Item, Post, Source
from ..schemas import HistoryPostOut, InstructionIn, PostOut, PostPatch
from ..services import pipeline
from ..services.charcount import weighted_length
from .errors import pipeline_errors

router = APIRouter(prefix="/api/posts", tags=["posts"], dependencies=[Depends(require_user)])


def _get(db: Session, post_id: int) -> Post:
    post = db.get(Post, post_id)
    if post is None:
        raise HTTPException(404, "Post not found")
    return post


@router.get("", response_model=list[HistoryPostOut])
def history(source_id: int | None = None, angle: str | None = None, status: str | None = None,
            date_from: date | None = None, date_to: date | None = None, limit: int = 100, offset: int = 0,
            db: Session = Depends(get_db)):
    q = (db.query(Post, Generation, Item, Source)
         .join(Generation, Post.generation_id == Generation.id)
         .join(Item, Generation.item_id == Item.id)
         .join(Source, Item.source_id == Source.id))
    if status:
        q = q.filter(Post.status == status)
    else:
        q = q.filter(Post.status.in_(("used", "edited")))
    if source_id:
        q = q.filter(Source.id == source_id)
    if angle:
        q = q.filter(Generation.angle == angle)
    if date_from:
        q = q.filter(Post.created_at >= datetime.combine(date_from, time.min, tzinfo=timezone.utc))
    if date_to:
        q = q.filter(Post.created_at <= datetime.combine(date_to, time.max, tzinfo=timezone.utc))
    rows = q.order_by(Post.created_at.desc()).limit(min(limit, 500)).offset(offset).all()
    return [
        HistoryPostOut(**PostOut.model_validate(p).model_dump(), angle=g.angle, tone=g.tone, item_id=i.id,
                       item_title=i.title, source_id=s.id, source_title=s.title or s.url,
                       canonical_url=i.canonical_url)
        for p, g, i, s in rows
    ]


@router.patch("/{post_id}", response_model=PostOut)
def edit_post(post_id: int, body: PostPatch, db: Session = Depends(get_db)):
    post = _get(db, post_id)
    if body.text != post.text:
        post.text = body.text
        post.char_count = weighted_length(body.text)
        if post.status == "candidate":
            post.status = "edited"
        if post.verification:
            post.verification = {**post.verification, "stale": True}
        db.commit()
    return post


@router.post("/{post_id}/verify", response_model=PostOut)
def verify(post_id: int, db: Session = Depends(get_db)):
    _get(db, post_id)
    with pipeline_errors():
        return pipeline.reverify_post(db, post_id)


@router.post("/{post_id}/regenerate", response_model=PostOut)
def regenerate(post_id: int, body: InstructionIn, db: Session = Depends(get_db)):
    _get(db, post_id)
    with pipeline_errors():
        return pipeline.regenerate_post(db, post_id, body.instruction)


@router.post("/{post_id}/use", response_model=PostOut)
def mark_used(post_id: int, db: Session = Depends(get_db)):
    post = _get(db, post_id)
    post.status = "used"
    post.used_at = datetime.now(timezone.utc)
    db.commit()
    return post


@router.post("/{post_id}/discard", response_model=PostOut)
def discard(post_id: int, db: Session = Depends(get_db)):
    post = _get(db, post_id)
    post.status = "discarded"
    db.commit()
    return post
