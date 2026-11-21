"use client";
import Link from "next/link";
import { useParams } from "next/navigation";
import { Fragment, useState } from "react";
import { useApi } from "@/lib/api";
import { useLang } from "@/lib/i18n";
import { useAuth } from "@/lib/auth";
import OfficerShell from "@/components/officer/OfficerShell";
import { inr, rupee, wardCode, wardSlug } from "@/lib/format";
import { ErrorBox, Loading, Progress, Stat } from "@/components/Ui";

const FACTORS = ["S", "F", "R", "A", "P", "C", "D"] as const;

type Alt = { method: string; reopen_pct: number; unit_rate_inr: number; unit: string };
type Item = {
  rank: number;
  issue_id: string;
  category: string;
  category_label: string;
  road_id: string | null;
  road_name: string | null;
  locality: string | null;
  kind: string;
  score: number;
  factors: Record<string, number>;
  weights: Record<string, number>;
  under_dlp: boolean;
  method: string | null;
  alternatives: Alt[];
  est_cost_inr: number | null;
  bmc_cost_inr: number;
  cumulative_inr: number;
  funded: boolean;
  action: string;
  reasons_text: string[];
  rationale: string;
  complaint_count: number;
  upvotes: number;
  location_known?: boolean;
};

/** Seven factor mini-bars; the weight is in the title so the arithmetic is inspectable. */
function Factors({ item, label }: { item: Item; label: (k: string) => string }) {
  return (
    <div className="flex items-end gap-0.5" role="img" aria-label={FACTORS.map((k) => `${label(k)} ${item.factors[k]}`).join(", ")}>
      {FACTORS.map((k) => (
        <div key={k} className="flex flex-col items-center" title={`${label(k)}: ${item.factors[k]} × ${item.weights[k]}`}>
          <div className="flex h-8 w-3 items-end bg-ledger-100">
            <div className="w-3 bg-ledger-600" style={{ height: `${Math.round(item.factors[k] * 100)}%` }} />
          </div>
          <span className="font-mono text-[9px]">{k}</span>
        </div>
      ))}
    </div>
  );
}

