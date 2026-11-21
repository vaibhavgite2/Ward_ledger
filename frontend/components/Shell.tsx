"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import type { ReactNode } from "react";
import { LANGS, useLang } from "@/lib/i18n";
import { homeFor, useAuth } from "@/lib/auth";

function Chevron() {
  return (
    <svg aria-hidden width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M2 4.25 6 8l4-3.75" />
    </svg>
  );
}

export default function Shell({ children }: { children: ReactNode }) {
  const { t, lang, setLang } = useLang();
  const { user, logout } = useAuth();
  const router = useRouter();
  const path = usePathname() || "/";
  const nav: [string, string][] = [
    ["/", "nav.home"],
    ["/complaints", "nav.complaints"],
    ["/map", "nav.map"],
    ["/wards", "nav.wards"],
    ["/contractors", "nav.contractors"],
    ["/ask", "nav.ask"],
    ["/rti", "nav.rti"],
  ];
  const isActive = (href: string) => (href === "/" ? path === "/" : path === href || path.startsWith(href + "/"));
  const panelLabel = user ? t(`nav.panel.${user.role}`) : "";
  const unread = user?.unread_notifications ?? 0;
  const canRaise = !user || user.role === "citizen";
  const wrap = "mx-auto w-full max-w-[1600px] px-4 sm:px-[30px]";
  const navLink = "rounded-md px-3 py-2 text-[15px] transition-colors hover:text-ink lg:text-[17px]";
  return (
    <>
      <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:z-50 focus:bg-white focus:p-2">
        {t("shell.skip")}
      </a>
      <header className="border-b border-ledger-200 bg-white no-print">
        <div className={`${wrap} flex flex-wrap items-center gap-x-6 gap-y-2 py-4`}>
          <Link href="/" className="font-display text-[26px] font-bold leading-none tracking-tight text-ledger-900">
            {t("common.app")}
          </Link>
          <nav aria-label="Main" className="flex flex-1 flex-wrap items-center gap-x-1 gap-y-1">
            {nav.map(([href, key]) => (
              <Link
                key={href}
                href={href}
                aria-current={isActive(href) ? "page" : undefined}
                className={`${navLink} ${isActive(href) ? "border border-ink font-medium text-ink" : "border border-transparent text-ink/75"}`}
              >
                {t(key)}
              </Link>
            ))}
            {user?.role === "officer" && (
              <Link
                href="/audit"
                aria-current={isActive("/audit") ? "page" : undefined}
                className={`${navLink} ${isActive("/audit") ? "border border-ink font-medium text-ink" : "border border-transparent text-ink/75"}`}
              >
                {t("nav.audit")}
              </Link>
            )}
          </nav>
          <div className="flex flex-wrap items-center gap-3">
            {canRaise && (
              <Link href="/complaints/new" className="btn btn-primary !min-h-[36px] !px-4 text-sm">
                {t("nav.raise")}
              </Link>
            )}
            <label className="relative flex items-center text-sm">
              <span className="sr-only">{t("shell.language")}</span>
              <select
                value={lang}
                onChange={(e) => setLang(e.target.value as typeof lang)}
                className="min-h-[36px] cursor-pointer appearance-none rounded-md border border-ledger-200 bg-white py-1 pl-3 pr-8 text-sm"
              >
                {LANGS.map((l) => (
                  <option key={l.code} value={l.code}>
                    {l.label}
                  </option>
                ))}
              </select>
              <span className="pointer-events-none absolute right-3 text-ink/60">
                <Chevron />
              </span>
            </label>
            {user ? (
              <>
                <Link href={homeFor(user)} className="btn btn-ghost !min-h-[36px] !px-4 text-sm !font-medium">
                  {panelLabel}
                  {unread > 0 && (
                    <span className="ml-1.5 rounded-full bg-amber-500 px-1.5 text-[10px] font-bold text-white" aria-label={t("notif.unread", { n: unread })}>
                      {unread}
                    </span>
                  )}
                </Link>
                <span className="hidden items-center gap-3 text-sm sm:flex">
                  <span className="font-mono text-[13px] tracking-wide text-ink/60" title={user.designation || ""}>
                    {user.display_name || user.login}
                  </span>
                  <span aria-hidden className="h-4 w-px bg-ledger-200" />
                </span>
                <button
                  type="button"
                  className="text-sm underline underline-offset-2"
                  onClick={async () => {
                    await logout();
                    router.push("/");
                  }}
                >
                  {t("auth.logout")}
                </button>
              </>
            ) : (
              <Link href="/login" className="btn btn-ghost !min-h-[36px] !px-4 text-sm !font-medium">
                {t("auth.login")}
              </Link>
            )}
          </div>
        </div>
      </header>
      <main id="main" className={`${wrap} py-9`}>
        {children}
      </main>
      <footer className={`${wrap} pb-12 text-[15px] leading-relaxed text-ink/80 no-print`}>
        <p className="max-w-[920px]">{t("footer.note")}</p>
      </footer>
    </>
  );
}
