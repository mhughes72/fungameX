"use client";

import { FormEvent, useEffect, useState } from "react";
import { api, timeAgo } from "@/lib/api";
import type { FeedPreview, Source } from "@/lib/types";
import { ErrorBox, Segmented } from "@/components/ui";

function parseTags(s: string): string[] {
  return s.split(",").map((t) => t.trim()).filter(Boolean);
}

export default function SourcesPage() {
  const [sources, setSources] = useState<Source[] | null>(null);
  const [type, setType] = useState<"rss" | "url">("rss");
  const [url, setUrl] = useState("");
  const [tags, setTags] = useState("");
  const [interval, setIntervalMin] = useState(30);
  const [preview, setPreview] = useState<FeedPreview | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showUrls, setShowUrls] = useState(false);

  async function load() {
    try {
      setSources(await api<Source[]>("/sources"));
    } catch (e) {
      setError((e as Error).message);
    }
  }

  useEffect(() => {
    load();
  }, []);

  function reset() {
    setUrl("");
    setTags("");
    setPreview(null);
  }

  async function doPreview(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    setPreview(null);
    try {
      if (type === "rss") {
        setPreview(await api<FeedPreview>("/sources/preview", { body: { url } }));
      } else {
        await api("/sources", { body: { type: "url", url, tags: parseTags(tags) } });
        reset();
        await load();
      }
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function addFeed() {
    if (!preview) return;
    setBusy(true);
    setError(null);
    try {
      await api("/sources", {
        body: { type: "rss", url, title: preview.title, tags: parseTags(tags), poll_interval_min: interval },
      });
      reset();
      await load();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function patch(id: number, body: Partial<Source>) {
    try {
      const updated = await api<Source>(`/sources/${id}`, { method: "PATCH", body });
      setSources((cur) => cur?.map((s) => (s.id === id ? updated : s)) ?? null);
    } catch (e) {
      setError((e as Error).message);
    }
  }

  async function remove(s: Source) {
    if (!confirm(`Delete "${s.title || s.url}" and all its items and posts? This can't be undone.`)) return;
    await api(`/sources/${s.id}`, { method: "DELETE" });
    setSources((cur) => cur?.filter((x) => x.id !== s.id) ?? null);
  }

  async function refresh(id: number) {
    await api(`/sources/${id}/refresh`, { method: "POST" });
    setTimeout(load, 3000);
  }

  function rename(s: Source) {
    const title = prompt("Rename source", s.title);
    if (title !== null && title.trim()) patch(s.id, { title: title.trim() });
  }

  function editTags(s: Source) {
    const t = prompt("Tags (comma separated)", s.tags.join(", "));
    if (t !== null) patch(s.id, { tags: parseTags(t) });
  }

  const feeds = sources?.filter((s) => s.type === "rss") ?? [];
  const urls = sources?.filter((s) => s.type === "url") ?? [];

  return (
    <div className="space-y-6">
      <section className="card space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="font-semibold">Add a source</h2>
          <Segmented value={type} onChange={(v) => { setType(v); setPreview(null); }}
            options={[{ value: "rss", label: "RSS feed" }, { value: "url", label: "Single URL" }]} />
        </div>
        <form onSubmit={doPreview} className="flex flex-wrap gap-2">
          <input className="input min-w-[16rem] flex-1" value={url} onChange={(e) => setUrl(e.target.value)}
            placeholder={type === "rss" ? "https://example.com/feed.xml" : "https://example.com/article"} />
          <input className="input w-48" value={tags} onChange={(e) => setTags(e.target.value)}
            placeholder="Tags, comma separated" />
          <button className="btn btn-primary" disabled={!url || busy}>
            {busy ? "Checking..." : type === "rss" ? "Preview" : "Add URL"}
          </button>
        </form>
        <ErrorBox message={error} />
        {preview && (
          <div className="rounded-md border border-stone-200 bg-stone-50 p-3">
            <p className="font-medium">{preview.title}</p>
            <ul className="mt-2 space-y-1 text-sm text-stone-600">
              {preview.entries.map((e, i) => (
                <li key={i}>· {e.title} <span className="text-stone-400">{timeAgo(e.published_at)}</span></li>
              ))}
              {preview.entries.length === 0 && <li>The feed is valid but has no entries right now.</li>}
            </ul>
            <div className="mt-3 flex items-center gap-2">
              <label className="text-sm text-stone-600">Check every</label>
              <select className="input w-auto" value={interval} onChange={(e) => setIntervalMin(Number(e.target.value))}>
                {[10, 15, 30, 60, 120, 360, 1440].map((m) => (
                  <option key={m} value={m}>{m < 60 ? `${m} min` : `${m / 60} h`}</option>
                ))}
              </select>
              <button className="btn btn-primary ml-auto" onClick={addFeed} disabled={busy}>Add feed</button>
            </div>
          </div>
        )}
      </section>

      <section>
        <h2 className="mb-2 font-semibold">Feeds</h2>
        {sources === null ? (
          <p className="text-sm text-stone-500">Loading...</p>
        ) : feeds.length === 0 ? (
          <p className="text-sm text-stone-500">No feeds yet.</p>
        ) : (
          <ul className="space-y-2">
            {feeds.map((s) => (
              <li key={s.id} className={`card ${s.active ? "" : "opacity-60"}`}>
                <div className="flex flex-wrap items-start gap-3">
                  <div className="min-w-0 flex-1">
                    <p className="font-medium">{s.title || s.url}</p>
                    <p className="truncate text-xs text-stone-500">{s.url}</p>
                    <div className="mt-1 flex flex-wrap gap-1 text-xs text-stone-500">
                      {s.tags.map((t) => <span key={t} className="badge bg-stone-100 text-stone-600">{t}</span>)}
                      <span>{s.item_count} items · every {s.poll_interval_min} min · checked {timeAgo(s.last_polled_at) || "never"}</span>
                    </div>
                    {s.last_error && <p className="mt-1 text-xs text-red-700">Last error: {s.last_error}</p>}
                  </div>
                  <div className="flex flex-wrap gap-1">
                    <button className="btn btn-sm" onClick={() => refresh(s.id)}>Refresh</button>
                    <button className="btn btn-sm" onClick={() => patch(s.id, { active: !s.active })}>
                      {s.active ? "Pause" : "Resume"}
                    </button>
                    <button className="btn btn-sm" onClick={() => rename(s)}>Rename</button>
                    <button className="btn btn-sm" onClick={() => editTags(s)}>Tags</button>
                    <button className="btn btn-sm btn-danger" onClick={() => remove(s)}>Delete</button>
                  </div>
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>

      {urls.length > 0 && (
        <section>
          <button className="mb-2 text-sm font-semibold text-stone-600 hover:text-stone-900" onClick={() => setShowUrls(!showUrls)}>
            {showUrls ? "▾" : "▸"} One-off URLs ({urls.length})
          </button>
          {showUrls && (
            <ul className="space-y-1">
              {urls.map((s) => (
                <li key={s.id} className="flex items-center gap-2 text-sm">
                  <span className="truncate text-stone-600">{s.url}</span>
                  <button className="btn btn-sm btn-danger ml-auto" onClick={() => remove(s)}>Delete</button>
                </li>
              ))}
            </ul>
          )}
        </section>
      )}
    </div>
  );
}
