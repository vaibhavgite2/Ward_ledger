"use client";
import Link from "next/link";
import { useState } from "react";
import { api, useApi } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { wardSlug } from "@/lib/format";
import { useLang } from "@/lib/i18n";
import { ErrorBox, Loading, PageTitle } from "@/components/Ui";
import { ContactCard, NeedLogin, Notifications } from "@/components/live/bits";
import ScoreCard from "@/components/ScoreCard";
import TaskRow from "@/components/live/TaskRow";
import FindingCard from "@/components/FindingCard";

const GROUPS: [string, string[]][] = [
  ["needsAction", ["assigned", "rework"]],
  ["inProgress", ["in_progress"]],
  ["underReview", ["submitted"]],
  ["done", ["completed", "cancelled"]],
];

/** Contractor panel: tasks assigned to my firm, notifications, and findings about my firm with right of reply. */
export default function TasksPanel() {
  const { t } = useLang();
  const { user, ready } = useAuth();
  const isC = user?.role === "contractor";
  const tasks = useApi<any>(isC ? "/tasks?limit=200" : null);
  if (!ready) return <Loading />;
  if (!user) return <NeedLogin role="contractor" next="/tasks" message={t("tasks.needLogin")} />;
  if (user.role === "officer")
    return (
      <p className="card mx-auto max-w-md text-sm">
        <Link href={`/officer/${wardSlug(user.ward_code || "K/E")}/tasks`} className="underline">
          {t("officer.tab.tasks")}
        </Link>
      </p>
    );
  if (!isC) return <p className="card mx-auto max-w-md text-sm">{t("tasks.contractorsOnly")}</p>;
  const items = tasks.data?.items || [];
  return (
    <div>
      <PageTitle sub={user.contractor_name || user.display_name || ""}>{t("nav.panel.contractor")}</PageTitle>
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[1fr_340px]">
        <div>
          {tasks.error && <ErrorBox error={tasks.error} onRetry={tasks.reload} />}
          {tasks.loading && !tasks.data && <Loading />}
          {tasks.data && items.length === 0 && <p className="card text-sm">{t("tasks.none")}</p>}
          {GROUPS.map(([g, sts]) => {
            const list = items.filter((k: any) => sts.includes(k.status));
            if (!list.length) return null;
            return (
              <section key={g}>
                <h2 className="h2 first:!mt-0">
                  {t("tasks.group." + g)} ({list.length})
                </h2>
                <ul className="space-y-2">
                  {list.map((k: any) => (
                    <li key={k.task_id}>
                      <TaskRow k={k} />
                    </li>
                  ))}
                </ul>
              </section>
            );
          })}
          {user.contractor_id && <MyFindings cid={user.contractor_id} />}
        </div>
        <div className="space-y-3">
          {user.contractor_id && <MyScore cid={user.contractor_id} />}
          <ContactCard />
          <Notifications />
          {user.contractor_id && (
            <Link href={`/contractor/${user.contractor_id}`} className="card block text-sm hover:bg-ledger-50">
              {t("tasks.myRecord")} →
            </Link>
          )}
        </div>
      </div>
    </div>
  );
}

/** The firm's own civic trust score, built from its recorded work (including tasks missed or finished through this app). */
function MyScore({ cid }: { cid: string }) {
  const list = useApi<any[]>("/contractors");
  const me = (list.data || []).find((c) => c.contractor_id === cid);
  if (!me) return null;
  return <ScoreCard name={me.name} contractorId={cid} score={me.score} />;
}

function MyFindings({ cid }: { cid: string }) {
  const { t } = useLang();
  const f = useApi<any[]>(`/findings?contractor=${cid}&polarity=concern&limit=30`);
  const [open, setOpen] = useState<string | null>(null);
  const [text, setText] = useState("");
  const [msg, setMsg] = useState<string | null>(null);
  const send = async (id: string) => {
    setMsg(null);
    try {
      await api("/contractor/reply", { method: "POST", body: { finding_id: id, reply_text: text } });
      setOpen(null);
      setText("");
      f.reload();
    } catch (e: any) {
      setMsg(e?.message || t("common.error"));
    }
  };
  return (
    <section>
      <h2 className="h2">{t("tasks.findings")}</h2>
      <p className="mb-2 text-xs text-ink/70">{t("tasks.findingsHelp")}</p>
      {f.loading && !f.data && <Loading />}
      <ul className="space-y-2">
        {(f.data || []).map((x: any) => (
          <li key={x.finding_id}>
            <FindingCard f={x} />
            {!x.reply &&
              (open === x.finding_id ? (
                <div className="mt-1 space-y-1">
                  <textarea value={text} onChange={(e) => setText(e.target.value)} rows={2} maxLength={2000} className="w-full rounded border border-ledger-200 p-1 text-xs" />
                  <button className="btn btn-primary !min-h-[32px] text-xs" disabled={text.trim().length < 5} onClick={() => send(x.finding_id)}>
                    {t("tasks.sendReply")}
                  </button>
                  {msg && <p className="text-xs text-red-800">{msg}</p>}
                </div>
              ) : (
                <button className="mt-1 text-xs underline" onClick={() => (setOpen(x.finding_id), setText(""))}>
                  {t("tasks.reply")}
                </button>
              ))}
          </li>
        ))}
      </ul>
    </section>
  );
}
