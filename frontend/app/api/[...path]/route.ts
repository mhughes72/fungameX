import { NextRequest, NextResponse } from "next/server";

// Server-side proxy to the FastAPI backend. The browser only ever talks to this
// origin, so the session cookie is first-party and the OpenAI key never leaves the backend.
const BACKEND_URL = (process.env.BACKEND_URL || "http://127.0.0.1:8000").replace(/\/$/, "");
const FORWARD_HEADERS = ["content-type", "cookie", "accept"];

export const dynamic = "force-dynamic";
export const maxDuration = 120;

async function proxy(req: NextRequest, { params }: { params: { path: string[] } }) {
  const target = `${BACKEND_URL}/api/${params.path.map(encodeURIComponent).join("/")}${req.nextUrl.search}`;
  const headers = new Headers();
  for (const h of FORWARD_HEADERS) {
    const v = req.headers.get(h);
    if (v) headers.set(h, v);
  }
  let res: Response;
  try {
    res = await fetch(target, {
      method: req.method,
      headers,
      body: ["GET", "HEAD"].includes(req.method) ? undefined : await req.arrayBuffer(),
      redirect: "manual",
      cache: "no-store",
    });
  } catch {
    return NextResponse.json({ detail: "Backend is unreachable. Is the API running?" }, { status: 502 });
  }
  const out = new Headers();
  const ct = res.headers.get("content-type");
  if (ct) out.set("content-type", ct);
  for (const c of res.headers.getSetCookie()) out.append("set-cookie", c);
  const body = res.status === 204 ? null : await res.arrayBuffer();
  return new NextResponse(body, { status: res.status, headers: out });
}

export { proxy as GET, proxy as POST, proxy as PUT, proxy as PATCH, proxy as DELETE };
