"""The three-step LLM pipeline: extract -> generate -> verify."""
import json
import logging
import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

import yaml
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..db import SessionLocal
from ..models import Generation, Item, ItemFacts, Post
from . import settings_store
from .charcount import URL_RE, URL_WEIGHT, count_hashtags, weighted_length
from .llm import ExtractResult, GenerateResult, LLMError, VerifyResult, call_structured, moderate

log = logging.getLogger("app.pipeline")

APP_DIR = Path(__file__).resolve().parent.parent
ANGLES = ("left", "center", "right")
TONES = ("neutral", "punchy", "wry", "formal")
LINK_SEPARATOR = "\n\n"


class BudgetExceeded(Exception):
    pass


class PipelineError(Exception):
    pass


# ---------------------------------------------------------------- config files


@dataclass(frozen=True)
class Prompt:
    version: str
    text: str


@lru_cache
def load_prompt(name: str) -> Prompt:
    raw = (APP_DIR / "prompts" / f"{name}.md").read_text(encoding="utf-8")
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", raw, re.S)
    if not m:
        raise RuntimeError(f"prompt {name} is missing its version header")
    meta = yaml.safe_load(m.group(1)) or {}
    return Prompt(version=str(meta["version"]), text=m.group(2).strip())


@lru_cache
def load_angle(angle: str) -> dict:
    if angle not in ANGLES:
        raise PipelineError(f"unknown angle: {angle}")
    return yaml.safe_load((APP_DIR / "angles" / f"{angle}.yaml").read_text(encoding="utf-8"))


def angle_rubric_text(angle: str) -> str:
    a = load_angle(angle)
    examples = "\n".join(f"- {e}" for e in a["examples"])
    return (
        f"Angle: {a['label']}\n"
        f"Core values to foreground: {a['values']}\n"
        f"Typical emphasis: {a['emphasis']}\n"
        f"Preferred solutions: {a['solutions']}\n"
        f"Tone guardrails: {a['tone_guardrails']}\n"
        f"Style examples (about a DIFFERENT, fictional story: \"{a['example_story']}\"; "
        f"copy the style, never these facts):\n{examples}"
    )


# ---------------------------------------------------------------- budget


def month_spend(db: Session) -> float:
    start = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    g = db.query(func.coalesce(func.sum(Generation.cost_usd), 0.0)).filter(Generation.created_at >= start).scalar()
    f = db.query(func.coalesce(func.sum(ItemFacts.cost_usd), 0.0)).filter(ItemFacts.created_at >= start).scalar()
    return float(g or 0) + float(f or 0)


def check_budget(db: Session) -> None:
    cap = float(settings_store.get_all(db).get("monthly_budget_usd") or 0)
    if cap > 0:
        spent = month_spend(db)
        if spent >= cap:
            raise BudgetExceeded(f"Monthly budget of ${cap:.2f} reached (spent ${spent:.2f}).")


# ---------------------------------------------------------------- step 1: extract

_QUOTE_TRANS = str.maketrans({"‘": "'", "’": "'", "“": '"', "”": '"', "–": "-",
                              "—": "-", " ": " "})


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.translate(_QUOTE_TRANS)).strip().lower()


def validate_claims(claims: list[dict], article: str) -> list[dict]:
    """Keep only claims whose quote really appears in the article."""
    body = _norm(article)
    return [c for c in claims if c.get("quote") and _norm(c["quote"]) in body]


