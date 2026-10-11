"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { api } from "@/lib/api";

const LINKS = [
  { href: "/", label: "Inbox" },
  { href: "/sources", label: "Sources" },
  { href: "/history", label: "History" },
  { href: "/settings", label: "Settings" },
  { href: "/admin", label: "Status" },
];

export default function Nav() {
  const path = usePathname();
  if (path.startsWith("/login")) return null;

  async function signOut() {
    await api("/auth/logout", { method: "POST" }).catch(() => undefined);
    window.location.href = "/login";
  }

  return (
    <header className="sticky top-0 z-10 border-b border-stone-200 bg-white/90 backdrop-blur">
      <div className="mx-auto flex max-w-5xl items-center gap-1 overflow-x-auto px-4 py-2">
        <Link href="/" className="mr-4 whitespace-nowrap font-semibold tracking-tight">
          X Post Generator
        </Link>
        {LINKS.map((l) => {
          const active = l.href === "/" ? path === "/" || path.startsWith("/items") : path.startsWith(l.href);
          return (
            <Link
              key={l.href}
              href={l.href}
              className={`whitespace-nowrap rounded-md px-3 py-1.5 text-sm ${
                active ? "bg-stone-900 text-white" : "text-stone-600 hover:bg-stone-100"
              }`}
            >
              {l.label}
            </Link>
          );
        })}
        <button onClick={signOut} className="ml-auto whitespace-nowrap text-sm text-stone-500 hover:text-stone-900">
          Sign out
        </button>
      </div>
    </header>
  );
}
