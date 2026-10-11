"""Thin wrapper over the OpenAI Responses API with Structured Outputs."""
import logging
import time
from functools import lru_cache
from typing import Literal, TypeVar

from openai import OpenAI
from pydantic import BaseModel

from ..config import get_settings

log = logging.getLogger("app.llm")

Role = Literal["fast", "writer"]
T = TypeVar("T", bound=BaseModel)


class LLMError(Exception):
    pass


# ---------------------------------------------------------------- schemas


class Claim(BaseModel):
    id: str
    text: str
    quote: str


class ExtractResult(BaseModel):
    summary: str
    claims: list[Claim]
    topic_tags: list[str]


class Candidate(BaseModel):
    text: str
    claim_ids: list[str]
    framing_note: str


class GenerateResult(BaseModel):
    candidates: list[Candidate]


class Issue(BaseModel):
    span: str
    problem: Literal["unsupported", "exaggerated", "misattributed"]
    explanation: str


class VerifyResult(BaseModel):
    supported: bool
    issues: list[Issue]


# ---------------------------------------------------------------- client


@lru_cache
def _client() -> OpenAI:
    key = get_settings().openai_api_key
    if not key:
        raise LLMError("OPENAI_API_KEY is not set")
    # max_retries=2 -> up to 3 attempts with exponential backoff (SDK built-in)
    return OpenAI(api_key=key, max_retries=2, timeout=90)


def model_for(role: Role) -> str:
    s = get_settings()
    return s.openai_model_writer if role == "writer" else s.openai_model_fast


def _cost(role: Role, input_tokens: int, output_tokens: int) -> float:
    s = get_settings()
    if role == "writer":
        pin, pout = s.openai_price_writer_input, s.openai_price_writer_output
    else:
        pin, pout = s.openai_price_fast_input, s.openai_price_fast_output
    return (input_tokens * pin + output_tokens * pout) / 1_000_000


def call_structured(role: Role, system: str, user: str, schema: type[T], step: str) -> tuple[T, float, str]:
    """Return (parsed, cost_usd, model)."""
    model = model_for(role)
    started = time.monotonic()
    try:
        resp = _client().responses.parse(model=model, instructions=system, input=user, text_format=schema)
    except LLMError:
        raise
    except Exception as e:  # openai.APIError and friends
        log.warning("llm call failed", extra={"step": step, "model": model, "error": str(e)})
        raise LLMError(f"OpenAI call failed: {e.__class__.__name__}: {e}") from e
    parsed = resp.output_parsed
    if parsed is None:
        raise LLMError("The model returned no structured output (it may have refused).")
    usage = resp.usage
    in_tok = usage.input_tokens if usage else 0
    out_tok = usage.output_tokens if usage else 0
    cost = _cost(role, in_tok, out_tok)
    log.info("llm call", extra={"step": step, "model": model, "input_tokens": in_tok, "output_tokens": out_tok,
                                "cost_usd": round(cost, 6), "ms": int((time.monotonic() - started) * 1000)})
    return parsed, cost, model


def moderate(text: str) -> tuple[bool, list[str]]:
    """Return (flagged, categories). Failures are logged and treated as not flagged."""
    try:
        res = _client().moderations.create(model=get_settings().openai_moderation_model, input=text).results[0]
    except LLMError:
        raise
    except Exception as e:
        log.warning("moderation failed", extra={"error": str(e)})
        return False, []
    cats = [k for k, v in res.categories.model_dump().items() if v]
    return bool(res.flagged), cats
