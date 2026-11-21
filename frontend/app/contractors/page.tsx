"use client";
import Link from "next/link";
import { useState } from "react";
import { useApi } from "@/lib/api";
import { useLang } from "@/lib/i18n";
import { rupee } from "@/lib/format";
import { ErrorBox, Loading, PageTitle } from "@/components/Ui";

// The API appends "(synthetic)" to every fictional name; show it as a quiet suffix.
const splitName = (name: string): [string, string] => {
  const m = name.match(/^(.*?)\s*(\(synthetic\))$/i);
  return m ? [m[1], m[2]] : [name, ""];
};

export default function ContractorsPage() {
  const { t } = useLang();
  const { data, error, loading, reload } = useApi<any[]>("/contractors");
  const [q, setQ] = useState("");
  const [cleanOnly, setCleanOnly] = useState(false);
  if (loading) return <Loading />;
  if (error) return <ErrorBox error={error} onRetry={reload} />;
  const rows = (data || []).filter(
    (c) => (!cleanOnly || c.clean_record_wards > 0) && c.name.toLowerCase().includes(q.trim().toLowerCase()),
  );
  return (
    <div>
      <div className="flex flex-col gap-4 border-b border-ledger-200 pb-8 lg:flex-row lg:items-end lg:justify-between">
        <PageTitle sub={t("contractors.sub")}>{t("contractors.title")}</PageTitle>
        <div className="flex flex-wrap items-center gap-4 lg:shrink-0">
          <label className="relative block w-full sm:w-[320px]">
            <span className="sr-only">{t("contractors.search")}</span>
            <svg aria-hidden className="absolute left-4 top-1/2 -translate-y-1/2 text-ink/50" width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round">
              <circle cx="7" cy="7" r="4.75" />
              <path d="m10.5 10.5 3 3" />
            </svg>
            <input
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder={t("contractors.search")}
              className="h-[42px] w-full rounded-lg border border-ledger-200 bg-white pl-11 pr-3 text-[15px] placeholder:text-ink/40"
            />
          </label>
          <button
            type="button"
            aria-pressed={cleanOnly}
            onClick={() => setCleanOnly((v) => !v)}
            className={`inline-flex h-[38px] items-center gap-2 rounded-lg border px-4 text-sm font-medium transition ${
              cleanOnly ? "border-emerald-400 bg-emerald-50 text-emerald-900" : "border-ledger-200 bg-white text-ink hover:bg-ledger-100"
            }`}
          >
            <span aria-hidden className="h-2 w-2 rounded-full bg-emerald-500" />
            {t("contractors.cleanOnly")}
          </button>
        </div>
      </div>

      {rows.length === 0 ? (
        <p className="mt-10 text-sm text-ink/70">{t("contractors.none")}</p>
      ) : (
        <ul className="mt-10 grid gap-6 md:grid-cols-2 lg:grid-cols-3">
          {rows.map((c) => {
            const [name, tag] = splitName(c.name);
            return (
              <li key={c.contractor_id}>
                <Link href={`/contractor/${c.contractor_id}`} className="card flex h-full min-h-[225px] flex-col p-6 hover:bg-ledger-100/60">
                  <div className="text-lg font-semibold leading-snug">
                    {name} {tag && <span className="text-sm font-normal text-ink/50">{tag}</span>}
                  </div>
                  <div className="mt-3 text-[15px] text-ink/70">
                    {t("contractors.since", { y: c.empanelled_since })} · {c.jobs} {t("common.jobs")} · {rupee(c.billed_inr)}
                  </div>
                  {c.clean_record_wards > 0 && (
                    <span className="chip mt-3 w-fit gap-2 border-emerald-300 bg-emerald-50 px-3 py-1 text-sm font-normal text-emerald-900">
                      <span aria-hidden className="h-1.5 w-1.5 rounded-full bg-emerald-600" />
                      {t("contractors.clean", { n: c.clean_record_wards })}
                    </span>
                  )}
                  <div className="mt-auto flex items-center justify-between border-t border-ledger-100 pt-4 text-sm text-ink/55">
                    <span>{t("contractors.viewAudit")}</span>
                    <span className="text-ink/35">#{c.contractor_id}</span>
                  </div>
                </Link>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
