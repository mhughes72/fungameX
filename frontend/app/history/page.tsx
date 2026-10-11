"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api, timeAgo, xIntentUrl } from "@/lib/api";
import type { HistoryPost, Source } from "@/lib/types";
import { AngleBadge, ErrorBox, StatusBadge } from "@/components/ui";

export default function HistoryPage() {
  const [posts, setPosts] = useState<HistoryPost[] | null>(null);
  const [sources, setSources] = useState<Source[]>([]);
  const [sourceId, setSourceId] = useState("");
  const [angle, setAngle] = useState("");
  const [status, setStatus] = useState("used");
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api<Source[]>("/sources").then(setSources).catch(() => undefined);
  }, []);

  useEffect(() => {
    const p = new URLSearchParams();
    if (sourceId) p.set("source_id", sourceId);
    if (angle) p.set("angle", angle);
    if (status) p.set("status", status);
    if (from) p.set("date_from", from);
    if (to) p.set("date_to", to);
    api<HistoryPost[]>(`/posts?${p}`).then(setPosts).catch((e) => setError(e.message));
  }, [sourceId, angle, status, from, to]);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end gap-2">
        <div>
          <span className="label">Status</span>
          <select className="input w-auto" value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="used">Used</option>
            <option value="edited">Edited, not used</option>
            <option value="">Used + edited</option>
            <option value="candidate">Unused candidates</option>
            <option value="discarded">Discarded</option>
          </select>
        </div>
        <div>
          <span className="label">Angle</span>
          <select className="input w-auto" value={angle} onChange={(e) => setAngle(e.target.value)}>
            <option value="">All</option>
            <option value="left">Left</option>
            <option value="center">Center</option>
            <option value="right">Right</option>
          </select>
        </div>
        <div>
          <span className="label">Source</span>
          <select className="input w-auto max-w-[14rem]" value={sourceId} onChange={(e) => setSourceId(e.target.value)}>
            <option value="">All</option>
            {sources.map((s) => <option key={s.id} value={s.id}>{s.title || s.url}</option>)}
          </select>
        </div>
        <div>
          <span className="label">From</span>
          <input type="date" className="input w-auto" value={from} onChange={(e) => setFrom(e.target.value)} />
        </div>
        <div>
          <span className="label">To</span>
          <input type="date" className="input w-auto" value={to} onChange={(e) => setTo(e.target.value)} />
        </div>
      </div>
      <ErrorBox message={error} />

      {posts === null ? (
        <p className="text-sm text-stone-500">Loading...</p>
      ) : posts.length === 0 ? (
        <p className="card text-center text-sm text-stone-500">No posts match these filters.</p>
      ) : (
        <ul className="space-y-3">
          {posts.map((p) => (
            <li key={p.id} className="card space-y-2">
              <div className="flex flex-wrap items-center gap-2 text-xs text-stone-500">
                <AngleBadge angle={p.angle} />
                <StatusBadge status={p.status} />
                <span>{p.used_at ? `used ${timeAgo(p.used_at)}` : `created ${timeAgo(p.created_at)}`}</span>
                <span>·</span>
                <span>{p.source_title}</span>
              </div>
              <p className="whitespace-pre-wrap text-sm">{p.text}</p>
              <div className="flex flex-wrap items-center gap-2">
                <Link href={`/items/${p.item_id}`} className="text-xs text-stone-500 underline">{p.item_title}</Link>
                <button className="btn btn-sm ml-auto" onClick={() => navigator.clipboard.writeText(p.text)}>Copy</button>
                <a className="btn btn-sm" href={xIntentUrl(p.text)} target="_blank" rel="noopener noreferrer">Open in X</a>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
