"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";
import { api, useApi } from "@/lib/api";
import { useLang } from "@/lib/i18n";
import { crore, rupee, wardSlug } from "@/lib/format";
import { ErrorBox, Loading, PageTitle, Stat } from "@/components/Ui";

const RE_COMPLAINT = /^BMC\d{2}-\d{6}$/i;
const RE_WO = /^WO\d{2}-\d{5}$/i;
const RE_ROAD = /^RD\d{4}$/i;
const RE_TICKET = /^CMP-\d{6}$/i;
const RE_TASK = /^TSK-\d{6}$/i;

export default function Home() {
  const { t, lang } = useLang();
  const router = useRouter();
  const [q, setQ] = useState("");
  const meta = useApi<any>("/meta");
  const wards = useApi<any[]>("/wards");
  const [near, setNear] = useState<any>(null);
  const [locState, setLocState] = useState<"idle" | "busy" | "denied">("idle");

  const submit = (e: FormEvent) => {
    e.preventDefault();
    const s = q.trim();
    if (!s) return;
    if (RE_TICKET.test(s)) router.push(`/ticket/${s.toUpperCase()}`);
    else if (RE_TASK.test(s)) router.push(`/tasks/${s.toUpperCase()}`);
    else if (RE_COMPLAINT.test(s)) router.push(`/complaint/${s.toUpperCase()}`);
    else if (RE_WO.test(s)) router.push(`/rti?work_order_id=${s.toUpperCase()}`);
    else if (RE_ROAD.test(s)) router.push(`/road/${s.toUpperCase()}`);
    else router.push(`/ask?q=${encodeURIComponent(s)}`);
  };

  const locate = () => {
    if (!navigator.geolocation) return setLocState("denied");
    setLocState("busy");
    navigator.geolocation.getCurrentPosition(
      async (pos) => {
        try {
          setNear(await api(`/works/near?lat=${pos.coords.latitude}&lon=${pos.coords.longitude}&radius=300`, { lang }));
          setLocState("idle");
        } catch {
          setLocState("denied");
        }
      },
      () => setLocState("denied"),
      { enableHighAccuracy: false, timeout: 10000 },
    );
  };

  const c = meta.data?.city;
  return (
    <div>
      <section className="rounded-xl bg-ledger-900 px-4 py-6 text-white">
        <h1 className="text-3xl font-extrabold leading-tight sm:text-4xl">{t("home.headline")}</h1>
        <p className="mt-2 max-w-2xl text-sm text-ledger-100">{t("home.sub")}</p>
        <form onSubmit={submit} className="mt-4 flex max-w-2xl flex-col gap-2 sm:flex-row" role="search">
          <label className="flex-1">
            <span className="sr-only">{t("home.searchLabel")}</span>
            <input
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder={t("home.searchPlaceholder")}
              className="min-h-[48px] w-full rounded-md border-0 px-3 text-base text-ink"
            />
          </label>
          <button className="btn btn-primary !bg-amber-500 !text-ledger-900 hover:!bg-amber-400" type="submit">
            {t("home.search")}
          </button>
        </form>
        <div className="mt-3 flex flex-wrap items-center gap-2 text-sm">
          <Link href="/complaints/new" className="btn btn-primary !bg-white !text-ledger-900 hover:!bg-ledger-100">
            {t("nav.raise")}
          </Link>
          <Link href="/complaints" className="btn btn-ghost !text-ink">
            {t("home.seeComplaints")}
          </Link>
          <button type="button" onClick={locate} className="btn btn-ghost !text-ink" disabled={locState === "busy"}>
            {locState === "busy" ? t("home.locating") : t("home.useLocation")}
          </button>
          <label className="flex min-w-0 max-w-full flex-wrap items-center gap-2">
            <span className="text-ledger-100">{t("home.pickWard")}</span>
            <select
              className="min-h-[44px] w-full min-w-0 max-w-full rounded-md px-2 text-ink sm:w-auto"
              defaultValue=""
              onChange={(e) => e.target.value && router.push(`/ward/${wardSlug(e.target.value)}`)}
            >
              <option value="" />
              {(wards.data || []).map((w) => (
                <option key={w.ward_code} value={w.ward_code}>
                  {w.ward_code} · {w.ward_name}
                </option>
              ))}
            </select>
          </label>
        </div>
        {locState === "denied" && <p className="mt-2 text-sm text-amber-200">{t("home.locationDenied")}</p>}
      </section>

      {near && (
        <section className="mt-4" aria-live="polite">
          <h2 className="h2">{t("home.nearTitle")}</h2>
          <p className="mb-2 text-xs text-ink/70">{t("home.nearHelp")}</p>
          {near.roads.length === 0 ? (
            <p className="card text-sm">{t("home.nearNone")}</p>
          ) : (
            <ul className="grid gap-2 sm:grid-cols-2">
              {near.roads.map((r: any) => (
                <li key={r.road_id}>
                  <Link href={`/road/${r.road_id}`} className="card block hover:bg-ledger-50">
                    <div className="font-semibold">
                      {r.road_name} · {r.segment_no}
                    </div>
                    <div className="text-xs text-ink/70">
                      ~{r.distance_m} m · {r.repairs} {t("common.jobs")} · {rupee(r.spent_inr)}
                      {r.failed_repairs > 0 && ` · ${r.failed_repairs} ${t("road.failed")}`}
                    </div>
                    {r.under_dlp && <span className="chip mt-1 border-blue-200 bg-blue-50 text-blue-900">{t("road.warranty")}</span>}
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </section>
      )}

      <section className="mt-6">
        <h2 className="h2 !mt-0">{t("home.cityTitle")}</h2>
        {meta.loading && <Loading />}
        {meta.error && <ErrorBox error={meta.error} onRetry={meta.reload} />}
        {c && (
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            <Stat label={t("home.cityBudget")} value={"₹" + crore(c.budget_inr)} />
            <Stat label={t("home.citySpend")} value={"₹" + crore(c.spend_inr)} sub={`${c.jobs.toLocaleString("en-IN")} ${t("common.jobs")}`} />
            <Stat
              label={t("home.cityFailed")}
              value={"₹" + crore(c.failed_inr)}
              sub={`${c.failed_jobs.toLocaleString("en-IN")} ${t("common.jobs")}`}
              tone="warn"
            />
            <Stat label={t("home.cityNever")} value={c.never_fixed_issues.toLocaleString("en-IN")} tone="warn" />
          </div>
        )}
      </section>

      <section className="mt-6">
        <h2 className="h2 !mt-0">{t("home.explore")}</h2>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {[
            ["/map", "home.linkMap"],
            ["/wards", "home.linkWards"],
            ["/contractors", "home.linkContractors"],
            ["/ask", "home.linkAsk"],
          ].map(([href, key]) => (
            <Link key={href} href={href} className="card text-sm font-semibold hover:bg-ledger-50">
              {t(key)} →
            </Link>
          ))}
        </div>
        <p className="mt-4 max-w-2xl text-sm text-ink/70">{t("home.about")}</p>
      </section>
    </div>
  );
}
