"use client";

import { ReactNode, useState } from "react";
import { api, xIntentUrl } from "@/lib/api";
import { weightedLength } from "@/lib/charcount";
import type { Claim, Post, Verification, VerificationIssue } from "@/lib/types";
import { ErrorBox, Spinner, StatusBadge } from "./ui";

const PROBLEM_LABEL: Record<VerificationIssue["problem"], string> = {
  unsupported: "Not in source",
  exaggerated: "Exaggerated",
  misattributed: "Misattributed",
};

function highlight(text: string, issues: VerificationIssue[]): ReactNode[] {
  const marks: { start: number; end: number; issue: VerificationIssue }[] = [];
  const lower = text.toLowerCase();
  for (const issue of issues) {
    const i = lower.indexOf(issue.span.toLowerCase());
    if (i >= 0) marks.push({ start: i, end: i + issue.span.length, issue });
  }
  marks.sort((a, b) => a.start - b.start);
  const out: ReactNode[] = [];
  let pos = 0;
  marks.forEach((m, k) => {
    if (m.start < pos) return;
    out.push(text.slice(pos, m.start));
    const color = m.issue.problem === "exaggerated" ? "bg-amber-200" : "bg-red-200";
    out.push(
      <mark key={k} className={`${color} rounded px-0.5`} title={`${PROBLEM_LABEL[m.issue.problem]}: ${m.issue.explanation}`}>
        {text.slice(m.start, m.end)}
      </mark>,
    );
    pos = m.end;
  });
  out.push(text.slice(pos));
  return out;
}

function VerificationBadge({ v }: { v: Verification | null }) {
  if (!v) return <span className="badge bg-stone-100 text-stone-600">Not checked</span>;
  if (v.stale) return <span className="badge bg-stone-200 text-stone-700">Edited, re-check</span>;
  if (v.status === "pass") return <span className="badge bg-emerald-100 text-emerald-800">Fact-check passed</span>;
  if (v.status === "warn") return <span className="badge bg-amber-100 text-amber-800">Check warnings</span>;
  return <span className="badge bg-red-100 text-red-800">Fact-check failed</span>;
}

