"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useLang } from "@/lib/i18n";
import { ApiError } from "@/lib/api";
import { ErrorBox } from "@/components/Ui";

type Citation = { id: string; file: string; row?: number | null; sha256?: string | null; ref: string };
type Para = { n: number; kind: string; text: string; citations: Citation[] };
type Draft = { work_id: string; lang: string; title: string; paras: Para[]; blocked: any[]; submitted: boolean; demo_notice?: string };

type Rec = "" | "accept" | "conditional" | "refer";

/**
 * File-noting editor. The draft is fetched once per language and then lives only in this component:
 * the officer edits it here; nothing is ever posted back (SPEC 6.9: never stored, never auto-filed).
 */
export default function NotingEditor({ workId, onClose }: { workId: string; onClose: () => void }) {
  const { t, lang: uiLang } = useLang();
  const [lang, setLang] = useState<"mr" | "en">(uiLang === "en" ? "en" : "mr");
  const [draft, setDraft] = useState<Draft | null>(null);
  const [paras, setParas] = useState<Para[]>([]);
  const [rec, setRec] = useState<Rec>("");
  const [recNote, setRecNote] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    let live = true;
    setLoading(true);
    setError(null);
    api<Draft>(`/officer/draft-noting/${workId}?lang=${lang}`, { method: "POST" })
      .then((d) => {
        if (!live) return;
        setDraft(d);
        setParas(d.paras.map((p) => ({ ...p })));
        setRec("");
        setRecNote("");
      })
      .catch((e) => live && setError(e as ApiError))
      .finally(() => live && setLoading(false));
    return () => {
      live = false;
    };
  }, [workId, lang]);

  const recLabel = (r: Rec) => (r ? t("officer.noting.rec." + r) : "");
  const plain = () =>
    [
      draft?.title ?? "",
      ...paras.map((p) =>
        p.kind === "officer_input"
          ? `${p.n}. ${t("officer.noting.recLabel")}: ${recLabel(rec)}${recNote ? " - " + recNote : ""}`
          : `${p.n}. ${p.text}${p.citations.length ? "  " + p.citations.map((c) => c.ref).join(" ") : ""}`
      ),
    ].join("\n\n");

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(plain());
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {}
  };

  const update = (i: number, text: string) => setParas((ps) => ps.map((p, j) => (j === i ? { ...p, text } : p)));

  return (
    <section className="border border-ledger-200 bg-white p-3" aria-label={t("officer.noting.title")}>
      <style>{`@media print { body * { visibility: hidden; } #noting-print, #noting-print * { visibility: visible; } #noting-print { position: absolute; left: 0; top: 0; width: 100%; } }`}</style>
      <div className="flex flex-wrap items-center gap-2 print:hidden">
        <h2 className="text-base font-bold">
          {t("officer.noting.title")} · <span className="font-mono">{workId}</span>
        </h2>
        <div className="ml-auto flex flex-wrap gap-2">
          {(["mr", "en"] as const).map((l) => (
            <button
              key={l}
              type="button"
              onClick={() => setLang(l)}
              aria-pressed={lang === l}
              className={`btn !min-h-[36px] ${lang === l ? "btn-primary" : "btn-ghost"}`}
            >
              {t(l === "mr" ? "officer.noting.langMr" : "officer.noting.langEn")}
            </button>
          ))}
          <button type="button" onClick={copy} className="btn btn-ghost !min-h-[36px]" disabled={!draft}>
            {copied ? t("officer.noting.copied") : t("officer.noting.copy")}
          </button>
          <button type="button" onClick={() => window.print()} className="btn btn-ghost !min-h-[36px]" disabled={!draft}>
            {t("officer.noting.print")}
          </button>
          <button type="button" onClick={onClose} className="btn btn-ghost !min-h-[36px]">
            {t("officer.noting.close")}
          </button>
        </div>
      </div>
      <p className="mt-2 border-l-4 border-amber-400 bg-amber-50 px-2 py-1 text-sm font-semibold text-amber-900 print:hidden">
        {t("officer.noting.only")}
      </p>

      {loading && <p className="py-4 text-sm text-ledger-700">{t("officer.noting.generating")}</p>}
      {error && <ErrorBox error={error} />}

      {draft && !loading && (
        <>
          <ol className="mt-3 space-y-3 print:hidden">
            {paras.map((p, i) => (
              <li key={p.n}>
                <label className="block text-xs font-semibold text-ledger-700">{t("officer.noting.para", { n: p.n })}</label>
                {p.kind === "officer_input" ? (
                  <div className="space-y-1 border border-dashed border-ledger-600 p-2">
                    <div className="text-sm font-semibold">{t("officer.noting.recLabel")}</div>
                    <select
                      value={rec}
                      onChange={(e) => setRec(e.target.value as Rec)}
                      className="min-h-[40px] w-full rounded border border-ledger-200 bg-white px-2 text-sm"
                    >
                      <option value="">{t("officer.noting.rec.choose")}</option>
                      <option value="accept">{t("officer.noting.rec.accept")}</option>
                      <option value="conditional">{t("officer.noting.rec.conditional")}</option>
                      <option value="refer">{t("officer.noting.rec.refer")}</option>
                    </select>
                    <textarea
                      aria-label={t("officer.noting.recText")}
                      placeholder={t("officer.noting.recText")}
                      value={recNote}
                      onChange={(e) => setRecNote(e.target.value)}
                      rows={2}
                      className="w-full rounded border border-ledger-200 p-2 text-sm"
                    />
                  </div>
                ) : (
                  <>
                    <textarea
                      value={p.text}
                      onChange={(e) => update(i, e.target.value)}
                      rows={Math.max(2, Math.ceil(p.text.length / 90))}
                      className="w-full rounded border border-ledger-200 p-2 text-sm"
                    />
                    <div className="mt-0.5 flex flex-wrap gap-1">
                      {p.citations.map((c, k) => (
                        <span key={k} className="chip border-ledger-200 bg-ledger-50 font-mono text-[10px] text-ledger-700">
                          {c.ref}
                        </span>
                      ))}
                    </div>
                  </>
                )}
              </li>
            ))}
          </ol>

          {draft.blocked.length > 0 && (
            <div role="alert" className="mt-3 border border-red-300 bg-red-50 p-2 text-sm text-red-900 print:hidden">
              <div className="font-bold">{t("officer.noting.blockedTitle")}</div>
              <ul className="mt-1 list-disc pl-5">
                {draft.blocked.map((b, i) => (
                  <li key={i}>
                    {b.text} <span className="font-mono text-xs">({b.reason})</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* print copy: plain text, no form controls */}
          <div id="noting-print" className="hidden print:block">
            <h2 className="mb-2 text-base font-bold">{draft.title}</h2>
            {paras.map((p) => (
              <p key={p.n} className="mb-2 text-sm">
                {p.n}.{" "}
                {p.kind === "officer_input"
                  ? `${t("officer.noting.recLabel")}: ${recLabel(rec)}${recNote ? " - " + recNote : ""}`
                  : p.text}
                {p.citations.length > 0 && <span className="block font-mono text-[10px]">{p.citations.map((c) => c.ref).join(" ")}</span>}
              </p>
            ))}
            <p className="mt-4 text-xs">{t("officer.noting.only")}</p>
          </div>
        </>
      )}
    </section>
  );
}
