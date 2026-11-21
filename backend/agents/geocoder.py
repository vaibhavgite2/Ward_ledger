"""Geocoder agent (SPEC §6.2): GPS -> gazetteer exact -> gazetteer prefix/fuzzy -> ward centroid.

Always stores an uncertainty radius and the method used; never asserts precision the source
text does not support (e.g. no road snapping from a locality name).
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from rapidfuzz import fuzz, process

import config
from pipeline.geo import Geo

R = config.RULES["geocode"]


def norm(s: str | None) -> str:
    if not isinstance(s, str):
        return ""
    s = s.lower().replace("'", "").replace("’", "")
    s = re.sub(r"[^\wऀ-ॿ\s]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


@dataclass
class Place:
    locality: str
    ward_code: str
    lat: float
    lon: float


class Gazetteer:
    def __init__(self, localities: list[dict]):
        self.places: list[Place] = []
        self.index: dict[str, list[Place]] = {}      # normalised name/alias -> places
        for r in localities:
            p = Place(r["locality"], r["ward_code"], float(r["lat"]), float(r["lon"]))
            self.places.append(p)
            names = [r["locality"]]
            if isinstance(r.get("aliases"), str):
                names += [a for a in r["aliases"].split(";") if a.strip()]
            for n in names:
                self.index.setdefault(norm(n), []).append(p)
        self.keys = list(self.index)

    @staticmethod
    def _pick(cands: list[Place], ward_hint: str | None) -> tuple[Place, bool]:
        """Choose among candidates sharing a name; prefer the ward the citizen gave. -> (place, ambiguous)"""
        if ward_hint:
            hit = [p for p in cands if p.ward_code == ward_hint]
            if hit:
                return hit[0], len(hit) > 1
        return cands[0], len(cands) > 1

    def lookup(self, text: str, ward_hint: str | None = None):
        """-> (Place|None, method, ambiguous, review_candidates)"""
        q = norm(text)
        if not q:
            return None, "none", False, []
        if q in self.index:
            p, amb = self._pick(self.index[q], ward_hint)
            return p, "gazetteer", amb, []
        # Truncated names ("Grant" for "Grant Road", "Vile" for "Vile Parle East"): token-prefix match.
        qt = q.split()
        pref = [k for k in self.keys if k.split()[:len(qt)] == qt]
        if pref:
            cands = [p for k in pref for p in self.index[k]]
            if ward_hint:
                inward = [p for p in cands if p.ward_code == ward_hint]
                cands = inward or cands
            p = cands[0]
            amb = len({c.locality for c in cands}) > 1 and not ward_hint
            return p, "gazetteer-prefix", amb, []
        best = process.extract(q, self.keys, scorer=fuzz.token_set_ratio, limit=3)
        if best and best[0][1] >= R["fuzzy_accept"]:
            p, amb = self._pick(self.index[best[0][0]], ward_hint)
            return p, "gazetteer-fuzzy", amb, []
        if best and best[0][1] >= R["fuzzy_review"]:
            return None, "none", False, [b[0] for b in best]
        return None, "none", False, []


def geocode(row: dict, gaz: Gazetteer, geo: Geo, ward_centroids: dict[str, tuple[float, float]]) -> dict:
    """row: complaint dict. Returns lat, lon, uncertainty_m, method, ward_code, ward_source, review (list)."""
    reported_ward = row.get("ward_code") if isinstance(row.get("ward_code"), str) else None
    lat, lon, acc = row.get("lat"), row.get("lon"), row.get("gps_accuracy_m")
    out = {"lat": None, "lon": None, "uncertainty_m": None, "method": "none", "ward_code": reported_ward,
           "ward_source": "reported" if reported_ward else None, "review": [], "ambiguous": False}
    has_gps = lat == lat and lon == lon and lat is not None and lon is not None
    gps_ok = has_gps and (acc is None or acc != acc or float(acc) <= R["gps_max_accuracy_m"])

    place, method, amb, review = gaz.lookup(row.get("locality_text"), reported_ward)
    out["review"] = review
    out["locality_resolved"] = place.locality if place else None
    out["gazetteer_ward"] = place.ward_code if place else None

    if gps_ok:
        out.update(lat=float(lat), lon=float(lon),
                   uncertainty_m=float(acc) if acc == acc and acc is not None else 100.0, method="gps")
        poly_ward = geo.ward_at(float(lat), float(lon))
        out["polygon_ward"] = poly_ward
        if not reported_ward and poly_ward:
            out.update(ward_code=poly_ward, ward_source="polygon")
    elif place:
        u = {"gazetteer": R["gazetteer_exact_m"], "gazetteer-prefix": R["gazetteer_fuzzy_m"],
             "gazetteer-fuzzy": R["gazetteer_fuzzy_m"]}[method]
        if amb:
            u = R["ward_centroid_m"]
        out.update(lat=place.lat, lon=place.lon, uncertainty_m=float(u), method=method, ambiguous=amb)
        if not reported_ward:
            out.update(ward_code=place.ward_code, ward_source="gazetteer")
    elif reported_ward and reported_ward in ward_centroids:
        clat, clon = ward_centroids[reported_ward]
        out.update(lat=clat, lon=clon, uncertainty_m=float(R["ward_centroid_m"]), method="ward-centroid")
    return out
