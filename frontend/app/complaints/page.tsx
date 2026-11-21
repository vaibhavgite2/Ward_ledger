"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { useApi } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { dateOnly } from "@/lib/format";
import { useLang } from "@/lib/i18n";
import { ErrorBox, Loading, PageTitle } from "@/components/Ui";
import { TicketCard } from "@/components/live/bits";

const PAGE = 20;
const STATUS = ["", "open", "submitted", "verified", "assigned", "in_progress", "work_submitted", "resolved", "closed"];
const RECORD_STATUS = ["", "fixed", "linked_via_issue", "fixed_failed", "never_fixed", "pending", "closed_other", "duplicate"];
const TONE: Record<string, string> = {
  fixed: "border-emerald-300 bg-emerald-50 text-emerald-900",
  linked_via_issue: "border-emerald-300 bg-emerald-50 text-emerald-900",
  fixed_failed: "border-amber-300 bg-amber-50 text-amber-900",
  never_fixed: "border-amber-300 bg-amber-50 text-amber-900",
};
const SELECT = "min-h-[40px] rounded border border-ledger-200 bg-white px-1";

/** The complaints section, visible to everyone with no login: complaints raised in this app, and the 2025 BMC records. */
export default function ComplaintsPage() {
  const { t } = useLang();
  const { user } = useAuth();
  const [tab, setTab] = useState<"app" | "records">("app");
  const [chosen, setChosen] = useState(false);
  const appCount = useApi<any>("/tickets?limit=1");
  const meta = useApi<any>("/meta");
  const appTotal: number | undefined = appCount.data?.total;
  // Nothing raised through the app yet? Open on the BMC records instead of an empty page.
  useEffect(() => {
    if (!chosen && appTotal === 0) setTab("records");
  }, [appTotal, chosen]);
  const pick = (x: "app" | "records") => (setChosen(true), setTab(x));

  return (
    <div>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <PageTitle sub={t("complaints.sub")}>{t("complaints.title")}</PageTitle>
        {(!user || user.role === "citizen") && (
          <Link href="/complaints/new" className="btn btn-primary">
            {t("nav.raise")}
          </Link>
        )}
      </div>
      <div className="mb-3 flex flex-wrap gap-2" role="tablist">
        {(
          [
            ["app", t("complaints.tab.app", { n: appTotal ?? "…" })],
            ["records", t("complaints.tab.records", { n: meta.data?.city?.complaints ?? "…" })],
          ] as const
        ).map(([k, label]) => (
          <button key={k} role="tab" aria-selected={tab === k} onClick={() => pick(k)} className={`btn ${tab === k ? "btn-primary" : "btn-ghost"}`}>
            {label}
          </button>
        ))}
      </div>
      {tab === "app" ? <AppComplaints /> : <RecordedComplaints />}
    </div>
  );
}

function Filters({ children }: { children: React.ReactNode }) {
  return <div className="mb-3 flex flex-wrap items-end gap-2 text-sm">{children}</div>;
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="flex flex-col text-xs">
      {label}
      {children}
    </label>
  );
}

function SharedFilters({ f, set, wards, opts }: { f: any; set: (k: string, v: string) => void; wards: any[]; opts: any }) {
  const { t } = useLang();
  return (
    <>
      <Field label={t("common.ward")}>
        <select value={f.ward} onChange={(e) => set("ward", e.target.value)} className={SELECT}>
          <option value="">{t("complaints.any")}</option>
          {wards.map((w) => (
            <option key={w.ward_code} value={w.ward_code}>
              {w.ward_code}
            </option>
          ))}
        </select>
      </Field>
      <Field label={t("raise.category")}>
        <select value={f.category} onChange={(e) => set("category", e.target.value)} className={SELECT}>
          <option value="">{t("complaints.any")}</option>
          {(opts?.categories || []).map((c: string) => (
            <option key={c} value={c}>
              {t("cat." + c)}
            </option>
          ))}
        </select>
      </Field>
      <Field label={t("complaints.section")}>
        <select value={f.section} onChange={(e) => set("section", e.target.value)} className={SELECT}>
          <option value="">{t("complaints.any")}</option>
          {(opts?.sections || []).map((c: string) => (
            <option key={c} value={c}>
              {t("section." + c)}
            </option>
          ))}
        </select>
      </Field>
      <Field label={t("complaints.sort")}>
        <select value={f.sort} onChange={(e) => set("sort", e.target.value)} className={SELECT}>
          {["recent", "upvotes"].map((s) => (
            <option key={s} value={s}>
              {t("complaints.sort." + s)}
            </option>
          ))}
        </select>
      </Field>
    </>
  );
}

