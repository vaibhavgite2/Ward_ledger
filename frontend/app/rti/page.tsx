"use client";
import { useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import { api } from "@/lib/api";
import { useLang } from "@/lib/i18n";
import { ErrorBox, Loading, PageTitle } from "@/components/Ui";

const RE_COMPLAINT = /^BMC\d{2}-\d{6}$/i;
const RE_WO = /^WO\d{2}-\d{5}$/i;
const RE_ROAD = /^RD\d{4}$/i;

type Draft = {
  text_en: string;
  text_mr: string;
  pio: { office: string; note: string };
  fee_inr: number;
  due_date_if_filed_today: string;
  disclaimer: Record<string, string>;
  demo_notice: string;
};

function RtiInner() {
  const { t, lang } = useLang();
  const sp = useSearchParams();
  const initial = sp.get("work_order_id") || sp.get("complaint_id") || sp.get("road_id") || "";
  const [ref, setRef] = useState(initial);
  const [draft, setDraft] = useState<Draft | null>(null);
  const [tab, setTab] = useState<"mr" | "en">(lang === "en" ? "en" : "mr");
  const [err, setErr] = useState<Error | null>(null);
  const [notFound, setNotFound] = useState(false);
  const [busy, setBusy] = useState(false);
  const [copied, setCopied] = useState(false);
  const ran = useRef<string | null>(null);

  // The saved language loads after first render, and the user can switch it at any time:
  // keep the visible RTI language in step with the UI language (Hindi readers get Marathi).
  useEffect(() => {
    setTab(lang === "en" ? "en" : "mr");
  }, [lang]);

  const generate = useCallback(async (value: string) => {
    const v = value.trim().toUpperCase();
    const body: Record<string, string> = RE_COMPLAINT.test(v) ? { complaint_id: v } : RE_WO.test(v) ? { work_order_id: v } : RE_ROAD.test(v) ? { road_id: v } : {};
    if (!Object.keys(body).length) {
      setNotFound(true);
      setDraft(null);
      return;
    }
    setBusy(true);
    setErr(null);
    setNotFound(false);
    try {
      setDraft(await api<Draft>("/rti-draft", { method: "POST", body }));
    } catch (e: any) {
      if (e?.status === 404) setNotFound(true);
      else setErr(e);
      setDraft(null);
    } finally {
      setBusy(false);
    }
  }, []);

  useEffect(() => {
    if (initial && ran.current !== initial) {
      ran.current = initial;
      generate(initial);
    }
  }, [initial, generate]);

  const submit = (e: FormEvent) => {
    e.preventDefault();
    generate(ref);
  };
  const text = draft ? (tab === "mr" ? draft.text_mr : draft.text_en) : "";
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {}
  };

  return (
    <div className="mx-auto max-w-3xl">
      <PageTitle sub={t("rti.help")}>{t("rti.title")}</PageTitle>
      <form onSubmit={submit} className="flex flex-col gap-2 no-print sm:flex-row">
        <label className="flex-1">
          <span className="sr-only">{t("rti.enter")}</span>
          <input
            value={ref}
            onChange={(e) => setRef(e.target.value)}
            placeholder={t("rti.enter")}
            className="min-h-[48px] w-full rounded-md border border-ledger-200 bg-white px-3 font-mono text-sm"
          />
        </label>
        <button className="btn btn-primary" disabled={busy}>
          {t("rti.generate")}
        </button>
      </form>
      {busy && <Loading />}
      {notFound && <p className="card mt-3 text-sm">{t("rti.notFound")}</p>}
      {err && <div className="mt-3"><ErrorBox error={err} /></div>}
      {draft && (
        <>
          <div className="card mt-4 text-sm no-print">
            <ul className="space-y-0.5">
              <li>{t("rti.pio", { x: draft.pio.office })}</li>
              <li>{t("rti.fee", { n: draft.fee_inr })}</li>
              <li>{t("rti.due", { date: draft.due_date_if_filed_today })}</li>
              <li>{t("rti.appeal")}</li>
            </ul>
            <p className="mt-2 text-xs text-ink/70">{draft.disclaimer[lang] || draft.disclaimer.en}</p>
            <p className="mt-1 text-xs text-ink/60">{t("rti.lawful")}</p>
          </div>
          <div className="mt-3 flex flex-wrap gap-2 no-print" role="tablist">
            {(["mr", "en"] as const).map((l) => (
              <button
                key={l}
                role="tab"
                aria-selected={tab === l}
                onClick={() => setTab(l)}
                className={`btn ${tab === l ? "btn-primary" : "btn-ghost"}`}
              >
                {t(l === "mr" ? "rti.marathi" : "rti.english")}
              </button>
            ))}
            <button className="btn btn-ghost" onClick={copy}>
              {copied ? t("common.copied") : t("rti.copy")}
            </button>
            <button className="btn btn-ghost" onClick={() => window.print()}>
              {t("common.print")}
            </button>
          </div>
          <article lang={tab} className="mt-2 whitespace-pre-wrap rounded-lg border border-ledger-200 bg-white p-5 font-serif text-[15px] leading-7 shadow-sm">
            {text}
          </article>
          <p className="mt-2 text-xs text-amber-800">{draft.demo_notice}</p>
        </>
      )}
    </div>
  );
}

export default function RtiPage() {
  return (
    <Suspense fallback={<Loading />}>
      <RtiInner />
    </Suspense>
  );
}