def extract_facts_for_item(item_id: int) -> ItemFacts | None:
    prompt = load_prompt("extract")
    with SessionLocal() as db:
        item = db.get(Item, item_id)
        if item is None or not item.raw_text:
            return None
        try:
            check_budget(db)
            user = f"Title: {item.title}\nURL: {item.canonical_url}\n\nArticle text:\n{item.raw_text}"
            result, cost, model = call_structured("fast", prompt.text, user, ExtractResult, "extract")
        except (LLMError, BudgetExceeded) as e:
            item.status, item.error = "extract_failed", str(e)
            db.commit()
            return None

        claims = validate_claims([c.model_dump() for c in result.claims], item.raw_text)
        dropped = len(result.claims) - len(claims)
        if dropped:
            log.info("dropped claims with non-verbatim quotes", extra={"item_id": item_id, "dropped": dropped})
        facts = ItemFacts(item_id=item.id, summary=result.summary.strip(), claims=claims,
                          topic_tags=result.topic_tags[:4], model=model, prompt_version=prompt.version,
                          cost_usd=cost)
        db.add(facts)
        if claims:
            item.status, item.error = "extracted", None
        else:
            item.status, item.error = "extract_failed", "no claims could be verified against the article text"
        db.commit()
        return facts


# ---------------------------------------------------------------- step 3: verify


def _strip_urls(text: str) -> str:
    return URL_RE.sub("", text).strip()


def verify_text(text: str, claims: list[dict], options: dict) -> tuple[dict, float]:
    """Return (verification dict, cost)."""
    max_chars = int(options.get("max_chars", 280))
    wanted_tags = int(options.get("hashtags", 0))
    checks = {
        "char_count": weighted_length(text),
        "too_long": weighted_length(text) > max_chars,
        "hashtags": count_hashtags(text),
        "hashtags_over": count_hashtags(text) > wanted_tags,
    }
    body = _strip_urls(text)
    prompt = load_prompt("verify")
    user = json.dumps({"post": body, "claims": claims}, ensure_ascii=False)
    issues: list[dict] = []
    supported = True
    cost = 0.0
    error = None
    try:
        res, cost, _ = call_structured("fast", prompt.text, user, VerifyResult, "verify")
        issues = [i.model_dump() for i in res.issues]
        supported = res.supported and not any(i["problem"] in ("unsupported", "misattributed") for i in issues)
    except LLMError as e:
        error = str(e)
        supported = False
    flagged, categories = (False, [])
    try:
        flagged, categories = moderate(body)
    except LLMError:
        pass

    if error or not supported or flagged or checks["too_long"]:
        status = "fail"
    elif issues or checks["hashtags_over"]:
        status = "warn"
    else:
        status = "pass"
    verification = {
        "status": status,
        "supported": supported,
        "issues": issues,
        "moderation_flagged": flagged,
        "moderation_categories": categories,
        "checks": checks,
        "error": error,
        "prompt_version": prompt.version,
        "verified_at": datetime.now(timezone.utc).isoformat(),
    }
    return verification, cost


# ---------------------------------------------------------------- step 2: generate


def _normalize_options(raw: dict, defaults: dict) -> dict:
    opts = {k: raw.get(k, defaults[k]) for k in ("angle", "tone", "include_link", "hashtags", "max_chars")}
    if opts["angle"] not in ANGLES:
        raise PipelineError(f"angle must be one of {ANGLES}")
    if opts["tone"] not in TONES:
        raise PipelineError(f"tone must be one of {TONES}")
    opts["hashtags"] = max(0, min(2, int(opts["hashtags"])))
    opts["max_chars"] = max(100, min(280, int(opts["max_chars"])))
    opts["include_link"] = bool(opts["include_link"])
    return opts


def _text_budget(opts: dict) -> int:
    budget = opts["max_chars"]
    if opts["include_link"]:
        budget -= URL_WEIGHT + len(LINK_SEPARATOR)
    return budget


def _finalize_text(text: str, link: str, opts: dict) -> str:
    text = _strip_urls(text) if opts["include_link"] else text.strip()
    if opts["include_link"]:
        text = f"{text}{LINK_SEPARATOR}{link}"
    return text


