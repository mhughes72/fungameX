// X weighted character counting. Keep in sync with backend/app/services/charcount.py.
export const URL_WEIGHT = 23;
const URL_RE = /https?:\/\/[^\s]+/gi;
const LIGHT_RANGES: [number, number][] = [
  [0, 4351],
  [8192, 8205],
  [8208, 8223],
  [8242, 8247],
];

function weight(cp: number): number {
  for (const [lo, hi] of LIGHT_RANGES) if (cp >= lo && cp <= hi) return 1;
  return 2;
}

function plainWeight(s: string): number {
  let total = 0;
  for (const ch of s) total += weight(ch.codePointAt(0)!);
  return total;
}

export function weightedLength(text: string): number {
  const t = text.normalize("NFC");
  let total = 0;
  let pos = 0;
  for (const m of t.matchAll(URL_RE)) {
    total += plainWeight(t.slice(pos, m.index)) + URL_WEIGHT;
    pos = m.index! + m[0].length;
  }
  return total + plainWeight(t.slice(pos));
}
