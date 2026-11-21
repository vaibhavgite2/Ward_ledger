"use client";
import { Fragment, useState } from "react";
import { API, api, useApi } from "@/lib/api";
import { useLang } from "@/lib/i18n";
import { getToken, useAuth } from "@/lib/auth";
import { NeedLogin } from "@/components/live/bits";
import { ErrorBox, Loading } from "@/components/Ui";

const LIMIT = 100;
type Filters = { ward: string; contractor: string; from: string; to: string; field: string; subject: string };
const EMPTY: Filters = { ward: "", contractor: "", from: "", to: "", field: "", subject: "" };

type Row = {
  seq: number;
  ts: string;
  subject_type: string;
  subject_id: string;
  field_path: string;
  value: unknown;
  actor: string;
  fact_id: string;
  from_claim: string | null;
  supersedes: string | null;
  superseded_by: string | null;
  superseded_note: string | null;
  row_hash: string;
  source_file: string | null;
  source_doc: string | null;
  source_row: number | null;
  extractor: string | null;
  prompt_hash: string | null;
  confidence: number | null;
};

function qs(f: Filters, extra: Record<string, string | number> = {}) {
  const p = new URLSearchParams();
  for (const [k, v] of Object.entries(f)) if (v) p.set(k, v);
  for (const [k, v] of Object.entries(extra)) p.set(k, String(v));
  return p.toString();
}

const fmt = (v: unknown) => {
  const s = typeof v === "string" ? v : JSON.stringify(v);
  return s.length > 60 ? s.slice(0, 57) + "..." : s;
};

