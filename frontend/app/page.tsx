"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";
import { api, useApi } from "@/lib/api";
import { useLang } from "@/lib/i18n";
import { crore, rupee, wardSlug } from "@/lib/format";
import { ErrorBox, Loading, Stat } from "@/components/Ui";

const RE_COMPLAINT = /^BMC\d{2}-\d{6}$/i;
const RE_WO = /^WO\d{2}-\d{5}$/i;
const RE_ROAD = /^RD\d{4}$/i;
const RE_TICKET = /^CMP-\d{6}$/i;
const RE_TASK = /^TSK-\d{6}$/i;

const SLIDES = [1, 2, 3];
const SLIDE_MS = 8000;

function Icon({ d, size = 16 }: { d: string; size?: number }) {
  return (
    <svg aria-hidden width={size} height={size} viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d={d} />
    </svg>
  );
}

export default function Home() {
  const { t, lang } = useLang();
  const router = useRouter();
  const [q, setQ] = useState("");
  const meta = useApi<any>("/meta");
  const wards = useApi<any[]>("/wards");
  const [near, setNear] = useState<any>(null);
  const [locState, setLocState] = useState<"idle" | "busy" | "denied">("idle");
  const [slide, setSlide] = useState(0);
  const [paused, setPaused] = useState(false);

  // Auto-advance the hero, unless the visitor prefers reduced motion or is interacting with it.
  useEffect(() => {
    if (paused || window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const id = setTimeout(() => setSlide((s) => (s + 1) % SLIDES.length), SLIDE_MS);
    return () => clearTimeout(id);
  }, [slide, paused]);
  const go = (n: number) => setSlide((n + SLIDES.length) % SLIDES.length);

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
  const n = slide + 1;
  const heroBtn =
    "inline-flex min-h-[40px] items-center justify-center gap-2 rounded-md bg-white px-5 text-[15px] font-medium text-ink transition hover:bg-ledger-100 disabled:opacity-70";
  const arrowBtn =
    "inline-flex h-8 w-8 items-center justify-center rounded-md border border-white/20 text-white/80 transition hover:bg-white/10 hover:text-white";

  return (
    <div>
      <section
        className="hero-grid rounded-[28px] bg-hero px-6 py-8 text-white shadow-[0_12px_32px_rgba(33,29,20,0.18)] sm:px-[50px] sm:py-[42px]"
        aria-roledescription="carousel"
        aria-label={t("home.cityTitle")}
        onMouseEnter={() => setPaused(true)}
        onMouseLeave={() => setPaused(false)}
        onFocus={() => setPaused(true)}
        onBlur={() => setPaused(false)}
      >
        <div className="flex items-center justify-between gap-4 border-b border-white/10 pb-4">
          <span className="rounded-md border border-accent/40 bg-accent/10 px-3 py-1 font-mono text-xs font-semibold uppercase tracking-[0.14em] text-accent">
            {t(`home.eyebrow${n}`)}
          </span>
          <div className="flex items-center gap-4">
            <div className="hidden items-center gap-1.5 sm:flex">
              {SLIDES.map((s, i) => (
                <button
                  key={s}
                  type="button"
                  onClick={() => setSlide(i)}
                  aria-label={t("home.slideOf", { n: s, total: SLIDES.length })}
                  aria-current={i === slide}
                  className={`h-1.5 rounded-full transition-all ${i === slide ? "w-9 bg-accent" : "w-2 bg-white/30 hover:bg-white/50"}`}
                />
              ))}
            </div>
            <span className="font-mono text-xs text-white/50">
              <b className="font-semibold text-white">{String(n).padStart(2, "0")}</b> / {String(SLIDES.length).padStart(2, "0")}
            </span>
            <div className="flex gap-1.5">
              <button type="button" className={arrowBtn} onClick={() => go(slide - 1)} aria-label={t("home.prev")}>
                <Icon d="M9.5 3.5 5 8l4.5 4.5" />
              </button>
              <button type="button" className={arrowBtn} onClick={() => go(slide + 1)} aria-label={t("home.next")}>
                <Icon d="M6.5 3.5 11 8l-4.5 4.5" />
              </button>
            </div>
          </div>
        </div>

        <div className="min-h-[150px] pt-6" aria-live="off">
          <h1 className="max-w-5xl font-display text-3xl font-bold leading-[1.15] tracking-tight sm:text-[44px]">{t(`home.slide${n}.title`)}</h1>
          <p className="mt-5 max-w-3xl text-base text-white/75 sm:text-[19px]">{t(`home.slide${n}.sub`)}</p>
        </div>

        <form onSubmit={submit} className="mt-10 flex max-w-[960px] sm:mt-16" role="search">
          <label className="min-w-0 flex-1">
            <span className="sr-only">{t("home.searchLabel")}</span>
            <input
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder={t("home.searchPlaceholder")}
              className="h-[50px] w-full rounded-l-md border-0 bg-white px-5 text-base text-ink placeholder:text-ink/40"
            />
          </label>
          <button className="h-[50px] shrink-0 rounded-r-md bg-accent px-8 text-base font-semibold text-ink transition hover:brightness-110" type="submit">
            {t("home.search")}
          </button>
        </form>

        <div className="mt-6 flex flex-wrap items-center gap-3">
          <Link href="/complaints/new" className={heroBtn}>
            {t("nav.raise")}
          </Link>
          <Link href="/complaints" className={heroBtn}>
            {t("home.seeComplaints")}
          </Link>
          <button type="button" onClick={locate} className={heroBtn} disabled={locState === "busy"}>
            <Icon d="M8 14.5s4.75-3.9 4.75-7.6a4.75 4.75 0 1 0-9.5 0c0 3.7 4.75 7.6 4.75 7.6ZM8 8.6a1.7 1.7 0 1 0 0-3.4 1.7 1.7 0 0 0 0 3.4Z" size={15} />
            {locState === "busy" ? t("home.locating") : t("home.useLocation")}
          </button>
          <label className="flex min-w-0 max-w-full flex-wrap items-center gap-3">
            <span className="text-sm text-white/75">{t("home.pickWard")}</span>
            <span className="relative block w-full sm:w-[274px]">
              <select
                className="h-10 w-full min-w-0 cursor-pointer appearance-none rounded-md border-0 bg-white pl-4 pr-9 text-[15px] text-ink"
                defaultValue=""
                onChange={(e) => e.target.value && router.push(`/ward/${wardSlug(e.target.value)}`)}
              >
                <option value="">{t("home.selectWard")}</option>
                {(wards.data || []).map((w) => (
                  <option key={w.ward_code} value={w.ward_code}>
                    {w.ward_code} · {w.ward_name}
                  </option>
                ))}
              </select>
              <span className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-ink/60">
                <Icon d="M3.5 6 8 10.5 12.5 6" size={14} />
              </span>
            </span>
          </label>
        </div>
        {locState === "denied" && <p className="mt-3 text-sm text-amber-200">{t("home.locationDenied")}</p>}
      </section>

      {near && (
        <section className="mt-8" aria-live="polite">
          <h2 className="h2 !mt-0">{t("home.nearTitle")}</h2>
          <p className="mb-3 text-sm text-ink/70">{t("home.nearHelp")}</p>
          {near.roads.length === 0 ? (
            <p className="card text-sm">{t("home.nearNone")}</p>
          ) : (
            <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {near.roads.map((r: any) => (
                <li key={r.road_id}>
                  <Link href={`/road/${r.road_id}`} className="card block hover:bg-ledger-100">
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

      <section className="mt-12">
        <h2 className="h2 !mt-0 !mb-5">{t("home.cityTitle")}</h2>
        {meta.loading && <Loading />}
        {meta.error && <ErrorBox error={meta.error} onRetry={meta.reload} />}
        {c && (
          <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-4">
            <Stat plain label={t("home.cityBudget")} value={"₹" + crore(c.budget_inr)} />
            <Stat plain label={t("home.citySpend")} value={"₹" + crore(c.spend_inr)} sub={`${c.jobs.toLocaleString("en-IN")} ${t("common.jobs")}`} />
            <Stat
              plain
              label={t("home.cityFailed")}
              value={"₹" + crore(c.failed_inr)}
              sub={`${c.failed_jobs.toLocaleString("en-IN")} ${t("common.jobs")}`}
            />
            <Stat plain label={t("home.cityNever")} value={c.never_fixed_issues.toLocaleString("en-IN")} />
          </div>
        )}
      </section>

      <section className="mt-12">
        <h2 className="h2 !mt-0 !mb-5">{t("home.explore")}</h2>
        <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
          {[
            ["/map", "home.linkMap"],
            ["/wards", "home.linkWards"],
            ["/contractors", "home.linkContractors"],
            ["/ask", "home.linkAsk"],
          ].map(([href, key]) => (
            <Link key={href} href={href} className="card flex min-h-[67px] items-center justify-between gap-3 px-5 py-4 text-[17px] font-medium hover:bg-ledger-100">
              {t(key)}
              <span className="text-ink/45">
                <Icon d="M3 8h10M9 4l4 4-4 4" />
              </span>
            </Link>
          ))}
        </div>
        <p className="mt-10 text-[15px] leading-relaxed text-ink/80">{t("home.about")}</p>
      </section>
    </div>
  );
}
