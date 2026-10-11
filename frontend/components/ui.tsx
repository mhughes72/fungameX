import type { Angle } from "@/lib/types";

export function ErrorBox({ message }: { message: string | null }) {
  if (!message) return null;
  return <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800">{message}</div>;
}

const STATUS_STYLES: Record<string, string> = {
  new: "bg-sky-100 text-sky-800",
  extracted: "bg-emerald-100 text-emerald-800",
  extract_failed: "bg-red-100 text-red-800",
  dismissed: "bg-stone-200 text-stone-600",
  candidate: "bg-stone-100 text-stone-700",
  edited: "bg-amber-100 text-amber-800",
  used: "bg-emerald-100 text-emerald-800",
  discarded: "bg-stone-200 text-stone-500",
};

const STATUS_LABELS: Record<string, string> = {
  new: "Processing",
  extracted: "Ready",
  extract_failed: "Failed",
};

export function StatusBadge({ status }: { status: string }) {
  return (
    <span className={`badge ${STATUS_STYLES[status] ?? "bg-stone-100 text-stone-700"}`}>
      {STATUS_LABELS[status] ?? status}
    </span>
  );
}

const ANGLE_STYLES: Record<Angle, string> = {
  left: "bg-blue-100 text-blue-800",
  center: "bg-violet-100 text-violet-800",
  right: "bg-red-100 text-red-800",
};

export function AngleBadge({ angle }: { angle: Angle }) {
  return <span className={`badge capitalize ${ANGLE_STYLES[angle]}`}>{angle}</span>;
}

export function Spinner() {
  return <span className="inline-block h-3.5 w-3.5 animate-spin rounded-full border-2 border-current border-r-transparent" />;
}

export function Segmented<T extends string>({
  value,
  options,
  onChange,
}: {
  value: T;
  options: { value: T; label: string }[];
  onChange: (v: T) => void;
}) {
  return (
    <div className="inline-flex rounded-md border border-stone-300 bg-white p-0.5 shadow-sm">
      {options.map((o) => (
        <button
          key={o.value}
          type="button"
          onClick={() => onChange(o.value)}
          className={`rounded px-3 py-1 text-sm ${value === o.value ? "bg-stone-900 text-white" : "text-stone-600 hover:bg-stone-100"}`}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}
