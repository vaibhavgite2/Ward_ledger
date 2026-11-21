"use client";
import "leaflet/dist/leaflet.css";
import { Fragment, useEffect } from "react";
import { Circle, CircleMarker, MapContainer, TileLayer, Tooltip, useMap, useMapEvents } from "react-leaflet";

export type Pt = { lat: number; lon: number; accuracy_m?: number | null; source: "gps" | "map" };

function Clicker({ onAdd }: { onAdd: (p: Pt) => void }) {
  useMapEvents({ click: (e) => onAdd({ lat: e.latlng.lat, lon: e.latlng.lng, accuracy_m: null, source: "map" }) });
  return null;
}

function FollowLast({ p }: { p?: Pt }) {
  const map = useMap();
  useEffect(() => {
    if (p) map.setView([p.lat, p.lon], Math.max(map.getZoom(), 16));
  }, [p, map]);
  return null;
}

/** Tap the map to drop pins (several for a stretch of road); GPS points also draw their accuracy circle.
 *  Read-only when onAdd is omitted. */
export default function LocationPicker({ points, onAdd, height = 300 }: { points: Pt[]; onAdd?: (p: Pt) => void; height?: number }) {
  const last = points[points.length - 1];
  return (
    <MapContainer
      center={last ? [last.lat, last.lon] : [19.07, 72.88]}
      zoom={last ? 16 : 11}
      style={{ height, width: "100%" }}
      className="rounded-lg border border-ledger-200"
    >
      <TileLayer attribution="&copy; OpenStreetMap contributors" url="https://tile.openstreetmap.org/{z}/{x}/{y}.png" />
      {onAdd && <Clicker onAdd={onAdd} />}
      {points.map((p, i) => (
        <Fragment key={`${p.lat},${p.lon},${i}`}>
          {p.accuracy_m ? <Circle center={[p.lat, p.lon]} radius={p.accuracy_m} pathOptions={{ color: "#2563eb", weight: 1, fillOpacity: 0.08 }} /> : null}
          <CircleMarker center={[p.lat, p.lon]} radius={9} pathOptions={{ color: "#7c2d12", fillColor: "#f59e0b", fillOpacity: 0.9, weight: 2 }}>
            <Tooltip permanent direction="top" offset={[0, -8]}>
              {i + 1}
            </Tooltip>
          </CircleMarker>
        </Fragment>
      ))}
      <FollowLast p={last} />
    </MapContainer>
  );
}
