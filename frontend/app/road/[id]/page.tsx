"use client";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useApi } from "@/lib/api";
import { useLang } from "@/lib/i18n";
import { dateOnly, inr, rupee, wardSlug } from "@/lib/format";
import { ErrorBox, Loading, PageTitle, Stat } from "@/components/Ui";
import { Source } from "@/components/Source";
import { RULE_LABEL } from "@/lib/rules";

export default function RoadPage() {
  const { id } = useParams<{ id: string }>();
  const { t, lang } = useLang();
  const { data: r, error, loading, reload } = useApi<any>(`/roads/${id}`);
  if (loading) return <Loading />;
  if (error) return <ErrorBox error={error} onRetry={reload} />;
  if (!r) return null;
  return (
    <div className="mx-auto max-w-4xl">
      <PageTitle sub={`${r.road_id} · ${t("common.ward")} ${r.ward_code}`}>{t("road.title", { name: r.road_name, n: r.segment_no })}</PageTitle>
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <span className="chip border-ledger-200 bg-white">
          {t("road.type")}: {r.road_type}
        </span>
        <span className="chip border-ledger-200 bg-white">
          {t("road.surface")}: {r.surface}
        </span>
        <span className="chip border-ledger-200 bg-white">
          {t("road.resurfaced")}: {dateOnly(r.last_resurfaced)}
        </span>
        {r.under_dlp && <span className="chip border-blue-300 bg-blue-50 text-blue-900">{t("road.warranty")}</span>}
        <Source ev={r.provenance[0]} label={r.road_id} />
      </div>

      <div className="mt-4 grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Stat label={t("road.repairs")} value={r.repairs} />
        <Stat label={t("road.spent")} value={rupee(r.spent_inr)} />
        <Stat label={t("road.failed")} value={r.failed_repairs} tone={r.failed_repairs ? "warn" : undefined} sub={r.failed_inr ? rupee(r.failed_inr) : undefined} />
        <Stat label={t("road.openIssues")} value={r.open_issues.length} tone={r.open_issues.length ? "warn" : undefined} />
      </div>

      {Object.keys(r.finding_counts).length > 0 && (
        <p className="mt-3 flex flex-wrap gap-1 text-xs">
          {Object.entries(r.finding_counts).map(([rule, n]) => (
            <span key={rule} className="chip border-ledger-200 bg-white">
              {RULE_LABEL[rule]?.[lang] || rule}: {String(n)}
            </span>
          ))}
        </p>
      )}

      <h2 className="h2">{t("road.history")}</h2>
      <div className="card overflow-x-auto p-0">
        <table className="w-full min-w-[560px] text-left text-sm">
          <thead className="bg-ledger-100 text-xs text-ink/70">
            <tr>
              <th className="p-2">{t("road.col.wo")}</th>
              <th className="p-2">{t("road.col.done")}</th>
              <th className="p-2">{t("complaint.method")}</th>
              <th className="p-2 text-right">{t("road.col.cost")}</th>
              <th className="p-2">{t("road.col.held")}</th>
              <th className="p-2">{t("common.contractor")}</th>
            </tr>
          </thead>
          <tbody>
            {r.works.map((w: any) => (
              <tr key={w.work_order_id} className="border-t border-ledger-100">
                <td className="p-2 font-mono text-xs">{w.work_order_id}</td>
                <td className="p-2">{dateOnly(w.completed_at)}</td>
                <td className="p-2">{w.repair_method}</td>
                <td className="p-2 text-right tabular-nums">{inr(w.cost_inr)}</td>
                <td className={`p-2 ${w.reopened_within_30d ? "font-semibold text-amber-800" : ""}`}>{w.reopened_within_30d ? t("common.no") : t("common.yes")}</td>
                <td className="p-2">
                  <Link href={`/contractor/${w.contractor_id}`} className="underline">
                    {w.contractor_name.replace(" (synthetic)", "")}
                  </Link>
                </td>
              </tr>
            ))}
            {r.works.length === 0 && (
              <tr>
                <td colSpan={6} className="p-3 text-center text-ink/60">
                  {t("map.noRepairs")}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <div className="mt-5 flex flex-wrap gap-2 no-print">
        <Link href={`/rti?road_id=${r.road_id}`} className="btn btn-primary">
          {t("road.rti")}
        </Link>
        <Link href={`/ward/${wardSlug(r.ward_code)}`} className="btn btn-ghost">
          {t("common.ward")} {r.ward_code}
        </Link>
      </div>
    </div>
  );
}
