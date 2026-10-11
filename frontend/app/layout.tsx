import type { Metadata } from "next";
import "./globals.css";
import Nav from "@/components/Nav";

export const metadata: Metadata = {
  title: "X Post Generator",
  description: "Turn your sources into fact-checked X posts from a chosen angle.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <Nav />
        <main className="mx-auto max-w-5xl px-4 pb-16 pt-6">{children}</main>
      </body>
    </html>
  );
}
