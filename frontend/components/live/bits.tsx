"use client";
import Link from "next/link";
import { useCallback, useEffect, useState, type FormEvent } from "react";
import { api, apiUrl } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { dateOnly } from "@/lib/format";
import { useLang } from "@/lib/i18n";

const TICKET_TONE: Record<string, string> = {
  submitted: "border-slate-300 bg-slate-50 text-slate-800",
  verified: "border-teal-300 bg-teal-50 text-teal-900",
  assigned: "border-indigo-300 bg-indigo-50 text-indigo-900",
  in_progress: "border-amber-300 bg-amber-50 text-amber-900",
  work_submitted: "border-amber-300 bg-amber-50 text-amber-900",
  resolved: "border-emerald-300 bg-emerald-50 text-emerald-900",
  rejected: "border-red-200 bg-red-50 text-red-900",
  duplicate: "border-slate-300 bg-slate-50 text-slate-700",
};
const TASK_TONE: Record<string, string> = {
  assigned: "border-indigo-300 bg-indigo-50 text-indigo-900",
  in_progress: "border-amber-300 bg-amber-50 text-amber-900",
  submitted: "border-teal-300 bg-teal-50 text-teal-900",
  rework: "border-red-200 bg-red-50 text-red-900",
  completed: "border-emerald-300 bg-emerald-50 text-emerald-900",
  cancelled: "border-slate-300 bg-slate-50 text-slate-700",
};

export function TicketStatus({ status }: { status: string }) {
  const { t } = useLang();
  return <span className={`chip ${TICKET_TONE[status] || TICKET_TONE.submitted}`}>{t("ticket.status." + status)}</span>;
}

export function TaskStatus({ status, overdue }: { status: string; overdue?: boolean }) {
  const { t } = useLang();
  return (
    <span className="inline-flex gap-1">
      <span className={`chip ${TASK_TONE[status] || TASK_TONE.assigned}`}>{t("task.status." + status)}</span>
      {overdue && <span className="chip border-red-300 bg-red-50 text-red-900">{t("task.overdue")}</span>}
    </span>
  );
}

const STEPS = ["submitted", "verified", "assigned", "in_progress", "work_submitted", "resolved"];

/** Where a complaint is in the DFD workflow. Rejected / duplicate end the line early. */
export function Stepper({ status }: { status: string }) {
  const { t } = useLang();
  if (status === "rejected" || status === "duplicate") return null;
  const at = STEPS.indexOf(status);
  return (
    <ol className="flex flex-wrap items-center gap-1 text-[11px]" aria-label={t("ticket.progress")}>
      {STEPS.map((s, i) => (
        <li key={s} className="flex items-center gap-1">
          <span
            className={`rounded-full px-2 py-0.5 ${i < at ? "bg-ledger-600 text-white" : i === at ? "bg-ledger-900 font-bold text-white" : "bg-ledger-100 text-ink/60"}`}
            aria-current={i === at ? "step" : undefined}
          >
            {t("ticket.step." + s)}
          </span>
          {i < STEPS.length - 1 && <span aria-hidden className="text-ink/30">›</span>}
        </li>
      ))}
    </ol>
  );
}

export type MediaItem = { media_id: string; kind: "photo" | "video" | "bill"; mime: string; url: string | null; public_url: string | null };

export function Gallery({ items, empty }: { items: MediaItem[]; empty?: string }) {
  const { t } = useLang();
  if (!items?.length) return empty ? <p className="text-xs text-ink/60">{empty}</p> : null;
  return (
    <ul className="flex flex-wrap gap-2">
      {items.map((m) => (
        <li key={m.media_id}>
          {m.kind === "photo" && m.url && (
            <a href={apiUrl(m.url)} target="_blank" rel="noreferrer" className="block">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={apiUrl(m.url)} alt={t("media.photo")} loading="lazy" className="h-28 w-36 rounded border border-ledger-200 object-cover" />
            </a>
          )}
          {m.kind === "video" && m.url && (
            <video src={apiUrl(m.url)} controls preload="metadata" className="h-28 w-48 rounded border border-ledger-200 bg-black" aria-label={t("media.video")} />
          )}
          {m.kind === "bill" && m.url && (
            <a href={apiUrl(m.url)} target="_blank" rel="noreferrer" className="chip border-ledger-200 bg-white !py-1">
              {t("media.bill")} ({m.mime === "application/pdf" ? "PDF" : t("media.photo")})
            </a>
          )}
        </li>
      ))}
    </ul>
  );
}

