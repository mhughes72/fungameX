from sqlalchemy.orm import Session

from ..models import Setting

DEFAULTS: dict = {
    "angle": "center",
    "tone": "neutral",
    "include_link": True,
    "hashtags": 0,
    "max_chars": 280,
    "monthly_budget_usd": 0.0,  # 0 = no cap
}


def get_all(db: Session) -> dict:
    out = dict(DEFAULTS)
    for row in db.query(Setting).all():
        if row.key in DEFAULTS:
            out[row.key] = row.value
    return out


def update(db: Session, values: dict) -> dict:
    for key, value in values.items():
        if key not in DEFAULTS:
            continue
        row = db.get(Setting, key)
        if row is None:
            db.add(Setting(key=key, value=value))
        else:
            row.value = value
    db.commit()
    return get_all(db)