def _write_candidates(item: Item, facts: ItemFacts, opts: dict, instruction: str | None, count: int,
                      avoid: list[str]) -> tuple[list, float, str, str]:
    prompt = load_prompt("generate")
    payload = {
        "article_title": item.title,
        "summary": facts.summary,
        "claims": facts.claims,
        "angle_rubric": angle_rubric_text(opts["angle"]),
        "tone": opts["tone"],
        "constraints": {"max_text_chars": _text_budget(opts), "hashtags": opts["hashtags"]},
        "candidates_requested": count,
        "user_instruction": instruction or None,
        "avoid_repeating": avoid or None,
    }
    result, cost, model = call_structured("writer", prompt.text, json.dumps(payload, ensure_ascii=False),
                                          GenerateResult, "generate")
    if not result.candidates:
        raise PipelineError("The model returned no candidates.")
    return result.candidates[:count], cost, model, prompt.version


def _make_post(generation: Generation, cand, item: Item, facts: ItemFacts, opts: dict) -> Post:
    text = _finalize_text(cand.text, item.canonical_url, opts)
    valid_ids = {c["id"] for c in facts.claims}
    return Post(generation=generation, text=text, original_text=text, char_count=weighted_length(text),
                claim_ids=[c for c in cand.claim_ids if c in valid_ids], framing_note=cand.framing_note,
                status="candidate")


def _verify_posts(posts: list[Post], claims: list[dict], opts: dict) -> float:
    with ThreadPoolExecutor(max_workers=max(1, len(posts))) as pool:
        results = list(pool.map(lambda p: verify_text(p.text, claims, opts), posts))
    total = 0.0
    for post, (verification, cost) in zip(posts, results):
        post.verification = verification
        total += cost
    return total


def generate(db: Session, item_id: int, raw_options: dict, instruction: str | None = None) -> Generation:
    item = db.get(Item, item_id)
    if item is None:
        raise PipelineError("item not found")
    facts = item.latest_facts
    if facts is None or not facts.claims:
        raise PipelineError("This item has no extracted facts yet.")
    check_budget(db)
    opts = _normalize_options(raw_options, settings_store.get_all(db))
    rubric = load_angle(opts["angle"])

    cands, cost, model, prompt_version = _write_candidates(item, facts, opts, instruction, 3, [])
    gen = Generation(item_id=item.id, facts_id=facts.id, angle=opts["angle"], tone=opts["tone"], options=opts,
                     instruction=instruction or None, model=model, prompt_version=prompt_version,
                     rubric_version=str(rubric["version"]), cost_usd=cost)
    db.add(gen)
    posts = [_make_post(gen, c, item, facts, opts) for c in cands]
    gen.cost_usd += _verify_posts(posts, facts.claims, opts)
    db.add_all(posts)
    db.commit()
    db.refresh(gen)
    return gen


def regenerate_post(db: Session, post_id: int, instruction: str | None = None) -> Post:
    old = db.get(Post, post_id)
    if old is None:
        raise PipelineError("post not found")
    gen = old.generation
    item, facts, opts = gen.item, gen.facts, gen.options
    check_budget(db)
    siblings = [p.text for p in gen.posts if p.status != "discarded"]
    cands, cost, _, _ = _write_candidates(item, facts, opts, instruction or gen.instruction, 1, siblings)
    new = _make_post(gen, cands[0], item, facts, opts)
    cost += _verify_posts([new], facts.claims, opts)
    gen.cost_usd += cost
    old.status = "discarded"
    db.add(new)
    db.commit()
    db.refresh(new)
    return new


def regenerate_all(db: Session, generation_id: int, instruction: str | None = None) -> Generation:
    gen = db.get(Generation, generation_id)
    if gen is None:
        raise PipelineError("generation not found")
    new = generate(db, gen.item_id, gen.options, instruction if instruction is not None else gen.instruction)
    for p in gen.posts:
        if p.status in ("candidate", "edited"):
            p.status = "discarded"
    db.commit()
    return new


def reverify_post(db: Session, post_id: int) -> Post:
    post = db.get(Post, post_id)
    if post is None:
        raise PipelineError("post not found")
    gen = post.generation
    verification, cost = verify_text(post.text, gen.facts.claims, gen.options)
    post.verification = verification
    gen.cost_usd += cost
    db.commit()
    return post
