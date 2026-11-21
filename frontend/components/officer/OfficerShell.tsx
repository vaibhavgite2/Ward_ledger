"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import type { ReactNode } from "react";
import { useApi } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { wardCode, wardSlug } from "@/lib/format";
import { useLang } from "@/lib/i18n";
import { Loading } from "@/components/Ui";
import { NeedLogin } from "@/components/live/bits";

/** Officer (admin) panel frame: login gate, ward selector and tabs. */
export default function OfficerShell({ ward, children }: { ward: string; children: ReactNode }) {
  const { t } = useLang();
  const { user, ready } = useAuth();
  const path = usePathname();
  const router = useRouter();
  const code = wardCode(ward);
  const slug = wardSlug(code);
  const wards = useApi<any[]>(user?.role === "officer" ? "/wards" : null);
  if (!ready) return <Loading />;
  if (!user || user.role !== "officer") return <NeedLogin role="officer" next={path || "/officer/K-E"} message={t("officer.needLogin")} />;
  const tabs: [string, string][] = [
    [`/officer/${slug}/complaints`, "officer.tab.complaints"],
    [`/officer/${slug}/tasks`, "officer.tab.tasks"],
    [`/officer/${slug}`, "officer.tab.works"],
    [`/officer/${slug}/budget`, "officer.tab.budget"],
    ["/audit", "officer.tab.audit"],
  ];
  const sub = path?.replace(/^\/officer\/[^/]+/, "") || "";
  return (
    <div className="text-sm">
      <div className="mb-2 flex flex-wrap items-center gap-3">
        <h1 className="text-xl font-extrabold">{t("officer.title", { code })}</h1>
        <label className="flex items-center gap-1 text-xs">
          {t("officer.selectWard")}
          <select
            value={code}
            onChange={(e) => router.push(`/officer/${wardSlug(e.target.value)}${sub}`)}
            className="min-h-[36px] rounded border border-ledger-200 bg-white px-1"
          >
            {(wards.data ?? [{ ward_code: code, ward_name: "" }]).map((w) => (
              <option key={w.ward_code} value={w.ward_code}>
                {w.ward_code} {w.ward_name ? "· " + w.ward_name : ""}
              </option>
            ))}
          </select>
        </label>
        <span className="text-xs text-ink/60">
          {user.display_name} · {user.designation}
          {!user.can_act && <span className="ml-1 chip border-slate-300 bg-slate-50">{t("officer.readOnly")}</span>}
        </span>
      </div>
      <nav aria-label={t("nav.panel.officer")} className="mb-3 flex flex-wrap gap-1 border-b border-ledger-200">
        {tabs.map(([href, key]) => {
          const on = path === href;
          return (
            <Link
              key={href}
              href={href}
              aria-current={on ? "page" : undefined}
              className={`-mb-px rounded-t border px-3 py-1.5 text-xs font-semibold ${on ? "border-ledger-200 border-b-white bg-white" : "border-transparent text-ink/70 hover:bg-ledger-100"}`}
            >
              {t(key)}
            </Link>
          );
        })}
      </nav>
      {children}
    </div>
  );
}
