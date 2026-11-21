"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import type { ReactNode } from "react";
import { LANGS, useLang } from "@/lib/i18n";
import { homeFor, useAuth } from "@/lib/auth";

export default function Shell({ children }: { children: ReactNode }) {
  const { t, lang, setLang } = useLang();
  const { user, logout } = useAuth();
  const router = useRouter();
  const nav: [string, string][] = [
    ["/", "nav.home"],
    ["/complaints", "nav.complaints"],
    ["/map", "nav.map"],
    ["/wards", "nav.wards"],
    ["/contractors", "nav.contractors"],
    ["/ask", "nav.ask"],
    ["/rti", "nav.rti"],
  ];
  const panelLabel = user ? t(`nav.panel.${user.role}`) : "";
  const unread = user?.unread_notifications ?? 0;
  const canRaise = !user || user.role === "citizen";
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
            {user?.role === "officer" && (
              <Link href="/audit" className="rounded px-1.5 py-1 text-ink hover:bg-ledger-100">
                {t("nav.audit")}
              </Link>
            )}
          </nav>
          {canRaise && (
            <Link href="/complaints/new" className="btn btn-primary !min-h-[36px] !px-3 text-xs">
              {t("nav.raise")}
            </Link>
          )}
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
          {user ? (
            <div className="flex items-center gap-2 text-xs">
              <Link href={homeFor(user)} className="btn btn-ghost !min-h-[36px] !px-2">
                {panelLabel}
                {unread > 0 && (
                  <span className="ml-1 rounded-full bg-amber-500 px-1.5 text-[10px] font-bold text-white" aria-label={t("notif.unread", { n: unread })}>
                    {unread}
                  </span>
                )}
              </Link>
              <span className="hidden text-ink/70 sm:inline" title={user.designation || ""}>
                {user.display_name || user.login}
              </span>
              <button
                type="button"
                className="underline"
                onClick={async () => {
                  await logout();
                  router.push("/");
                }}
              >
                {t("auth.logout")}
              </button>
            </div>
          ) : (
            <Link href="/login" className="btn btn-ghost !min-h-[36px] !px-3 text-xs">
              {t("auth.login")}
            </Link>
          )}
        </div>
      </header>
      <main id="main" className="mx-auto max-w-6xl px-3 py-4">
        {children}
      </main>
      <footer className="mx-auto max-w-6xl px-3 pb-8 pt-4 text-xs text-ledger-700 no-print">{t("footer.note")}</footer>
    </>
  );
}
