"use client";
import Link from "next/link";
import { useLang } from "@/lib/i18n";
import { PageTitle } from "@/components/Ui";

/** The three separate login panels (DFD 1.1 Citizen, 1.2 Officer, 1.3 Contractor). Nobody has to log in to browse. */
export default function LoginChooser() {
  const { t } = useLang();
  const panels: ["citizen" | "officer" | "contractor", string][] = [
    ["citizen", "border-l-emerald-600"],
    ["officer", "border-l-ledger-700"],
    ["contractor", "border-l-amber-500"],
  ];
  return (
    <div className="mx-auto max-w-3xl">
      <PageTitle sub={t("auth.chooserSub")}>{t("auth.chooserTitle")}</PageTitle>
      <div className="grid gap-3 sm:grid-cols-3">
        {panels.map(([role, tone]) => (
          <Link key={role} href={`/login/${role}`} className={`card block border-l-4 ${tone} hover:bg-ledger-50`}>
            <div className="text-base font-bold">{t(`auth.title.${role}`)}</div>
            <p className="mt-1 text-xs text-ink/70">{t(`auth.sub.${role}`)}</p>
          </Link>
        ))}
      </div>
      <p className="mt-4 text-sm text-ink/70">{t("auth.noLoginNeeded")}</p>
    </div>
  );
}
