"use client";
import Link from "next/link";
import { useLang } from "@/lib/i18n";
import { SourceList, type Evidence } from "./Source";

export type Finding = {
  finding_id: string;
  rule: string;
  title: string;
  polarity: "concern" | "positive";
  severity: "high" | "medium" | "low" | "info";
  subject: { type: string; id: string };
  text: string;
  metrics: Record<string, any>;
  context: Record<string, any>;
  evidence: Evidence[];
  reply?: { text: string; received_at: string } | null;
  actions: string[];
  flag_label?: string; // officer view only
};

const SEV_STYLE: Record<string, string> = {
  high: "border-amber-300 bg-amber-50 text-amber-900",
  medium: "border-yellow-200 bg-yellow-50 text-yellow-900",
  low: "border-ledger-200 bg-ledger-50 text-ink/70",
  info: "border-emerald-200 bg-emerald-50 text-emerald-900",
};

/** One finding: neutral text, context chips, evidence chips, reply slot, RTI action. */
export default function FindingCard({ f, officer = false }: { f: Finding; officer?: boolean }) {
  const { t } = useLang();
  const ctx: string[] = [];
  if (f.context?.low_lying_ward) ctx.push(t("finding.lowLying"));
  if (f.context?.heavy_rain_week || f.context?.heavy_rain_week_after) ctx.push(t("finding.heavyRain"));
  if (f.context?.threshold_relaxed) ctx.push(t("finding.relaxed"));
  const positive = f.polarity === "positive";
  const rtiHref = f.subject.type === "work_order" ? `/rti?work_order_id=${f.subject.id}` : "/rti";
  return (
    <article className={`card ${positive ? "border-emerald-200" : ""}`}>
      <div className="flex flex-wrap items-center gap-2">
        <h3 className="text-sm font-bold">{officer && f.flag_label ? f.flag_label : f.title}</h3>
        <span className={`chip ${SEV_STYLE[f.severity] || SEV_STYLE.low}`}>{t("sev." + f.severity)}</span>
        {f.subject.type === "work_order" && <span className="font-mono text-[11px] text-ledger-700">{f.subject.id}</span>}
      </div>
      <p className="mt-1 text-sm">{f.text}</p>
      {ctx.length > 0 && (
        <p className="mt-1 text-xs text-ink/60">
          {t("finding.context")}: {ctx.join(", ")}
        </p>
      )}
      <SourceList evidence={f.evidence} />
      {!positive && (
        <p className="mt-1.5 text-xs text-ink/70">
          <span className="font-semibold">{t("finding.reply")}:</span> {f.reply ? f.reply.text : t("finding.noReply")}
        </p>
      )}
      {!positive && f.actions?.includes("rti") && !officer && (
        <Link href={rtiHref} className="btn btn-ghost mt-2 !min-h-[36px] text-xs no-print">
          {t("finding.rti")}
        </Link>
      )}
    </article>
  );
}
