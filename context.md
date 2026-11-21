# The Ward Ledger — Project Context

> Mumbai civic works transparency platform. Synthetic BMC data, Claude-powered, hackathon-born.
> **All data is synthetic. All contractors are fictional. No real citizens.**

---

## 1. What This Is

A decision-support system layered over publicly-available Mumbai BMC (Brihanmumbai Municipal Corporation) civic data. The core insight: **don't build a watchdog — build an officer's shield.** A system that protects an Executive Engineer from future audit findings gets adopted. A public leaderboard that embarrasses contractors does not.

Three audiences, one data spine, three thin faces:

| Face | Audience | Key Action |
|---|---|---|
| **Officer Console** | Executive Engineer, AE | Pre-award risk flags, DLP clocks, drafted file noting with citations |
| **Citizen Window** | Public, Corporators | Pin → sanctioned works → contractor → cost → DLP status |
| **Audit Trail** | Municipal Chief Auditor | Append-only, hash-chained, every figure links to source page |

---

## 2. Data Spine

### Source Files (all CSV/GeoJSON, UTF-8, synthetic)

| File | Rows | Key Fields | Purpose |
|---|---:|---|---|
| `work_orders.csv` | 2,499 | `work_order_id`, `linked_complaint_ids`, `ward_code`, `road_id`, `contractor_id`, `cost_inr`, `sla_met`, `reopened_within_30d` | Core money trail |
| `complaints.csv` | 6,501 | `complaint_id`, `channel`, `description` (multilingual), `ward_code`, `lat/lon`, `status`, `resolved_at` | Citizen grievances |
| `complaints_sample_200.csv` | 200 | Same | Quick prototyping subset (Jul 7–8 heavy-rain) |
| `social_posts.csv` | 650 | `source`, `text` (mixed scripts, emoji, noise) | Social signal layer |
| `contractors.csv` | 8 | `contractor_id`, `contractor_name`, `empanelled_since`, `active_wards` | Contractor registry |
| `rate_card.csv` | 10 | `repair_method`, `unit`, `standard_rate_inr` | Billing benchmark |
| `roads.csv` / `.geojson` | 291 | `road_id`, `ward_code`, `under_dlp`, `last_resurfaced`, `surface` | Road segments + DLP status |
| `wards.csv` / `.geojson` | 24 | `ward_code`, `monsoon_repair_budget_inr_2025`, `low_lying_index`, `engineering_crews` | Ward-level budget & risk |
| `localities.csv` | 118 | `locality`, `ward_code`, `lat/lon`, `aliases` (Devanagari) | Geocoding gazetteer |
| `flood_hotspots.csv` | 28 | `flood_threshold_mm_per_day`, `tide_sensitive`, `avg_water_depth_cm` | Chronic flood risk |
| `rainfall_daily.csv` | 244 | `date`, `station`, `rainfall_mm`, `imd_category`, `imd_alert` | Weather context |
| `tides.csv` | 244 | `date`, `high_tide_time`, `height_m`, `big_tide_flag` | Tide context |
| `traffic.csv` | 291 | `road_id`, `congestion_index_0_10`, `peak_hour_vehicles` | Road criticality |
| `accidents.csv` | 420 | `road_id`, `severity`, `probable_cause` (Pothole/Waterlogged/Uneven) | Safety risk |
| `facilities.csv` | 160 | `type` (Hospital/School), `ambulance_entry_road` | Proximity risk |

### Relationship Graph

```
complaints ──(linked_complaint_ids)──> work_orders ──(road_id)──> roads
                                            │                        │
                              contractor_id─┤        last_resurfaced─┤
                              ward_code─────┤        under_dlp───────┘
                              repair_method─┘
                                   │
                              rate_card   wards   flood_hotspots
                                              rainfall  tides
                                              traffic   accidents
                                              facilities
```

### Critical Data Quirks