/** Filter state shared by both tabs. `paged` lists use limit/offset pages; the others grow with "show more". */
function useFilters(paged = false) {
  const [f, setF] = useState({ status: "", ward: "", category: "", section: "", sort: "recent", q: "", mine: false });
  const [limit, setLimit] = useState(PAGE);
  const [page, setPage] = useState(0);
  const set = (k: string, v: any) => {
    setF((p) => ({ ...p, [k]: v }));
    setLimit(PAGE);
    setPage(0);
  };
  const qs = new URLSearchParams({ limit: String(limit) });
  if (paged && page > 0) qs.set("offset", String(page * PAGE));
  for (const k of ["status", "ward", "category", "section"] as const) if (f[k]) qs.set(k, f[k]);
  if (f.sort !== "recent") qs.set("sort", f.sort);
  if (f.q.trim()) qs.set("q", f.q.trim());
  if (f.mine) qs.set("mine", "1");
  return { f, set, limit, setLimit, page, setPage, qs: qs.toString() };
}

/** Complaints raised through this app (live tickets). */
function AppComplaints() {
  const { t } = useLang();
  const { user } = useAuth();
  const { f, set, limit, setLimit, qs } = useFilters();
  const wards = useApi<any[]>("/wards");
  const opts = useApi<any>("/live/options");
  const list = useApi<any>(`/tickets?${qs}`);
  const counts = list.data?.counts || {};
  const openN = ["submitted", "verified", "assigned", "in_progress", "work_submitted"].reduce((a, k) => a + (counts[k] || 0), 0);
  const anyFilter = f.status || f.ward || f.category || f.section || f.q.trim() || f.mine;
  return (
    <>
      <p className="mb-3 flex flex-wrap gap-2 text-xs">
        <span className="chip border-ledger-200 bg-white">{t("complaints.countOpen", { n: openN })}</span>
        <span className="chip border-emerald-300 bg-emerald-50 text-emerald-900">{t("complaints.countResolved", { n: counts.resolved || 0 })}</span>
      </p>
      <Filters>
        <Field label={t("complaints.status")}>
          <select value={f.status} onChange={(e) => set("status", e.target.value)} className={SELECT}>
            {STATUS.map((s) => (
              <option key={s} value={s}>
                {s ? t("complaints.filter." + s) : t("complaints.any")}
              </option>
            ))}
          </select>
        </Field>
        <SharedFilters f={f} set={set} wards={wards.data || []} opts={opts.data} />
        <Field label={t("complaints.search")}>
          <input value={f.q} onChange={(e) => set("q", e.target.value)} placeholder="CMP-000001" className="min-h-[40px] rounded border border-ledger-200 px-2" />
        </Field>
        {user?.role === "citizen" && (
          <label className="flex min-h-[40px] items-center gap-1 text-xs">
            <input type="checkbox" checked={f.mine} onChange={(e) => set("mine", e.target.checked)} className="h-4 w-4" />
            {t("complaints.onlyMine")}
          </label>
        )}
      </Filters>
      {list.error && <ErrorBox error={list.error} onRetry={list.reload} />}
      {list.loading && !list.data && <Loading />}
      {list.data && (
        <>
          {list.data.items.length === 0 && <p className="card text-sm">{anyFilter ? t("complaints.none") : t("complaints.emptyApp")}</p>}
          <ul className="grid grid-cols-1 gap-2 md:grid-cols-2">
            {list.data.items.map((x: any) => (
              <li key={x.ticket_id}>
                <TicketCard x={x} />
              </li>
            ))}
          </ul>
          {list.data.total > list.data.items.length && (
            <button className="btn btn-ghost mt-3" onClick={() => setLimit(limit + PAGE)}>
              {t("common.more")} ({list.data.total - list.data.items.length})
            </button>
          )}
        </>
      )}
    </>
  );
}

