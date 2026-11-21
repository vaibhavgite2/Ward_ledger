"use client";
import Link from "next/link";
import { useId, useState } from "react";
import { useLang } from "@/lib/i18n";

export type Score = {
  score: number;
  band: "reliable" | "mixed" | "below";
  band_label: string;
  durability_pct: number;
  sla_pct: number;
  billing_pct: number;
  flood_index: number;
  verdict: string;
  basis: { repairs: number; app_tasks: number };
  weights: { durability: number; sla: number; billing: number };
};

const BAND = {
  reliable: { ring: "#16a34a", badge: "bg-emerald-50 text-emerald-800", dot: "bg-emerald-500" },
  mixed: { ring: "#d97706", badge: "bg-amber-50 text-amber-800", dot: "bg-amber-500" },
  below: { ring: "#dc2626", badge: "bg-rose-50 text-rose-800", dot: "bg-rose-500" },
} as const;

const clean = (n: string) => n.replace(" (synthetic)", "");
const initials = (n: string) =>
  clean(n)
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((w) => w[0]!.toUpperCase())
    .join("");

/** The ring gauge: the score as an arc, the number in the middle. Colour is paired with the band label, never alone. */
function Ring({ score, band }: { score: number; band: keyof typeof BAND }) {
  const r = 24;
  const c = 2 * Math.PI * r;
  return (
    <svg width="64" height="64" viewBox="0 0 64 64" role="img" aria-label={`${score}/100`} className="shrink-0">
      <circle cx="32" cy="32" r={r} fill="none" stroke="#e5e7eb" strokeWidth="6" />
      <circle
        cx="32"
        cy="32"
        r={r}
        fill="none"
        stroke={BAND[band].ring}
        strokeWidth="6"
        strokeLinecap="round"
        strokeDasharray={c}
        strokeDashoffset={c * (1 - Math.max(0, Math.min(100, score)) / 100)}
        transform="rotate(-90 32 32)"
      />
      <text x="32" y="38" textAnchor="middle" fontSize="20" fontWeight="800" fill="#0f172a">
        {score}
      </text>
    </svg>
  );
}

/**
 * Contractor card: civic trust score, the three measures behind it, the context note, and a plain-language verdict that
 * opens on demand. Shown on the contractors list, each contractor's page and the contractor's own panel.
 */
export default function ScoreCard({ name, contractorId, score, meta, linkName = true }: { name: string; contractorId: string; score: Score | null; meta?: string; linkName?: boolean }) {
  const { t } = useLang();
  const [open, setOpen] = useState(false);
  const panel = useId();
  const href = `/contractor/${contractorId}`;
  return (
    <article className="rounded-2xl border border-ledger-100 bg-white p-4 shadow-sm">
      <div className="flex items-start justify-between">
        <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-slate-100 text-sm font-bold text-slate-700" aria-hidden>
          {initials(name)}
        </div>
        {linkName && (
          <Link href={href} aria-label={`${t("score.fullRecord")}: ${clean(name)}`} title={t("score.fullRecord")} className="rounded px-2 text-lg leading-none text-slate-400 hover:bg-slate-100 hover:text-slate-700">
            ···
          </Link>
        )}
      </div>
      <h3 className="mt-3 text-sm font-semibold text-slate-900">
        {linkName ? (
          <Link href={href} className="hover:underline">
            {clean(name)}
          </Link>
        ) : (
          clean(name)
        )}
      </h3>
      {meta && <p className="text-xs text-slate-500">{meta}</p>}

      {!score ? (
        <p className="mt-3 text-xs text-slate-500">{t("score.noRecord")}</p>
      ) : (
        <>
          <div className="mt-3 flex items-center gap-3">
            <Ring score={score.score} band={score.band} />
            <div>
              <div className="text-[11px] font-medium uppercase tracking-wide text-slate-500">{t("score.title")}</div>
              <span className={`mt-1 inline-flex items-center gap-1.5 rounded-md px-2 py-0.5 text-xs font-semibold ${BAND[score.band].badge}`}>
                <span className={`h-1.5 w-1.5 rounded-full ${BAND[score.band].dot}`} aria-hidden />
                {score.band_label}
              </span>
            </div>
          </div>

          <dl className="mt-4 grid grid-cols-3 gap-2 border-t border-slate-100 pt-3">
            {(
              [
                ["score.durability", score.durability_pct],
                ["score.sla", score.sla_pct],
                ["score.billing", score.billing_pct],
              ] as const
            ).map(([k, v]) => (
              <div key={k}>
                <dt className="text-[10px] font-medium uppercase leading-tight tracking-wide text-slate-500">{t(k)}</dt>
                <dd className="mt-1 text-lg font-bold tabular-nums text-slate-900">{v}%</dd>
              </div>
            ))}
          </dl>

          <p className="mt-3 flex items-center gap-1.5 border-t border-slate-100 pt-3 text-[11px] text-slate-600">
            <svg width="14" height="14" viewBox="0 0 16 16" aria-hidden className="shrink-0 text-emerald-600">
              <path d="M3 8.5l3.2 3.2L13 4.8" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
            {t("score.context", { x: score.flood_index.toFixed(2) })}
          </p>

          <button
            type="button"
            aria-expanded={open}
            aria-controls={panel}
            onClick={() => setOpen(!open)}
            className="mt-3 flex min-h-[36px] w-full items-center justify-between border-t border-slate-100 pt-3 text-left text-xs text-slate-600 hover:text-slate-900"
          >
            {t("score.verdict")}
            <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden className={`transition-transform ${open ? "rotate-180" : ""}`}>
              <path d="M4 6l4 4 4-4" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </button>
          <div id={panel} hidden={!open} className="mt-1 text-xs leading-relaxed text-slate-700">
            {score.verdict}
          </div>
        </>
      )}
    </article>
  );
}
