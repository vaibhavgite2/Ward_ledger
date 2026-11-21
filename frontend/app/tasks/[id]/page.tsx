"use client";
import dynamic from "next/dynamic";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState, type FormEvent } from "react";
import { api, useApi } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { rupee } from "@/lib/format";
import { useLang } from "@/lib/i18n";
import { ErrorBox, Loading } from "@/components/Ui";
import { Gallery, NeedLogin, TaskStatus, TicketStatus, Timeline } from "@/components/live/bits";

const LocationPicker = dynamic(() => import("@/components/live/LocationPicker"), { ssr: false, loading: () => <Loading /> });
const TONE: Record<string, string> = {
  concern: "border-amber-300 bg-amber-50 text-amber-900",
  info: "border-ledger-200 bg-white",
  positive: "border-emerald-300 bg-emerald-50 text-emerald-900",
};

/** One task (DFD 4.0-6.0): the assigned contractor works and reports here; officers review here. */
export default function TaskPage() {
  const { id } = useParams<{ id: string }>();
  const tid = decodeURIComponent(id).toUpperCase();
  const { t } = useLang();
  const { user, ready } = useAuth();
  const ok = user && (user.role === "officer" || user.role === "contractor");
  const k = useApi<any>(ok ? `/tasks/${tid}` : null);
  if (!ready) return <Loading />;
  if (!ok) return <NeedLogin role="contractor" next={`/tasks/${tid}`} message={t("task.needLogin")} />;
  if (k.error) return <ErrorBox error={k.error} onRetry={k.reload} />;
  if (!k.data) return <Loading />;
  const x = k.data;
  const pts = x.complaints.flatMap((c: any) => (c.locations?.length ? c.locations : c.location?.lat != null ? [c.location] : []));
  return (
    <div className="mx-auto max-w-4xl space-y-4">
      <header>
        <div className="flex flex-wrap items-center gap-2">
          <h1 className="text-xl font-extrabold">{t("task.title", { id: x.task_id })}</h1>
          <TaskStatus status={x.status} overdue={x.overdue} />
        </div>
        <p className="mt-1 text-sm font-semibold">{x.title}</p>
        <dl className="mt-2 grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-sm">
          <dt className="text-ink/60">{t("common.contractor")}</dt>
          <dd>{x.contractor_name}</dd>
          <dt className="text-ink/60">{t("common.ward")}</dt>
          <dd>{x.ward_code}</dd>
          <dt className="text-ink/60">{t("task.due")}</dt>
          <dd>{x.due_at?.replace("T", " ").slice(0, 16)}</dd>
          {x.repair_method && (
            <>
              <dt className="text-ink/60">{t("complaint.method")}</dt>
              <dd>
                {x.repair_method}
                {x.est_area_sqm ? ` · ${x.est_area_sqm} sqm` : ""}
              </dd>
            </>
          )}
          {x.est_cost_inr != null && (
            <>
              <dt className="text-ink/60">{t("task.estimate")}</dt>
              <dd>{rupee(x.est_cost_inr)}</dd>
            </>
          )}
          {x.approved_cost_inr != null && (
            <>
              <dt className="text-ink/60">{t("ticket.approvedCost")}</dt>
              <dd className="font-semibold">{rupee(x.approved_cost_inr)}</dd>
            </>
          )}
        </dl>
        {x.instructions && <p className="mt-2 rounded bg-ledger-50 p-2 text-sm">{x.instructions}</p>}
      </header>

      <Actions x={x} onDone={k.reload} />

      <section>
        <h2 className="mb-2 text-sm font-bold">{t("task.complaintsN", { n: x.complaints.length })}</h2>
        {pts.length > 0 && <LocationPicker points={pts} height={240} />}
        <ul className="mt-2 space-y-2">
          {x.complaints.map((c: any) => (
            <li key={c.ticket_id} className="card text-sm">
              <div className="flex flex-wrap items-center gap-2">
                <Link href={`/ticket/${c.ticket_id}`} className="font-mono text-xs underline">
                  {c.ticket_id}
                </Link>
                <TicketStatus status={c.status} />
                <span className="font-semibold">{t("cat." + c.category)}</span>
              </div>
              <p className="mt-1 text-xs text-ink/70">
                {c.road ? `${c.road.road_name} · ` : ""}
                {c.location?.lat != null ? `${Number(c.location.lat).toFixed(5)}, ${Number(c.location.lon).toFixed(5)}` : ""}
                {c.location?.lat != null && (
                  <a
                    className="ml-2 underline"
                    target="_blank"
                    rel="noreferrer"
                    href={`https://www.openstreetmap.org/?mlat=${c.location.lat}&mlon=${c.location.lon}#map=18/${c.location.lat}/${c.location.lon}`}
                  >
                    {t("task.openMap")}
                  </a>
                )}
              </p>
              <p className="mt-1 whitespace-pre-line">{c.description}</p>
              <div className="mt-2">
                <Gallery items={c.media} />
              </div>
            </li>
          ))}
        </ul>
      </section>

      {x.reports.length > 0 && (
        <section>
          <h2 className="mb-2 text-sm font-bold">{t("task.reports")}</h2>
          <ul className="space-y-2">
            {x.reports.map((r: any) => (
              <li key={r.report_id} className="card space-y-2 text-sm">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-mono text-xs">{r.report_id}</span>
                  <span className={`chip ${r.decision === "approved" ? TONE.positive : r.decision === "rejected" ? TONE.concern : TONE.info}`}>
                    {t("task.decision." + r.decision)}
                  </span>
                  <span className="text-xs text-ink/60">{r.submitted_at?.replace("T", " ").slice(0, 16)}</span>
                </div>
                <p className="whitespace-pre-line">{r.summary}</p>
                <p className="text-xs text-ink/70">
                  {r.repair_method}
                  {r.area_sqm != null ? ` · ${r.area_sqm} sqm` : ""} · {t("task.bill")}: <strong>{rupee(r.bill_amount_inr)}</strong>
                  {r.bill_ref ? ` (${r.bill_ref})` : ""}
                </p>
                {r.checks?.length > 0 && (
                  <ul className="space-y-1">
                    {r.checks.map((c: any, i: number) => (
                      <li key={i} className={`rounded border px-2 py-1 text-xs ${TONE[c.tone] || TONE.info}`}>
                        {c.text}
                      </li>
                    ))}
                  </ul>
                )}
                <Gallery items={r.evidence} />
                <Gallery items={r.bills} />
                {r.decision_note && <p className="rounded bg-ledger-50 px-2 py-1 text-xs">“{r.decision_note}”</p>}
              </li>
            ))}
          </ul>
        </section>
      )}

      <section>
        <h2 className="mb-2 text-sm font-bold">{t("ticket.history")}</h2>
        <Timeline events={x.events} kind="task" />
      </section>
    </div>
  );
}

