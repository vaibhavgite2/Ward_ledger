"use client";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useApi } from "@/lib/api";
import { useLang } from "@/lib/i18n";
import { rupee, wardSlug } from "@/lib/format";
import { ErrorBox, Loading, PageTitle } from "@/components/Ui";
import { RULE_LABEL } from "@/lib/rules";

/** Two bars for one measure: what happened vs what is expected for the same mix. Both values are printed. */
function Compare({ title, actual, expected, suffix = "%", note }: { title: string; actual: number; expected: number; suffix?: string; note?: string }) {
  const { t } = useLang();
  const max = Math.max(actual, expected, 1);
  const row = (label: string, v: number, cls: string) => (
    <div className="grid grid-cols-[120px_1fr_48px] items-center gap-2 text-xs">
      <span className="text-ink/70">{label}</span>
      <span className="h-3 rounded bg-ledger-100" aria-hidden>
        <span className={`block h-3 rounded ${cls}`} style={{ width: `${Math.max(2, (v / max) * 100)}%` }} />
      </span>
      <span className="text-right font-semibold tabular-nums">
        {v}
        {suffix}
      </span>
    </div>
  );
  return (
    <section className="card">
      <h3 className="mb-2 text-sm font-bold">{title}</h3>
      <div className="space-y-1.5">
        {row(t("common.actual"), actual, "bg-ledger-700")}
        {row(t("common.expected"), expected, "bg-slate-400")}
      </div>
      {note && <p className="mt-2 text-[11px] text-ink/60">{note}</p>}
    </section>
  );
}

export default function ContractorPage() {
  const { id } = useParams<{ id: string }>();
  const { t, lang } = useLang();
  const { data: c, error, loading, reload } = useApi<any>(`/contractors/${id}/scorecard`);
  if (loading) return <Loading />;
  if (error) return <ErrorBox error={error} onRetry={reload} />;
  if (!c) return null;
  const m = c.metrics;
  const replies = c.right_of_reply.replies as any[];
  return (
    <div className="mx-auto max-w-4xl">
      <PageTitle sub={t("contractors.since", { y: c.empanelled_since })}>{c.name}</PageTitle>

      <section className="card">
        <h2 className="mb-1 text-sm font-bold">{t("scorecard.title")}</h2>
        <p className="text-sm leading-relaxed">{c.narrative.text}</p>
        <p className="mt-1 text-[11px] text-ink/50">{c.narrative.source === "claude" ? t("scorecard.generated") : t("scorecard.template")}</p>
        <p className="mt-2 border-t border-ledger-100 pt-2 text-xs text-ink/70">{c.context_note}</p>
      </section>

      <div className="mt-4 grid gap-3 sm:grid-cols-2">
        <Compare title={t("scorecard.speed")} actual={m.sla_pct} expected={m.expected_sla_pct} />
        <Compare title={`${t("scorecard.durability")} — ${t("scorecard.reopenedPct")}`} actual={m.reopen_pct} expected={m.expected_reopen_pct} note={`${m.completed} ${t("common.jobs")} · ${rupee(m.failed_cost_inr)}`} />
        <section className="card">
          <h3 className="mb-1 text-sm font-bold">{t("scorecard.cost")}</h3>
          <div className="text-2xl font-extrabold tabular-nums">{m.within_rate_pct}%</div>
          <div className="text-xs text-ink/70">
            {m.overrun_jobs} / {m.completed} {t("common.jobs")}
          </div>
        </section>
        <section className="card">
          <h3 className="mb-1 text-sm font-bold">{t("scorecard.warranty")}</h3>
          <div className="text-2xl font-extrabold tabular-nums">{m.dlp_jobs}</div>
          <div className="text-xs text-ink/70">{rupee(m.billed_inr)}</div>
        </section>
      </div>

      {c.clean_record.length > 0 && (
        <>
          <h2 className="h2">{t("scorecard.clean")}</h2>
          <p className="mb-2 text-xs text-ink/70">{t("scorecard.cleanHelp")}</p>
          <ul className="grid gap-2 sm:grid-cols-2">
            {c.clean_record.map((x: any) => (
              <li key={x.finding_id} className="card border-emerald-200 text-sm">
                <Link href={`/ward/${wardSlug(x.ward_code)}`} className="font-semibold underline">
                  {t("common.ward")} {x.ward_code}
                </Link>
                <p className="mt-1">{x.text}</p>
              </li>
            ))}
          </ul>
        </>
      )}

      <h2 className="h2">{t("scorecard.byWard")}</h2>
      <div className="card overflow-x-auto p-0">
        <table className="w-full min-w-[480px] text-sm">
          <thead className="bg-ledger-100 text-xs text-ink/70">
            <tr>
              <th className="p-2 text-left">{t("common.ward")}</th>
              <th className="p-2 text-right">{t("common.jobs")}</th>
              <th className="p-2 text-right">₹</th>
              <th className="p-2 text-right">{t("scorecard.speed")}</th>
              <th className="p-2 text-right">{t("scorecard.reopenedPct")}</th>
            </tr>
          </thead>
          <tbody>
            {c.by_ward.map((w: any) => (
              <tr key={w.ward_code} className="border-t border-ledger-100">
                <td className="p-2">
                  <Link href={`/ward/${wardSlug(w.ward_code)}`} className="underline">
                    {w.ward_code}
                  </Link>
                </td>
                <td className="p-2 text-right tabular-nums">{w.completed}</td>
                <td className="p-2 text-right tabular-nums">{rupee(w.billed_inr)}</td>
                <td className="p-2 text-right tabular-nums">{w.sla_pct}%</td>
                <td className="p-2 text-right tabular-nums">{w.reopen_pct}%</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <h2 className="h2">{t("scorecard.findings")}</h2>
      <p className="flex flex-wrap gap-1 text-xs">
        {Object.entries(c.findings)
          .filter(([r]) => r !== "clean_record")
          .map(([r, n]) => (
            <span key={r} className="chip border-ledger-200 bg-white">
              {RULE_LABEL[r]?.[lang] || r}: {String(n)}
            </span>
          ))}
      </p>

      <h2 className="h2">{t("scorecard.replyTitle")}</h2>
      <p className="text-sm text-ink/70">{t("scorecard.replyHelp")}</p>
      {replies.length > 0 && (
        <ul className="mt-2 space-y-1 text-sm">
          {replies.map((r, i) => (
            <li key={i} className="card">
              {r.reply_text}
            </li>
          ))}
        </ul>
      )}
      <p className="mt-4 text-xs text-ink/60">
        {c.evidence.count} {t("common.jobs")} · {c.evidence.file} ({c.evidence.filter})
      </p>
    </div>
  );
}
