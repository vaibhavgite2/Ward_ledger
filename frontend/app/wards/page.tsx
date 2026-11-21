"use client";
import Link from "next/link";
import { useMemo, useState } from "react";
import { useApi } from "@/lib/api";
import { useLang } from "@/lib/i18n";
import { crore, wardSlug } from "@/lib/format";
import { ErrorBox, Loading, PageTitle } from "@/components/Ui";

type Col = { key: string; label: string; num?: boolean; fmt?: (v: any, row: any) => string };

export default function WardsPage() {
  const { t } = useLang();
  const { data, error, loading, reload } = useApi<any[]>("/wards/compare");
  const [sort, setSort] = useState<{ key: string; dir: 1 | -1 }>({ key: "failed_inr", dir: -1 });

  const cols: Col[] = [
    { key: "ward_code", label: t("wards.col.ward") },
    { key: "budget_inr", label: t("wards.col.budget"), num: true, fmt: (v) => crore(v) },
    { key: "spend_inr", label: t("wards.col.billed"), num: true, fmt: (v) => crore(v) },
    { key: "utilisation_pct", label: t("wards.col.used"), num: true, fmt: (v) => v + "%" },
    { key: "failed_inr", label: t("wards.col.failed"), num: true, fmt: (v) => crore(v) },
    { key: "failed_pct", label: t("wards.col.failedPct"), num: true, fmt: (v) => v + "%" },
    { key: "sla_pct", label: t("wards.col.onTime"), num: true, fmt: (v) => v + "%" },
    { key: "complaints", label: t("wards.col.complaints"), num: true },
    { key: "never_fixed", label: t("wards.col.noRepair"), num: true },
    { key: "open_issues", label: t("wards.col.open"), num: true },
  ];
  const rows = useMemo(() => {
    const r = [...(data || [])];
    r.sort((a, b) => {
      const x = a[sort.key],
        y = b[sort.key];
      return (typeof x === "number" && typeof y === "number" ? x - y : String(x).localeCompare(String(y))) * sort.dir;
    });
    return r;
  }, [data, sort]);

  if (loading) return <Loading />;
  if (error) return <ErrorBox error={error} onRetry={reload} />;
  return (
    <div>
      <PageTitle sub={t("wards.sub")}>{t("wards.title")}</PageTitle>
      <div className="card overflow-x-auto p-0">
        <table className="w-full min-w-[760px] text-sm">
          <thead className="bg-ledger-100 text-xs text-ink/70">
            <tr>
              {cols.map((c) => (
                <th key={c.key} className={`p-0 ${c.num ? "text-right" : "text-left"}`} aria-sort={sort.key === c.key ? (sort.dir === 1 ? "ascending" : "descending") : "none"}>
                  <button
                    className="w-full p-2 font-semibold hover:bg-ledger-200"
                    onClick={() => setSort((s) => ({ key: c.key, dir: s.key === c.key ? ((-s.dir) as 1 | -1) : -1 }))}
                  >
                    {c.label} {sort.key === c.key ? (sort.dir === 1 ? "↑" : "↓") : ""}
                  </button>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.ward_code} className="border-t border-ledger-100 hover:bg-ledger-50">
                {cols.map((c) => (
                  <td key={c.key} className={`p-2 tabular-nums ${c.num ? "text-right" : ""}`}>
                    {c.key === "ward_code" ? (
                      <Link href={`/ward/${wardSlug(r.ward_code)}`} className="font-semibold underline">
                        {r.ward_code} <span className="font-normal text-ink/60">{r.ward_name.split(",")[0]}</span>
                      </Link>
                    ) : c.fmt ? (
                      c.fmt(r[c.key], r)
                    ) : (
                      r[c.key]
                    )}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="mt-2 text-xs text-ink/60">₹ in lakh (L) / crore (Cr)</p>
    </div>
  );
}
