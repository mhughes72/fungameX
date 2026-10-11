from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Angle = Literal["left", "center", "right"]
Tone = Literal["neutral", "punchy", "wry", "formal"]


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class LoginIn(BaseModel):
    password: str


class SourceIn(BaseModel):
    type: Literal["rss", "url"]
    url: str
    title: str | None = None
    tags: list[str] = []
    poll_interval_min: int = Field(default=30, ge=10, le=1440)


class SourcePatch(BaseModel):
    title: str | None = None
    tags: list[str] | None = None
    active: bool | None = None
    poll_interval_min: int | None = Field(default=None, ge=10, le=1440)


class PreviewIn(BaseModel):
    url: str


class SourceOut(ORM):
    id: int
    type: str
    url: str
    title: str
    tags: list[str]
    active: bool
    poll_interval_min: int
    last_polled_at: datetime | None
    last_error: str | None
    created_at: datetime
    item_count: int = 0


class ClaimOut(BaseModel):
    id: str
    text: str
    quote: str


class FactsOut(ORM):
    id: int
    summary: str
    claims: list[ClaimOut]
    topic_tags: list[str]
    model: str
    prompt_version: str
    created_at: datetime


class ItemListOut(ORM):
    id: int
    source_id: int
    source_title: str
    canonical_url: str
    title: str
    published_at: datetime | None
    status: str
    error: str | None
    summary: str | None
    created_at: datetime
    duplicate_count: int = 0


class PostOut(ORM):
    id: int
    generation_id: int
    text: str
    char_count: int
    claim_ids: list[str]
    framing_note: str | None
    verification: dict | None
    status: str
    used_at: datetime | None
    created_at: datetime


class GenerationOut(ORM):
    id: int
    item_id: int
    angle: str
    tone: str
    options: dict
    instruction: str | None
    model: str
    prompt_version: str
    rubric_version: str
    cost_usd: float
    created_at: datetime
    posts: list[PostOut]


class DuplicateOut(BaseModel):
    id: int
    source_title: str
    canonical_url: str
    title: str


class ItemDetailOut(ItemListOut):
    author: str | None
    raw_text: str | None
    facts: FactsOut | None
    generations: list[GenerationOut]
    duplicates: list[DuplicateOut]


class GenerateIn(BaseModel):
    angle: Angle | None = None
    tone: Tone | None = None
    include_link: bool | None = None
    hashtags: int | None = Field(default=None, ge=0, le=2)
    max_chars: int | None = Field(default=None, ge=100, le=280)
    instruction: str | None = Field(default=None, max_length=500)


class InstructionIn(BaseModel):
    instruction: str | None = Field(default=None, max_length=500)


class PostPatch(BaseModel):
    text: str = Field(min_length=1, max_length=2000)


class HistoryPostOut(PostOut):
    angle: str
    tone: str
    item_id: int
    item_title: str
    source_id: int
    source_title: str
    canonical_url: str


class SettingsIn(BaseModel):
    angle: Angle | None = None
    tone: Tone | None = None
    include_link: bool | None = None
    hashtags: int | None = Field(default=None, ge=0, le=2)
    max_chars: int | None = Field(default=None, ge=100, le=280)
    monthly_budget_usd: float | None = Field(default=None, ge=0)
