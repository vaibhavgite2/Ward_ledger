"use client";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";
import { useApi } from "@/lib/api";
import { useLang } from "@/lib/i18n";
import { inr, rupee, wardCode, wardSlug } from "@/lib/format";
import { useAuth } from "@/lib/auth";
import { BarList, ErrorBox, Loading, PageTitle, Progress, Stat } from "@/components/Ui";
import FindingCard from "@/components/FindingCard";

const FUNNEL_ORDER = [
  "received",
  "unique_issues",
  "fixed_and_held",
  "fixed_but_failed",
  "linked_via_duplicate_issue",
  "never_fixed",
  "closed_other",
  "pending",
  "duplicate",
];
const FACTORS = ["S", "F", "R", "A", "P", "C", "D"];

export default function WardPage() {
  const params = useParams<{ code: string }>();
  const code = wardCode(params.code);
  const slug = wardSlug(code);
  const { t } = useLang();
  const { user } = useAuth();
  const trail = useApi<any>(`/wards/${slug}/money-trail`);
  const prio = useApi<any>(`/wards/${slug}/priorities?limit=12`);
  const [showAll, setShowAll] = useState(false);

  if (trail.loading) return <Loading />;
  if (trail.error) return <ErrorBox error={trail.error} onRetry={trail.reload} />;
  const w = trail.data;
  if (!w) return null;
  const f = w.funnel;
  const funnelRows = FUNNEL_ORDER.filter((k) => (f[k] ?? 0) > 0).map((k) => ({
    label: t("funnel." + k),
    value: f[k],
    text: f[k].toLocaleString("en-IN"),
  }));
  const findings: any[] = w.findings || [];
  const shown = showAll ? findings : findings.slice(0, 6);

  return (
    <div>
      <PageTitle sub={w.office}>{t("ward.title", { code: w.ward_code, name: w.ward_name })}</PageTitle>

      <section className="card">
        <h2 className="mb-1 text-sm font-bold">{t("ward.summary")}</h2>
        <p className="text-sm leading-relaxed">{w.narrative.text}</p>
        <p className="mt-1 text-[11px] text-ink/50">{w.narrative.source === "claude" ? t("scorecard.generated") : t("scorecard.template")}</p>
      </section>

      <div className="mt-4 grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Stat label={t("ward.budget")} value={rupee(w.budget_inr)} />
        <div className="card border-l-4 border-l-ledger-600">
          <div className="text-xs font-medium text-ledger-700">{t("ward.billed")}</div>
          <div className="mt-1 text-2xl font-extrabold tabular-nums">{rupee(w.spend_inr)}</div>
          <div className="mt-2">
            <Progress pct={w.utilisation_pct} over={w.overspent} />
          </div>
          <div className="mt-1 text-xs text-ink/70">{w.overspent ? t("ward.overspent") : t("ward.utilisation", { n: w.utilisation_pct })}</div>
        </div>
        <Stat
          label={t("ward.failedTitle")}
          value={rupee(w.failed_inr)}
          sub={t("ward.failedSub", { jobs: w.failed_jobs, pct: w.failed_pct_of_spend })}
          tone="warn"
        />
        <Stat label={t("ward.dlpTitle")} value={rupee(w.dlp_inr)} sub={t("ward.dlpSub", { jobs: w.dlp_jobs })} />
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        <section className="card">
          <h2 className="mb-2 text-sm font-bold">{t("ward.funnelTitle")}</h2>
          <BarList rows={funnelRows} />
        </section>
        <section className="card">
          <h2 className="mb-2 text-sm font-bold">{t("ward.byContractor")}</h2>
          <BarList
            rows={w.by_contractor.map((c: any) => ({
              label: (
                <Link href={`/contractor/${c.contractor_id}`} className="underline">
                  {c.name.replace(" (synthetic)", "")}
                </Link>
              ),
              value: c.billed_inr,
              text: rupee(c.billed_inr),
              sub: `${c.jobs} ${t("common.jobs")} · ${t("ward.failedPct")}: ${rupee(c.failed_inr)}`,
            }))}
          />
        </section>
        <section className="card">
          <h2 className="mb-2 text-sm font-bold">{t("ward.byMethod")}</h2>
          <BarList
            color="bg-amber-600"
            rows={w.by_method.map((m: any) => ({
              label: m.method,
              value: m.billed_inr,
              text: rupee(m.billed_inr),
              sub: `${m.jobs} ${t("common.jobs")} · ${m.failed_pct}% ${t("ward.failedPct")}`,
            }))}
          />
        </section>
        <section className="card">
          <h2 className="mb-2 text-sm font-bold">{t("ward.byMonth")}</h2>
          <BarList
            color="bg-slate-500"
            rows={w.by_month.map((m: any) => ({ label: m.month, value: m.billed_inr, text: rupee(m.billed_inr), sub: `${m.jobs} ${t("common.jobs")}` }))}
          />
          <h3 className="mb-1 mt-4 text-sm font-bold">{t("ward.context")}</h3>
          <dl className="grid grid-cols-[auto_1fr] gap-x-3 text-xs">
            <dt className="text-ink/60">{t("ward.lowLying")}</dt>
            <dd>{w.context.low_lying_index}</dd>
            <dt className="text-ink/60">{t("ward.heavyDays")}</dt>
            <dd>{w.context.heavy_rain_days_season}</dd>
            <dt className="text-ink/60">{t("ward.crews")}</dt>
            <dd>{w.context.crews}</dd>
            <dt className="text-ink/60">{t("ward.onTime")}</dt>
            <dd>{w.sla_pct}%</dd>
          </dl>
        </section>
      </div>

      <h2 className="h2">{t("ward.prioritiesTitle")}</h2>
      <p className="mb-2 text-sm text-ink/70">{t("ward.prioritiesSub")}</p>
      {prio.loading && <Loading />}
      {prio.error && <ErrorBox error={prio.error} onRetry={prio.reload} />}
      {prio.data && (
        <>
          <p className="mb-2 text-xs text-ink/70">
            {t("ward.asOf", { date: prio.data.as_of })} · {t("ward.remaining")}: {rupee(prio.data.remaining_inr)} ·{" "}
            {t("ward.allocation", { cap: prio.data.allocation_cap_pct, amt: inr(prio.data.allocatable_inr) })}
          </p>
          {prio.data.items.length === 0 && <p className="card text-sm">{t("ward.noPriorities")}</p>}
          <ol className="space-y-2">
            {prio.data.items.map((it: any) => (
              <li key={it.issue_id} className="card">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="flex h-7 w-7 items-center justify-center rounded-full bg-ledger-900 text-sm font-bold text-white">{it.rank}</span>
                  <strong className="text-sm">{it.category_label}</strong>
                  <span className="text-sm text-ink/70">{it.road_name || it.locality || ""}</span>
                  <span className={`chip ml-auto ${it.funded ? "border-emerald-300 bg-emerald-50 text-emerald-900" : "border-ledger-200 bg-ledger-50 text-ink/70"}`}>
                    {it.under_dlp ? t("ward.warranty") : it.funded ? t("ward.funded") : t("ward.notFunded")}
                  </span>
                </div>
                <p className="mt-1 text-sm">{(it.reasons as string[]).join("; ")}.</p>
                <div className="mt-1 text-xs text-ink/70">
                  {t("ward.method")}: {it.method} · {t("ward.estCost")}: {rupee(it.est_cost_inr)}
                </div>
                <details className="mt-2 text-xs">
                  <summary className="cursor-pointer text-ledger-700">{t("ward.howScore")}</summary>
                  <ul className="mt-1 space-y-1">
                    {FACTORS.map((k) => (
                      <li key={k} className="grid grid-cols-[110px_1fr_auto] items-center gap-2">
                        <span>{t("factor." + k)}</span>
                        <span className="h-2 rounded bg-ledger-100" aria-hidden>
                          <span className="block h-2 rounded bg-ledger-600" style={{ width: `${Math.round(it.factors[k] * 100)}%` }} />
                        </span>
                        <span className="tabular-nums text-ink/60">
                          {Math.round(it.factors[k] * 100)}% × {it.weights[k]}
                        </span>
                      </li>
                    ))}
                  </ul>
                </details>
              </li>
            ))}
          </ol>
        </>
      )}

      <h2 className="h2">{t("ward.findings")}</h2>
      <p className="mb-2 text-sm text-ink/70">{t("ward.findingsHelp")}</p>
      <div className="grid gap-2 lg:grid-cols-2">
        {shown.map((x) => (
          <FindingCard key={x.finding_id} f={x} />
        ))}
      </div>
      {findings.length > 6 && !showAll && (
        <button className="btn btn-ghost mt-2" onClick={() => setShowAll(true)}>
          {t("common.more")} ({findings.length - 6})
        </button>
      )}

      {w.clean_records?.length > 0 && (
        <>
          <h2 className="h2">{t("ward.cleanTitle")}</h2>
          <div className="grid gap-2 lg:grid-cols-2">
            {w.clean_records.map((x: any) => (
              <FindingCard key={x.finding_id} f={x} />
            ))}
          </div>
        </>
      )}

      <div className="mt-6 flex flex-wrap gap-2 no-print">
        <button className="btn btn-primary" onClick={() => window.print()}>
          {t("ward.print")}
        </button>
        {user?.role === "officer" && (
          <Link href={`/officer/${slug}`} className="btn btn-ghost">
            {t("nav.officer")}
          </Link>
        )}
      </div>
    </div>
  );
}