export function Timeline({ events, kind }: { events: any[]; kind: "ticket" | "task" }) {
  const { t } = useLang();
  return (
    <ol className="space-y-2 border-l-2 border-ledger-200 pl-4">
      {events.map((e, i) => (
        <li key={i} className="relative text-sm">
          <span className="absolute -left-[22px] top-1.5 h-3 w-3 rounded-full border-2 border-ledger-600 bg-white" aria-hidden />
          <div className="font-semibold">
            {e.event === "assigned" && e.contractor?.name
              ? t("ticket.ev.assignedTo", { name: e.contractor.name.replace(" (synthetic)", "") })
              : t(`${kind}.ev.${e.event}`)}
          </div>
          <div className="text-xs text-ink/70">
            {e.at?.replace("T", " ").slice(0, 16)} · {e.actor_label || t(`actor.${e.actor_role}`)}
            {e.actor_id ? <span className="font-mono"> ({e.actor_id})</span> : null}
          </div>
          {e.reason && <div className="text-xs">{t("ticket.reason." + e.reason)}</div>}
          {e.note && <div className="mt-0.5 rounded bg-ledger-50 px-2 py-1 text-xs">“{e.note}”</div>}
        </li>
      ))}
    </ol>
  );
}

export function Notifications({ limit = 20 }: { limit?: number }) {
  const { t, lang } = useLang();
  const { refresh } = useAuth();
  const [data, setData] = useState<any>(null);
  const load = useCallback(async () => {
    try {
      setData(await api("/me/notifications", { lang }));
    } catch {
      setData({ items: [], unread: 0 });
    }
  }, [lang]);
  useEffect(() => {
    load();
  }, [load]);
  const markAll = async () => {
    await api("/me/notifications/read", { method: "POST", body: {} });
    await load();
    refresh();
  };
  const items = (data?.items || []).slice(0, limit);
  return (
    <section className="card">
      <div className="mb-2 flex items-center justify-between">
        <h2 className="text-sm font-bold">
          {t("notif.title")} {data?.unread ? <span className="chip ml-1 border-amber-300 bg-amber-50 text-amber-900">{t("notif.unread", { n: data.unread })}</span> : null}
        </h2>
        {data?.unread > 0 && (
          <button className="text-xs underline" onClick={markAll}>
            {t("notif.markAll")}
          </button>
        )}
      </div>
      {items.length === 0 && <p className="text-xs text-ink/60">{t("notif.none")}</p>}
      <ul className="space-y-1.5">
        {items.map((n: any) => (
          <li key={n.id} className={`rounded px-2 py-1 text-xs ${n.read ? "" : "bg-amber-50"}`}>
            <Link href={n.entity_type === "task" ? `/tasks/${n.entity_id}` : `/ticket/${n.entity_id}`} className="hover:underline">
              {n.text}
            </Link>
            <div className="text-[10px] text-ink/50">{n.created_at?.replace("T", " ").slice(0, 16)}</div>
          </li>
        ))}
      </ul>
    </section>
  );
}

/** One complaint in a list (complaints section, my complaints, officer queue). */
export function TicketCard({ x, href, selected, onClick }: { x: any; href?: string; selected?: boolean; onClick?: () => void }) {
  const { t } = useLang();
  const body = (
    <div className={`card flex gap-3 ${selected ? "ring-2 ring-ledger-600" : ""} hover:bg-ledger-50`}>
      {x.thumb_url ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={apiUrl(x.thumb_url)} alt="" loading="lazy" className="h-16 w-20 shrink-0 rounded object-cover" />
      ) : (
        <div className="flex h-16 w-20 shrink-0 items-center justify-center rounded bg-ledger-100 text-[10px] text-ink/50">{t("media.noPhoto")}</div>
      )}
      <div className="min-w-0 flex-1 text-sm">
        <div className="flex flex-wrap items-center gap-1.5">
          <span className="font-mono text-xs">{x.ticket_id}</span>
          <TicketStatus status={x.status} />
          {x.is_mine && <span className="chip border-ledger-300 bg-white">{t("ticket.mine")}</span>}
          {x.upvotes > 0 && (
            <span className="chip border-ledger-200 bg-white" title={t("upvote.count", { n: x.upvotes })}>
              ▲ {x.upvotes}
            </span>
          )}
        </div>
        <div className="mt-0.5 font-semibold">
          {t("cat." + x.category)}
          {x.section && x.section !== "roads" && <span className="ml-2 chip border-indigo-200 bg-indigo-50 text-indigo-900">{t("section." + x.section)}</span>}
        </div>
        <div className="truncate text-xs text-ink/70">
          {t("common.ward")} {x.ward_code}
          {x.road_name ? ` · ${x.road_name}` : x.locality_text ? ` · ${x.locality_text}` : ""} · {dateOnly(x.created_at)}
          {x.contractor_name ? ` · ${x.contractor_name.replace(" (synthetic)", "")}` : ""}
        </div>
      </div>
    </div>
  );
  if (onClick)
    return (
      <button type="button" onClick={onClick} className="block w-full text-left">
        {body}
      </button>
    );
  return <Link href={href || `/ticket/${x.ticket_id}`}>{body}</Link>;
}

const OPEN_STATUS = ["submitted", "verified", "assigned", "in_progress", "work_submitted"];

