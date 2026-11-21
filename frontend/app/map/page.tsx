"use client";
import dynamic from "next/dynamic";
import Link from "next/link";
import { useState } from "react";
import { useApi } from "@/lib/api";
import { useLang } from "@/lib/i18n";
import { rupee, wardSlug } from "@/lib/format";
import { ErrorBox, Loading, PageTitle } from "@/components/Ui";
import { ROAD_COLOR, type RoadProps } from "@/lib/roadStyle";

const MapView = dynamic(() => import("@/components/MapView"), {
  ssr: false,
  loading: () => <p className="py-10 text-center text-sm text-ledger-700">...</p>,
});

export default function MapPage() {
  const { t } = useLang();
  const [ward, setWard] = useState("");
  const [sel, setSel] = useState<RoadProps | null>(null);
  const wardsList = useApi<any[]>("/wards");
  const wardsGeo = useApi<any>("/wards/geojson");
  const roads = useApi<any>(`/roads/geojson${ward ? `?ward=${encodeURIComponent(ward)}` : ""}`);

  const legend: [string, string, string][] = [
    [ROAD_COLOR.held, "map.held", "solid"],
    [ROAD_COLOR.some, "map.some", "solid"],
    [ROAD_COLOR.often, "map.often", "solid"],
    [ROAD_COLOR.none, "map.noRepairs", "solid"],
  ];

  return (
    <div>
      <PageTitle sub={t("map.tap")}>{t("map.title")}</PageTitle>
      <div className="mb-2 flex flex-wrap items-center gap-3">
        <label className="flex items-center gap-2 text-sm">
          <span>{t("common.ward")}</span>
          <select
            className="min-h-[44px] rounded-md border border-ledger-200 bg-white px-2"
            value={ward}
            onChange={(e) => {
              setWard(e.target.value);
              setSel(null);
            }}
          >
            <option value="">{t("map.allWards")}</option>
            {(wardsList.data || []).map((w) => (
              <option key={w.ward_code} value={w.ward_code}>
                {w.ward_code} · {w.ward_name}
              </option>
            ))}
          </select>
        </label>
        <ul className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs" aria-label={t("map.legend")}>
          {legend.map(([c, k, style]) => (
            <li key={k} className="flex items-center gap-1">
              <span className="inline-block w-6" style={{ borderTop: `4px ${style} ${c}` }} aria-hidden />
              {t(k)}
            </li>
          ))}
          <li className="flex items-center gap-1">
            <span className="inline-block w-6" style={{ borderTop: "4px dashed #4b5563" }} aria-hidden />
            {t("map.warranty")}
          </li>
          <li className="flex items-center gap-1">
            <span className="inline-block w-6 border-t-[7px] border-gray-600" aria-hidden />
            {t("map.open")}
          </li>
        </ul>
      </div>
      {roads.error && <ErrorBox error={roads.error} onRetry={roads.reload} />}
      {(roads.loading || wardsGeo.loading) && !roads.data && <Loading />}
      {roads.data && wardsGeo.data && <MapView wards={wardsGeo.data} roads={roads.data} ward={ward} onSelect={setSel} selected={sel?.road_id} />}
      {sel && (
        <section className="card mt-2" aria-live="polite">
          <div className="flex flex-wrap items-baseline gap-x-3">
            <h2 className="font-bold">{sel.road_name}</h2>
            <span className="font-mono text-xs text-ink/60">
              {sel.road_id} · {t("common.ward")} {sel.ward_code}
            </span>
          </div>
          <p className="mt-1 text-sm">
            {sel.repairs} {t("common.jobs")} · {rupee(sel.spent)}
            {sel.failed > 0 && ` · ${sel.failed} ${t("road.failed")}`}
            {sel.under_dlp && ` · ${t("road.warranty")}`}
            {sel.open_issues > 0 && ` · ${sel.open_issues} ${t("road.openIssues")}`}
          </p>
          <div className="mt-2 flex gap-2">
            <Link href={`/road/${sel.road_id}`} className="btn btn-primary">
              {t("map.openRoad")}
            </Link>
            <Link href={`/ward/${wardSlug(sel.ward_code)}`} className="btn btn-ghost">
              {t("common.ward")} {sel.ward_code}
            </Link>
          </div>
        </section>
      )}
      <p className="mt-2 text-xs text-ink/60">{t("map.approx")}</p>
    </div>
  );
}
