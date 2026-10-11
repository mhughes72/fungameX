export type Angle = "left" | "center" | "right";
export type Tone = "neutral" | "punchy" | "wry" | "formal";

export interface Source {
  id: number;
  type: "rss" | "url";
  url: string;
  title: string;
  tags: string[];
  active: boolean;
  poll_interval_min: number;
  last_polled_at: string | null;
  last_error: string | null;
  created_at: string;
  item_count: number;
}

export interface FeedPreview {
  title: string;
  entries: { title: string; url: string | null; published_at: string | null }[];
}

export interface Claim {
  id: string;
  text: string;
  quote: string;
}

export interface Facts {
  id: number;
  summary: string;
  claims: Claim[];
  topic_tags: string[];
  model: string;
  prompt_version: string;
  created_at: string;
}

export interface ItemSummary {
  id: number;
  source_id: number;
  source_title: string;
  canonical_url: string;
  title: string;
  published_at: string | null;
  status: "new" | "extracted" | "extract_failed" | "dismissed";
  error: string | null;
  summary: string | null;
  created_at: string;
  duplicate_count: number;
}

export interface VerificationIssue {
  span: string;
  problem: "unsupported" | "exaggerated" | "misattributed";
  explanation: string;
}

export interface Verification {
  status: "pass" | "warn" | "fail";
  supported: boolean;
  issues: VerificationIssue[];
  moderation_flagged: boolean;
  moderation_categories: string[];
  checks: { char_count: number; too_long: boolean; hashtags: number; hashtags_over: boolean };
  error: string | null;
  stale?: boolean;
}

export interface Post {
  id: number;
  generation_id: number;
  text: string;
  char_count: number;
  claim_ids: string[];
  framing_note: string | null;
  verification: Verification | null;
  status: "candidate" | "edited" | "used" | "discarded";
  used_at: string | null;
  created_at: string;
}

export interface GenerationOptions {
  angle: Angle;
  tone: Tone;
  include_link: boolean;
  hashtags: number;
  max_chars: number;
}

export interface Generation {
  id: number;
  item_id: number;
  angle: Angle;
  tone: Tone;
  options: GenerationOptions;
  instruction: string | null;
  model: string;
  prompt_version: string;
  rubric_version: string;
  cost_usd: number;
  created_at: string;
  posts: Post[];
}

export interface ItemDetail extends ItemSummary {
  author: string | null;
  raw_text: string | null;
  facts: Facts | null;
  generations: Generation[];
  duplicates: { id: number; source_title: string; canonical_url: string; title: string }[];
}

export interface HistoryPost extends Post {
  angle: Angle;
  tone: Tone;
  item_id: number;
  item_title: string;
  source_id: number;
  source_title: string;
  canonical_url: string;
}

export interface AppSettings extends GenerationOptions {
  monthly_budget_usd: number;
}
