"use client";
import dynamic from "next/dynamic";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { api, useApi } from "@/lib/api";
import { dateOnly } from "@/lib/format";
import { useAuth } from "@/lib/auth";
import { useLang } from "@/lib/i18n";
import { Loading, PageTitle } from "@/components/Ui";
import { NeedLogin, TicketStatus, UpvoteButton } from "@/components/live/bits";
import type { Pt } from "@/components/live/LocationPicker";

const LocationPicker = dynamic(() => import("@/components/live/LocationPicker"), { ssr: false, loading: () => <Loading /> });

type Pick = { file: File; url: string; kind: "photo" | "video" };
const PHOTO = ["image/jpeg", "image/png", "image/webp"];
const VIDEO = ["video/mp4", "video/quicktime", "video/webm"];

/** DFD 2.0 Raise Complaint: category, description, photos, videos, current location or pins, optional locality. */
export default function RaisePage() {
  const { t } = useLang();
  const { user, ready } = useAuth();
  if (!ready) return <Loading />;
  if (!user) return <NeedLogin role="citizen" next="/complaints/new" message={t("raise.needLogin")} />;
  if (user.role !== "citizen") return <p className="card mx-auto max-w-md text-sm">{t("raise.citizenOnly")}</p>;
  return <RaiseForm />;
}

