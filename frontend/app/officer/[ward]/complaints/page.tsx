"use client";
import { useParams } from "next/navigation";
import { useState } from "react";
import { useApi } from "@/lib/api";
import { wardCode, wardSlug } from "@/lib/format";
import { useLang } from "@/lib/i18n";
import { ErrorBox, Loading } from "@/components/Ui";
import OfficerShell from "@/components/officer/OfficerShell";
import { TicketCard } from "@/components/live/bits";
import TicketView from "@/components/live/TicketView";

const FILTERS = ["submitted", "verified", "open", "resolved", "closed"];

/** DFD 3.0 Verify Complaint: the ward's queue, newest first, with the complaint and actions side by side. */
export default function OfficerComplaints() {
  const params = useParams<{ ward: string }>();
  const slug = wardSlug(wardCode(params.ward));
  const { t } = useLang();
  const [status, setStatus] = useState("submitted");
  const [sel, setSel] = useState<string | null>(null);
  const [bySupport, setBySupport] = useState(false);       // officers can put the most-supported complaints first
  const list = useApi<any>(`/tickets?ward=${slug}&status=${status}&limit=100${bySupport ? "&sort=upvotes" : ""}`);
  const counts = list.data?.counts || {};
  return (
    <OfficerShell ward={params.ward}>
      <div className="mb-2 flex flex-wrap gap-1.5">
        {FILTERS.map((f) => (
          <button
            key={f}
            type="button"
            aria-pressed={status === f}
            onClick={() => (setStatus(f), setSel(null))}
            className={`chip !text-xs ${status === f ? "border-ledger-700 bg-ledger-700 text-white" : "border-ledger-200 bg-white"}`}
          >
            {t("officerq.filter." + f)}
            {counts[f] != null ? ` (${counts[f]})` : ""}
          </button>
        ))}
        <label className="ml-auto flex items-center gap-1 text-xs">
          <input type="checkbox" checked={bySupport} onChange={(e) => setBySupport(e.target.checked)} className="h-4 w-4" />
          {t("complaints.sort.upvotes")}
        </label>
      </div>
      {list.error && <ErrorBox error={list.error} onRetry={list.reload} />}
      {list.loading && !list.data && <Loading />}
      {list.data && (
        <div className="grid grid-cols-1 gap-3 lg:grid-cols-[380px_1fr]">
          <ul className="max-h-[75vh] space-y-2 overflow-y-auto pr-1">
            {list.data.items.length === 0 && <li className="card text-xs">{t("officerq.empty")}</li>}
            {list.data.items.map((x: any) => (
              <li key={x.ticket_id}>
                <TicketCard x={x} selected={sel === x.ticket_id} onClick={() => setSel(x.ticket_id)} />
              </li>
            ))}
          </ul>
          <div>{sel ? <TicketView key={sel} id={sel} onChanged={list.reload} /> : <p className="card text-sm text-ink/70">{t("officerq.pick")}</p>}</div>
        </div>
      )}
    </OfficerShell>
  );
}
