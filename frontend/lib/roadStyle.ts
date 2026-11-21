/** Road styling shared by the map page (legend) and MapView. Deliberately free of any leaflet import:
 *  leaflet touches `window` on load, so anything the server renders must not pull it in. */
export type RoadProps = {
  road_id: string;
  road_name: string;
  ward_code: string;
  repairs: number;
  failed: number;
  spent: number;
  under_dlp: boolean;
  open_issues: number;
};

/** Colour = how repairs on this road turned out (failure RATE, not "any failure": nearly every road has one).
 *  Dashes = under contractor warranty. Thickness = open issue. Colour-blind-safe, and always paired with a legend. */
export const ROAD_COLOR = { held: "#0f766e", some: "#d97706", often: "#b91c1c", none: "#9ca3af" };
export const OFTEN_FAILED_AT = 0.4;

export function roadColor(p: RoadProps) {
  if (p.repairs === 0) return ROAD_COLOR.none;
  const rate = p.failed / p.repairs;
  if (rate === 0) return ROAD_COLOR.held;
  return rate >= OFTEN_FAILED_AT ? ROAD_COLOR.often : ROAD_COLOR.some;
}
