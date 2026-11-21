"use client";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";
import { useApi } from "@/lib/api";
import { useLang } from "@/lib/i18n";
import { dateOnly, rupee } from "@/lib/format";
import { ErrorBox, Loading, PageTitle } from "@/components/Ui";
import { Source } from "@/components/Source";
import FindingCard from "@/components/FindingCard";

const TONE: Record<string, string> = {
  fixed: "border-emerald-300 bg-emerald-50 text-emerald-900",
  linked_via_issue: "border-emerald-300 bg-emerald-50 text-emerald-900",
  fixed_failed: "border-amber-300 bg-amber-50 text-amber-900",
  never_fixed: "border-amber-300 bg-amber-50 text-amber-900",
  pending: "border-ledger-200 bg-ledger-50 text-ink",
  closed_other: "border-ledger-200 bg-ledger-50 text-ink",
  duplicate: "border-ledger-200 bg-ledger-50 text-ink",
  resolved_no_record: "border-ledger-200 bg-ledger-50 text-ink",
};

export default function ComplaintPage() {
  const { id } = useParams<{ id: string }>();
  const { t } = useLang();
  const { data: c, error, loading, reload } = useApi<any>(`/complaints/${id}`);
  const [copied, setCopied] = useState(false);

  const share = async () => {
    const url = window.location.href;
    try {
      if (navigator.share) await navigator.share({ title: t("complaint.title", { id }), url });
      else {
        await navigator.clipboard.writeText(url);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
      }
    } catch {}
  };

  if (loading) return <Loading />;
  if (error) return <ErrorBox error={error} onRetry={reload} />;
  if (!c) return null;
  const w = c.work;
  const evLabels: Record<string, string> = {
    received: "complaint.ev.received",
    assigned: "complaint.ev.assigned",
    started: "complaint.ev.started",
    completed: "complaint.ev.completed",
  };

  return (
    <div className="mx-auto max-w-3xl">
      <PageTitle>{t("complaint.title", { id: c.complaint_id })}</PageTitle>
      <div className="flex flex-wrap items-center gap-2">
        <span className={`chip text-sm ${TONE[c.link_status] || TONE.pending}`}>{t("complaint.status." + c.link_status)}</span>
        <Source ev={c.provenance[0]} label={c.complaint_id} />
      </div>

      <section className="card mt-3 text-sm">
        <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1">
          <dt className="text-ink/60">{t("complaint.received")}</dt>
          <dd>
            {dateOnly(c.received_at)} · {c.channel}
          </dd>
          <dt className="text-ink/60">{t("complaint.category")}</dt>
          <dd>
            <strong>{c.category_label}</strong>
            {c.category_changed && <span className="block text-xs text-ink/60">{t("complaint.reportedAs", { x: c.category_reported })}</span>}
            <span className="block text-xs text-ink/60">{c.category_verified ? t("complaint.verified") : t("complaint.unverified")}</span>
          </dd>
          {c.location.locality && (
            <>
              <dt className="text-ink/60">{t("common.ward")}</dt>
              <dd>
                {c.location.ward_code} · {t("complaint.location", { x: c.location.locality })}
              </dd>
            </>
          )}
          {c.issue && c.issue.reported_times > 1 && (
            <>
              <dt className="text-ink/60"> </dt>
              <dd>{t("complaint.reportedTimes", { n: c.issue.reported_times })}</dd>
            </>
          )}
        </dl>
      </section>

      <h2 className="h2">{t("complaint.timeline")}</h2>
      <ol className="space-y-3 border-l-2 border-ledger-200 pl-4">
        {c.events.map((e: any, i: number) => (
          <li key={i} className="relative">
            <span className="absolute -left-[22px] top-1.5 h-3 w-3 rounded-full border-2 border-ledger-600 bg-white" aria-hidden />
            <div className="text-sm font-semibold">{t(evLabels[e.kind])}</div>
            <div className="text-xs text-ink/70">
              {dateOnly(e.at)}
              {e.channel ? ` · ${e.channel}` : ""}
            </div>
          </li>
        ))}
        {!w && (
          <li className="relative">
            <span className="absolute -left-[22px] top-1.5 h-3 w-3 rounded-full border-2 border-amber-500 bg-amber-100" aria-hidden />
            <div className="text-sm font-semibold">{t("complaint.noWork")}</div>
            {c.days_open !== null && <div className="text-xs text-ink/70">{t("complaint.daysOpen", { n: c.days_open })}</div>}
          </li>
        )}
      </ol>

      {c.filed_after_completion && c.issue && (
        <p className="mt-2 text-xs text-ink/70">{t("complaint.afterCompletion", { n: c.issue.reported_times })}</p>
      )}

      {w && (
        <section className="card mt-4 text-sm">
          <h2 className="mb-2 font-bold">{t("complaint.work")}</h2>
          <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1.5">
            <dt className="text-ink/60">{t("complaint.wo")}</dt>
            <dd className="font-mono">
              {w.work_order_id} <Source ev={w.provenance[0]} label="source" />
            </dd>
            <dt className="text-ink/60">{t("common.contractor")}</dt>
            <dd>
              <Link href={`/contractor/${w.contractor_id}`} className="underline">
                {w.contractor_name}
              </Link>
            </dd>
            <dt className="text-ink/60">{t("complaint.method")}</dt>
            <dd>{w.repair_method}</dd>
            <dt className="text-ink/60">{t("complaint.cost")}</dt>
            <dd>
              <strong>{rupee(w.cost_inr)}</strong>
              {w.expected_cost_inr ? (
                <span className="block text-xs text-ink/70">
                  {t("complaint.expected")} {rupee(w.expected_cost_inr)} ({t("complaint.vsRate", { n: (w.cost_vs_rate_pct >= 0 ? "+" : "") + w.cost_vs_rate_pct })})
                </span>
              ) : null}
            </dd>
            <dt className="text-ink/60">{t("complaint.sla")}</dt>
            <dd>
              {w.sla_met ? t("common.yes") : t("common.no")} <span className="text-xs text-ink/60">({t("complaint.slaTarget", { n: w.sla_hours })})</span>
            </dd>
            <dt className="text-ink/60">{t("complaint.reopened")}</dt>
            <dd className={w.reopened_within_30d ? "font-semibold text-amber-800" : ""}>{w.reopened_within_30d ? t("common.yes") : t("common.no")}</dd>
            {w.road && (
              <>
                <dt className="text-ink/60">{t("common.road")}</dt>
                <dd>
                  <Link href={`/road/${w.road.road_id}`} className="underline">
                    {w.road.road_name} · {w.road.segment_no}
                  </Link>
                  <span className="block text-xs text-ink/70">{w.road.under_dlp ? t("complaint.warranty") : t("complaint.noWarranty")}</span>
                </dd>
              </>
            )}
          </dl>
        </section>
      )}

      {(w || c.findings.length > 0) && (
        <>
          <h2 className="h2">{t("complaint.findings")}</h2>
          {c.findings.length === 0 ? (
            <p className="card text-sm">{t("complaint.noFindings")}</p>
          ) : (
            <div className="space-y-2">
              {c.findings
                .filter((f: any) => f.rule !== "sla_missed")
                .map((f: any) => (
                  <FindingCard key={f.finding_id} f={f} />
                ))}
            </div>
          )}
        </>
      )}

      <div className="mt-5 flex flex-wrap items-center gap-2 no-print">
        <Link href={`/rti?complaint_id=${c.complaint_id}`} className={`btn ${c.rti_suggested ? "btn-primary" : "btn-ghost"}`}>
          {t("finding.rti")}
        </Link>
        <button onClick={share} className="btn btn-ghost">
          {copied ? t("common.copied") : t("common.share")}
        </button>
        <Link href="/" className="btn btn-ghost">
          {t("complaint.lookup")}
        </Link>
      </div>
      <p className="mt-2 text-xs text-ink/60">{t("complaint.rtiHelp")}</p>
    </div>
  );
}