export default function BudgetPage() {
  const params = useParams<{ ward: string }>();
  const { t } = useLang();
  const { user } = useAuth();
  const code = wardCode(params.ward);
  const slug = wardSlug(code);
  const ok = user?.role === "officer";
  const [input, setInput] = useState("");
  const [asOf, setAsOf] = useState("");
  const path = ok ? `/officer/budget/${slug}${asOf ? `?as_of=${asOf}` : ""}` : null;
  const { data, error, loading, reload } = useApi<any>(path);

  if (!ok) return <OfficerShell ward={params.ward}>{null}</OfficerShell>;

  const items: Item[] = data?.items ?? [];
  const firstUnfunded = items.findIndex((i) => !i.funded);
  const fLabel = (k: string) => t("factor." + k);
  const usedPct = data && data.budget_inr ? (data.spend_inr / data.budget_inr) * 100 : 0;

  return (
    <div className="text-sm">
      <div className="mb-2 flex flex-wrap items-center gap-3">
        <h1 className="text-xl font-extrabold">{t("officer.budget.title", { code })}</h1>
        <Link href={`/officer/${slug}`} className="btn btn-ghost !min-h-[36px] text-xs">
          {t("officer.budget.back")}
        </Link>
        <form
          className="flex items-center gap-1 text-xs"
          onSubmit={(e) => {
            e.preventDefault();
            setAsOf(input);
          }}
        >
          <label className="flex items-center gap-1">
            {t("officer.budget.asOf")}
            <input
              type="date"
              value={input || data?.as_of || ""}
              min="2025-06-01"
              max="2025-10-05"
              onChange={(e) => setInput(e.target.value)}
              className="min-h-[36px] rounded border border-ledger-200 bg-white px-1"
            />
          </label>
          <button type="submit" className="btn btn-primary !min-h-[36px] text-xs">
            {t("officer.budget.apply")}
          </button>
        </form>
      </div>

      {loading && !data && <Loading />}
      {error && <ErrorBox error={error} onRetry={reload} />}

      {data && (
        <>
          <p className="mb-2 text-xs text-ink/70">{t("officer.budget.advisory")}</p>
          <div className="grid grid-cols-2 gap-2 md:grid-cols-4 lg:grid-cols-8">
            <Stat label={t("officer.budget.budget")} value={rupee(data.budget_inr)} />
            <Stat label={t("officer.budget.spent")} value={rupee(data.spend_inr)} tone={data.over_budget ? "warn" : undefined} />
            <Stat label={t("officer.budget.remaining")} value={rupee(data.remaining_inr)} tone={data.over_budget ? "warn" : undefined} />
            <Stat label={t("officer.budget.cap", { pct: data.allocation_cap_pct })} value={rupee(data.allocatable_inr)} />
            <Stat label={t("officer.budget.allocated")} value={rupee(data.allocated_inr)} />
            <Stat label={t("officer.budget.rain")} value={data.rain_7d_mm} />
            <Stat label={t("officer.budget.candidates")} value={data.candidates} />
            <Stat label={t("officer.budget.fundedCount")} value={data.funded} />
          </div>
          <div className="my-2 max-w-md">
            <Progress pct={usedPct} over={data.over_budget} />
          </div>
          {data.over_budget && <p role="alert" className="mb-2 border-l-4 border-amber-400 bg-amber-50 px-2 py-1">{t("officer.budget.overBudget")}</p>}
          <p className="mb-2 font-mono text-[11px] text-ink/70">
            {t("officer.budget.weights")}: {Object.entries(data.weights as Record<string, number>).map(([k, v]) => `${k}=${v}`).join("  ")}
            {"  ·  "}
            {FACTORS.map((k) => `${k} ${fLabel(k)}`).join(", ")}
          </p>

          {items.length === 0 ? (
            <p>{t("officer.budget.noItems")}</p>
          ) : (
            <div className="overflow-x-auto border border-ledger-200 bg-white">
              <table className="w-full min-w-[1000px] text-left text-xs">
                <thead className="border-b border-ledger-200 bg-ledger-100">
                  <tr>
                    <th className="px-1.5 py-1">{t("officer.budget.col.rank")}</th>
                    <th className="px-1.5">{t("officer.budget.col.issue")}</th>
                    <th className="px-1.5">{t("officer.budget.col.priority")}</th>
                    <th className="px-1.5">{t("officer.budget.col.factors")}</th>
                    <th className="px-1.5">{t("officer.budget.col.method")}</th>
                    <th className="px-1.5 text-right">{t("officer.budget.col.est")}</th>
                    <th className="px-1.5 text-right">{t("officer.budget.col.bmc")}</th>
                    <th className="px-1.5 text-right">{t("officer.budget.col.cum")}</th>
                    <th className="px-1.5">{t("officer.budget.col.plan")}</th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((it, idx) => (
                    <Fragment key={it.issue_id}>
                      {idx === firstUnfunded && firstUnfunded > 0 && (
                        <tr className="bg-amber-50">
                          <td colSpan={9} className="border-y-2 border-dashed border-amber-400 px-2 py-1 font-semibold text-amber-900">
                            {t("officer.budget.divider", { pct: data.allocation_cap_pct })}
                          </td>
                        </tr>
                      )}
                      <tr className={`border-b border-ledger-100 align-top ${it.funded ? "" : "text-ink/60"}`}>
                        <td className="px-1.5 py-1 font-mono">{it.rank}</td>
                        <td className="max-w-[320px] px-1.5">
                          <div className="font-semibold">
                            {it.category_label} · {it.road_name || it.locality || "-"}
                          </div>
                          <div className="font-mono text-[10px] text-ink/60">
                            {it.issue_id} · {t("officer.budget.kind." + it.kind)} · {t("officer.budget.reports", { n: it.complaint_count, u: it.upvotes })}
                          </div>
                          {it.location_known === false && <div className="text-[10px] text-ink/60">{t("officer.budget.unlocated")}</div>}
                          <details className="mt-0.5">
                            <summary className="cursor-pointer text-[11px] underline">{t("officer.budget.why")}</summary>
                            <p className="mt-0.5">{it.rationale}</p>
                          </details>
                        </td>
                        <td className="px-1.5">
                          <div className="font-mono tabular-nums">{it.score.toFixed(3)}</div>
                          <div className="mt-0.5 h-1.5 w-16 bg-ledger-100">
                            <div className="h-1.5 bg-amber-500" style={{ width: `${Math.min(100, it.score * 100)}%` }} />
                          </div>
                        </td>
                        <td className="px-1.5">
                          <Factors item={it} label={fLabel} />
                        </td>
                        <td className="max-w-[220px] px-1.5">
                          <div>{it.method}</div>
                          {it.alternatives.length > 1 && (
                            <details>
                              <summary className="cursor-pointer text-[11px] underline">{t("officer.budget.alt")}</summary>
                              <ul className="font-mono text-[10px]">
                                {it.alternatives.map((a) => (
                                  <li key={a.method}>
                                    {a.method}: {a.reopen_pct}%
                                  </li>
                                ))}
                              </ul>
                            </details>
                          )}
                        </td>
                        <td className="px-1.5 text-right font-mono tabular-nums">{it.est_cost_inr === null ? "-" : inr(it.est_cost_inr)}</td>
                        <td className="px-1.5 text-right font-mono tabular-nums">
                          {it.under_dlp ? (
                            <span className="font-semibold text-emerald-800" title={t("officer.budget.warrantyAction")}>
                              0
                            </span>
                          ) : (
                            inr(it.bmc_cost_inr)
                          )}
                          {it.under_dlp && <div className="font-sans text-[10px] font-normal text-emerald-800">{t("officer.budget.warrantyAction")}</div>}
                        </td>
                        <td className="px-1.5 text-right font-mono tabular-nums">{inr(it.cumulative_inr)}</td>
                        <td className="px-1.5">
                          <span className={`chip !text-[10px] ${it.funded ? "border-emerald-300 bg-emerald-50 text-emerald-900" : "border-ledger-200 bg-ledger-50"}`}>
                            {it.funded ? t("officer.budget.funded") : t("officer.budget.notFunded")}
                          </span>
                        </td>
                      </tr>
                    </Fragment>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
    </div>
  );
}