/** The recorded 2025 complaint history (what Ask looks up), listed so it can be browsed without knowing an ID. */
function RecordedComplaints() {
  const { t } = useLang();
  const { f, set, page, setPage, qs } = useFilters(true);
  const wards = useApi<any[]>("/wards");
  const opts = useApi<any>("/live/options");
  const list = useApi<any>(`/complaints?${qs}`);
  return (
    <>
      <p className="mb-3 text-xs text-ink/70">{t("complaints.recordsNote")}</p>
      <Filters>
        <Field label={t("complaints.status")}>
          <select value={f.status} onChange={(e) => set("status", e.target.value)} className={SELECT}>
            {RECORD_STATUS.map((s) => (
              <option key={s} value={s}>
                {s ? t("complaint.status." + s) : t("complaints.any")}
              </option>
            ))}
          </select>
        </Field>
        <SharedFilters f={f} set={set} wards={wards.data || []} opts={opts.data} />
        <Field label={t("complaints.search")}>
          <input value={f.q} onChange={(e) => set("q", e.target.value)} placeholder="BMC25-000037" className="min-h-[40px] rounded border border-ledger-200 px-2" />
        </Field>
      </Filters>
      {list.error && <ErrorBox error={list.error} onRetry={list.reload} />}
      {list.loading && !list.data && <Loading />}
      {list.data && (
        <>
          {list.data.items.length === 0 && <p className="card text-sm">{t("complaints.none")}</p>}
          <ul className="grid grid-cols-1 gap-2 md:grid-cols-2">
            {list.data.items.map((x: any) => (
              <li key={x.complaint_id}>
                <Link href={`/complaint/${x.complaint_id}`} className="card block hover:bg-ledger-50">
                  <div className="flex flex-wrap items-center gap-1.5 text-sm">
                    <span className="font-mono text-xs">{x.complaint_id}</span>
                    <span className={`chip ${TONE[x.link_status] || "border-ledger-200 bg-ledger-50"}`}>{t("complaint.status." + x.link_status)}</span>
                    {x.upvotes > 0 && (
                      <span className="chip border-ledger-200 bg-white" title={t("complaints.reportedTimes", { n: x.upvotes })}>
                        ▲ {x.upvotes}
                      </span>
                    )}
                  </div>
                  <div className="mt-0.5 text-sm font-semibold">
                    {x.category_label}
                    {x.section !== "roads" && <span className="ml-2 chip border-indigo-200 bg-indigo-50 text-indigo-900">{t("section." + x.section)}</span>}
                  </div>
                  <div className="truncate text-xs text-ink/70">
                    {t("common.ward")} {x.ward_code}
                    {x.locality ? ` · ${x.locality}` : ""} · {dateOnly(x.received_at)}
                  </div>
                  <div className="text-xs">
                    <span className="text-ink/60">{t("ticket.assignedTo")}: </span>
                    {x.contractor_name ? x.contractor_name.replace(" (synthetic)", "") : <span className="text-ink/70">{t("complaint.notAssigned")}</span>}
                  </div>
                </Link>
              </li>
            ))}
          </ul>
          {list.data.total > PAGE && (
            <nav className="mt-3 flex items-center gap-3 text-sm" aria-label="Pages">
              <button className="btn btn-ghost" disabled={page === 0} onClick={() => setPage(page - 1)}>
                ←
              </button>
              <span className="tabular-nums">
                {page * PAGE + 1}–{Math.min(list.data.total, (page + 1) * PAGE)} / {list.data.total}
              </span>
              <button className="btn btn-ghost" disabled={(page + 1) * PAGE >= list.data.total} onClick={() => setPage(page + 1)}>
                →
              </button>
            </nav>
          )}
        </>
      )}
      <p className="mt-4 text-xs text-ink/60">
        {t("complaints.history")}{" "}
        <Link href="/ask" className="underline">
          {t("nav.ask")}
        </Link>
      </p>
    </>
  );
}
