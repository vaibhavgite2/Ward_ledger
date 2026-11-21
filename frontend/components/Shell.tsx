"use client";
import Link from "next/link";
import type { ReactNode } from "react";
import { LANGS, useLang } from "@/lib/i18n";
import { useRole, type Role } from "@/lib/role";

export default function Shell({ children }: { children: ReactNode }) {
  const { t, lang, setLang } = useLang();
  const { role, setRole } = useRole();
  const nav: [string, string][] = [
    ["/", "nav.home"],
    ["/map", "nav.map"],
    ["/wards", "nav.wards"],
    ["/contractors", "nav.contractors"],
    ["/ask", "nav.ask"],
    ["/rti", "nav.rti"],
  ];
  if (role === "officer") nav.push(["/officer/K-E", "nav.officer"]);
  if (role === "auditor") nav.push(["/audit", "nav.audit"]);
  return (
    <>
      <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:z-50 focus:bg-white focus:p-2">
        {t("shell.skip")}
      </a>
      <div role="note" className="bg-amber-100 px-3 py-1.5 text-center text-xs font-medium text-amber-900 no-print">
        {t("common.demo")}
      </div>
      <header className="border-b border-ledger-200 bg-white no-print">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-4 gap-y-2 px-3 py-2">
          <Link href="/" className="text-lg font-extrabold tracking-tight text-ledger-900">
            {t("common.app")}
          </Link>
          <nav aria-label="Main" className="flex flex-1 flex-wrap gap-x-3 gap-y-1 text-sm">
            {nav.map(([href, key]) => (
              <Link key={href} href={href} className="rounded px-1.5 py-1 text-ink hover:bg-ledger-100">
                {t(key)}
              </Link>
            ))}
          </nav>
          <label className="flex items-center gap-1 text-xs">
            <span className="sr-only">{t("shell.language")}</span>
            <select
              value={lang}
              onChange={(e) => setLang(e.target.value as typeof lang)}
              className="min-h-[36px] rounded border border-ledger-200 bg-white px-1"
            >
              {LANGS.map((l) => (
                <option key={l.code} value={l.code}>
                  {l.label}
                </option>
              ))}
            </select>
          </label>
          <label className="flex items-center gap-1 text-xs">
            <span className="text-ledger-700">{t("shell.role")}</span>
            <select
              value={role}
              onChange={(e) => setRole(e.target.value as Role)}
              className="min-h-[36px] rounded border border-ledger-200 bg-white px-1"
            >
              {(["public", "officer", "auditor"] as Role[]).map((r) => (
                <option key={r} value={r}>
                  {t("role." + r)}
                </option>
              ))}
            </select>
          </label>
        </div>
      </header>
      <main id="main" className="mx-auto max-w-6xl px-3 py-4">
        {children}
      </main>
      <footer className="mx-auto max-w-6xl px-3 pb-8 pt-4 text-xs text-ledger-700 no-print">{t("footer.note")}</footer>
    </>
  );
}
