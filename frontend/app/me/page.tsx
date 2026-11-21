"use client";
import Link from "next/link";
import { useApi } from "@/lib/api";
import { homeFor, useAuth } from "@/lib/auth";
import { useLang } from "@/lib/i18n";
import { ErrorBox, Loading, PageTitle } from "@/components/Ui";
import { ContactCard, NeedLogin, Notifications, TicketCard } from "@/components/live/bits";

/** Citizen panel: the complaints I raised, where each one is, and my notifications. */
export default function MyPanel() {
  const { t } = useLang();
  const { user, ready } = useAuth();
  const mine = useApi<any>(user?.role === "citizen" ? "/tickets?mine=1&limit=100" : null);
  if (!ready) return <Loading />;
  if (!user) return <NeedLogin role="citizen" next="/me" message={t("me.needLogin")} />;
  if (user.role !== "citizen")
    return (
      <p className="card mx-auto max-w-md text-sm">
        {t("me.otherRole")}{" "}
        <Link href={homeFor(user)} className="underline">
          {t(`nav.panel.${user.role}`)}
        </Link>
      </p>
    );
  const items = mine.data?.items || [];
  const open = items.filter((x: any) => !["resolved", "rejected", "duplicate"].includes(x.status));
  const closed = items.filter((x: any) => ["resolved", "rejected", "duplicate"].includes(x.status));
  return (
    <div>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <PageTitle sub={t("me.sub", { name: user.display_name || user.login })}>{t("nav.panel.citizen")}</PageTitle>
        <Link href="/complaints/new" className="btn btn-primary">
          {t("nav.raise")}
        </Link>
      </div>
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[1fr_340px]">
        <div>
          {mine.error && <ErrorBox error={mine.error} onRetry={mine.reload} />}
          {mine.loading && !mine.data && <Loading />}
          {mine.data && items.length === 0 && (
            <p className="card text-sm">
              {t("me.none")}{" "}
              <Link href="/complaints/new" className="underline">
                {t("nav.raise")}
              </Link>
            </p>
          )}
          {open.length > 0 && (
            <>
              <h2 className="h2 !mt-0">{t("me.open", { n: open.length })}</h2>
              <ul className="space-y-2">
                {open.map((x: any) => (
                  <li key={x.ticket_id}>
                    <TicketCard x={x} />
                  </li>
                ))}
              </ul>
            </>
          )}
          {closed.length > 0 && (
            <>
              <h2 className="h2">{t("me.closed", { n: closed.length })}</h2>
              <ul className="space-y-2">
                {closed.map((x: any) => (
                  <li key={x.ticket_id}>
                    <TicketCard x={x} />
                  </li>
                ))}
              </ul>
            </>
          )}
        </div>
        <div className="space-y-3">
          <ContactCard />
          <Notifications />
        </div>
      </div>
    </div>
  );
}
