"use client";
import type { ReactNode } from "react";
import { useLang } from "@/lib/i18n";
import type { ApiError } from "@/lib/api";

export function Loading() {
  const { t } = useLang();
  return (
    <p role="status" className="py-6 text-center text-sm text-ledger-700">
      {t("common.loading")}
    </p>
  );
}

export function ErrorBox({ error, onRetry }: { error: ApiError | Error; onRetry?: () => void }) {
  const { t } = useLang();
  const status = (error as ApiError).status;
  return (
    <div role="alert" className="card border-red-200 bg-red-50 text-sm text-red-900">
      <p>{status === 404 ? t("common.notFound") : t("common.error")}</p>
      {status !== 404 && <p className="mt-1 break-words text-xs opacity-70">{error.message}</p>}
      {onRetry && status !== 404 && (
        <button onClick={onRetry} className="btn btn-ghost mt-2">
          {t("common.retry")}
        </button>
      )}
    </div>
  );
}

export function Stat({
  label,
  value,
  sub,
  tone,
  plain,
}: {
  label: string;
  value: ReactNode;
  sub?: ReactNode;
  tone?: "warn" | "good";
  /** Roomy card without the coloured left accent bar (used on the home page). */
  plain?: boolean;
}) {
  const border = tone === "warn" ? "border-l-amber-500" : tone === "good" ? "border-l-emerald-600" : "border-l-ledger-600";
  if (plain) {
    return (
      <div className="card flex min-h-[150px] flex-col p-6">
        <div className="text-sm text-ink/70">{label}</div>
        <div className="mt-2 font-display text-4xl font-bold tabular-nums tracking-tight">{value}</div>
        {sub && <div className="mt-auto pt-4 font-mono text-xs text-ink/55">{sub}</div>}
      </div>
    );
  }
  return (
    <div className={`card border-l-4 ${border}`}>
      <div className="text-xs font-medium text-ledger-700">{label}</div>
      <div className="mt-1 text-2xl font-extrabold tabular-nums">{value}</div>
      {sub && <div className="mt-0.5 text-xs text-ink/70">{sub}</div>}
    </div>
  );
}

export function PageTitle({ children, sub }: { children: ReactNode; sub?: ReactNode }) {
  return (
    <div className="mb-3">
      <h1 className="font-display text-4xl font-bold leading-tight tracking-tight sm:text-[44px]">{children}</h1>
      {sub && <p className="mt-3 max-w-3xl text-lg text-ink/70">{sub}</p>}
    </div>
  );
}

/** Horizontal bar list: label | bar | value. Values are always printed (never colour-only). */
export function BarList({
  rows,
  color = "bg-ledger-600",
}: {
  rows: { label: ReactNode; value: number; text: ReactNode; sub?: ReactNode }[];
  color?: string;
}) {
  const max = Math.max(1, ...rows.map((r) => r.value));
  return (
    <ul className="space-y-2">
      {rows.map((r, i) => (
        <li key={i}>
          <div className="flex items-baseline justify-between gap-2 text-sm">
            <span className="min-w-0 truncate">{r.label}</span>
            <span className="shrink-0 font-semibold tabular-nums">{r.text}</span>
          </div>
          <div className="mt-0.5 h-2 rounded bg-ledger-100" aria-hidden>
            <div className={`h-2 rounded ${color}`} style={{ width: `${Math.max(2, (r.value / max) * 100)}%` }} />
          </div>
          {r.sub && <div className="mt-0.5 text-xs text-ink/60">{r.sub}</div>}
        </li>
      ))}
    </ul>
  );
}

export function Progress({ pct, over }: { pct: number; over?: boolean }) {
  return (
    <div className="h-3 rounded bg-ledger-100" role="progressbar" aria-valuenow={Math.round(pct)} aria-valuemin={0} aria-valuemax={100}>
      <div className={`h-3 rounded ${over ? "bg-amber-500" : "bg-ledger-600"}`} style={{ width: `${Math.min(100, pct)}%` }} />
    </div>
  );
}
