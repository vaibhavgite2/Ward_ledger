"use client";
import { useState } from "react";
import { api } from "@/lib/api";
import { useLang } from "@/lib/i18n";

export type Evidence = { table: string; id: string; row?: number | null; file: string; sha256?: string | null; note?: string | null };

/** Provenance chip: every number can show the source row it came from (SPEC section 8). */
export function Source({ ev, label }: { ev: Evidence; label?: string }) {
  const { t } = useLang();
  const [open, setOpen] = useState(false);
  const [data, setData] = useState<any>(null);
  const [err, setErr] = useState(false);
  const canFetch = !!ev.row;
  const toggle = async () => {
    setOpen(!open);
    if (!open && canFetch && !data) {
      try {
        setData(await api(`/source/${ev.file}/${ev.row}`));
      } catch {
        setErr(true);
      }
    }
  };
  return (
    <span className="inline-block align-baseline">
      <button
        type="button"
        onClick={toggle}
        aria-expanded={open}
        className="chip border-ledger-200 bg-ledger-50 font-mono text-[11px] text-ledger-700 hover:bg-ledger-100"
        title={t("source.title")}
      >
        {label || ev.id}
      </button>
      {open && (
        <div className="card mt-1 block max-w-full overflow-x-auto text-xs" role="dialog" aria-label={t("source.title")}>
          <div className="font-semibold">{t("source.title")}</div>
          <div className="mt-1 font-mono">
            {t("source.file")}: {ev.file}
            {ev.row ? (
              <>
                {" "}
                · {t("source.row")} {ev.row}
              </>
            ) : ev.note ? (
              <> · {ev.note}</>
            ) : null}
          </div>
          {(data?.sha256 || ev.sha256) && (
            <div className="mt-1 break-all font-mono text-[10px] text-ink/60">
              {t("source.hash")}: {data?.sha256 || ev.sha256}
            </div>
          )}
          {canFetch && data && (
            <table className="mt-2 w-full text-left font-mono text-[11px]">
              <tbody>
                {Object.entries(data.data)
                  .filter(([k]) => k !== "_row")
                  .map(([k, v]) => (
                    <tr key={k} className="border-t border-ledger-100">
                      <th className="pr-2 font-semibold text-ledger-700">{k}</th>
                      <td className="break-all">{String(v ?? "")}</td>
                    </tr>
                  ))}
              </tbody>
            </table>
          )}
          {canFetch && !data && !err && <div className="mt-1">{t("common.loading")}</div>}
          {err && <div className="mt-1 text-red-700">{t("common.error")}</div>}
          <div className="mt-1 text-[10px] text-ink/50">{t("source.note")}</div>
          <button type="button" onClick={() => setOpen(false)} className="mt-1 underline">
            {t("source.close")}
          </button>
        </div>
      )}
    </span>
  );
}

export function SourceList({ evidence, max = 6 }: { evidence: Evidence[]; max?: number }) {
  const { t } = useLang();
  return (
    <div className="mt-1 flex flex-wrap items-start gap-1 text-xs">
      <span className="text-ink/60">{t("finding.evidence")}:</span>
      {evidence.slice(0, max).map((e, i) => (
        <Source key={e.id + i} ev={e} />
      ))}
      {evidence.length > max && <span className="text-ink/60">+{evidence.length - max}</span>}
    </div>
  );
}