function Actions({ x, onDone }: { x: any; onDone: () => void }) {
  const { t } = useLang();
  const { refresh } = useAuth();
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [note, setNote] = useState("");
  const a = x.actions || {};
  const run = async (path: string, body: unknown) => {
    setBusy(true);
    setErr(null);
    try {
      await api(path, { method: "POST", body });
      setNote("");
      onDone();
      refresh();
    } catch (e: any) {
      setErr(e?.message || t("common.error"));
    } finally {
      setBusy(false);
    }
  };
  if (!a.start && !a.submit_report && !a.approve && !a.send_back && !a.cancel) return null;
  return (
    <section className="card space-y-3 border-ledger-600">
      {a.start && (
        <button className="btn btn-primary" disabled={busy} onClick={() => run(`/tasks/${x.task_id}/start`, {})}>
          {t("task.start")}
        </button>
      )}
      {a.submit_report && <ReportForm x={x} onDone={onDone} />}
      {(a.approve || a.send_back) && (
        <div className="space-y-2">
          <h2 className="text-sm font-bold">{t("task.review")}</h2>
          <p className="text-xs text-ink/70">{t("task.reviewHelp", { n: x.complaints.length })}</p>
          <textarea value={note} onChange={(e) => setNote(e.target.value)} rows={2} maxLength={1000} placeholder={t("task.reviewNote")} className="w-full rounded border border-ledger-200 p-2 text-sm" />
          <div className="flex flex-wrap gap-2">
            <button className="btn btn-primary" disabled={busy} onClick={() => run(`/tasks/${x.task_id}/approve`, { note: note || null })}>
              {t("task.approve", { n: x.complaints.length })}
            </button>
            <button className="btn btn-ghost" disabled={busy || note.trim().length < 5} onClick={() => run(`/tasks/${x.task_id}/send-back`, { reason: note })}>
              {t("task.sendBack")}
            </button>
          </div>
        </div>
      )}
      {a.cancel && (
        <details className="text-xs">
          <summary className="cursor-pointer text-ledger-700">{t("task.cancel")}</summary>
          <div className="mt-2 space-y-1">
            <textarea value={note} onChange={(e) => setNote(e.target.value)} rows={2} placeholder={t("task.cancelReason")} className="w-full rounded border border-ledger-200 p-1" />
            <button className="btn btn-ghost !min-h-[32px]" disabled={busy || note.trim().length < 5} onClick={() => run(`/tasks/${x.task_id}/cancel`, { reason: note })}>
              {t("task.cancelBtn")}
            </button>
          </div>
        </details>
      )}
      {err && (
        <p role="alert" className="rounded border border-red-200 bg-red-50 p-2 text-sm text-red-900">
          {err}
        </p>
      )}
    </section>
  );
}

