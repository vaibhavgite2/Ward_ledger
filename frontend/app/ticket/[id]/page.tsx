"use client";
import Link from "next/link";
import { useParams, useSearchParams } from "next/navigation";
import { Suspense } from "react";
import { useAuth } from "@/lib/auth";
import { useLang } from "@/lib/i18n";
import { Loading } from "@/components/Ui";
import TicketView from "@/components/live/TicketView";

function Inner() {
  const { id } = useParams<{ id: string }>();
  const fresh = useSearchParams().get("new") === "1";
  const { t } = useLang();
  const { user } = useAuth();
  return (
    <div className="mx-auto max-w-3xl">
      {fresh && (
        <p role="status" className="card mb-3 border-emerald-300 bg-emerald-50 text-sm">
          {t("ticket.received")}
        </p>
      )}
      <TicketView id={decodeURIComponent(id).toUpperCase()} />
      <div className="mt-5 flex flex-wrap gap-2 no-print">
        <Link href="/complaints" className="btn btn-ghost">
          {t("ticket.allComplaints")}
        </Link>
        {user?.role === "citizen" && (
          <Link href="/me" className="btn btn-ghost">
            {t("nav.panel.citizen")}
          </Link>
        )}
      </div>
    </div>
  );
}

export default function TicketPage() {
  return (
    <Suspense fallback={<Loading />}>
      <Inner />
    </Suspense>
  );
}
