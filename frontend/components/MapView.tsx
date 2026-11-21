"use client";
import "leaflet/dist/leaflet.css";
import L from "leaflet";
import { useEffect } from "react";
import { GeoJSON, MapContainer, TileLayer, useMap } from "react-leaflet";
import { roadColor, type RoadProps } from "@/lib/roadStyle";

function Fit({ roads, wards, ward }: { roads: any; wards: any; ward: string }) {
  const map = useMap();
  useEffect(() => {
    try {
      const src = roads?.features?.length ? roads : wards;     // fit to the data, not the wide ward polygons
      const b = L.geoJSON(src).getBounds();
      if (b.isValid()) map.fitBounds(b, { padding: [20, 20], maxZoom: 15 });
    } catch {}
  }, [roads, wards, ward, map]);
  return null;
}

export default function MapView({
  wards,
  roads,
  ward,
  onSelect,
  selected,
}: {
  wards: any;
  roads: any;
  ward: string;
  onSelect: (p: RoadProps) => void;
  selected?: string | null;
}) {
  return (
    <MapContainer center={[19.07, 72.88]} zoom={11} style={{ height: "62vh", minHeight: 360, width: "100%" }} className="rounded-lg border border-ledger-200">
      <TileLayer attribution="&copy; OpenStreetMap contributors" url="https://tile.openstreetmap.org/{z}/{x}/{y}.png" />
      {wards && (
        <GeoJSON
          key={"w" + ward}
          data={wards}
          style={(f) => ({
            color: "#7a6a3a",
            weight: f?.properties?.ward_code === ward ? 3 : 1,
            fillOpacity: f?.properties?.ward_code === ward ? 0.05 : 0.02,
            dashArray: "4 3",
          })}
          interactive={false}
        />
      )}
      {roads && (
        <GeoJSON
          key={"r" + ward + (selected || "")}
          data={roads}
          style={(f) => {
            const p = f?.properties as RoadProps;
            return {
              color: roadColor(p),
              weight: p.road_id === selected ? 9 : p.open_issues > 0 ? 6 : 4,
              opacity: 0.9,
              dashArray: p.under_dlp ? "8 5" : undefined,
            };
          }}
          onEachFeature={(f, layer) => {
            layer.on("click", () => onSelect(f.properties as RoadProps));
            layer.bindTooltip(`${f.properties.road_name} (${f.properties.road_id})`, { sticky: true });
          }}
        />
      )}
      <Fit roads={roads} wards={wards} ward={ward} />
    </MapContainer>
  );
}
