"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api, timeAgo } from "@/lib/api";
import { ErrorBox } from "@/components/ui";

interface Status {
  openai_key_set: boolean;
  models: { fast: string; writer: string };
  prices_configured: boolean;
  jobs_mode: string;
  month_spend_usd: number;
  monthly_budget_usd: number;
  source_errors: { id: number; title: string; error: string; at: string | null }[];
  item_errors: { id: number; title: string; error: string | null; at: string }[];
  recent_generations: { id: number; item_id: number; angle: string; model: string; cost_usd: number; at: string }[];
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex justify-between gap-4 border-b border-stone-100 py-1.5 text-sm last:border-0">
      <span className="text-stone-500">{label}</span>
      <span className="text-right font-medium">{children}</span>
    </div>
  );
}

export default function AdminPage() {
  const [s, setS] = useState<Status | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api<Status>("/admin/status").then(setS).catch((e) => setError(e.message));
  }, []);

  if (!s) return error ? <ErrorBox message={error} /> : <p className="text-sm text-stone-500">Loading...</p>;

  return (
    <div className="grid gap-4 md:grid-cols-2">
      <section className="card">
        <h2 className="mb-2 font-semibold">Setup</h2>
        <Row label="OpenAI key">
          {s.openai_key_set ? <span className="text-emerald-700">Set</span> : <span className="text-red-700">Missing (set OPENAI_API_KEY)</span>}
        </Row>
        <Row label="Writer model">{s.models.writer}</Row>
        <Row label="Fast model">{s.models.fast}</Row>
        <Row label="Background jobs">{s.jobs_mode === "rq" ? "Redis worker" : "In-process"}</Row>
      </section>
      <section className="card">
        <h2 className="mb-2 font-semibold">Spend this month</h2>
        <Row label="Spent">
          {s.prices_configured ? `$${s.month_spend_usd.toFixed(2)}` : "Not tracked (set OPENAI_PRICE_*)"}
        </Row>
        <Row label="Budget">{s.monthly_budget_usd > 0 ? `$${s.monthly_budget_usd.toFixed(2)}` : "No cap"}</Row>
      </section>
      <section className="card md:col-span-2">
        <h2 className="mb-2 font-semibold">Feed errors</h2>
        {s.source_errors.length === 0 ? <p className="text-sm text-stone-500">None.</p> : (
          <ul className="space-y-1 text-sm">
            {s.source_errors.map((e) => (
              <li key={e.id}><span className="font-medium">{e.title}</span>: <span className="text-red-700">{e.error}</span> <span className="text-stone-400">{timeAgo(e.at)}</span></li>
            ))}
          </ul>
        )}
      </section>
      <section className="card md:col-span-2">
        <h2 className="mb-2 font-semibold">Items that failed</h2>
        {s.item_errors.length === 0 ? <p className="text-sm text-stone-500">None.</p> : (
          <ul className="space-y-1 text-sm">
            {s.item_errors.map((e) => (
              <li key={e.id}>
                <Link href={`/items/${e.id}`} className="font-medium underline">{e.title}</Link>: <span className="text-red-700">{e.error}</span>
              </li>
            ))}
          </ul>
        )}
      </section>
      <section className="card md:col-span-2">
        <h2 className="mb-2 font-semibold">Recent generations</h2>
        {s.recent_generations.length === 0 ? <p className="text-sm text-stone-500">None yet.</p> : (
          <ul className="space-y-1 text-sm">
            {s.recent_generations.map((g) => (
              <li key={g.id} className="flex gap-2">
                <Link href={`/items/${g.item_id}`} className="underline">Item {g.item_id}</Link>
                <span className="capitalize">{g.angle}</span>
                <span className="text-stone-500">{g.model}</span>
                <span className="ml-auto text-stone-500">${g.cost_usd.toFixed(4)} · {timeAgo(g.at)}</span>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
