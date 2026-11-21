"use client";
import { useState } from "react";
import { api, useApi } from "@/lib/api";
import { useLang } from "@/lib/i18n";
import { ErrorBox, Loading } from "@/components/Ui";

type Item = {
  item_id: string;
  reason: string;
  subject_id: string;
  field_path: string;
  value_json: string;
  extractor: string;
  confidence: number | null;
};

function show(v: string) {
  try {
    const o = JSON.parse(v);
    return typeof o === "object" && o !== null ? (o.category ?? JSON.stringify(o)) : String(o);
  } catch {
    return v;
  }
}

/** Human-in-the-loop queue: approving appends a fact signed by a named officer (SPEC 5). */
export default function ReviewQueue({ onChange }: { onChange?: () => void }) {
  const { t } = useLang();
  const { data, error, loading, reload } = useApi<{ total: number; items: Item[] }>("/officer/review-queue?status=pending&limit=10");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const [done, setDone] = useState(false);
  const [err, setErr] = useState<Error | null>(null);

  const decide = async (id: string, action: "approve" | "reject") => {
    setBusy(id);
    setErr(null);
    try {
      await api(`/officer/review/${id}`, { method: "POST", role: "officer", user: "ae-4471", body: { action, note: note || null } });
      setDone(true);
      setNote("");
      reload();
      onChange?.();
    } catch (e) {
      setErr(e as Error);
    } finally {
      setBusy(null);
    }
  };

  return (
    <section className="border border-ledger-200 bg-white p-3" aria-label={t("officer.review.title")}>
      <h2 className="text-base font-bold">
        {t("officer.review.title")} {data ? <span className="font-mono text-sm">({data.total})</span> : null}
      </h2>
      <p className="text-xs text-ink/70">{t("officer.review.help")}</p>
      <label className="mt-2 block text-xs">
        {t("officer.review.note")}
        <input value={note} onChange={(e) => setNote(e.target.value)} className="mt-0.5 w-full rounded border border-ledger-200 px-2 py-1 text-sm" />
      </label>
      {done && <p className="mt-1 text-xs font-semibold text-emerald-800">{t("officer.review.done")}</p>}
      {err && <ErrorBox error={err} />}
      {loading && <Loading />}
      {error && <ErrorBox error={error} onRetry={reload} />}
      {data && data.items.length === 0 && <p className="mt-2 text-sm">{t("officer.review.empty")}</p>}
      {data && data.items.length > 0 && (
        <div className="mt-2 overflow-x-auto">
          <table className="w-full min-w-[640px] text-left text-xs">
            <thead className="border-b border-ledger-200 text-ledger-700">
              <tr>
                <th className="py-1 pr-2">{t("officer.review.subject")}</th>
                <th className="pr-2">{t("officer.review.field")}</th>
                <th className="pr-2">{t("officer.review.value")}</th>
                <th className="pr-2">{t("officer.review.reason")}</th>
                <th className="pr-2">{t("officer.review.extractor")}</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {data.items.map((it) => (
                <tr key={it.item_id} className="border-b border-ledger-100 align-top">
                  <td className="py-1 pr-2 font-mono">{it.subject_id}</td>
                  <td className="pr-2 font-mono">{it.field_path}</td>
                  <td className="pr-2">{show(it.value_json)}</td>
                  <td className="pr-2">{it.reason}</td>
                  <td className="pr-2 font-mono text-[10px]">
                    {it.extractor}
                    {it.confidence !== null && it.confidence !== undefined ? ` · ${it.confidence}` : ""}
                  </td>
                  <td className="whitespace-nowrap">
                    <button disabled={busy === it.item_id} onClick={() => decide(it.item_id, "approve")} className="btn btn-primary !min-h-[32px] !px-2 text-xs">
                      {t("officer.review.approve")}
                    </button>{" "}
                    <button disabled={busy === it.item_id} onClick={() => decide(it.item_id, "reject")} className="btn btn-ghost !min-h-[32px] !px-2 text-xs">
                      {t("officer.review.reject")}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
