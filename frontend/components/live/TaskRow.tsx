"use client";
import Link from "next/link";
import { dateOnly, rupee } from "@/lib/format";
import { useLang } from "@/lib/i18n";
import { TaskStatus } from "./bits";

export default function TaskRow({ k }: { k: any }) {
  const { t } = useLang();
  return (
    <Link href={`/tasks/${k.task_id}`} className="card block hover:bg-ledger-50">
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <span className="font-mono text-xs">{k.task_id}</span>
        <TaskStatus status={k.status} overdue={k.overdue} />
        <span className="ml-auto text-xs text-ink/70">
          {t("task.due")}: {dateOnly(k.due_at)}
        </span>
      </div>
      <div className="mt-1 font-semibold">{k.title}</div>
      <div className="text-xs text-ink/70">
        {t("task.complaintsN", { n: k.tickets })} · {t("common.ward")} {k.ward_code}
        {k.contractor_name ? ` · ${k.contractor_name.replace(" (synthetic)", "")}` : ""}
        {k.approved_cost_inr != null ? ` · ${rupee(k.approved_cost_inr)}` : k.est_cost_inr ? ` · ~${rupee(k.est_cost_inr)}` : ""}
      </div>
      {k.overdue_notified_at && <div className="mt-0.5 text-xs text-red-900">{t("task.reminded", { date: dateOnly(k.overdue_notified_at) })}</div>}
    </Link>
  );
}