- **~7% of complaints** have blank `ward_code` — must geocode from `locality_text` via `localities.csv`
- **~18% of complaints** have wrong/vague `category_reported` — Claude must re-classify from description
- Descriptions are in **en / hi-en (Hinglish) / mr (Marathi) / hi (Hindi)** — multilingual parsing required
- Social posts contain **sarcasm, forwards, noise** — not all are genuine complaints
- `gps_accuracy_m` can be large — weight GPS pins accordingly
- `work_orders.cost_inr` ± 20–30% of rate-card is normal variation; flag beyond that
- Total season spend ≈ ₹13 Cr (synthetic, smaller than real BMC)
- Ward GeoJSON uses Voronoi approximation, not official boundaries

---

## 3. The Claims → Facts Architecture

The model **never writes facts directly**. This is the core architectural guard:

```
PDF/CSV Ingest
     │
     ▼
  [claim]  ← model output: value + source_doc + page + bbox + confidence + extractor_version
     │
  [resolve] ← entity resolution (GSTIN hard key, trigram fallback, adjudication queue)
     │
  [promote] ← rule (two-source-agree) OR named human event
     │
  [fact]   ← immutable, append-only, supersedes chain, never deleted
     │
  [serve]  ← read-only API → three UI faces
```

**Why this matters for adoption:** Every number renders with a provenance chip. Officers verify in 4 seconds. Auditors can trace every figure to its source document and page.

---

## 4. Risk Flags (Rule Engine — No Black Box)

Scores are **never shown publicly**. Officers see flags + supporting documents, not a numerical score.

| Flag | Rule | Severity |
|---|---|---|
| Cost overrun | Final bill >15% above awarded on ≥2 prior works | 🔴 High |
| Silent extension | Time extension granted, no LD penalty levied | 🔴 High |
| Related bidders | Shared PAN-within-GSTIN, shared director DIN, or shared address | 🔴 High |
| DLP breach | New work sanctioned on road still under defect liability | 🟡 Medium |
| Single-bid award | Fewer than 3 technically qualified bids | 🟡 Medium |
| Estimate drift | Sanctioned amount >20% above ward median for same schedule item | 🟡 Medium |
| Clean record | No flags across ≥3 completed works, bills within 5% | 🟢 Positive |

**Key design rule:** A positive flag exists. Systems that only accuse get switched off. Systems that also certify good work get used by contractors' own staff — which is how they survive a change of Commissioner.

---

## 5. Contractor Identity Resolution (Entity Resolution)

Order of precedence (hard keys first, guesses last):

1. **GSTIN** → PAN embedded at chars 3–12 → same legal entity if PAN matches
2. **Registered address** match
3. **Trigram similarity** on normalised name (after stripping legal suffixes)
4. **Below threshold** → adjudication queue (human review), not auto-linked

> "M/s A. B. Constructions", "AB Construction Pvt. Ltd.", "ए. बी. कन्स्ट्रक्शन" may be one firm or three. Never assert without hard keys. Entity resolution is the difference between an insight and a libel.

---

## 6. Geo Strategy

- Store locations as **lines, not points** (tenders describe stretches of road)
- Store **uncertainty** alongside coordinates
- PostGIS + ward polygons → pin-to-ward is instant
- Pin-to-work needs buffer + candidate list → citizen confirms
- Never claim precision you don't have

---

## 7. Three UI Faces

### Officer Console
- Dense table (not tiles), sorted by what expires soonest (DLP, SLA deadlines)
- Marathi/English toggle at shell level
- Every number clickable → highlighted region on source page
- **Primary action: "Draft noting"** (not "Export")
- Target: Desktop, 1366×768, IE-era muscle memory
- Language model drafts the file noting paragraph with numbered sub-paras citing document+page

### Citizen Window
- **Map first**. No login to browse; login only to file a report
- One tap: pin → plain-language summary (Marathi default)
- Must work on 2GB Android, 3G, offline photo queue
- Citizen photo = **trigger for inspection**, not evidence of fraud (critical framing for BMC acceptance)
- In-app capture only, server-side timestamp, EXIF retained internally, stripped on public render

