"use client";

import { FormEvent, useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { Angle, AppSettings, Tone } from "@/lib/types";
import { ErrorBox, Segmented } from "@/components/ui";

export default function SettingsPage() {
  const [s, setS] = useState<AppSettings | null>(null);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api<AppSettings>("/settings").then(setS).catch((e) => setError(e.message));
  }, []);

  async function save(e: FormEvent) {
    e.preventDefault();
    if (!s) return;
    setError(null);
    try {
      setS(await api<AppSettings>("/settings", { method: "PUT", body: s }));
      setSaved(true);
      setTimeout(() => setSaved(false), 1500);
    } catch (err) {
      setError((err as Error).message);
    }
  }

  if (!s) return error ? <ErrorBox message={error} /> : <p className="text-sm text-stone-500">Loading...</p>;

  return (
    <form onSubmit={save} className="card max-w-xl space-y-5">
      <h1 className="font-semibold">Defaults for new posts</h1>
      <div>
        <span className="label">Angle</span>
        <Segmented<Angle> value={s.angle} onChange={(angle) => setS({ ...s, angle })}
          options={[{ value: "left", label: "Left" }, { value: "center", label: "Center" }, { value: "right", label: "Right" }]} />
      </div>
      <div>
        <span className="label">Tone</span>
        <select className="input w-auto capitalize" value={s.tone} onChange={(e) => setS({ ...s, tone: e.target.value as Tone })}>
          {["neutral", "punchy", "wry", "formal"].map((t) => <option key={t} value={t}>{t}</option>)}
        </select>
      </div>
      <div className="flex gap-6">
        <div>
          <span className="label">Hashtags</span>
          <select className="input w-auto" value={s.hashtags} onChange={(e) => setS({ ...s, hashtags: Number(e.target.value) })}>
            {[0, 1, 2].map((n) => <option key={n} value={n}>{n}</option>)}
          </select>
        </div>
        <div>
          <span className="label">Character limit</span>
          <input type="number" min={100} max={280} className="input w-28" value={s.max_chars}
            onChange={(e) => setS({ ...s, max_chars: Number(e.target.value) })} />
        </div>
      </div>
      <label className="flex items-center gap-2 text-sm">
        <input type="checkbox" checked={s.include_link} onChange={(e) => setS({ ...s, include_link: e.target.checked })} />
        Include the source link in the post (uses 23 characters)
      </label>
      <div>
        <span className="label">Monthly OpenAI budget (USD)</span>
        <input type="number" min={0} step="0.5" className="input w-32" value={s.monthly_budget_usd}
          onChange={(e) => setS({ ...s, monthly_budget_usd: Number(e.target.value) })} />
        <p className="mt-1 text-xs text-stone-500">
          0 means no cap. Generation stops once this month&apos;s spend reaches the cap. Spend is only tracked if the
          OPENAI_PRICE_* environment variables are set.
        </p>
      </div>
      <ErrorBox message={error} />
      <button className="btn btn-primary">{saved ? "Saved" : "Save"}</button>
    </form>
  );
}
