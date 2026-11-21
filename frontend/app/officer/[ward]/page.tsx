"use client";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useState } from "react";
import { useApi } from "@/lib/api";
import { useLang } from "@/lib/i18n";
import { useRole } from "@/lib/role";
import { dateOnly, inr, wardCode, wardSlug } from "@/lib/format";
import { ErrorBox, Loading } from "@/components/Ui";
import WorkDetail from "@/components/officer/WorkDetail";
import NotingEditor from "@/components/officer/NotingEditor";
import ReviewQueue from "@/components/officer/ReviewQueue";

const PAGE = 50;
const SORTS = ["dlp", "sla", "findings", "recent", "cost"] as const;
const SEV_DOT: Record<string, string> = {
  high: "border-amber-400 bg-amber-100 text-amber-900",
  medium: "border-yellow-300 bg-yellow-50 text-yellow-900",
  low: "border-ledger-200 bg-ledger-50 text-ink/70",
};

type Row = {
  work_order_id: string;
  road_id: string;
  road_name: string;
  work_type: string;
  repair_method: string;
  contractor_name: string;
  completed_at: string;
  cost_inr: number;
  sla_hours: number;
  sla_met: boolean;
  reopened_within_30d: boolean;
  under_dlp: boolean;
  flags: { rule: string; severity: string; label: string }[];
};