function RaiseForm() {
  const { t } = useLang();
  const router = useRouter();
  const opts = useApi<any>("/live/options");
  const lim = opts.data?.limits;
  const [category, setCategory] = useState("");
  const [section, setSection] = useState("roads");
  const [supported, setSupported] = useState<string[]>([]);
  const [desc, setDesc] = useState("");
  const [locality, setLocality] = useState("");
  const [points, setPoints] = useState<Pt[]>([]);
  const [picks, setPicks] = useState<Pick[]>([]);
  const [geo, setGeo] = useState<"idle" | "busy" | "denied">("idle");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const cam = useRef<HTMLInputElement>(null);
  const gal = useRef<HTMLInputElement>(null);
  const picksRef = useRef(picks);
  picksRef.current = picks;
  useEffect(() => () => picksRef.current.forEach((p) => URL.revokeObjectURL(p.url)), []);

  // Complaints already raised close to the first pin: support one instead of filing a duplicate.
  const first = points[0];
  const near = useApi<any>(first ? `/tickets/nearby?lat=${first.lat}&lon=${first.lon}${category ? `&category=${encodeURIComponent(category)}` : ""}` : null);
  const similar: any[] = first ? near.data?.items || [] : [];
  const maxLoc = lim?.locations ?? 5;
  const addPoint = (p: Pt) => setPoints((ps) => (ps.length >= maxLoc ? ps : [...ps, p]));
  const useGps = () => {
    if (!navigator.geolocation) return setGeo("denied");
    setGeo("busy");
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        addPoint({ lat: pos.coords.latitude, lon: pos.coords.longitude, accuracy_m: Math.round(pos.coords.accuracy), source: "gps" });
        setGeo("idle");
      },
      () => setGeo("denied"),
      { enableHighAccuracy: true, timeout: 15000 },
    );
  };

  const addFiles = (list: FileList | null) => {
    if (!list) return;
    setErr(null);
    const next = [...picks];
    for (const f of Array.from(list)) {
      const kind = PHOTO.includes(f.type) ? "photo" : VIDEO.includes(f.type) ? "video" : null;
      if (!kind) {
        setErr(t("raise.badType", { name: f.name }));
        continue;
      }
      const maxMb = kind === "photo" ? lim?.photo_mb ?? 10 : lim?.video_mb ?? 50;
      if (f.size > maxMb * 1024 * 1024) {
        setErr(t("raise.tooBig", { name: f.name, mb: maxMb }));
        continue;
      }
      const count = next.filter((p) => p.kind === kind).length;
      if (count >= (kind === "photo" ? lim?.photos ?? 6 : lim?.videos ?? 2)) {
        setErr(t("raise.tooMany", { photos: lim?.photos ?? 6, videos: lim?.videos ?? 2 }));
        continue;
      }
      next.push({ file: f, url: URL.createObjectURL(f), kind });
    }
    setPicks(next);
  };
  const removePick = (i: number) => {
    URL.revokeObjectURL(picks[i].url);
    setPicks(picks.filter((_, j) => j !== i));
  };

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setErr(null);
    if (!category) return setErr(t("raise.pickCategory"));
    if (desc.trim().length < (lim?.description?.[0] ?? 10)) return setErr(t("raise.describe"));
    if (!points.length && !locality.trim()) return setErr(t("raise.needLocation"));
    const form = new FormData();
    form.append("category", category);
    form.append("section", section);
    form.append("description", desc.trim());
    if (locality.trim()) form.append("locality_text", locality.trim());
    form.append("locations", JSON.stringify(points));
    picks.forEach((p) => form.append("files", p.file, p.file.name));
    setBusy(true);
    try {
      const r = await api<any>("/tickets", { form });
      router.push(`/ticket/${r.ticket_id}?new=1`);
    } catch (e: any) {
      setErr(e?.message || t("common.error"));
      setBusy(false);
    }
  };

  return (
    <form onSubmit={submit} className="mx-auto max-w-3xl space-y-4">
      <PageTitle sub={t("raise.sub")}>{t("raise.title")}</PageTitle>

      <section className="card space-y-2">
        <label className="block text-sm">
          <span className="font-semibold">{t("raise.category")}</span>
          <select value={category} onChange={(e) => setCategory(e.target.value)} required className="mt-1 min-h-[44px] w-full rounded-md border border-ledger-200 bg-white px-2">
            <option value="">{t("raise.choose")}</option>
            {(opts.data?.categories || []).map((c: string) => (
              <option key={c} value={c}>
                {t("cat." + c)}
              </option>
            ))}
          </select>
        </label>
        <label className="block text-sm">
          <span className="font-semibold">{t("raise.section")}</span>
          <select value={section} onChange={(e) => setSection(e.target.value)} className="mt-1 min-h-[44px] w-full rounded-md border border-ledger-200 bg-white px-2">
            {(opts.data?.sections || ["roads"]).map((c: string) => (
              <option key={c} value={c}>
                {t("section." + c)}
              </option>
            ))}
          </select>
          <span className="text-xs text-ink/60">{t("raise.sectionHelp")}</span>
        </label>
        <label className="block text-sm">
          <span className="font-semibold">{t("raise.description")}</span>
          <textarea
            value={desc}
            onChange={(e) => setDesc(e.target.value)}
            rows={4}
            maxLength={lim?.description?.[1] ?? 2000}
            placeholder={t("raise.descPlaceholder")}
            className="mt-1 w-full rounded-md border border-ledger-200 p-2"
          />
          <span className="text-xs text-ink/60">
            {t("raise.descHelp")} ({desc.length}/{lim?.description?.[1] ?? 2000})
          </span>
        </label>
      </section>

      <section className="card space-y-2">
        <h2 className="text-sm font-bold">{t("raise.where")}</h2>
        <div className="flex flex-wrap items-center gap-2">
          <button type="button" className="btn btn-primary" onClick={useGps} disabled={geo === "busy" || points.length >= maxLoc}>
            {geo === "busy" ? t("home.locating") : t("raise.useGps")}
          </button>
          <span className="text-xs text-ink/70">{t("raise.tapMap", { n: maxLoc })}</span>
        </div>
        {geo === "denied" && <p className="text-xs text-amber-800">{t("raise.gpsDenied")}</p>}
        <LocationPicker points={points} onAdd={addPoint} />
        {points.length > 0 && (
          <ul className="space-y-1 text-xs">
            {points.map((p, i) => (
              <li key={i} className="flex items-center gap-2">
                <span className="font-mono">
                  {i + 1}. {p.lat.toFixed(5)}, {p.lon.toFixed(5)}
                </span>
                <span className="text-ink/60">{p.source === "gps" ? t("raise.gpsPoint", { m: p.accuracy_m ?? "?" }) : t("raise.mapPoint")}</span>
                <button type="button" className="underline" onClick={() => setPoints(points.filter((_, j) => j !== i))}>
                  {t("raise.remove")}
                </button>
              </li>
            ))}
          </ul>
        )}
        <label className="block text-sm">
          <span className="font-semibold">{t("raise.locality")}</span>
          <input value={locality} onChange={(e) => setLocality(e.target.value)} maxLength={120} placeholder={t("raise.localityPlaceholder")} className="mt-1 min-h-[44px] w-full rounded-md border border-ledger-200 px-3" />
        </label>
      </section>

      {similar.length > 0 && (
        <section className="card space-y-2 border-amber-300 bg-amber-50/60" aria-live="polite">
          <h2 className="text-sm font-bold">{t("raise.similarTitle")}</h2>
          <p className="text-xs text-ink/70">{t("raise.similarHelp")}</p>
          <ul className="space-y-2">
            {similar.map((x: any) => (
              <li key={x.ticket_id} className="rounded border border-ledger-200 bg-white p-2">
                <div className="flex flex-wrap items-center gap-2 text-sm">
                  <a href={`/ticket/${x.ticket_id}`} target="_blank" rel="noreferrer" className="font-mono text-xs underline">
                    {x.ticket_id}
                  </a>
                  <TicketStatus status={x.status} />
                  <span className="text-xs text-ink/60">{t("raise.similarAway", { m: x.distance_m })}</span>
                </div>
                <div className="mb-1 text-xs text-ink/70">
                  {t("cat." + x.category)}
                  {x.road_name ? ` · ${x.road_name}` : x.locality_text ? ` · ${x.locality_text}` : ""} · {dateOnly(x.created_at)}
                </div>
                <UpvoteButton
                  id={x.ticket_id}
                  count={x.upvotes}
                  supported={x.upvoted_by_me}
                  mine={x.is_mine}
                  status={x.status}
                  onChange={(s) => setSupported((p) => (s ? [...new Set([...p, x.ticket_id])] : p.filter((i) => i !== x.ticket_id)))}
                />
              </li>
            ))}
          </ul>
          {supported.length > 0 ? (
            <p className="text-xs font-semibold text-emerald-900">{t("upvote.done")} ({supported.join(", ")})</p>
          ) : (
            <p className="text-xs text-ink/60">{t("raise.similarNone")} ↓</p>
          )}
        </section>
      )}

      <section className="card space-y-2">
        <h2 className="text-sm font-bold">{t("raise.media")}</h2>
        <div className="flex flex-wrap gap-2">
          <button type="button" className="btn btn-ghost" onClick={() => cam.current?.click()}>
            {t("raise.camera")}
          </button>
          <button type="button" className="btn btn-ghost" onClick={() => gal.current?.click()}>
            {t("raise.gallery")}
          </button>
          <input ref={cam} type="file" accept="image/*,video/*" capture="environment" hidden onChange={(e) => (addFiles(e.target.files), (e.target.value = ""))} />
          <input ref={gal} type="file" accept={[...PHOTO, ...VIDEO].join(",")} multiple hidden onChange={(e) => (addFiles(e.target.files), (e.target.value = ""))} />
        </div>
        <p className="text-xs text-ink/60">{t("raise.mediaLimits", { photos: lim?.photos ?? 6, videos: lim?.videos ?? 2, pmb: lim?.photo_mb ?? 10, vmb: lim?.video_mb ?? 50 })}</p>
        {picks.length > 0 && (
          <ul className="flex flex-wrap gap-2">
            {picks.map((p, i) => (
              <li key={p.url} className="relative">
                {p.kind === "photo" ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img src={p.url} alt={p.file.name} className="h-24 w-32 rounded border border-ledger-200 object-cover" />
                ) : (
                  <video src={p.url} className="h-24 w-32 rounded border border-ledger-200 bg-black" muted />
                )}
                <button type="button" onClick={() => removePick(i)} className="absolute right-1 top-1 rounded bg-white/90 px-1.5 text-xs" aria-label={t("raise.remove")}>
                  ✕
                </button>
              </li>
            ))}
          </ul>
        )}
        <p className="text-xs text-ink/70">{t("raise.photoNote")}</p>
      </section>

      {err && (
        <p role="alert" className="rounded border border-red-200 bg-red-50 p-2 text-sm text-red-900">
          {err}
        </p>
      )}
      <button className="btn btn-primary w-full sm:w-auto" disabled={busy}>
        {busy ? t("raise.sending") : t("raise.submit")}
      </button>
      <p className="text-xs text-ink/60">{t("raise.privacy")}</p>
    </form>
  );
}
