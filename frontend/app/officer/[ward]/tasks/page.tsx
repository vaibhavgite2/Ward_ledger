"use client";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { api, useApi } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { rupee, wardCode, wardSlug } from "@/lib/format";
import { useLang } from "@/lib/i18n";
import { ErrorBox, Loading } from "@/components/Ui";
import OfficerShell from "@/components/officer/OfficerShell";
import { TicketStatus } from "@/components/live/bits";
import TaskRow from "@/components/live/TaskRow";

const TONE: Record<string, string> = {
  concern: "border-amber-300 bg-amber-50 text-amber-900",
  info: "border-ledger-200 bg-white",
  positive: "border-emerald-300 bg-emerald-50 text-emerald-900",
};
const TASK_FILTERS = ["active", "submitted", "rework", "completed", "cancelled"];

/** DFD 4.0 Assign Contractor: bundle verified complaints into one task, with pre-award checks; plus the ward's tasks. */
function Inner() {
  const params = useParams<{ ward: string }>();
  const code = wardCode(params.ward);
  const slug = wardSlug(code);
  const { t, lang } = useLang();
  const { user } = useAuth();
  const router = useRouter();
  const pre = useSearchParams().get("select");
  const verified = useApi<any>(`/tickets?ward=${slug}&status=verified&limit=100`);
  const opts = useApi<any>("/live/options");
  const [picked, setPicked] = useState<string[]>(pre ? [pre] : []);
  const [contractor, setContractor] = useState("");
  const [pv, setPv] = useState<any>(null);
  const [form, setForm] = useState<any>({});
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [filter, setFilter] = useState("active");
  const tasks = useApi<any>(`/tasks?ward=${slug}&status=${filter}&limit=100`);
  const canAct = !!user?.can_act;
  const [sweep, setSweep] = useState<string | null>(null);
  const checkOverdue = async () => {
    setSweep(null);
    try {
      const r = await api<any>("/tasks/check-overdue", { method: "POST" });
      setSweep(r.notified.length ? t("officert.checkedOverdue", { n: r.notified.length }) : t("officert.checkedNone"));
      tasks.reload();
    } catch (e: any) {
      setSweep(e?.message || t("common.error"));
    }
  };

  const toggle = (id: string) => {
    setPv(null);
    setPicked((p) => (p.includes(id) ? p.filter((x) => x !== id) : [...p, id]));
  };
  const check = async () => {
    setErr(null);
    setBusy(true);
    try {
      const r = await api<any>("/tasks/preview", { method: "POST", lang, body: { contractor_id: contractor, ticket_ids: picked } });
      setPv(r);
      setForm({
        repair_method: r.suggested.repair_method || "",
        est_area_sqm: r.suggested.est_area_sqm ?? "",
        est_cost_inr: r.suggested.est_cost_inr ?? "",
        due_date: (r.suggested.due_at || "").slice(0, 10),
        instructions: "",
      });
    } catch (e: any) {
      setErr(e?.message || t("common.error"));
    } finally {
      setBusy(false);
    }
  };
  const assign = async () => {
    setErr(null);
    setBusy(true);
    const sugDue = pv.suggested.due_at as string;
    const due_at = form.due_date && form.due_date !== sugDue.slice(0, 10) ? `${form.due_date}T23:59:00+05:30` : sugDue;
    try {
      const r = await api<any>("/tasks", {
        method: "POST",
        body: {
          contractor_id: contractor,
          ticket_ids: picked,
          repair_method: form.repair_method || null,
          est_area_sqm: form.est_area_sqm === "" ? null : Number(form.est_area_sqm),
          est_cost_inr: form.est_cost_inr === "" ? null : Number(form.est_cost_inr),
          due_at,
          instructions: form.instructions || null,
        },
      });
      router.push(`/tasks/${r.task_id}`);
    } catch (e: any) {
      setErr(e?.message || t("common.error"));
      setBusy(false);
    }
  };

  const items = verified.data?.items || [];
  return (
    <OfficerShell ward={params.ward}>
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <section className="card space-y-3">
          <h2 className="font-bold">{t("officert.create")}</h2>
          {!canAct && <p className="text-xs text-ink/70">{t("officer.readOnly")}</p>}
          <div>
            <h3 className="mb-1 text-xs font-semibold">{t("officert.pick", { n: picked.length })}</h3>
            {verified.loading && !verified.data && <Loading />}
            {items.length === 0 && verified.data && <p className="text-xs text-ink/60">{t("officert.noneVerified")}</p>}
            <ul className="max-h-64 space-y-1 overflow-y-auto">
              {items.map((x: any) => (
                <li key={x.ticket_id}>
                  <label className="flex items-start gap-2 rounded px-1 py-1 text-xs hover:bg-ledger-50">
                    <input type="checkbox" checked={picked.includes(x.ticket_id)} onChange={() => toggle(x.ticket_id)} disabled={!canAct} className="mt-0.5 h-4 w-4" />
                    <span>
                      <span className="font-mono">{x.ticket_id}</span> · {t("cat." + x.category)} · {x.road_name || x.locality_text || ""}{" "}
                      <TicketStatus status={x.status} />
                    </span>
                  </label>
                </li>
              ))}
            </ul>
          </div>
          <label className="block text-xs">
            {t("common.contractor")}
            <select
              value={contractor}
              onChange={(e) => (setContractor(e.target.value), setPv(null))}
              disabled={!canAct}
              className="mt-1 min-h-[40px] w-full rounded border border-ledger-200 bg-white px-1"
            >
              <option value="">{t("raise.choose")}</option>
              {(opts.data?.contractors || []).map((c: any) => (
                <option key={c.contractor_id} value={c.contractor_id}>
                  {c.contractor_name}
                </option>
              ))}
            </select>
          </label>
          <button className="btn btn-ghost" disabled={!canAct || busy || !contractor || picked.length === 0} onClick={check}>
            {t("officert.check")}
          </button>

          {pv && (
            <div className="space-y-3 border-t border-ledger-200 pt-3">
              <h3 className="text-xs font-semibold">{t("officert.checks", { name: pv.contractor.name })}</h3>
              <ul className="space-y-1">
                {pv.checks.map((c: any, i: number) => (
                  <li key={i} className={`rounded border px-2 py-1 text-xs ${TONE[c.tone] || TONE.info}`}>
                    {c.text}
                  </li>
                ))}
              </ul>
              <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                <label className="text-xs">
                  {t("complaint.method")}
                  <select value={form.repair_method} onChange={(e) => setForm({ ...form, repair_method: e.target.value })} className="mt-1 min-h-[36px] w-full rounded border border-ledger-200 bg-white px-1">
                    <option value="">-</option>
                    {(opts.data?.methods || []).map((m: any) => (
                      <option key={m.repair_method} value={m.repair_method}>
                        {m.repair_method}
                      </option>
                    ))}
                  </select>
                  {pv.suggested.alternatives?.length > 0 && (
                    <span className="mt-0.5 block text-[10px] text-ink/60">
                      {pv.suggested.alternatives.map((a: any) => t("officert.reopenRate", { m: a.method, p: a.reopen_pct })).join(" · ")}
                    </span>
                  )}
                </label>
                <label className="text-xs">
                  {t("task.area")}
                  <input type="number" min="0" step="0.1" value={form.est_area_sqm} onChange={(e) => setForm({ ...form, est_area_sqm: e.target.value })} className="mt-1 min-h-[36px] w-full rounded border border-ledger-200 px-2" />
                </label>
                <label className="text-xs">
                  {t("task.estimate")} (₹)
                  <input type="number" min="0" step="1" value={form.est_cost_inr} onChange={(e) => setForm({ ...form, est_cost_inr: e.target.value })} className="mt-1 min-h-[36px] w-full rounded border border-ledger-200 px-2" />
                </label>
                <label className="text-xs">
                  {t("task.due")}
                  <input type="date" value={form.due_date} onChange={(e) => setForm({ ...form, due_date: e.target.value })} className="mt-1 min-h-[36px] w-full rounded border border-ledger-200 px-2" />
                  <span className="text-[10px] text-ink/60">{t("officert.sla", { h: pv.suggested.sla_hours })}</span>
                </label>
              </div>
              <textarea value={form.instructions} onChange={(e) => setForm({ ...form, instructions: e.target.value })} rows={2} maxLength={2000} placeholder={t("officert.instructions")} className="w-full rounded border border-ledger-200 p-2 text-xs" />
              <button className="btn btn-primary" disabled={busy} onClick={assign}>
                {t("officert.assign", { n: picked.length, name: pv.contractor.name })}
              </button>
              {pv.suggested.est_cost_inr != null && <p className="text-[11px] text-ink/60">{t("officert.estNote", { cost: rupee(pv.suggested.est_cost_inr) })}</p>}
            </div>
          )}
          {err && (
            <p role="alert" className="rounded border border-red-200 bg-red-50 p-2 text-xs text-red-900">
              {err}
            </p>
          )}
        </section>

        <section>
          <div className="mb-2 flex flex-wrap items-center gap-1.5">
            <h2 className="mr-2 font-bold">{t("officert.list")}</h2>
            {TASK_FILTERS.map((f) => (
              <button
                key={f}
                type="button"
                aria-pressed={filter === f}
                onClick={() => setFilter(f)}
                className={`chip !text-xs ${filter === f ? "border-ledger-700 bg-ledger-700 text-white" : "border-ledger-200 bg-white"}`}
              >
                {t("officert.filter." + f)}
              </button>
            ))}
          </div>
          <div className="mb-2 flex flex-wrap items-center gap-2 text-xs">
            <span className="text-ink/70">{t("officert.overdueHelp")}</span>
            {canAct && (
              <button type="button" className="btn btn-ghost !min-h-[32px] text-xs" onClick={checkOverdue}>
                {t("officert.checkOverdue")}
              </button>
            )}
            {sweep && (
              <span role="status" className="font-semibold">
                {sweep}
              </span>
            )}
          </div>
          {tasks.error && <ErrorBox error={tasks.error} onRetry={tasks.reload} />}
          {tasks.data?.items.length === 0 && <p className="card text-xs">{t("officert.noTasks")}</p>}
          <ul className="space-y-2">
            {(tasks.data?.items || []).map((k: any) => (
              <li key={k.task_id}>
                <TaskRow k={k} />
              </li>
            ))}
          </ul>
        </section>
      </div>
    </OfficerShell>
  );
}

export default function OfficerTasks() {
  return (
    <Suspense fallback={<Loading />}>
      <Inner />
    </Suspense>
  );
}