export default function OfficerWardPage() {
  const params = useParams<{ ward: string }>();
  const router = useRouter();
  const { t } = useLang();
  const { role } = useRole();
  const code = wardCode(params.ward);
  const slug = wardSlug(code);
  const ok = role === "officer";

  const [sort, setSort] = useState<(typeof SORTS)[number]>("dlp");
  const [rule, setRule] = useState<string | null>(null);
  const [page, setPage] = useState(0);
  const [sel, setSel] = useState<string | null>(null);
  const [noting, setNoting] = useState<string | null>(null);
  const [showQueue, setShowQueue] = useState(false);

  const wards = useApi<any[]>(ok ? "/wards" : null);
  const works = useApi<{ total: number; items: Row[] }>(ok ? `/officer/works?ward=${slug}&sort=${sort}&limit=500` : null);
  const flags = useApi<{ counts: Record<string, number>; review_queue_pending: number }>(ok ? `/officer/flags?ward=${slug}&limit=1` : null);

  if (!ok) {
    return <p role="alert" className="card border-amber-300 bg-amber-50 text-sm">{t("officer.needRole")}</p>;
  }

  const all = works.data?.items ?? [];
  const items = rule ? all.filter((r) => r.flags.some((f) => f.rule === rule)) : all;
  const pages = Math.max(1, Math.ceil(items.length / PAGE));
  const cur = Math.min(page, pages - 1);
  const shown = items.slice(cur * PAGE, cur * PAGE + PAGE);
  const counts = flags.data?.counts ?? {};
  const err = works.error || flags.error;

  return (
    <div className="text-sm">
      <div className="mb-2 flex flex-wrap items-center gap-3">
        <h1 className="text-xl font-extrabold">{t("officer.title", { code })}</h1>
        <label className="flex items-center gap-1 text-xs">
          {t("officer.selectWard")}
          <select
            value={code}
            onChange={(e) => {
              setSel(null);
              setRule(null);
              setPage(0);
              router.push(`/officer/${wardSlug(e.target.value)}`);
            }}
            className="min-h-[36px] rounded border border-ledger-200 bg-white px-1"
          >
            {(wards.data ?? [{ ward_code: code, ward_name: "" }]).map((w) => (
              <option key={w.ward_code} value={w.ward_code}>
                {w.ward_code} {w.ward_name ? "· " + w.ward_name : ""}
              </option>
            ))}
          </select>
        </label>
        <Link href={`/officer/${slug}/budget`} className="btn btn-ghost !min-h-[36px] text-xs">
          {t("officer.budgetLink")}
        </Link>
        <Link href={`/ward/${slug}`} className="btn btn-ghost !min-h-[36px] text-xs">
          {t("officer.publicWard")}
        </Link>
        <button type="button" onClick={() => setShowQueue((v) => !v)} className="btn btn-ghost !min-h-[36px] text-xs" aria-expanded={showQueue}>
          {t("officer.pendingReview", { n: flags.data?.review_queue_pending ?? "…" })}
        </button>
      </div>

      <div className="mb-2 border-y border-ledger-200 py-1.5">
        <div className="mb-1 text-xs text-ledger-700">{t("officer.flagStrip")}</div>
        <div className="flex flex-wrap gap-1.5">
          <button
            type="button"
            onClick={() => {
              setRule(null);
              setPage(0);
            }}
            aria-pressed={rule === null}
            className={`chip !text-xs ${rule === null ? "border-ledger-700 bg-ledger-700 text-white" : "border-ledger-200 bg-white"}`}
          >
            {t("officer.all")} ({works.data?.total ?? "…"})
          </button>
          {Object.entries(counts).map(([r, n]) =>
            r === "never_fixed" ? (
              <span key={r} className="chip border-ledger-200 bg-ledger-50 !text-xs text-ink/70">
                {t("officer.rule." + r)} ({n})
              </span>
            ) : (
              <button
                key={r}
                type="button"
                onClick={() => {
                  setRule(rule === r ? null : r);
                  setPage(0);
                }}
                aria-pressed={rule === r}
                className={`chip !text-xs ${rule === r ? "border-ledger-700 bg-ledger-700 text-white" : "border-ledger-200 bg-white"}`}
              >
                {t("officer.rule." + r)} ({n})
              </button>
            )
          )}
        </div>
      </div>

      {showQueue && (
        <div className="mb-3">
          <ReviewQueue onChange={flags.reload} />
        </div>
      )}
      {noting && (
        <div className="mb-3">
          <NotingEditor workId={noting} onClose={() => setNoting(null)} />
        </div>
      )}

      {err && <ErrorBox error={err} onRetry={works.reload} />}
      {works.loading && !works.data && <Loading />}

      {works.data && (
        <div className="flex flex-col gap-3 lg:flex-row lg:items-start">
          <div className="min-w-0 flex-1">
            <div className="mb-1 flex flex-wrap items-center gap-3 text-xs">
              <label className="flex items-center gap-1">
                {t("officer.sortBy")}
                <select
                  value={sort}
                  onChange={(e) => {
                    setSort(e.target.value as typeof sort);
                    setPage(0);
                  }}
                  className="min-h-[32px] rounded border border-ledger-200 bg-white px-1"
                >
                  {SORTS.map((s) => (
                    <option key={s} value={s}>
                      {t("officer.sort." + s)}
                    </option>
                  ))}
                </select>
              </label>
              <span className="text-ink/70">{t("officer.total", { n: items.length, p: cur + 1, pages })}</span>
              <span className="ml-auto flex gap-1">
                <button type="button" disabled={cur === 0} onClick={() => setPage(cur - 1)} className="btn btn-ghost !min-h-[28px] !px-2 text-xs">
                  {t("officer.prev")}
                </button>
                <button type="button" disabled={cur >= pages - 1} onClick={() => setPage(cur + 1)} className="btn btn-ghost !min-h-[28px] !px-2 text-xs">
                  {t("officer.next")}
                </button>
              </span>
            </div>
            <div className="overflow-x-auto border border-ledger-200 bg-white">
              <table className="w-full min-w-[820px] text-left text-xs">
                <thead className="sticky top-0 border-b border-ledger-200 bg-ledger-100 text-ledger-900">
                  <tr>
                    <th className="px-1.5 py-1">{t("officer.col.wo")}</th>
                    <th className="px-1.5">{t("officer.col.road")}</th>
                    <th className="px-1.5">{t("officer.col.type")}</th>
                    <th className="px-1.5">{t("officer.col.contractor")}</th>
                    <th className="px-1.5">{t("officer.col.done")}</th>
                    <th className="px-1.5 text-right">{t("officer.col.billed")}</th>
                    <th className="px-1.5">{t("officer.col.sla")}</th>
                    <th className="px-1.5">{t("officer.col.held")}</th>
                    <th className="px-1.5">{t("officer.col.dlp")}</th>
                    <th className="px-1.5">{t("officer.col.flags")}</th>
                  </tr>
                </thead>
                <tbody>
                  {shown.map((r) => (
                    <tr
                      key={r.work_order_id}
                      onClick={() => setSel(r.work_order_id)}
                      className={`cursor-pointer border-b border-ledger-100 align-top hover:bg-ledger-50 ${sel === r.work_order_id ? "bg-amber-50" : ""}`}
                    >
                      <td className="px-1.5 py-1 font-mono">
                        <button type="button" onClick={() => setSel(r.work_order_id)} className="underline">
                          {r.work_order_id}
                        </button>
                      </td>
                      <td className="px-1.5">{r.road_name}</td>
                      <td className="px-1.5">{r.work_type}</td>
                      <td className="px-1.5">{r.contractor_name.replace(" (synthetic)", "")}</td>
                      <td className="px-1.5 font-mono">{dateOnly(r.completed_at)}</td>
                      <td className="px-1.5 text-right font-mono tabular-nums">{inr(r.cost_inr)}</td>
                      <td className={`px-1.5 ${r.sla_met ? "" : "font-semibold text-amber-800"}`}>
                        {r.sla_met ? t("officer.sla.met") : t("officer.sla.missed")}
                      </td>
                      <td className={`px-1.5 ${r.reopened_within_30d ? "font-semibold text-amber-800" : ""}`}>
                        {r.reopened_within_30d ? t("officer.held.no") : t("officer.held.yes")}
                      </td>
                      <td className="px-1.5">{r.under_dlp ? <span className="font-bold text-amber-800">{t("officer.dlp.mark")}</span> : ""}</td>
                      <td className="px-1.5">
                        <div className="flex flex-wrap gap-1">
                          {r.flags
                            .filter((f) => f.rule !== "clean_record")
                            .map((f) => (
                              <span key={f.rule} className={`chip !px-1.5 !py-0 text-[10px] ${SEV_DOT[f.severity] || SEV_DOT.low}`}>
                                {t("officer.rule." + f.rule)}
                              </span>
                            ))}
                        </div>
                      </td>
                    </tr>
                  ))}
                  {shown.length === 0 && (
                    <tr>
                      <td colSpan={10} className="px-2 py-4 text-center">
                        {t("officer.empty")}
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
          {sel && (
            <div className="w-full shrink-0 lg:sticky lg:top-2 lg:w-[400px]">
              <WorkDetail woId={sel} onClose={() => setSel(null)} onDraft={(id) => setNoting(id)} />
            </div>
          )}
        </div>
      )}
    </div>
  );
}
