"use client";
import dynamic from "next/dynamic";
import Link from "next/link";
import { useState } from "react";
import { api, useApi } from "@/lib/api";
import { dateOnly, rupee } from "@/lib/format";
import { useLang } from "@/lib/i18n";
import { ErrorBox, Loading } from "@/components/Ui";
import { Gallery, Stepper, TicketStatus, Timeline, UpvoteButton } from "./bits";

const OPEN = ["submitted", "verified", "assigned", "in_progress", "work_submitted"];

const LocationPicker = dynamic(() => import("./LocationPicker"), { ssr: false, loading: () => <Loading /> });

/** A complaint as THIS viewer may see it (the API decides: public, owner, assigned contractor or officer). */
export default function TicketView({ id, onChanged }: { id: string; onChanged?: () => void }) {
  const { t } = useLang();
  const { data: x, error, loading, reload } = useApi<any>(`/tickets/${id}`);
  if (loading && !x) return <Loading />;
  if (error) return <ErrorBox error={error} onRetry={reload} />;
  if (!x) return null;
  const pts = x.locations?.length ? x.locations : x.location?.lat != null ? [{ lat: x.location.lat, lon: x.location.lon, source: "map" }] : [];
  const changed = () => {
    reload();
    onChanged?.();
  };
  return (
    <article className="space-y-3">
      <header>
        <div className="flex flex-wrap items-center gap-2">
          <h1 className="text-xl font-extrabold">{t("ticket.title", { id: x.ticket_id })}</h1>
          <TicketStatus status={x.status} />
          {x.viewer === "owner" && <span className="chip border-ledger-300 bg-white">{t("ticket.mine")}</span>}
        </div>
        <div className="mt-1 flex flex-wrap items-center gap-2 text-sm">
          <span className="font-semibold">{t("cat." + x.category)}</span>
          {x.section && <span className="chip border-indigo-200 bg-indigo-50 text-indigo-900">{t("section." + x.section)}</span>}
        </div>
        {(x.contractor || !["rejected", "duplicate"].includes(x.status)) && (
          <p className="mt-1 text-sm">
            <span className="text-ink/60">{t("ticket.assignedTo")}: </span>
            {x.contractor ? (
              <Link href={`/contractor/${x.contractor.contractor_id}`} className="font-semibold underline">
                {x.contractor.name}
              </Link>
            ) : (
              <span className="text-ink/70">{t("ticket.notAssigned")}</span>
            )}
          </p>
        )}
        <div className="mt-2">
          <Stepper status={x.status} />
        </div>
      </header>

      {x.status === "rejected" && (
        <p className="card border-red-200 bg-red-50 text-sm">
          {t("ticket.rejectedBecause")} {t("ticket.reason." + x.reject_reason)}
        </p>
      )}
      {x.duplicate_of && (
        <p className="card text-sm">
          {t("ticket.trackedWith")}{" "}
          <Link href={`/ticket/${x.duplicate_of}`} className="font-mono underline">
            {x.duplicate_of}
          </Link>
        </p>
      )}

      <section className="card text-sm">
        <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1">
          <dt className="text-ink/60">{t("ticket.raised")}</dt>
          <dd>{x.created_at?.replace("T", " ").slice(0, 16)}</dd>
          <dt className="text-ink/60">{t("common.ward")}</dt>
          <dd>{x.ward_code}</dd>
          {x.road && (
            <>
              <dt className="text-ink/60">{t("common.road")}</dt>
              <dd>
                <Link href={`/road/${x.road.road_id}`} className="underline">
                  {x.road.road_name} · {x.road.segment_no}
                </Link>
                {x.road.under_dlp && <span className="ml-2 chip border-blue-300 bg-blue-50 text-blue-900">{t("road.warranty")}</span>}
              </dd>
            </>
          )}
          {x.locality_text && (
            <>
              <dt className="text-ink/60">{t("ticket.locality")}</dt>
              <dd>{x.locality_text}</dd>
            </>
          )}
          <dt className="text-ink/60">{t("ticket.location")}</dt>
          <dd className="text-xs">
            {x.location?.approximate
              ? t("ticket.approxLocation")
              : t("ticket.exactLocation", { m: x.location?.accuracy_m ?? "?", method: x.location?.method ?? "" })}
          </dd>
        </dl>
        <p className="mt-2 whitespace-pre-line">{x.description}</p>
      </section>

      {(OPEN.includes(x.status) || x.upvotes > 0) && (
        <section className="card">
          <UpvoteButton id={x.ticket_id} count={x.upvotes || 0} supported={!!x.upvoted_by_me} mine={x.viewer === "owner"} status={x.status} />
        </section>
      )}

      {pts.length > 0 && <LocationPicker points={pts} height={220} />}

      <section>
        <h2 className="mb-1 text-sm font-bold">{t("ticket.photos")}</h2>
        <Gallery items={x.media} empty={t("ticket.noMedia")} />
      </section>

      {x.task && (
        <section className="card text-sm">
          <h2 className="mb-1 font-bold">{t("ticket.repair")}</h2>
          <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1">
            <dt className="text-ink/60">{t("common.contractor")}</dt>
            <dd>
              <Link href={`/contractor/${x.task.contractor_id}`} className="underline">
                {x.task.contractor_name}
              </Link>
            </dd>
            <dt className="text-ink/60">{t("task.id")}</dt>
            <dd className="font-mono">
              {x.viewer === "officer" || x.viewer === "contractor" ? (
                <Link href={`/tasks/${x.task.task_id}`} className="underline">
                  {x.task.task_id}
                </Link>
              ) : (
                x.task.task_id
              )}
            </dd>
            {x.task.due_at && x.status !== "resolved" && (
              <>
                <dt className="text-ink/60">{t("task.due")}</dt>
                <dd>{dateOnly(x.task.due_at)}</dd>
              </>
            )}
            {x.task.approved_cost_inr != null && (
              <>
                <dt className="text-ink/60">{t("ticket.approvedCost")}</dt>
                <dd className="font-semibold">{rupee(x.task.approved_cost_inr)}</dd>
              </>
            )}
          </dl>
          {x.repair_evidence?.length > 0 && (
            <div className="mt-2">
              <h3 className="mb-1 text-xs font-semibold">{t("ticket.afterPhotos")}</h3>
              <Gallery items={x.repair_evidence} />
            </div>
          )}
        </section>
      )}

      {x.viewer === "officer" && <OfficerPanel x={x} onDone={changed} />}

      <section>
        <h2 className="mb-2 text-sm font-bold">{t("ticket.history")}</h2>
        <Timeline events={x.events} kind="ticket" />
      </section>
    </article>
  );
}

