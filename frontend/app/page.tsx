"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useState } from "react";
import { api, timeAgo } from "@/lib/api";
import type { ItemSummary, Source } from "@/lib/types";
import { ErrorBox, StatusBadge } from "@/components/ui";

const STATUS_FILTERS = [
  { value: "", label: "Active" },
  { value: "extracted", label: "Ready" },
  { value: "new", label: "Processing" },
  { value: "extract_failed", label: "Failed" },
  { value: "dismissed", label: "Dismissed" },
];

export default function InboxPage() {
  const [items, setItems] = useState<ItemSummary[] | null>(null);
  const [sources, setSources] = useState<Source[]>([]);
  const [status, setStatus] = useState("");
  const [sourceId, setSourceId] = useState("");
  const [q, setQ] = useState("");
  const [url, setUrl] = useState("");
  const [adding, setAdding] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    const params = new URLSearchParams();
    if (status) params.set("status", status);
    if (sourceId) params.set("source_id", sourceId);
    if (q) params.set("q", q);
    try {
      setItems(await api<ItemSummary[]>(`/items?${params}`));
    } catch (e) {
      setError((e as Error).message);
    }
  }, [status, sourceId, q]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    api<Source[]>("/sources?type=rss").then(setSources).catch(() => undefined);
  }, []);

  // Keep polling while anything is still being fetched or extracted.
  useEffect(() => {
    if (!items?.some((i) => i.status === "new")) return;
    const t = setInterval(load, 5000);
    return () => clearInterval(t);
  }, [items, load]);

  async function addUrl(e: FormEvent) {
    e.preventDefault();
    setAdding(true);
    setError(null);
    try {
      await api("/sources", { body: { type: "url", url } });
      setUrl("");
      await load();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setAdding(false);
    }
  }

  async function dismiss(id: number) {
    await api(`/items/${id}/dismiss`, { method: "POST" });
    setItems((cur) => cur?.filter((i) => i.id !== id) ?? null);
  }

  async function restore(id: number) {
    await api(`/items/${id}/restore`, { method: "POST" });
    setItems((cur) => cur?.filter((i) => i.id !== id) ?? null);
  }

  return (
    <div className="space-y-5">
      <form onSubmit={addUrl} className="flex gap-2">
        <input className="input" placeholder="Paste an article URL to post about..." value={url}
          onChange={(e) => setUrl(e.target.value)} />
        <button className="btn btn-primary whitespace-nowrap" disabled={!url || adding}>
          {adding ? "Adding..." : "Add URL"}
        </button>
      </form>
      <ErrorBox message={error} />

      <div className="flex flex-wrap items-center gap-2">
        {STATUS_FILTERS.map((f) => (
          <button key={f.value} onClick={() => setStatus(f.value)}
            className={`rounded-full px-3 py-1 text-sm ${status === f.value ? "bg-stone-900 text-white" : "bg-white text-stone-600 ring-1 ring-stone-200 hover:bg-stone-100"}`}>
            {f.label}
          </button>
        ))}
        <select className="input ml-auto w-auto" value={sourceId} onChange={(e) => setSourceId(e.target.value)}>
          <option value="">All sources</option>
          {sources.map((s) => (
            <option key={s.id} value={s.id}>{s.title || s.url}</option>
          ))}
        </select>
        <input className="input w-48" placeholder="Search titles" value={q} onChange={(e) => setQ(e.target.value)} />
      </div>

      {items === null ? (
        <p className="text-sm text-stone-500">Loading...</p>
      ) : items.length === 0 ? (
        <div className="card text-center text-sm text-stone-500">
          Nothing here yet. <Link href="/sources" className="underline">Add an RSS feed</Link> or paste a URL above.
        </div>
      ) : (
        <ul className="space-y-3">
          {items.map((item) => (
            <li key={item.id} className="card flex gap-4">
              <div className="min-w-0 flex-1">
                <div className="mb-1 flex flex-wrap items-center gap-2 text-xs text-stone-500">
                  <StatusBadge status={item.status} />
                  <span>{item.source_title}</span>
                  <span>·</span>
                  <span>{timeAgo(item.published_at ?? item.created_at)}</span>
                  {item.duplicate_count > 0 && (
                    <span className="badge bg-stone-100 text-stone-600">
                      +{item.duplicate_count} other source{item.duplicate_count > 1 ? "s" : ""}
                    </span>
                  )}
                </div>
                <Link href={`/items/${item.id}`} className="font-medium hover:underline">{item.title}</Link>
                {item.summary && <p className="mt-1 line-clamp-2 text-sm text-stone-600">{item.summary}</p>}
                {item.status === "extract_failed" && item.error && (
                  <p className="mt-1 text-xs text-red-700">{item.error}</p>
                )}
              </div>
              <div className="flex shrink-0 flex-col items-end gap-2">
                <Link href={`/items/${item.id}`} className="btn btn-sm btn-primary">
                  {item.status === "extracted" ? "Write posts" : "Open"}
                </Link>
                {item.status === "dismissed" ? (
                  <button className="btn btn-sm" onClick={() => restore(item.id)}>Restore</button>
                ) : (
                  <button className="btn btn-sm" onClick={() => dismiss(item.id)}>Dismiss</button>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
