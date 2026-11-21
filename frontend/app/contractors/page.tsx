"use client";
import { useApi } from "@/lib/api";
import { useLang } from "@/lib/i18n";
import { rupee } from "@/lib/format";
import { ErrorBox, Loading, PageTitle } from "@/components/Ui";
import ScoreCard from "@/components/ScoreCard";

/** Contractors, listed alphabetically (never ranked), each with its civic trust score and the measures behind it. */
export default function ContractorsPage() {
  const { t } = useLang();
  const { data, error, loading, reload } = useApi<any[]>("/contractors");
  if (loading) return <Loading />;
  if (error) return <ErrorBox error={error} onRetry={reload} />;
  return (
    <div>
      <PageTitle sub={t("contractors.sub")}>{t("contractors.title")}</PageTitle>
      <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {(data || []).map((c) => (
          <li key={c.contractor_id}>
            <ScoreCard
              name={c.name}
              contractorId={c.contractor_id}
              score={c.score}
              meta={`${t("contractors.since", { y: c.empanelled_since })} · ${c.jobs} ${t("common.jobs")} · ${rupee(c.billed_inr)}`}
            />
            {c.clean_record_wards > 0 && (
              <span className="chip mt-2 border-emerald-300 bg-emerald-50 text-emerald-900">{t("contractors.clean", { n: c.clean_record_wards })}</span>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