/** Inline chain for one work order: every fact, the claims behind them, per-row hash check. */
function Chain({ id, onClose }: { id: string; onClose: () => void }) {
  const { t } = useLang();
  const { data, error, loading } = useApi<any>(`/audit/${id}/chain`);
  return (
    <div className="border-l-2 border-black pl-2 text-[11px]">
      <div className="flex gap-3">
        <b>{t("audit.chain.title", { id })}</b>
        <button type="button" onClick={onClose} className="underline">
          [{t("audit.chain.close")}]
        </button>
      </div>
      {loading && <Loading />}
      {error && <ErrorBox error={error} />}
      {data && (
        <>
          <div>
            {data.all_hashes_ok ? t("audit.chain.allOk") : t("audit.chain.someBad")} · {data.claims.length} {t("audit.chain.claims")} ·{" "}
            {data.findings.length} {t("audit.chain.findings")}
          </div>
          <table className="mt-1 w-full whitespace-nowrap">
            <tbody>
              {data.facts.map((f: any) => (
                <tr key={f.fact_id} className="border-t border-gray-300">
                  <td className="pr-2">{f.seq}</td>
                  <td className="pr-2">{f.subject_type}:{f.subject_id}</td>
                  <td className="pr-2">{f.field_path}</td>
                  <td className="pr-2">{fmt(f.value)}</td>
                  <td className="pr-2">{f.actor}</td>
                  <td className="pr-2">{f.row_hash.slice(0, 12)}</td>
                  <td className={f.row_hash_ok ? "" : "font-bold"}>{f.row_hash_ok ? "[ok] " + t("audit.chain.hashOk") : "[!!] " + t("audit.chain.hashBad")}</td>
                  {f.superseded_note && <td className="pl-2">{f.superseded_note}</td>}
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}
    </div>
  );
}

function ActionLog() {
  const { t } = useLang();
  const { data, error, loading } = useApi<{ items: any[] }>("/audit/log/actions?limit=50");
  return (
    <div className="mt-2 text-[11px]">
      <b>{t("audit.actions.title")}</b>
      {loading && <Loading />}
      {error && <ErrorBox error={error} />}
      {data && (
        <pre className="mt-1 overflow-x-auto whitespace-pre">
          {data.items.map((a) => `${a.seq}  ${a.ts}  ${a.actor}  ${a.action}  ${a.object_type}:${a.object_id}  ${a.detail_json}`).join("\n")}
        </pre>
      )}
    </div>
  );
}

/** The complaint/task tracking log (ticket_event): same rules as the fact log, raw rows only. */
function LiveLog() {
  const { t } = useLang();
  const [open, setOpen] = useState(false);
  const [entity, setEntity] = useState("");
  const [applied, setApplied] = useState("");
  const [v, setV] = useState<string | null>(null);
  const { data } = useApi<{ total: number; items: any[] }>(open ? `/audit/live?limit=200${applied ? `&entity=${encodeURIComponent(applied)}` : ""}` : null);
  const verify = async () => {
    const r = await api<any>("/audit/live/verify");
    setV(r.ok ? t("audit.verifyOk", { n: r.checked, h: (r.head_hash || "").slice(0, 16) }) : t("audit.verifyBroken", { s: r.first_broken_seq, n: r.checked }));
  };
  return (
    <div className="mb-3 border border-gray-400 p-1.5">
      <button type="button" className="font-bold underline" onClick={() => setOpen(!open)} aria-expanded={open}>
        {t("audit.liveTitle")}
      </button>
      {open && (
        <div className="mt-1">
          <p className="mb-1">{t("audit.liveSub")}</p>
          <div className="mb-1 flex flex-wrap gap-2">
            <input value={entity} onChange={(e) => setEntity(e.target.value)} placeholder="CMP-000001 / TSK-000001" className="border border-gray-400 bg-white px-1 py-0.5 font-mono text-[11px]" />
            <button type="button" className="border border-black px-2" onClick={() => setApplied(entity.trim())}>
              {t("audit.apply")}
            </button>
            <button type="button" className="border border-black px-2" onClick={verify}>
              {t("audit.verify")}
            </button>
            {v && <span>{v}</span>}
          </div>
          {data && (
            <pre className="overflow-x-auto whitespace-pre">
              {data.items
                .map((r) => `${r.seq}  ${r.at}  ${r.entity_type}:${r.entity_id}  ${r.event}  ${r.from_status ?? "-"} -> ${r.to_status ?? "-"}  ${r.actor_id}  ${r.row_hash.slice(0, 12)}`)
                .join("\n")}
            </pre>
          )}
        </div>
      )}
    </div>
  );
}

export default function AuditPage() {
  const { t } = useLang();
  const { user, ready } = useAuth();
  const ok = user?.role === "officer";
  const [draft, setDraft] = useState<Filters>(EMPTY);
  const [applied, setApplied] = useState<Filters>(EMPTY);
  const [offset, setOffset] = useState(0);
  const [chainFor, setChainFor] = useState<string | null>(null);
  const [verify, setVerify] = useState<string | null>(null);
  const [verifyBad, setVerifyBad] = useState(false);
  const [exportMsg, setExportMsg] = useState<string | null>(null);
  const [showActions, setShowActions] = useState(false);
  const [busy, setBusy] = useState(false);

  const { data, error, loading, reload } = useApi<{ total: number; offset: number; items: Row[] }>(
    ok ? `/audit?${qs(applied, { limit: LIMIT, offset })}` : null
  );

  if (!ready) return <Loading />;
  if (!ok) return <NeedLogin role="officer" next="/audit" message={t("audit.needLogin")} />;

  const doVerify = async () => {
    setBusy(true);
    setVerify(t("audit.verifying"));
    try {
      const v = await api<any>("/audit/verify");
      setVerifyBad(!v.ok);
      setVerify(
        v.ok
          ? t("audit.verifyOk", { n: v.checked, h: (v.head_hash || "").slice(0, 16) })
          : t("audit.verifyBroken", { s: v.first_broken_seq, n: v.checked })
      );
    } catch (e) {
      setVerifyBad(true);
      setVerify((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const doExport = async () => {
    setExportMsg(null);
    try {
      const params = new URLSearchParams({ format: "csv" });
      for (const [k, v] of Object.entries(applied)) if (v && ["ward", "contractor", "from", "to", "field"].includes(k)) params.set(k, v);
      const res = await fetch(`${API}/audit/export?${params}`, { headers: { Authorization: `Bearer ${getToken()}` } });
      if (!res.ok) throw new Error(res.statusText);
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "ward-ledger-audit.csv";
      a.click();
      URL.revokeObjectURL(url);
      setExportMsg(t("audit.exported", { n: res.headers.get("X-Rows") ?? "?", ok: res.headers.get("X-Chain-OK") ?? "?" }));
    } catch (e) {
      setExportMsg((e as Error).message);
    }
  };

  const total = data?.total ?? 0;
  const from = total === 0 ? 0 : offset + 1;
  const to = Math.min(total, offset + LIMIT);
  const input = "border border-gray-400 bg-white px-1 py-0.5 font-mono text-[11px]";

  return (
    <div className="font-mono text-[11px] leading-snug">
      <h1 className="text-base font-bold">{t("audit.title")}</h1>
      <p className="mb-2 max-w-3xl">{t("audit.sub")}</p>
      <LiveLog />

      <form
        className="mb-2 flex flex-wrap items-end gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          setOffset(0);
          setApplied(draft);
        }}
      >
        {(Object.keys(EMPTY) as (keyof Filters)[]).map((k) => (
          <label key={k} className="flex flex-col">
            {t("audit.f." + k)}
            <input
              type={k === "from" || k === "to" ? "date" : "text"}
              value={draft[k]}
              onChange={(e) => setDraft({ ...draft, [k]: e.target.value })}
              className={input + " w-28"}
              placeholder={k === "ward" ? "K/E" : k === "field" ? "cost_inr" : k === "subject" ? "WO25-00017" : ""}
            />
          </label>
        ))}
        <button type="submit" className="border border-black px-2 py-0.5">
          [{t("audit.apply")}]
        </button>
        <button
          type="button"
          className="border border-gray-400 px-2 py-0.5"
          onClick={() => {
            setDraft(EMPTY);
            setApplied(EMPTY);
            setOffset(0);
          }}
        >
          [{t("audit.reset")}]
        </button>
      </form>

      <div className="mb-2 flex flex-wrap items-center gap-3 border-y border-gray-400 py-1">
        <button type="button" disabled={busy} onClick={doVerify} className="border border-black px-2 py-0.5">
          [{t("audit.verify")}]
        </button>
        {verify && <span className={verifyBad ? "font-bold" : ""}>{verify}</span>}
        <button type="button" onClick={doExport} className="border border-black px-2 py-0.5">
          [{t("audit.export")}]
        </button>
        {exportMsg && <span>{exportMsg}</span>}
        <button type="button" onClick={() => setShowActions((v) => !v)} className="underline">
          [{showActions ? t("audit.actions.hide") : t("audit.actions.show")}]
        </button>
      </div>
      {showActions && <ActionLog />}

      {loading && !data && <Loading />}
      {error && <ErrorBox error={error} onRetry={reload} />}

      {data && (
        <>
          <div className="mb-1 flex items-center gap-3">
            <span>{t("audit.total", { n: total, a: from, b: to })}</span>
            <button type="button" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - LIMIT))} className="underline disabled:opacity-40">
              [{t("audit.prev")}]
            </button>
            <button type="button" disabled={offset + LIMIT >= total} onClick={() => setOffset(offset + LIMIT)} className="underline disabled:opacity-40">
              [{t("audit.next")}]
            </button>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full whitespace-nowrap text-left">
              <thead>
                <tr className="border-b border-black">
                  <th className="pr-3">{t("audit.col.seq")}</th>
                  <th className="pr-3">{t("audit.col.time")}</th>
                  <th className="pr-3">{t("audit.col.subject")}</th>
                  <th className="pr-3">{t("audit.col.field")}</th>
                  <th className="pr-3">{t("audit.col.value")}</th>
                  <th className="pr-3">{t("audit.col.source")}</th>
                  <th className="pr-3">{t("audit.col.extractor")}</th>
                  <th className="pr-3">{t("audit.col.promoted")}</th>
                  <th>{t("audit.col.hash")}</th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((r, idx) => (
                  <Fragment key={r.fact_id}>
                    <tr className="border-b border-gray-300 align-top">
                      <td className="pr-3">{r.seq}</td>
                      <td className="pr-3">{r.ts}</td>
                      <td className="pr-3">
                        {r.subject_type === "work_order" ? (
                          <button type="button" className="underline" onClick={() => setChainFor(chainFor === r.subject_id ? null : r.subject_id)}>
                            {r.subject_type}:{r.subject_id}
                          </button>
                        ) : (
                          <>
                            {r.subject_type}:{r.subject_id}
                          </>
                        )}
                      </td>
                      <td className="pr-3">{r.field_path}</td>
                      <td className="pr-3">
                        {fmt(r.value)}
                        {r.superseded_note && <span className="ml-1 font-bold">{r.superseded_note}</span>}
                      </td>
                      <td className="pr-3">
                        {r.source_file}
                        {r.source_row ? ` row ${r.source_row}` : ""} {(r.source_doc || "").slice(0, 8)}
                      </td>
                      <td className="pr-3">{r.extractor ? `${r.extractor} ${(r.prompt_hash || "-").slice(0, 8)} ${r.confidence ?? ""}` : "-"}</td>
                      <td className="pr-3">{r.actor}</td>
                      <td>{r.row_hash.slice(0, 12)}</td>
                    </tr>
                    {chainFor === r.subject_id && r.subject_type === "work_order" && idx === data.items.findIndex((x) => x.subject_id === chainFor) && (
                      <tr>
                        <td colSpan={9} className="py-1">
                          <Chain id={r.subject_id} onClose={() => setChainFor(null)} />
                        </td>
                      </tr>
                    )}
                  </Fragment>
                ))}
                {data.items.length === 0 && (
                  <tr>
                    <td colSpan={9}>{t("audit.empty")}</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}
