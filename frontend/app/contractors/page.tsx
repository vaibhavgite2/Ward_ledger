"use client";
import Link from "next/link";
import { useApi } from "@/lib/api";
import { useLang } from "@/lib/i18n";
import { rupee } from "@/lib/format";
import { ErrorBox, Loading, PageTitle } from "@/components/Ui";

export default function ContractorsPage() {
  const { t } = useLang();
  const { data, error, loading, reload } = useApi<any[]>("/contractors");
  if (loading) return <Loading />;
  if (error) return <ErrorBox error={error} onRetry={reload} />;
  return (
    <div>
      <PageTitle sub={t("contractors.sub")}>{t("contractors.title")}</PageTitle>
      <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {(data || []).map((c) => (
          <li key={c.contractor_id}>
            <Link href={`/contractor/${c.contractor_id}`} className="card block hover:bg-ledger-50">
              <div className="font-bold">{c.name}</div>
              <div className="mt-1 text-xs text-ink/70">
                {t("contractors.since", { y: c.empanelled_since })} · {c.jobs} {t("common.jobs")} · {rupee(c.billed_inr)}
              </div>
              {c.clean_record_wards > 0 && (
                <span className="chip mt-2 border-emerald-300 bg-emerald-50 text-emerald-900">{t("contractors.clean", { n: c.clean_record_wards })}</span>
              )}
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}
