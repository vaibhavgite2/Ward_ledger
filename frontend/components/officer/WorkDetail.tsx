"use client";
import { useState } from "react";
import { api, useApi } from "@/lib/api";
import { useLang } from "@/lib/i18n";
import { dateOnly, inr } from "@/lib/format";
import { ErrorBox, Loading } from "@/components/Ui";
import FindingCard, { type Finding } from "@/components/FindingCard";
import { Source } from "@/components/Source";

function ReplyForm({ findingId, onSaved }: { findingId: string; onSaved: () => void }) {
  const { t } = useLang();
  const [open, setOpen] = useState(false);
  const [text, setText] = useState("");
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<Error | null>(null);
  const save = async () => {
    setErr(null);
    try {
      await api("/officer/reply", { method: "POST", body: { finding_id: findingId, reply_text: text } });
      setMsg(t("officer.reply.saved"));
      setText("");
      setOpen(false);
      onSaved();
    } catch (e) {
      setErr(e as Error);
    }
  };
  return (
    <div className="mt-1 text-xs">
      {!open && (
        <button type="button" onClick={() => setOpen(true)} className="underline">
          {t("officer.reply.title")}
        </button>
      )}
      {open && (
        <div className="space-y-1">
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder={t("officer.reply.placeholder")}
            rows={2}
            className="w-full rounded border border-ledger-200 p-2 text-sm"
          />
          <button type="button" disabled={!text.trim()} onClick={save} className="btn btn-primary !min-h-[32px] text-xs">
            {t("officer.reply.save")}
          </button>
        </div>
      )}
      {msg && <p className="text-emerald-800">{msg}</p>}
      {err && <ErrorBox error={err} />}
    </div>
  );
}

/** Side panel for one work order: facts, numbered flags with evidence, reply slot, and the primary action. */
export default function WorkDetail({ woId, onClose, onDraft }: { woId: string; onClose: () => void; onDraft: (id: string) => void }) {
  const { t } = useLang();
  const { data: w, error, loading, reload } = useApi<any>(`/officer/works/${woId}`);
  if (loading && !w) return <Loading />;
  if (error) return <ErrorBox error={error} onRetry={reload} />;
  if (!w) return null;
  const flags: Finding[] = w.findings || [];
  const row = (k: string, v: React.ReactNode) => (
    <div className="flex justify-between gap-3 border-b border-ledger-100 py-0.5 text-sm">
      <span className="text-ledger-700">{k}</span>
      <span className="text-right">{v}</span>
    </div>
  );
  return (
    <aside className="border border-ledger-200 bg-white p-3" aria-label={t("officer.detail.title", { id: woId })}>
      <div className="flex items-center gap-2">
        <h2 className="font-mono text-base font-bold">{t("officer.detail.title", { id: woId })}</h2>
        <button type="button" onClick={onClose} className="btn btn-ghost ml-auto !min-h-[32px] text-xs">
          {t("officer.detail.close")}
        </button>
      </div>
      <button type="button" onClick={() => onDraft(woId)} className="btn btn-primary mt-2 w-full">
        {t("officer.detail.draft")}
      </button>

      <h3 className="h2 !mt-4 !text-sm">{t("officer.detail.facts")}</h3>
      <div>
        {row(t("officer.detail.road"), `${w.road?.road_name ?? w.road_id} (${w.road_id})`)}
        {row(t("officer.detail.contractor"), `${w.contractor_name}`)}
        {row(t("officer.detail.method"), w.repair_method)}
        {row(t("officer.detail.area"), w.area_sqm)}
        {row(t("officer.detail.assigned"), dateOnly(w.assigned_at))}
        {row(t("officer.detail.completed"), dateOnly(w.completed_at))}
        {row(
          t("officer.detail.billed"),
          <>
            ₹{inr(w.cost_inr)}{" "}
            {w.cost_vs_rate_pct !== null && w.cost_vs_rate_pct !== undefined && (
              <span className="text-xs text-ink/60">({t("officer.detail.vsRate", { n: w.cost_vs_rate_pct })})</span>
            )}
          </>
        )}
        {row(t("officer.detail.expected"), `₹${inr(w.expected_cost_inr)}`)}
        {w.road?.under_dlp && row(t("officer.detail.dlp"), t("common.yes"))}
        {w.engineer_remark && row(t("officer.detail.remark"), w.engineer_remark)}
      </div>
      <div className="mt-1 flex flex-wrap gap-1">
        {(w.provenance || []).map((p: any, i: number) => (
          <Source key={i} ev={p} />
        ))}
      </div>

      {w.linked_complaints?.length > 0 && (
        <p className="mt-2 text-xs">
          <span className="font-semibold">{t("officer.detail.linked")}:</span>{" "}
          <span className="font-mono">{w.linked_complaints.map((c: any) => c.complaint_id).join(", ")}</span>
        </p>
      )}

      <h3 className="h2 !text-sm">{t("officer.detail.flags")}</h3>
      {flags.length === 0 && <p className="text-sm">{t("officer.detail.noFlags")}</p>}
      <ol className="space-y-2">
        {flags.map((f, i) => (
          <li key={f.finding_id}>
            <div className="mb-0.5 font-mono text-xs text-ledger-700">{i + 1}.</div>
            <FindingCard f={f} officer />
            {f.polarity === "concern" && <ReplyForm findingId={f.finding_id} onSaved={reload} />}
          </li>
        ))}
      </ol>
    </aside>
  );
}