/** "Me too": a citizen supports someone else's open complaint instead of raising a duplicate. */
export function UpvoteButton({ id, count, supported, mine, status, next, onChange }: { id: string; count: number; supported: boolean; mine: boolean; status: string; next?: string; onChange?: (supported: boolean) => void }) {
  const { t } = useLang();
  const { user } = useAuth();
  const [n, setN] = useState(count);
  const [sup, setSup] = useState(supported);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {
    setN(count);
    setSup(supported);
  }, [count, supported]);
  const send = async (verb: "upvote" | "unvote") => {
    setBusy(true);
    setErr(null);
    try {
      const r = await api<any>(`/tickets/${id}/${verb}`, { method: "POST" });
      setN(r.upvotes);
      setSup(r.upvoted_by_me);
      onChange?.(r.upvoted_by_me);
    } catch (e: any) {
      setErr(e?.message || t("common.error"));
    } finally {
      setBusy(false);
    }
  };
  const open = OPEN_STATUS.includes(status);
  return (
    <div className="space-y-1 text-sm">
      <div className="flex flex-wrap items-center gap-2">
        <span className="chip border-ledger-200 bg-white" aria-live="polite">
          ▲ {t("upvote.count", { n })}
        </span>
        {!open && <span className="text-xs text-ink/70">{t("upvote.closed")}</span>}
        {open && mine && <span className="text-xs text-ink/70">{t("upvote.own")}</span>}
        {open && !mine && user?.role === "citizen" &&
          (sup ? (
            <>
              <span className="chip border-emerald-300 bg-emerald-50 text-emerald-900">✓ {t("upvote.done")}</span>
              <button type="button" className="text-xs underline" disabled={busy} onClick={() => send("unvote")}>
                {t("upvote.undo")}
              </button>
            </>
          ) : (
            <button type="button" className="btn btn-primary !min-h-[36px] text-xs" disabled={busy} onClick={() => send("upvote")}>
              {t("upvote.cta")}
            </button>
          ))}
        {open && !user && (
          <Link href={`/login/citizen?next=${encodeURIComponent(next || `/ticket/${id}`)}`} className="btn btn-ghost !min-h-[36px] text-xs">
            {t("upvote.cta")}
          </Link>
        )}
      </div>
      {open && !user && <p className="text-xs text-ink/70">{t("upvote.loginTo")}</p>}
      {open && !mine && user?.role === "citizen" && !sup && <p className="text-xs text-ink/70">{t("upvote.help")}</p>}
      {err && (
        <p role="alert" className="text-xs text-red-800">
          {err}
        </p>
      )}
    </div>
  );
}

/** Optional e-mail address: complaint-resolved e-mails (citizens) and deadline reminders (contractors). */
export function ContactCard() {
  const { t, lang } = useLang();
  const { user, refresh } = useAuth();
  const [email, setEmail] = useState(user?.email || "");
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => setEmail(user?.email || ""), [user?.email]);
  if (!user) return null;
  const save = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setMsg(null);
    try {
      const r = await api<{ email: string | null }>("/me/contact", { method: "POST", body: { email: email.trim(), lang } });
      await refresh();
      setMsg({ ok: true, text: r.email ? t("mail.saved", { email: r.email }) : t("mail.cleared") });
    } catch (err: any) {
      setMsg({ ok: false, text: err?.message || t("common.error") });
    } finally {
      setBusy(false);
    }
  };
  return (
    <form onSubmit={save} className="card space-y-2 text-sm">
      <h2 className="text-sm font-bold">{t("mail.title")}</h2>
      <p className="text-xs text-ink/70">{t(user.role === "contractor" ? "mail.helpContractor" : "mail.helpCitizen")}</p>
      <div className="flex gap-2">
        <input
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          maxLength={120}
          autoComplete="email"
          placeholder={t("mail.placeholder")}
          aria-label={t("mail.title")}
          className="min-h-[40px] min-w-0 flex-1 rounded-md border border-ledger-200 px-2"
        />
        <button className="btn btn-primary !min-h-[40px]" disabled={busy}>
          {t("mail.save")}
        </button>
      </div>
      {!user.email && !msg && <p className="text-xs text-ink/60">{t("mail.none")}</p>}
      {msg && (
        <p role="status" className={`text-xs ${msg.ok ? "text-emerald-800" : "text-red-800"}`}>
          {msg.text}
        </p>
      )}
    </form>
  );
}

/** "Log in to continue" box shown instead of a panel, never as a wall in front of public pages. */
export function NeedLogin({ role, next, message }: { role: "citizen" | "officer" | "contractor"; next: string; message: string }) {
  const { t } = useLang();
  return (
    <div className="card mx-auto max-w-md text-sm">
      <p>{message}</p>
      <div className="mt-3 flex flex-wrap gap-2">
        <Link href={`/login/${role}?next=${encodeURIComponent(next)}`} className="btn btn-primary">
          {t(`auth.title.${role}`)}
        </Link>
        <Link href="/complaints" className="btn btn-ghost">
          {t("auth.keepBrowsing")}
        </Link>
      </div>
    </div>
  );
}
