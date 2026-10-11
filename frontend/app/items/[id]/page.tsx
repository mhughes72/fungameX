"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { api, timeAgo } from "@/lib/api";
import type { Angle, AppSettings, Generation, ItemDetail, Post, Tone } from "@/lib/types";
import PostCard from "@/components/PostCard";
import { AngleBadge, ErrorBox, Segmented, Spinner, StatusBadge } from "@/components/ui";

const ANGLES: { value: Angle; label: string }[] = [
  { value: "left", label: "Left" },
  { value: "center", label: "Center" },
  { value: "right", label: "Right" },
];
const TONES: Tone[] = ["neutral", "punchy", "wry", "formal"];

export default function ItemPage({ params }: { params: { id: string } }) {
  const [item, setItem] = useState<ItemDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [angle, setAngle] = useState<Angle>("center");
  const [tone, setTone] = useState<Tone>("neutral");
  const [includeLink, setIncludeLink] = useState(true);
  const [hashtags, setHashtags] = useState(0);
  const [maxChars, setMaxChars] = useState(280);
  const [instruction, setInstruction] = useState("");
  const [generating, setGenerating] = useState(false);
  const [showSource, setShowSource] = useState(false);
  const [showDiscarded, setShowDiscarded] = useState(false);

  const load = useCallback(async () => {
    try {
      setItem(await api<ItemDetail>(`/items/${params.id}`));
    } catch (e) {
      setError((e as Error).message);
    }
  }, [params.id]);

  useEffect(() => {
    load();
    api<AppSettings>("/settings")
      .then((s) => {
        setAngle(s.angle);
        setTone(s.tone);
        setIncludeLink(s.include_link);
        setHashtags(s.hashtags);
        setMaxChars(s.max_chars);
      })
      .catch(() => undefined);
  }, [load]);

  useEffect(() => {
    if (item?.status !== "new") return;
    const t = setInterval(load, 4000);
    return () => clearInterval(t);
  }, [item?.status, load]);

  async function generate() {
    setGenerating(true);
    setError(null);
    try {
      const gen = await api<Generation>(`/items/${params.id}/generate`, {
        body: { angle, tone, include_link: includeLink, hashtags, max_chars: maxChars, instruction: instruction || null },
      });
      setItem((cur) => (cur ? { ...cur, generations: [gen, ...cur.generations] } : cur));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setGenerating(false);
    }
  }

  async function regenerateAll(gen: Generation) {
    setGenerating(true);
    setError(null);
    try {
      const fresh = await api<Generation>(`/generations/${gen.id}/regenerate`, { body: { instruction: instruction || null } });
      await load();
      setItem((cur) => (cur && !cur.generations.some((g) => g.id === fresh.id)
        ? { ...cur, generations: [fresh, ...cur.generations] } : cur));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setGenerating(false);
    }
  }

  async function retry() {
    await api(`/items/${params.id}/retry`, { method: "POST" });
    await load();
  }

  function updatePost(p: Post) {
    setItem((cur) => cur && {
      ...cur,
      generations: cur.generations.map((g) => g.id === p.generation_id
        ? { ...g, posts: g.posts.map((x) => (x.id === p.id ? p : x)) } : g),
    });
  }

  function replacePost(oldId: number, p: Post) {
    setItem((cur) => cur && {
      ...cur,
      generations: cur.generations.map((g) => g.id === p.generation_id
        ? { ...g, posts: [...g.posts.map((x) => (x.id === oldId ? { ...x, status: "discarded" as const } : x)), p] } : g),
    });
  }

  if (!item) {
    return error ? <ErrorBox message={error} /> : <p className="text-sm text-stone-500">Loading...</p>;
  }

  const claims = item.facts?.claims ?? [];

  return (
    <div className="space-y-6">
      <div>
        <Link href="/" className="text-sm text-stone-500 hover:text-stone-900">← Inbox</Link>
        <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-stone-500">
          <StatusBadge status={item.status} />
          <span>{item.source_title}</span>
          <span>·</span>
          <span>{timeAgo(item.published_at ?? item.created_at)}</span>
          {item.author && <><span>·</span><span>{item.author}</span></>}
        </div>
        <h1 className="mt-1 text-xl font-semibold leading-snug">{item.title}</h1>
        <a href={item.canonical_url} target="_blank" rel="noopener noreferrer" className="break-all text-sm text-stone-500 underline">
          {item.canonical_url}
        </a>
      </div>

      {item.status === "new" && (
        <div className="card flex items-center gap-2 text-sm text-stone-600">
          <Spinner /> Fetching the article and extracting facts...
        </div>
      )}
      {item.status === "extract_failed" && (
        <div className="card space-y-2 border-red-200">
          <p className="text-sm text-red-800">Couldn&apos;t prepare this item: {item.error}</p>
          <button className="btn btn-sm" onClick={retry}>Try again</button>
        </div>
      )}

      {item.facts && (
        <section className="card space-y-3">
          <div>
            <h2 className="label">Summary</h2>
            <p className="text-sm">{item.facts.summary}</p>
          </div>
          <div>
            <h2 className="label">Facts from the source ({claims.length})</h2>
            <ul className="space-y-1.5 text-sm">
              {claims.map((c) => (
                <li key={c.id} className="flex gap-2">
                  <span className="badge h-fit bg-stone-100 text-stone-700">{c.id}</span>
                  <span>
                    {c.text}
                    <span className="block text-xs text-stone-500">&ldquo;{c.quote}&rdquo;</span>
                  </span>
                </li>
              ))}
            </ul>
          </div>
          {item.duplicates.length > 0 && (
            <div>
              <h2 className="label">Also covered by</h2>
              <ul className="text-sm">
                {item.duplicates.map((d) => (
                  <li key={d.id}>
                    <a href={d.canonical_url} target="_blank" rel="noopener noreferrer" className="underline">{d.source_title}</a>
                    <span className="text-stone-500"> — {d.title}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
          {item.raw_text && (
            <div>
              <button className="text-xs text-stone-500 underline" onClick={() => setShowSource(!showSource)}>
                {showSource ? "Hide" : "Show"} extracted article text
              </button>
              {showSource && (
                <p className="mt-2 max-h-80 overflow-y-auto whitespace-pre-wrap rounded bg-stone-50 p-3 text-xs text-stone-700">{item.raw_text}</p>
              )}
            </div>
          )}
        </section>
      )}

      {item.status === "extracted" && (
        <section className="card space-y-4">
          <h2 className="font-semibold">Write posts</h2>
          <div className="flex flex-wrap items-end gap-4">
            <div>
              <span className="label">Angle</span>
              <Segmented value={angle} options={ANGLES} onChange={setAngle} />
            </div>
            <div>
              <span className="label">Tone</span>
              <select className="input w-auto capitalize" value={tone} onChange={(e) => setTone(e.target.value as Tone)}>
                {TONES.map((t) => <option key={t} value={t}>{t}</option>)}
              </select>
            </div>
            <div>
              <span className="label">Hashtags</span>
              <select className="input w-auto" value={hashtags} onChange={(e) => setHashtags(Number(e.target.value))}>
                {[0, 1, 2].map((n) => <option key={n} value={n}>{n}</option>)}
              </select>
            </div>
            <label className="flex items-center gap-2 pb-2 text-sm">
              <input type="checkbox" checked={includeLink} onChange={(e) => setIncludeLink(e.target.checked)} />
              Include source link
            </label>
          </div>
          <div className="flex gap-2">
            <input className="input" placeholder='Optional instruction, e.g. "lead with the vote count"' value={instruction}
              onChange={(e) => setInstruction(e.target.value)} />
            <button className="btn btn-primary whitespace-nowrap" onClick={generate} disabled={generating}>
              {generating ? <><Spinner /> Writing and fact-checking...</> : "Generate 3 posts"}
            </button>
          </div>
          <ErrorBox message={error} />
        </section>
      )}

      {item.generations.length > 0 && (
        <div className="flex items-center justify-end">
          <label className="flex items-center gap-2 text-xs text-stone-500">
            <input type="checkbox" checked={showDiscarded} onChange={(e) => setShowDiscarded(e.target.checked)} />
            Show discarded
          </label>
        </div>
      )}

      {item.generations.map((gen) => {
        const posts = gen.posts.filter((p) => showDiscarded || p.status !== "discarded");
        if (posts.length === 0) return null;
        return (
          <section key={gen.id} className="space-y-3">
            <div className="flex flex-wrap items-center gap-2 text-sm">
              <AngleBadge angle={gen.angle} />
              <span className="capitalize text-stone-600">{gen.tone}</span>
              <span className="text-stone-400">· {timeAgo(gen.created_at)}</span>
              {gen.instruction && <span className="text-xs italic text-stone-500">&ldquo;{gen.instruction}&rdquo;</span>}
              <button className="btn btn-sm ml-auto" onClick={() => regenerateAll(gen)} disabled={generating}>
                Regenerate all
              </button>
            </div>
            {posts.map((p) => (
              <PostCard key={p.id} post={p} claims={claims} maxChars={gen.options.max_chars}
                onUpdate={updatePost} onReplace={replacePost} />
            ))}
          </section>
        );
      })}
    </div>
  );
}
