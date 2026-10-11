"use client";

import { FormEvent, Suspense, useState } from "react";
import { useSearchParams } from "next/navigation";
import { api } from "@/lib/api";
import { ErrorBox } from "@/components/ui";

function LoginForm() {
  const params = useSearchParams();
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api("/auth/login", { body: { password } });
      const next = params.get("next");
      window.location.href = next && next.startsWith("/") ? next : "/";
    } catch (err) {
      setError((err as Error).message);
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="card mx-auto mt-24 max-w-sm space-y-4">
      <div>
        <h1 className="text-lg font-semibold">X Post Generator</h1>
        <p className="text-sm text-stone-500">Sign in to continue.</p>
      </div>
      <div>
        <label className="label" htmlFor="pw">Password</label>
        <input id="pw" type="password" className="input" value={password} autoFocus
          onChange={(e) => setPassword(e.target.value)} />
      </div>
      <ErrorBox message={error} />
      <button className="btn btn-primary w-full" disabled={busy || !password}>
        {busy ? "Signing in..." : "Sign in"}
      </button>
    </form>
  );
}

export default function LoginPage() {
  return (
    <Suspense>
      <LoginForm />
    </Suspense>
  );
}
