"use client";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import { api } from "@/lib/api";
import { useLang } from "@/lib/i18n";
import { ErrorBox, Loading, PageTitle } from "@/components/Ui";
import { Source } from "@/components/Source";

type Answer = {
  answer: string;
  lang: string;
  citations: any[];
  candidates: any[];
  rti_suggested: boolean;
  resolved?: { type?: string; id?: string };
  source?: string;
};

const EXAMPLES = ["BMC25-000037", "pothole near Andheri station", "माझ्या अंधेरीच्या तक्रारीचे काय झाले?", "Hindmata waterlogging"];

function AskInner() {
  const { t, lang } = useLang();
  const params = useSearchParams();
  const [q, setQ] = useState(params.get("q") || "");
  const [res, setRes] = useState<Answer | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<Error | null>(null);
  const ran = useRef<string | null>(null);

  const run = useCallback(
    async (text: string) => {
      if (!text.trim()) return;
      setBusy(true);
      setErr(null);
      try {
        setRes(await api<Answer>("/ask", { method: "POST", body: { question: text, lang } }));
      } catch (e) {
        setErr(e as Error);
      } finally {
        setBusy(false);
      }
    },
    [lang],
  );

  useEffect(() => {
    const initial = params.get("q");
    if (initial && ran.current !== initial) {
      ran.current = initial;
      run(initial);
    }
  }, [params, run]);

  const submit = (e: FormEvent) => {
    e.preventDefault();
    run(q);
  };

  const rtiHref = res?.resolved?.type === "complaint" ? `/rti?complaint_id=${res.resolved.id}` : res?.resolved?.type === "work" ? `/rti?work_order_id=${res.resolved.id}` : res?.resolved?.type === "road" ? `/rti?road_id=${res.resolved.id}` : "/rti";

  return (
    <div className="mx-auto max-w-2xl">
      <PageTitle sub={t("ask.sub")}>{t("ask.title")}</PageTitle>
      <form onSubmit={submit} className="flex flex-col gap-2 sm:flex-row">
        <label className="flex-1">
          <span className="sr-only">{t("ask.title")}</span>
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder={t("ask.placeholder")}
            maxLength={500}
            className="min-h-[48px] w-full rounded-md border border-ledger-200 bg-white px-3 text-base"
          />
        </label>
        <button className="btn btn-primary" type="submit" disabled={busy}>
          {t("ask.send")}
        </button>
      </form>
      <div className="mt-2 flex flex-wrap items-center gap-2 text-xs">
        <span className="text-ink/60">{t("ask.try")}:</span>
        {EXAMPLES.map((x) => (
          <button
            key={x}
            type="button"
            className="chip border-ledger-200 bg-white hover:bg-ledger-100"
            onClick={() => {
              setQ(x);
              run(x);
            }}
          >
            {x}
          </button>
        ))}
      </div>

      {busy && <p role="status" className="mt-4 text-sm text-ledger-700">{t("ask.thinking")}</p>}
      {err && <div className="mt-4"><ErrorBox error={err} /></div>}
      {res && !busy && (
        <section className="card mt-4" aria-live="polite">
          <p className="whitespace-pre-line text-base leading-relaxed">{res.answer}</p>
          {res.candidates.length > 0 && (
            <div className="mt-3">
              <p className="text-sm font-semibold">{t("ask.pick")}</p>
              <ul className="mt-1 space-y-1">
                {res.candidates.map((c: any) => (
                  <li key={c.complaint_id || c.road_id}>
                    <Link href={c.complaint_id ? `/complaint/${c.complaint_id}` : `/road/${c.road_id}`} className="card block text-sm hover:bg-ledger-50">
                      <span className="font-mono text-xs">{c.complaint_id || c.road_id}</span>
                      {c.category && <span> · {c.category}</span>}
                      {c.locality && <span> · {c.locality}</span>}
                      {c.received_at && <span className="text-ink/60"> · {c.received_at.slice(0, 10)}</span>}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          )}
          {res.citations.length > 0 && (
            <div className="mt-3 flex flex-wrap items-center gap-1 text-xs">
              <span className="text-ink/60">{t("ask.sources")}:</span>
              {res.citations.map((c, i) => (
                <Source key={i} ev={c} label={c.label} />
              ))}
            </div>
          )}
          <div className="mt-3 flex flex-wrap gap-2 no-print">
            {res.resolved?.type === "complaint" && (
              <Link href={`/complaint/${res.resolved.id}`} className="btn btn-ghost">
                {t("ask.openComplaint")}
              </Link>
            )}
            {res.resolved?.type === "road" && (
              <Link href={`/road/${res.resolved.id}`} className="btn btn-ghost">
                {t("ask.openRoad")}
              </Link>
            )}
            {res.rti_suggested && (
              <Link href={rtiHref} className="btn btn-primary">
                {t("ask.rti")}
              </Link>
            )}
          </div>
        </section>
      )}
      <p className="mt-4 text-xs text-ink/60">{t("ask.disclaimer")}</p>
    </div>
  );
}

export default function AskPage() {
  return (
    <Suspense fallback={<Loading />}>
      <AskInner />
    </Suspense>
  );
}