function ReportForm({ x, onDone }: { x: any; onDone: () => void }) {
  const { t } = useLang();
  const opts = useApi<any>("/live/options");
  const [summary, setSummary] = useState("");
  const [method, setMethod] = useState(x.repair_method || "");
  const [area, setArea] = useState(x.est_area_sqm ? String(x.est_area_sqm) : "");
  const [bill, setBill] = useState("");
  const [ref, setRef] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const [bills, setBills] = useState<File[]>([]);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const unit = (opts.data?.methods || []).find((m: any) => m.repair_method === method)?.unit;
  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setErr(null);
    const f = new FormData();
    f.append("summary", summary);
    if (method) f.append("repair_method", method);
    if (area) f.append("area_sqm", area);
    f.append("bill_amount_inr", bill);
    if (ref) f.append("bill_ref", ref);
    files.forEach((x) => f.append("files", x, x.name));
    bills.forEach((x) => f.append("bill_files", x, x.name));
    setBusy(true);
    try {
      await api(`/tasks/${x.task_id}/report`, { form: f });
      onDone();
    } catch (e: any) {
      setErr(e?.message || t("common.error"));
    } finally {
      setBusy(false);
    }
  };
  return (
    <form onSubmit={submit} className="space-y-2 text-sm">
      <h2 className="font-bold">{t("task.reportTitle")}</h2>
      <textarea value={summary} onChange={(e) => setSummary(e.target.value)} rows={3} required minLength={10} maxLength={2000} placeholder={t("task.reportSummary")} className="w-full rounded border border-ledger-200 p-2" />
      <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
        <label className="text-xs">
          {t("complaint.method")}
          <select value={method} onChange={(e) => setMethod(e.target.value)} className="mt-1 min-h-[40px] w-full rounded border border-ledger-200 bg-white px-1">
            <option value="">-</option>
            {(opts.data?.methods || []).map((m: any) => (
              <option key={m.repair_method} value={m.repair_method}>
                {m.repair_method} (₹{m.standard_rate_inr} {m.unit})
              </option>
            ))}
          </select>
        </label>
        <label className="text-xs">
          {t("task.area")}
          <input type="number" min="0" step="0.1" value={area} onChange={(e) => setArea(e.target.value)} required={unit === "per sqm"} className="mt-1 min-h-[40px] w-full rounded border border-ledger-200 px-2" />
        </label>
        <label className="text-xs">
          {t("task.billAmount")}
          <input type="number" min="1" step="1" value={bill} onChange={(e) => setBill(e.target.value)} required className="mt-1 min-h-[40px] w-full rounded border border-ledger-200 px-2" />
        </label>
        <label className="text-xs">
          {t("task.billRef")}
          <input value={ref} onChange={(e) => setRef(e.target.value)} maxLength={60} className="mt-1 min-h-[40px] w-full rounded border border-ledger-200 px-2" />
        </label>
      </div>
      <label className="block text-xs">
        {t("task.evidence")}
        <input type="file" multiple accept="image/jpeg,image/png,image/webp,video/mp4,video/quicktime,video/webm" onChange={(e) => setFiles(Array.from(e.target.files || []))} className="mt-1 block" />
      </label>
      <label className="block text-xs">
        {t("task.billFiles")}
        <input type="file" multiple accept="application/pdf,image/jpeg,image/png,image/webp" onChange={(e) => setBills(Array.from(e.target.files || []))} className="mt-1 block" />
      </label>
      {err && (
        <p role="alert" className="rounded border border-red-200 bg-red-50 p-2 text-red-900">
          {err}
        </p>
      )}
      <button className="btn btn-primary" disabled={busy}>
        {busy ? t("raise.sending") : t("task.submitReport")}
      </button>
    </form>
  );
}