export default function PostCard({
  post,
  claims,
  maxChars,
  onUpdate,
  onReplace,
}: {
  post: Post;
  claims: Claim[];
  maxChars: number;
  onUpdate: (p: Post) => void;
  onReplace: (oldId: number, p: Post) => void;
}) {
  const [text, setText] = useState(post.text);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [regenOpen, setRegenOpen] = useState(false);
  const [instruction, setInstruction] = useState("");
  const [copied, setCopied] = useState(false);

  const dirty = text !== post.text;
  const count = weightedLength(text);
  const v = post.verification;
  const failed = v?.status === "fail" && !v.stale && !dirty;
  const claimById = Object.fromEntries(claims.map((c) => [c.id, c]));

  async function run<T>(label: string, fn: () => Promise<T>): Promise<T | undefined> {
    setBusy(label);
    setError(null);
    try {
      return await fn();
    } catch (e) {
      setError((e as Error).message);
      return undefined;
    } finally {
      setBusy(null);
    }
  }

  async function save(): Promise<Post | undefined> {
    if (!dirty) return post;
    const updated = await api<Post>(`/posts/${post.id}`, { method: "PATCH", body: { text } });
    onUpdate(updated);
    return updated;
  }

  async function markUsed() {
    const updated = await api<Post>(`/posts/${post.id}/use`, { method: "POST" });
    onUpdate(updated);
  }

  async function copy() {
    await run("copy", async () => {
      await navigator.clipboard.writeText(text);
      await save();
      await markUsed();
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    });
  }

  async function openInX() {
    // Open the window synchronously so popup blockers allow it.
    const win = window.open(xIntentUrl(text), "_blank", "noopener,noreferrer");
    if (!win) setError("Your browser blocked the X window. Allow popups for this site.");
    await run("open", async () => {
      await save();
      await markUsed();
    });
  }

  async function verify() {
    await run("verify", async () => {
      await save();
      onUpdate(await api<Post>(`/posts/${post.id}/verify`, { method: "POST" }));
    });
  }

  async function regenerate() {
    await run("regen", async () => {
      const fresh = await api<Post>(`/posts/${post.id}/regenerate`, { body: { instruction: instruction || null } });
      setRegenOpen(false);
      setInstruction("");
      onReplace(post.id, fresh);
    });
  }

  async function discard() {
    await run("discard", async () => onUpdate(await api<Post>(`/posts/${post.id}/discard`, { method: "POST" })));
  }

  return (
    <div className={`card space-y-3 ${failed ? "border-red-200 bg-red-50/30" : ""}`}>
      <div className="flex flex-wrap items-center gap-2">
        <VerificationBadge v={dirty ? { ...(v as Verification), stale: true } : v} />
        <StatusBadge status={post.status} />
        {post.framing_note && <span className="text-xs italic text-stone-500">{post.framing_note}</span>}
      </div>

      <div className={failed ? "opacity-70" : ""}>
        <textarea className="input min-h-[7rem] resize-y font-[inherit] leading-relaxed" value={text}
          onChange={(e) => setText(e.target.value)} />
        <div className="mt-1 flex items-center justify-between text-xs">
          <span className="text-stone-500">Links count as 23 characters.</span>
          <span className={count > maxChars ? "font-semibold text-red-700" : "text-stone-500"}>
            {count} / {maxChars}
          </span>
        </div>
      </div>

      {v && !v.stale && !dirty && (v.issues.length > 0 || v.moderation_flagged || v.error || v.checks.too_long || v.checks.hashtags_over) && (
        <div className="space-y-2 rounded-md border border-stone-200 bg-white p-3 text-sm">
          {v.issues.length > 0 && <p className="leading-relaxed text-stone-800">{highlight(post.text, v.issues)}</p>}
          <ul className="space-y-1 text-xs">
            {v.issues.map((i, k) => (
              <li key={k}>
                <span className={`badge mr-1 ${i.problem === "exaggerated" ? "bg-amber-100 text-amber-800" : "bg-red-100 text-red-800"}`}>
                  {PROBLEM_LABEL[i.problem]}
                </span>
                &ldquo;{i.span}&rdquo; — {i.explanation}
              </li>
            ))}
            {v.checks.too_long && <li className="text-red-700">Over the {maxChars}-character limit.</li>}
            {v.checks.hashtags_over && <li className="text-amber-700">More hashtags than requested.</li>}
            {v.moderation_flagged && (
              <li className="text-red-700">Flagged by moderation: {v.moderation_categories.join(", ")}</li>
            )}
            {v.error && <li className="text-red-700">Fact-check error: {v.error}</li>}
          </ul>
        </div>
      )}

      {post.claim_ids.length > 0 && (
        <div className="flex flex-wrap items-center gap-1 text-xs text-stone-500">
          Uses:
          {post.claim_ids.map((id) => (
            <span key={id} className="badge cursor-help bg-stone-100 text-stone-700" title={claimById[id]?.text}>{id}</span>
          ))}
        </div>
      )}

      <ErrorBox message={error} />

      {regenOpen && (
        <div className="flex gap-2">
          <input className="input" placeholder='Optional instruction, e.g. "mention the vote count"' value={instruction}
            onChange={(e) => setInstruction(e.target.value)} autoFocus />
          <button className="btn btn-primary whitespace-nowrap" onClick={regenerate} disabled={!!busy}>
            {busy === "regen" ? <Spinner /> : null} Rewrite
          </button>
        </div>
      )}

      <div className="flex flex-wrap gap-2">
        <button className="btn btn-primary" onClick={openInX} disabled={!!busy || count > maxChars}>
          Open in X
        </button>
        <button className="btn" onClick={copy} disabled={!!busy}>
          {copied ? "Copied" : "Copy"}
        </button>
        {dirty && (
          <button className="btn" onClick={() => run("save", save)} disabled={!!busy}>
            {busy === "save" ? <Spinner /> : null} Save edit
          </button>
        )}
        <button className="btn" onClick={verify} disabled={!!busy}>
          {busy === "verify" ? <Spinner /> : null} Re-check facts
        </button>
        <button className="btn" onClick={() => setRegenOpen(!regenOpen)} disabled={!!busy}>Regenerate</button>
        <button className="btn btn-danger ml-auto" onClick={discard} disabled={!!busy}>Discard</button>
      </div>
    </div>
  );
}