function OfficerPanel({ x, onDone }: { x: any; onDone: () => void }) {
  const { t } = useLang();
  const opts = useApi<any>("/live/options");
  const [category, setCategory] = useState(x.category);
  const [section, setSection] = useState(x.section || "roads");
  const [note, setNote] = useState("");
  const [reason, setReason] = useState("");
  const [dupOf, setDupOf] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const act = async (path: string, body: unknown) => {
    setBusy(true);
    setErr(null);
    try {
      await api(path, { method: "POST", body });
      onDone();
    } catch (e: any) {
      setErr(e?.message || t("common.error"));
    } finally {
      setBusy(false);
    }
  };
  const sug = x.category_suggested;
  return (
    <section className="card space-y-3 border-ledger-600 text-sm">
      <h2 className="font-bold">{t("officerq.panel")}</h2>
      <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-xs">
        <dt className="text-ink/60">{t("officerq.citizen")}</dt>
        <dd>
          {x.citizen?.display_name || "-"} · <span className="font-mono">{x.citizen?.mobile}</span>
        </dd>
        <dt className="text-ink/60">{t("officerq.reported")}</dt>
        <dd>{t("cat." + x.category_reported)}</dd>
        {sug?.category && (
          <>
            <dt className="text-ink/60">{t("officerq.ourReading")}</dt>
            <dd>
              {t("cat." + sug.category)} ({Math.round((sug.confidence || 0) * 100)}%){" "}
              {sug.category !== x.category_reported && <span className="chip border-amber-300 bg-amber-50 text-amber-900">{t("officerq.differs")}</span>}
            </dd>
          </>
        )}
      </dl>
      {x.duplicate_candidates?.length > 0 && (
        <div>
          <h3 className="text-xs font-semibold">{t("officerq.possibleDup")}</h3>
          <ul className="mt-1 space-y-1 text-xs">
            {x.duplicate_candidates.map((d: any) => (
              <li key={d.ticket_id} className="flex flex-wrap items-center gap-2">
                <Link href={`/ticket/${d.ticket_id}`} className="font-mono underline">
                  {d.ticket_id}
                </Link>
                <span>{t("ticket.status." + d.status)}</span>
                <span className="text-ink/60">{d.distance_m != null ? `${d.distance_m} m` : t("officerq.sameRoad")}</span>
                {x.actions?.reject && (
                  <button type="button" className="underline" onClick={() => (setReason("duplicate"), setDupOf(d.ticket_id))}>
                    {t("officerq.useAsOriginal")}
                  </button>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}
      {x.actions?.verify ? (
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
          <div className="space-y-2 rounded border border-teal-200 bg-teal-50/40 p-2">
            <h3 className="font-semibold">{t("officerq.verify")}</h3>
            <label className="block text-xs">
              {t("officerq.category")}
              <select value={category} onChange={(e) => setCategory(e.target.value)} className="mt-1 min-h-[36px] w-full rounded border border-ledger-200 bg-white px-1">
                {(opts.data?.categories || []).map((c: string) => (
                  <option key={c} value={c}>
                    {t("cat." + c)}
                  </option>
                ))}
              </select>
            </label>
            <label className="block text-xs">
              {t("ticket.section")}
              <select value={section} onChange={(e) => setSection(e.target.value)} className="mt-1 min-h-[36px] w-full rounded border border-ledger-200 bg-white px-1">
                {(opts.data?.sections || []).map((c: string) => (
                  <option key={c} value={c}>
                    {t("section." + c)}
                  </option>
                ))}
              </select>
            </label>
            <textarea value={note} onChange={(e) => setNote(e.target.value)} rows={2} maxLength={500} placeholder={t("officerq.note")} className="w-full rounded border border-ledger-200 p-1 text-xs" />
            <button className="btn btn-primary w-full" disabled={busy} onClick={() => act(`/tickets/${x.ticket_id}/verify`, { category, section, note: note || null })}>
              {t("officerq.verifyBtn")}
            </button>
          </div>
          <div className="space-y-2 rounded border border-red-200 bg-red-50/40 p-2">
            <h3 className="font-semibold">{t("officerq.reject")}</h3>
            <select value={reason} onChange={(e) => setReason(e.target.value)} className="min-h-[36px] w-full rounded border border-ledger-200 bg-white px-1 text-xs">
              <option value="">{t("raise.choose")}</option>
              {(opts.data?.reject_reasons || []).map((r: any) => (
                <option key={r.code} value={r.code}>
                  {t("ticket.reason." + r.code)}
                </option>
              ))}
            </select>
            {reason === "duplicate" && (
              <input value={dupOf} onChange={(e) => setDupOf(e.target.value)} placeholder="CMP-000123" className="min-h-[36px] w-full rounded border border-ledger-200 px-2 font-mono text-xs" />
            )}
            <textarea value={note} onChange={(e) => setNote(e.target.value)} rows={2} maxLength={500} placeholder={t("officerq.note")} className="w-full rounded border border-ledger-200 p-1 text-xs" />
            <button
              className="btn btn-ghost w-full"
              disabled={busy || !reason}
              onClick={() => act(`/tickets/${x.ticket_id}/reject`, { reason, note: note || null, duplicate_of: dupOf || null })}
            >
              {t("officerq.rejectBtn")}
            </button>
          </div>
        </div>
      ) : (
        x.status === "submitted" && <p className="text-xs text-ink/70">{t("officerq.readOnly")}</p>
      )}
      {x.status === "verified" && (
        <Link href={`/officer/${x.ward_code.replace("/", "-")}/tasks?select=${x.ticket_id}`} className="btn btn-primary">
          {t("officerq.assign")}
        </Link>
      )}
      {err && (
        <p role="alert" className="rounded border border-red-200 bg-red-50 p-2 text-red-900">
          {err}
        </p>
      )}
    </section>
  );
}