### Audit Trail
- Chronological, filterable, exportable
- No interpretation, no design flourishes — looks like a log on purpose
- Hash-chained, append-only, corrections supersede (never delete)
- RTI draft generator: pre-fills Section 6(1) application, correct PIO, 30-day clock, first-appeal path

---

## 8. Adoption Phases

| Phase | Window | What Runs | What It Needs |
|---|---|---|---|
| **0** | 0–90 days | One ward, read-only, public PDFs only, offline review by one EE | A nodal officer. No MoU, no integration, no payment |
| **1** | 3–9 months | Officer console in one zone, human-in-loop promotion, measure minutes saved | Pilot MoU, departmental hosting |
| **2** | 9–18 months | Integration: read-only e-tendering replica, SSO, citizen window opens | Procurement under existing IT head, security audit |
| **3** | 18m+ | Mandate machine-readable publication in tender documents | A policy circular — no code |

**Signing chain:** Ward AMC (ground access) → Executive Engineer (substance) → Dy. Commissioner IT (servers). Phase 0 rides on nobody's budget.

---

## 9. Legal & Governance Rails

| Concern | Mitigation |
|---|---|
| Defamation | Publish only facts already public. Risk scores stay inside officer console. Flagged firms get right of reply on record. |
| DPDP Act 2023 | Collect minimum citizen data, state purpose at capture, retention schedule with auto-expiry, strip EXIF on public render |
| RTI | First-class output — Section 6(1) draft, correct PIO, fee, 30-day clock, appeal path |
| Audit | Append-only, hash-chained. Corrections supersede; nothing deleted. |
| Model boundary | Public docs → hosted model OK. Staff IDs + draft notings → corp-controlled infra only |

---

## 10. Stack Reference

| Layer | Choice |
|---|---|
| DB | PostgreSQL + PostGIS + pg_trgm |
| API | FastAPI |
| OCR/Vision | Claude Vision (table structure) + standard OCR (text spans) |
| Map | Any library the front-end lane knows (Leaflet/MapLibre) |
| Deferred | pgvector (Phase 1 — skip on day 0) |

---

## 11. Hackathon Scope (11 hours)

Focused on **K/East ward (Andheri East)**, ~30 staged real documents.

| Time | Milestone |
|---|---|
| 09:00–09:30 | Lock scope, split 4 lanes: ingest / API / map+frontend / pitch |
| 09:30–11:00 | Ingest → claims table with page + bbox. **This must exist by 11:00.** |
| 11:00–12:00 | Entity resolution + adjudication queue demo |
| 12:00–13:00 | Geo: ward polygons, pin → candidate works |
| 13:00–13:30 | First end-to-end pass. Find breakage now. |
| 13:30–15:00 | Rule engine + officer console (7 flags, citing facts) |
| 15:00–16:30 | **File noting + RTI draft generators** (demo climax — protect this time) |
| 16:30–18:00 | Citizen window (map, pin, photo, bilingual summary) |
| 18:00 | Feature freeze. Seed demo path. Record backup video. |
| 18:00–19:00 | Demo script: 3 minutes, one real pothole photo → cited noting + filed RTI |
| 19:00–20:00 | Rehearse 3×, then stop |

---

## 12. Judging Rubric

| Criterion | Weight |
|---|---|
| Audit accuracy (flags vs answer key) | 25% |
| Fair accountability (evidence-based, not misleading) | 20% |
| Budget recommendation (next-rupee ranking) | 20% |
| Connects the trail (complaints → issues → work orders) | 15% |
| Usable by a real person (ward officer / corporator / citizen) | 10% |
| Demo and clarity | 10% |

---

## 13. The Pitch Line

> "A 90-day, single-ward, zero-rupee pilot running only on documents the corporation already publishes, with one named nodal officer and a success metric agreed before it starts."

Not funding. Not an MoU. Not a data feed. Those are Phase 1 conversations.

**Closing line:** Phase 3 requires every tender to publish a structured record alongside the PDF. That retires most of Phases 0–2 permanently, and a corporation can mandate it without buying anything. The pipeline is the bridge, not the destination.
