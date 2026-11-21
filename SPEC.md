# The Ward Ledger — Product & Technical Specification

> **Follow the Rupee: Mumbai Monsoon Roads** · Claude Impact Lab Mumbai · 21 Nov 2026
> Status: v1.0 (hackathon MVP) · Stack: Next.js + FastAPI + SQLite + Claude
>
> ⚠️ **All data is synthetic. All contractors are fictional.** Every page of the app shows this banner.

Related docs: [README.md](README.md) (challenge) · [DATA_DICTIONARY.md](DATA_DICTIONARY.md) (columns) · [agents.md](agents.md) (full agent architecture) · [context.md](context.md) (adoption & governance) · [STARTER_IDEAS.md](STARTER_IDEAS.md) (rubric)

---

## 1. Overview

### 1.1 Problem
Every monsoon Mumbai spends crores repairing the same roads. Citizens complain, repairs are logged, and the potholes come back. Nobody can easily answer:
1. **Where did the money go?**
2. **Did the fix last?**
3. **Who is responsible?**
4. **Where should the next rupee go?**

### 1.2 Product
The Ward Ledger is a **citizen-first web app**. It traces every ward's road-repair rupee from complaint → work order → contractor → cost → outcome, in plain Marathi, English or Hindi. Every number links back to the record it came from.

It has three faces that read **one shared fact layer**:

| Face | Audience | Purpose |
|---|---|---|
| **Citizen Window** (primary) | Citizens, corporators | Track my complaint, see my road and ward's money trail, check contractors, see what gets fixed next, file an RTI |
| **Officer Console** (secondary) | Ward Executive / Assistant Engineers | The same findings framed as risk flags, budget planner, auto-drafted file noting with citations |
| **Audit Trail** (secondary) | Auditors, journalists, curious citizens | Boring, append-only log: every figure → source file, row, hash, rule/model that produced it |

### 1.3 Design principles
1. **Facts, not accusations.** Citizens see neutral, evidenced statements ("billed 45% above the standard rate"). They never see verdicts ("fraud", "suspicious").
2. **The model never writes facts.** Claude output is a *claim*. Only a deterministic rule or a named human promotes it to a *fact* ([agents.md](agents.md#architectural-principle)).
3. **Every number has a receipt.** Each figure carries a provenance chip that opens its source rows.
4. **Fair by construction.** Context (low-lying ward, heavy-rain week) is applied before any comparison. A positive "Clean record" finding is mandatory.
5. **Every journey ends in an action.** File an RTI, raise it with the corporator, or share.
6. **Go narrow and finish.** Build CSV-driven features that can be judged. Defer the PDF/OCR machinery.

---

## 2. Scope

### 2.1 In scope (MVP), mapped to the judging rubric

| Rubric pillar (weight) | MVP feature |
|---|---|
| Audit accuracy (25%) | Deterministic finding rules (§6.4) with evidence WO IDs |
| Fair accountability (20%) | Context-adjusted contractor and ward scorecards, neutral language, clean-record badge, right-of-reply |
| Budget recommendation (20%) | Next-rupee planner per ward (§6.6) |
| Connects the trail (15%) | Complaint parser + geocoder + dedup + complaint→WO linker (§6.1–6.3) |
| Usable by a real person (10%) | Mobile-first bilingual citizen window, RTI drafts, officer file noting |
| Demo & clarity (10%) | Citizen-led demo script (§13.3) |

### 2.2 Out of scope / deferred

| Item | Why | When |
|---|---|---|
| Harvester, OCR Extractor, Vision Table Reconstructor | Dataset has no PDFs, only CSV/GeoJSON | Phase 1 (real BMC PDFs) |
| GSTIN/PAN entity resolution, adjudication queue | `contractors.csv` has 8 clean, canonical rows | Phase 1 |
| PostGIS / pg_trgm | Replaced by shapely + haversine + rapidfuzz in Python | When data > single ward/city CSV scale |
| Offline photo queue | Needs a service worker and background sync | Stretch (photo/video upload itself: built, §16) |
| SSO / SMS OTP login | Built instead: three password login panels over one user table (§16); SSO and OTP need a government IdP / SMS gateway | Phase 2 |
| Live portal harvesting | Synthetic dataset only | Phase 1 |

### 2.3 Doc-vs-data reconciliation
[agents.md](agents.md) assumes tender PDFs, bids, GSTINs and awarded-vs-final bills. The dataset has none of these. Every agent and flag is classified below:

| agents.md item | MVP status | Notes |
|---|---|---|
| 1 Harvester | **Adapted** | Becomes the CSV loader: sha256 of each file, stored in `source_doc` |
| 2 OCR Extractor / 3 Vision Reconstructor | Deferred | No PDFs |
| 4 Complaint Parser | **MVP** | Claude Haiku + gazetteer |
| 5 Social Signal Classifier | Stretch | `social_posts.csv`, signal only, shown as "also reported on social" |
| 6 Geocoder | **Adapted** | Points + `uncertainty_m`, not LINESTRING. Road snapping uses `roads.geojson` |
| 7 Entity Resolver | Deferred | Contractor IDs are already canonical |
| 8 Rule Engine | **MVP** | Promotes CSV rows and agreeing claims to facts, evaluates findings |
| 9 Risk Flagger | **MVP** | Same findings as citizens, officer framing |
| 10 File Noting Drafter | **MVP** | Cites WO IDs + source rows instead of PDF pages |
| 11 RTI Draft Generator | **MVP** | Citizen hero feature |
| 12 Budget Planner | **MVP** | Public "what gets fixed next" + officer planner |
| 13 Citizen Accountability Bot | **MVP** | "Ask" box |
| 14 Audit Trail Renderer | **MVP** | Log table + CSV export |

| Flag (agents.md §9) | MVP status | Replacement / data needed |
|---|---|---|
| `cost_overrun_history` | **Adapted** → `rate_card_overrun` | No awarded amount; compare `cost_inr` to rate card |
| `silent_extension` | N/A | Needs extension orders + LD penalty records |
| `related_bidders` | N/A | Needs bidder lists + GSTIN/address |
| `single_bid_award` | N/A | Needs tender bid counts |
| `dlp_breach` | **MVP** | `roads.under_dlp = Y` |
| `estimate_drift` | **MVP** | Ward median unit cost per method |
| `clean_record` | **Adapted** | "Within 5% of rate card" is impossible given normal ±20–30% variance, so redefined in §6.4 |
| *(new)* `possible_double_billing` | **MVP** | From STARTER_IDEAS #2 |
| *(new)* `sla_missed`, `failed_within_30d` | **MVP** | From work_orders |
| *(new)* `never_fixed` | **MVP** | Complaint with no linked WO and not legitimately closed |

---

## 3. Users & key journeys

### 3.1 Citizen (primary)
Mobile (360 px+), no login, Marathi by default (English / Hindi toggle). Must work on a slow 3G connection: under 200 KB JS on the first route, map tiles lazy-loaded.

| # | Journey | Flow | Ends in |
|---|---|---|---|
| C1 | **"What happened to my complaint?"** | Enter `BMC25-xxxxxx` (or type "pothole near Andheri station") → timeline: received → category (as parsed) → linked WO → contractor → cost → completed on → SLA met? → held up 30 days? → road under warranty? | RTI draft if unresolved / failed / DLP-billed. Share. |
| C2 | **"What's going on with my road?"** | "Use my location" or tap the map → nearest road segments (≤200 m) → road card: repairs this season, ₹ spent, times it failed, warranty status, open complaints | RTI, "raise with corporator" letter |
| C3 | **"Where did my ward's money go?"** | Ward page: budget vs spend, spend by contractor and method, **₹ spent on fixes that failed within 30 days**, findings list | Share ward summary (one-page, printable) |
| C4 | **"How good is this contractor?"** | Contractor page: fair scorecard, findings with evidence, clean-record badge, right-of-reply | — |
| C5 | **"What gets fixed next?"** | Ward priority list with plain reasons ("school 120 m away, flooded 4 of last 5 years, 3 pothole accidents") | Upvote / share with corporator |
| C6 | **Ask** | Free-text question in any language → bot answer built only from facts | RTI if data missing |

### 3.2 Corporator (secondary)
Uses the same public pages plus a **ward comparison** table (all 24 wards: budget utilisation, failed-fix ₹, SLA rate, open complaints) and a printable ward summary for ward-committee meetings.

### 3.3 Ward officer (secondary)
`/officer/[ward]`: a dense, sortable WO table (sorted by DLP / SLA urgency), flag panel with evidence, budget planner, and a **"Draft noting"** button producing a bilingual note-sheet paragraph with numbered, cited sub-paras.

### 3.4 Auditor (secondary)
`/audit`: a chronological log of facts and claims, filterable by ward / contractor / date / field, with CSV export and source-file hashes.

---

## 4. Data

### 4.1 Source
The dataset is not in this repo. A fetch script clones it into `data/` (gitignored):

```bash
# scripts/fetch_data.sh
git clone --depth 1 https://github.com/SumeetGDoshi/Claude-Impact-Labs-data-2.git /tmp/wl-data
mkdir -p data && cp /tmp/wl-data/data/* data/
```

Files and columns: see [DATA_DICTIONARY.md](DATA_DICTIONARY.md). Key joins:

```
complaints.complaint_id  ◄──(pipe-split linked_complaint_ids)── work_orders
work_orders.road_id       ──► roads.road_id ──► traffic, accidents, facilities.ambulance_entry_road
work_orders.contractor_id ──► contractors
work_orders.repair_method ──► rate_card
work_orders.ward_code     ──► wards (budget, low_lying_index)
```

### 4.2 Load pipeline (`backend/pipeline/load.py`)
1. For each file in `data/`: compute sha256 and insert into `source_doc(doc_id=sha256, filename, rows, loaded_at)`.
2. Load CSV → SQLite (`backend/ward_ledger.db`) with pandas. Keep the original row number as `_row` on every table for citations.
3. Parse timestamps (IST), split `linked_complaint_ids` into a `wo_complaint` bridge table, and load GeoJSON into memory as shapely geometries (wards polygons, road LineStrings) with an STRtree index.
4. Run derived steps in order: §6.1 parse → §6.2 geocode → §6.3 link/dedup → §6.4 promote + findings → §6.5 scorecards → §6.6 budget.
5. Idempotent: re-running with unchanged hashes is a no-op. Claude calls are cached on disk (§9.3).

CLI: `python -m backend.pipeline run [--sample]` (`--sample` uses `complaints_sample_200.csv`).

### 4.3 Data quirks to handle
| Quirk | Handling |
|---|---|
| ~7% complaints with blank `ward_code` | Geocode `locality_text` / GPS → point-in-polygon on `wards.geojson` |
| ~18% wrong/vague `category_reported` | Claude re-classifies from `description` + `photo_description` |
| Multilingual text (en, hi-en, mr, hi) | Claude handles; Devanagari aliases from `localities.csv` |
| Large `gps_accuracy_m` | Prefer gazetteer if accuracy > 500 m; store `uncertainty_m` |
| Normal ±20–30% cost variance | Overrun threshold 1.30× (§6.4) |
| Social noise / sarcasm | Signal only, never a finding |
| Voronoi ward polygons | Consistent with dataset `ward_code`; label as "approximate" on the map |

### 4.4 Derived constants
- **Severity from SLA:** `sla_hours` → severity: 24→5, 48→4, 72→3, 120→2, 168→1 (nearest bucket).
- **Rain station by ward:** island-city wards (A, B, C, D, E, F/S, F/N, G/S, G/N) → Colaba; all others → Santacruz.
- **Heavy-rain day:** `imd_category ∈ {Heavy, Very heavy, Extremely heavy}`. A **heavy-rain week** for a WO means ≥2 heavy-rain days in the 7 days after `completed_at` (relevant to durability) or before `assigned_at` (relevant to cost).
- **Low-lying ward:** `low_lying_index ≥ 0.6`.
- **As-of date** for "open" and "remaining budget": the last `received_at` in the data (configurable).

---

## 5. Data model (SQLite)

Raw CSV tables are loaded as-is (plus `_row`). Derived tables:

```sql
CREATE TABLE source_doc (doc_id TEXT PRIMARY KEY, filename TEXT, rows INT, loaded_at TEXT);

-- Anything produced by Claude or a heuristic: a CLAIM
CREATE TABLE claim (
  claim_id     TEXT PRIMARY KEY,         -- uuid
  subject_type TEXT,                      -- complaint | work_order | road | contractor | ward
  subject_id   TEXT,
  field_path   TEXT,                      -- e.g. 'category', 'ward_code', 'locality', 'duplicate_of'
  value_json   TEXT,
  source_doc   TEXT REFERENCES source_doc, source_row INT,
  extractor    TEXT,                      -- 'claude-haiku-5-5/complaint-parser@v1' | 'gazetteer@v1'
  prompt_hash  TEXT, confidence REAL, created_at TEXT
);

-- Promoted, append-only. Never UPDATE/DELETE (enforced by triggers).
CREATE TABLE fact (
  fact_id      TEXT PRIMARY KEY,
  subject_type TEXT, subject_id TEXT, field_path TEXT, value_json TEXT,
  from_claim   TEXT REFERENCES claim,     -- null when promoted straight from a CSV row
  source_doc   TEXT, source_row INT,
  promoted_by  TEXT,                      -- 'rule:source-csv@v1' | 'rule:two-source-agree@v1' | 'user:ae-4471'
  promoted_at  TEXT,
  supersedes   TEXT REFERENCES fact,
  prev_hash    TEXT, row_hash TEXT        -- hash chain: sha256(prev_hash || canonical row)
);
CREATE TRIGGER fact_no_update BEFORE UPDATE ON fact BEGIN SELECT RAISE(ABORT,'fact is append-only'); END;
CREATE TRIGGER fact_no_delete BEFORE DELETE ON fact BEGIN SELECT RAISE(ABORT,'fact is append-only'); END;

CREATE TABLE parsed_complaint (
  complaint_id TEXT PRIMARY KEY, category TEXT, category_confidence REAL, category_changed INT,
  language TEXT, locality TEXT, ward_code TEXT, lat REAL, lon REAL, uncertainty_m REAL,
  geocode_method TEXT,                    -- gps | gazetteer | gazetteer-fuzzy | ward-centroid | none
  road_id TEXT, road_distance_m REAL,
  issue_id TEXT,                          -- dedup cluster id
  link_status TEXT                        -- fixed | fixed_failed | in_progress | never_fixed | closed_other
);

CREATE TABLE issue (issue_id TEXT PRIMARY KEY, category TEXT, road_id TEXT, ward_code TEXT,
  lat REAL, lon REAL, first_reported TEXT, complaint_count INT, upvotes INT, severity INT,
  work_order_id TEXT, status TEXT);

CREATE TABLE finding (
  finding_id TEXT PRIMARY KEY, rule TEXT, rule_version TEXT,
  subject_type TEXT, subject_id TEXT,     -- work_order | contractor | ward | complaint
  polarity TEXT,                          -- concern | positive
  severity TEXT,                          -- high | medium | low | info
  metrics_json TEXT,                      -- numbers used, e.g. {"cost":48200,"expected":33000,"ratio":1.46}
  evidence_json TEXT,                     -- [{"table":"work_orders","id":"WO25-00042","row":42}, ...]
  context_json TEXT,                      -- adjustments applied (low-lying, heavy-rain)
  public_text_en TEXT, public_text_mr TEXT, -- neutral, template-rendered
  created_at TEXT
);

CREATE TABLE right_of_reply (subject_type TEXT, subject_id TEXT, finding_id TEXT, reply_text TEXT, received_at TEXT);
CREATE TABLE review_queue (item_id TEXT PRIMARY KEY, claim_id TEXT, reason TEXT, status TEXT, decided_by TEXT, decided_at TEXT);
CREATE TABLE budget_recommendation (run_id TEXT, ward_code TEXT, rank INT, issue_id TEXT, road_id TEXT,
  score REAL, factors_json TEXT, method TEXT, est_cost_inr REAL, cumulative_inr REAL, rationale_en TEXT, rationale_mr TEXT, created_at TEXT);
CREATE TABLE audit_log (seq INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, actor TEXT, action TEXT, object_type TEXT, object_id TEXT, detail_json TEXT);
```

**Promotion rules (Rule Engine, `backend/rules/promote.py`):**
- `rule:source-csv@v1`: fields read directly from a CSV row (cost, dates, contractor, sla_met, reopened, under_dlp) become facts citing `(source_doc, source_row)`.
- `rule:two-source-agree@v1`: a Claude claim is promoted when an independent source agrees. Examples: parsed category agrees with `category_reported` or with the linked WO's `work_type`; geocoded ward agrees with GPS point-in-polygon.
- `rule:high-confidence@v1`: a Claude category claim with confidence ≥ 0.85 and no conflicting source is promoted, tagged `confidence` in the UI.
- Everything else goes to `review_queue`. The UI shows it as "unverified" and it is never used in findings.
- Human decisions (officer UI, stretch) promote with `promoted_by='user:<id>'`.

---

## 6. Pipeline & agents (MVP)

All agents live in `backend/agents/` and prompts in `backend/prompts/*.md` (versioned; `prompt_hash = sha256(template + model + params)`).

### 6.1 Complaint Parser (Claude Haiku, batched)
- **Input:** `complaint_id, description, category_reported, locality_text, photo_description, language` (batches of 25).
- **Output (JSON per complaint):** `category ∈ {Pothole, Waterlogging, Open manhole, Drain overflow, Road cave-in, Road damage, Other}`, `confidence`, `locality_mentioned` (verbatim), `language`, `reason` (≤ 1 line).
- **Prompt:** the template in [agents.md §4](agents.md#4-complaint-parser-agent). Add: "Do not add information not in the text. Return JSON array only."
- **Writes:** `claim` rows. Promotion follows §5.
- **Fallback (no API key / offline):** keyword classifier (multilingual keyword lists, e.g. `खड्डा`, `gaddha`, `paani bhar`) with confidence 0.5.

### 6.2 Geocoder (deterministic)
Order of precedence:
1. **GPS** if present and `gps_accuracy_m ≤ 500` → `uncertainty_m = gps_accuracy_m`.
2. **Gazetteer exact**: normalise `locality_text` (lowercase, strip punctuation) and match `localities.locality` or any alias (incl. Devanagari) → `uncertainty_m = 750`.
3. **Gazetteer fuzzy**: rapidfuzz token-set ratio ≥ 85 → `uncertainty_m = 1000`. 70–85 → claim to `review_queue`.
4. **Ward centroid** if only `ward_code` is known → `uncertainty_m = 2000`.

Then: point-in-polygon on wards fills a blank `ward_code` (a claim, promoted if it agrees with the gazetteer ward). Snap to the nearest road segment within `max(200, uncertainty_m)` m → `road_id`, `road_distance_m`.

### 6.3 Dedup & Complaint→WO Linker (deterministic)
- **Dedup → issues:** complaints with the same parsed category, within **150 m** (or the same `road_id` when uncertainty > 150 m) and within **48 h**, are clustered into one `issue` (union-find). Complaints already in a WO's `linked_complaint_ids` join that WO's issue. `Closed - Duplicate` status supports clustering but doesn't override it. Clusters are candidates, shown as "reported N times".
- **Link status per complaint:**
  - `fixed`: linked WO completed, `reopened_within_30d = N`
  - `fixed_failed`: linked WO with `reopened_within_30d = Y`
  - `in_progress`: linked WO not completed
  - `closed_other`: status is `Forwarded to …` or `Rejected - …` (shown with the reason, not as a failure)
  - `never_fixed`: no linked WO and status `Open`/`In Progress` older than the SLA for its severity → finding `never_fixed`
- **Unlinked WOs:** WOs with blank `linked_complaint_ids` are flagged as context for double billing (they are not a finding on their own).

### 6.4 Rule Engine: findings (deterministic, `backend/rules/findings.py`)
Each rule produces `finding` rows with metrics, evidence (WO IDs + source rows), context applied, and **template-rendered neutral text** (no LLM in the finding itself). Thresholds live in `backend/rules/config.yaml`.

| Rule | Subject | Logic | Severity | Citizen text (en template) |
|---|---|---|---|---|
| `rate_card_overrun` | WO | `expected = area_sqm × rate` (per sqm) or `rate` (per job). Flag if `cost_inr / expected > 1.30` (1.40 if low-lying ward **and** heavy-rain week) | high if > 1.6, else medium | "Billed ₹{cost}, which is {pct}% above the standard rate of ₹{expected} for {method}." |
| `possible_double_billing` | WO pair | Same `road_id` + same `work_type`, second WO `assigned_at` within **7 days** of the first's `completed_at`, second has **no** linked complaint | high | "Two repairs of the same type were billed on {road} within {d} days; the second has no linked complaint." |
| `dlp_breach` | WO | `roads.under_dlp = Y` for the WO's `road_id` | medium | "This road is still under the original contractor's warranty (Defect Liability Period); this repair was billed to BMC (₹{cost})." |
| `sla_missed` | WO | `sla_met = N` | low (medium if ≥ 2× sla_hours) | "Completed in {h} h against a target of {sla} h." |
| `failed_within_30d` | WO | `reopened_within_30d = Y` | medium (low if heavy-rain week after completion) | "This repair failed within 30 days and the complaint was reopened." |
| `estimate_drift` | WO | Unit cost (`cost/area` for per sqm) > **1.20 ×** the ward median for the same method (1.30 if low-lying or heavy-rain week). Needs ≥ 5 WOs in the comparison group, else uses the city median | medium | "Cost per sqm ₹{u} vs ₹{m} typical for {method} in this ward." |
| `never_fixed` | complaint/issue | §6.3 | medium | "No repair has been linked to this complaint {days} days after it was filed." |
| `clean_record` (positive) | contractor × ward | ≥ 3 completed WOs and zero `rate_card_overrun`, `possible_double_billing` or `dlp_breach`, and SLA rate ≥ 90%, and reopen rate ≤ city median for the same method mix | positive | "Clean record in {ward}: {n} completed repairs, on time and within the standard rate." |

Rules:
- One finding per (rule, subject). A WO can carry several findings.
- **Language style guide (enforced by a unit test):** banned words in public text (`fraud, scam, suspicious, corrupt, theft, loot, घोटाळा, भ्रष्टाचार`). Findings describe *what the records show*. The words "red flag" are officer-only.
- Each public finding shows **"Contractor's reply"** (from `right_of_reply`, or "No reply on record") and a **"Request documents (RTI)"** button.

### 6.5 Scorecards
**Contractor scorecard** (`/contractors/{id}/scorecard`), computed over completed WOs:

| Metric | Definition | Fairness adjustment |
|---|---|---|
| Volume | # WOs, ₹ billed, wards active | — |
| Speed | SLA met % | Shown alongside the ward average for the same severity mix |
| Durability | Reopened-within-30d % | **Expected reopen rate**: reopen rate for the same (method × low-lying bucket × heavy-rain-week) cells, city-wide, weighted by the contractor's mix. Show actual vs expected. |
| Cost | Median `cost/expected` ratio, % of WOs > 1.30 | Same method mix |
| Warranty | # WOs billed on DLP roads | — |
| Findings | Count by rule + clean-record wards | — |

**No composite score, grade or rank** on public pages. Contractors are listed alphabetically. Sorting by a metric is allowed, with that metric visible.

**Narrative:** Claude Sonnet writes ≤ 120 words, citizen-readable, from a JSON of the metrics above. Prompt from [STARTER_IDEAS.md](STARTER_IDEAS.md#prompts-to-start-with) plus: "Use only the numbers provided; mention context adjustments; include one strength and one thing to improve; no accusations." Post-check: every number in the output must appear in the input JSON (§9.4).

**Ward scorecard / money trail** (`/wards/{code}/money-trail`):
- Budget (`monsoon_repair_budget_inr_2025`) vs spend and utilisation %
- Spend by contractor, by repair method, by month
- **₹ spent on fixes that failed within 30 days** (headline number)
- ₹ billed on DLP roads
- Complaint funnel: received → unique issues → linked to WO → fixed and held / failed / never fixed
- Context: low_lying_index, heavy-rain days, crews
- Claude one-page plain-language summary (≤ 200 words), with the same number check

### 6.6 Budget Planner: "next rupee" (`backend/agents/budget.py`)
**Candidates:** open `issue`s in the ward (no completed WO, or last WO `failed_within_30d`), aggregated to road segment.

**Score** (weights from [agents.md §12](agents.md#12-budget-planner-agent); each factor normalised to 0–1):

| Factor | Weight | Normalisation |
|---|---|---|
| S complaint severity | 0.25 | `max(category base, sla-derived) / 5`, with category base: Road cave-in 5, Open manhole 5, Waterlogging 4, Pothole 3, Drain overflow 3, Road damage 2, Other 1. +1 (capped at 5) if issue upvotes + complaint_count ≥ 10 |
| F flood hotspot | 0.20 | 1 if within 300 m of a hotspot, scaled by `years_flagged_last_5 / 5`; else 0 |
| R rainfall risk | 0.15 | `min(1, 7-day rainfall at station before as-of date / 300 mm)`, × 1.2 if hotspot is `tide_sensitive` and a big tide falls within the next 7 days (capped at 1) |
| A accident severity | 0.15 | Σ on road_id (Minor 1, Grievous 3, Fatal 5) for causes ∈ {Pothole, Waterlogged road, Uneven road / open chamber}, ÷ ward max |
| P hospital/school | 0.10 | 1 if a facility is within 250 m or `ambulance_entry_road = road_id` (hospital with emergency = 1, school = 0.7) |
| C congestion | 0.10 | `congestion_index_0_10 / 10` (+0.1 if `bus_route = Y`, capped at 1) |
| D days since last repair | 0.05 | `min(1, days since last completed WO or last_resurfaced / 365)` |

**Adjustments:**
- **DLP discount:** if `under_dlp = Y`, score × 0.5, cost to BMC = ₹0, and the action is "Ask the warranty contractor to repair at no cost".
- **Method choice:** among `rate_card` methods valid for the issue category, pick the one with the lowest **observed reopen rate** in comparable conditions. On high-traffic roads (congestion ≥ 6 or bus route) or with rain risk R ≥ 0.6, cold mix is excluded and hot mix / mastic is preferred.
- **Cost estimate:** rate card × estimated area (median `area_sqm` for that category in the ward) or per-job rate.
- **Budget cap:** remaining = budget − spend to as-of date. Greedily allocate down the ranking until **80%** of remaining is reached. Show what's funded and what's not.

**Output:** ranked list with score, factor breakdown (bar), method, ₹ estimate, cumulative ₹, and a one-line plain rationale per item (template + optional Claude polish, number-checked). Versioned in `budget_recommendation`, marked "advisory".

### 6.7 Citizen Accountability Bot (`POST /ask`)
1. **Resolve the query.** Regex for a complaint ID, WO ID or road ID. Otherwise Claude Haiku extracts `{intent, locality, road, category}` → geocode → candidate issues/roads. If ambiguous, return up to 3 candidates and ask the citizen to pick.
2. **Gather facts.** Complaint → issue → WO → contractor → cost → SLA → reopened → DLP → public findings. Facts only, no unverified claims.
3. **Answer.** Claude Sonnet, in the user's language (detected, or the UI language): ≤ 120 words with a citation list. Rules: "Use only these facts. If something is missing, say 'We don't have this information yet' and offer an RTI. Never infer wrongdoing."
4. **Post-check numbers** (§9.4). On failure, fall back to the templated answer.

Example answer: see [agents.md §13](agents.md#13-citizen-accountability-bot).

### 6.8 RTI Draft Generator (`POST /rti-draft`)
- **Input:** `{work_order_id | complaint_id | road_id, lang}`.
- **Output:** printable application under **Section 6(1), RTI Act 2005**:
  - Addressed to the Public Information Officer, ward office (`wards.assistant_commissioner_office`)
  - Fee ₹10 (BPL exempt)
  - 30-day reply clock with the computed date
  - First appeal under Section 19(1) to the First Appellate Authority within 30 days
- **Documents requested:** work order, estimate, measurement book entries, completion certificate, bill/payment record, contractor's DLP obligation for the road, inspection report, and any LD/penalty records.
- **Tone:** requests documents "for citizen verification". No allegations. Mentions the specific facts that prompted it (e.g. "the road appears in records as under Defect Liability Period").
- **Languages:** Marathi + English side by side. A disclaimer asks the citizen to verify the current PIO name and address before filing.
- Structure is template-driven, and Claude fills only the "particulars of information" paragraph. Never persisted beyond the session. `audit_log` records only that a draft was generated (no PII).

### 6.9 File Noting Drafter (officer, `POST /draft-noting/{work_id}`)
- Assembles the WO, contractor history, findings and context. Claude Sonnet drafts a note-sheet in the BMC format ([agents.md §10](agents.md#10-file-noting-drafter-agent)): numbered paras, each ending in a citation `[Ref: WO25-00042 · work_orders.csv row 42 · sha256:ab12…]`.
- Includes the contractor's clean-record finding where present (balance).
- **Unsourced assertion block:** the output is parsed paragraph by paragraph. Any paragraph without a citation, or citing an ID not in the input bundle, is removed and flagged in the UI.
- Marathi default, English toggle. Returned to the editor only, never saved as a fact. The officer edits, copies or prints it.

### 6.10 Audit Trail Renderer (`GET /audit`)
- A chronological union of `fact`, `claim`, `finding` and `audit_log`. Each row shows timestamp, subject, field, value, source file + row, source sha256, extractor/rule + version, prompt_hash, promoter, and supersedes link.
- Corrections are shown inline: `[SUPERSEDED by fact:… on … by …]`.
- **Hash chain check:** the `/audit/verify` endpoint recomputes the `fact.row_hash` chain and reports OK or the first broken link.
- CSV export. Monospace table, no charts, no summarisation.

### 6.11 Social Signal Classifier (stretch)
Claude Haiku classifies `social_posts` into `genuine_complaint | thank_you | sarcasm | forward | noise | media_report` and extracts location. Genuine, geocodable posts are matched to issues and shown as "also reported on social media (N)". They never create issues or findings.

---

## 7. API (FastAPI, `backend/app/`)

Base `/api`. JSON. Identity via `Authorization: Bearer <token>` from one of the three login panels (§16); no token means the public view. Language via `?lang=mr|en|hi`.

| Method | Path | Role | Returns |
|---|---|---|---|
| GET | `/wards` | public | List: code, name, budget, spend, utilisation, failed-fix ₹, open issues |
| GET | `/wards/{code}/money-trail` | public | §6.5 ward breakdown + summary + findings (public) |
| GET | `/wards/{code}/priorities` | public | §6.6 ranked list (public view: reasons, no officer notes) |
| GET | `/wards/compare` | public | Corporator comparison table |
| GET | `/works?ward=&contractor=&road=&finding=&sort=` | public | WO list with fact fields + finding chips |
| GET | `/works/{id}` | public | WO detail, linked complaints, road, findings, provenance |
| GET | `/works/near?lat=&lon=&radius=200` | public | Roads + WOs within radius |
| GET | `/roads/{id}` | public | Road card (C2) |
| GET | `/complaints/{id}` | public | Timeline (C1); PII-free |
| GET | `/contractors` · `/contractors/{id}/scorecard` | public | §6.5 |
| GET | `/findings?subject_type=&subject_id=` | public | Public findings (neutral text) |
| POST | `/ask` | public | §6.7 `{answer, lang, citations[], candidates[], rti_suggested}` |
| POST | `/rti-draft` | public | §6.8 `{text_mr, text_en, pio, fee, due_date}` |
| GET | `/source/{doc}/{row}` | public | Raw source row + sha256 (provenance chip target) |
| GET | `/officer/flags?ward=` | officer | Findings with officer framing ("risk flag"), sorted by severity, including review-queue counts |
| GET | `/officer/budget/{ward}` | officer | Full planner with factor detail, editable as-of date |
| POST | `/officer/draft-noting/{work_id}` | officer | §6.9 `{paras:[{n,text,citations[]}], blocked:[…], lang}` |
| GET | `/audit` · `/audit/export?format=csv` · `/audit/verify` | auditor | §6.10 |

**Finding (public) shape:**
```json
{
  "finding_id": "f_…", "rule": "dlp_breach", "polarity": "concern", "severity": "medium",
  "subject": {"type": "work_order", "id": "WO25-00042"},
  "text": "This road is still under the original contractor's warranty …",
  "metrics": {"cost_inr": 24500},
  "context": {"low_lying_ward": true, "heavy_rain_week": false},
  "evidence": [{"table": "work_orders", "id": "WO25-00042", "row": 42, "sha256": "ab12…"},
               {"table": "roads", "id": "RD0142", "row": 142, "sha256": "cd34…"}],
  "reply": null,
  "actions": ["rti"]
}
```
Public endpoints are serialised through `PublicFinding` Pydantic models that **exclude** officer-only fields. A test asserts that no public route returns the `flag_label` / noting fields.

---

## 8. Frontend (Next.js App Router + Tailwind + Leaflet)

- **Mobile-first** (360 px), Marathi default with an English/Hindi toggle in the header (next-intl, all UI strings in `messages/{mr,en,hi}.json`). Fonts: Noto Sans + Noto Sans Devanagari.
- **Provenance chip** (`<Source id=…/>`) next to every number. It opens a drawer with the source row, file hash and rule/extractor.
- **Synthetic-data banner** on every page.
- Charts: simple bar/stacked bars (Recharts), colour-blind safe, always with labelled values.
- Server components fetch the FastAPI backend (`NEXT_PUBLIC_API_URL`). The map is client-only and lazy-loaded.

| Route | Face | Content |
|---|---|---|
| `/` | Citizen | Search ("complaint ID, road or locality"), "Use my location", ward picker, Ask box, 3 headline city numbers |
| `/complaint/[id]` | Citizen | Timeline (C1), findings, RTI button, share |
| `/map` | Citizen | Ward polygons, road segments coloured by repairs this season / failed fixes / under warranty; tap → road card |
| `/road/[id]` | Citizen | Road card (C2) |
| `/ward/[code]` | Citizen/Corporator | Money trail, failed-fix ₹, funnel, findings, "What gets fixed next", printable summary (`?print=1`) |
| `/wards` | Corporator | Compare all wards |
| `/contractor/[id]` | Citizen | Scorecard, narrative, findings, clean-record badges, reply |
| `/ask` | Citizen | Chat-style single Q&A with citations |
| `/rti` | Citizen | Draft builder (prefilled from context), print / download |
| `/officer/[ward]` | Officer | Dense WO table (sort: DLP, SLA, findings), flag panel, evidence drawer, "Draft noting" editor |
| `/officer/[ward]/budget` | Officer | Planner with factor bars, method, cumulative ₹ vs 80% cap |
| `/audit` | Auditor | Monospace log table, filters, verify chain, export |

The officer routes (including the audit trail) need an officer login (§16). Their visual style is denser (desktop 1366×768).

---

## 9. Claude integration

### 9.1 Models
| Use | Model | Why |
|---|---|---|
| Complaint parsing, query intent, social classification | `claude-haiku-5-5` | Bulk, cheap, multilingual |
| Scorecard / ward narratives, bot answers, RTI particulars, file noting | `claude-sonnet-5-5` | Quality bilingual writing |

Configured in `backend/config.py` (env-overridable). `ANTHROPIC_API_KEY` comes from the environment only. Never commit it (`.env` is gitignored).

### 9.2 Calling conventions
- Structured JSON output (tool-use / JSON schema) for every extraction call, validated with Pydantic. Retry once on schema failure, then fall back to the deterministic path.
- Temperature 0 for extraction, 0.3 for narratives.
- Every call stores `extractor = "{model}/{agent}@{prompt_version}"` and `prompt_hash`.

### 9.3 Cache & cost
- Disk cache `backend/.cache/claude/{sha256(model+prompt+input)}.json`. Re-runs are free and deterministic for the demo.
- Full complaints (~6.5k) at batch 25 is ~260 Haiku calls. Run once and cache. The cache is gitignored by default, but since the data is synthetic, it may be shipped with the demo for offline runs.
- Concurrency limited to 4 with exponential backoff on 429/529.

### 9.4 "Model never invents numbers" check
For any narrative output: extract all numerals (incl. ₹, %, Devanagari digits ०–९) and verify each against the set of numbers in the input JSON (allowing formatting like lakh/crore and rounding to 0 decimals). Any mismatch → regenerate once, then fall back to the template text. The check is unit-tested.

---

## 10. Guardrails & fairness

| Principle | Implementation |
|---|---|
| Facts, not verdicts | Template-rendered public finding text, banned-word test, no composite score or rank |
| Model never writes facts | Claude → `claim`; only rules/humans → `fact`; unverified claims labelled and excluded from findings |
| Balance | Mandatory `clean_record` positive finding, strengths in every scorecard narrative |
| Context before blame | Low-lying ward and heavy-rain-week adjustments on cost, durability and drift, shown in `context` |
| Right of reply | Every contractor finding shows the reply slot |
| Evidence | Every finding/number → WO IDs + source row + file sha256 |
| Officer-only framing | "Risk flag" wording and file notings only on `/officer/*` |
| Privacy (DPDP) | `complainant_id` never exposed. Complaint pages show category, locality and dates only, with free text shown only after parsing. Exact GPS rounded to 3 decimals on public pages. |
| Synthetic disclaimer | Banner on every page and in every export/RTI footer ("demo data") |
| Reproducibility | `prompt_hash`, extractor/rule versions, source hashes on everything |

---

## 11. Repository layout

```
Ward_ledger/
├── SPEC.md  README.md  agents.md  context.md  DATA_DICTIONARY.md  STARTER_IDEAS.md
├── scripts/
│   └── fetch_data.sh                 # clones dataset into data/
├── data/                             # gitignored
├── backend/
│   ├── pyproject.toml                # fastapi, uvicorn, pandas, shapely, rapidfuzz, anthropic, pydantic, pytest
│   ├── config.py
│   ├── app/                          # FastAPI: main.py, routers/{public,officer,audit}.py, schemas.py
│   ├── pipeline/                     # load.py, run.py (CLI), geo.py
│   ├── agents/                       # complaint_parser.py, geocoder.py, linker.py, scorecard.py,
│   │                                 # budget.py, bot.py, rti.py, noting.py, social.py, claude_client.py
│   ├── rules/                        # promote.py, findings.py, config.yaml, templates/{en,mr,hi}.yaml
│   ├── prompts/                      # *.md, versioned
│   └── tests/
├── frontend/
│   ├── package.json                  # next, react, tailwind, leaflet, react-leaflet, recharts, next-intl
│   ├── app/                          # routes from §8
│   ├── components/                   # Source chip, FindingCard, Timeline, MoneyTrail, PriorityList, Map…
│   └── messages/{mr,en,hi}.json
└── .env.example                      # ANTHROPIC_API_KEY=, NEXT_PUBLIC_API_URL=http://localhost:8000/api
```

Run locally:
```bash
bash scripts/fetch_data.sh
cd backend && pip install -e . && python -m pipeline.run && uvicorn app.main:app --reload
cd frontend && npm i && npm run dev
```

---

## 12. Build milestones (hackathon day)

| # | Time | Milestone | Done when |
|---|---|---|---|
| M0 | 09:00–09:30 | Scaffold repo, fetch data, `.env` | Both servers start |
| M1 | 09:30–10:30 | Loader + `source_doc` + CSV facts | `fact` rows with source refs. `/works/{id}` works. |
| M2 | 10:30–12:00 | Findings rules (§6.4) + tests | All rules pass unit tests. `/findings` returns evidence. |
| M3 | 12:00–13:00 | Complaint parser (sample 200) + geocoder + linker | Funnel numbers on the ward page. Blank wards filled. |
| M4 | 13:00–13:30 | **First end-to-end pass** | Complaint ID → timeline in the browser |
| M5 | 13:30–14:30 | Scorecards + ward money trail + narratives | Contractor and ward pages render with number-check passing |
| M6 | 14:30–15:30 | Budget planner | Ranked list within 80% cap |
| M7 | 15:30–16:30 | Ask bot + RTI draft (citizen hero) | Bilingual RTI printable |
| M8 | 16:30–17:15 | Officer console + file noting | Cited noting with blocked unsourced paras |
| M9 | 17:15–17:45 | Audit log + verify + export | Chain verifies |
| M10 | 17:45–18:00 | Full complaint set run (cached), map polish, i18n pass | Feature freeze |
| — | 18:00+ | Seed demo path, backup video, rehearse | — |

Cut order if behind: social classifier → map colouring → audit verify → officer budget page → Hindi.

---

## 13. Acceptance criteria & verification

### 13.1 Automated (`pytest backend/tests`)
- **Loader:** row counts match DATA_DICTIONARY (work_orders 2,499; complaints 6,501; …). sha256 is stored. Re-running is a no-op.
- **Rules:** a hand-built fixture for each finding rule (positive + negative case, incl. context relaxation). `clean_record` fires for a contractor fixture.
- **Append-only:** UPDATE/DELETE on `fact` raises. Hash chain verifies, and tampering is detected.
- **Separation:** every public route's response contains no officer-only fields.
- **Language:** banned-word scan over all rendered public templates in en/mr/hi.
- **Number check:** a fabricated number in a narrative is rejected.
- **Budget:** allocation ≤ 80% of remaining. DLP roads cost ₹0 to BMC. Ranking is stable for a fixed as-of date.

### 13.2 Manual / end-to-end
- Pipeline on `complaints_sample_200.csv`, then the full set. Spot-check 20 parsed categories and 20 geocodes.
- Every finding and every narrative sentence with a number resolves to WO IDs via the provenance chip.
- Citizen pages are usable at 360 px width, in Marathi, on a throttled "Slow 3G" profile.
- Compare findings counts against the judges' answer key once published. Tune `rules/config.yaml`.

### 13.3 Demo script (3 minutes, citizen-led)
1. A citizen enters complaint **BMC25-xxxxxx** (seeded: pothole, fix failed, road under DLP). The timeline shows the contractor, ₹ billed, "failed within 30 days", and "road under warranty, billed to BMC".
2. Tap **Request documents (RTI)** → bilingual Section 6(1) draft, PIO, fee and due date → print.
3. Ward page: "₹X of this ward's monsoon budget went to repairs that failed within 30 days". Then **What gets fixed next** with plain reasons (school, flood spot).
4. Contractor page: fair scorecard with context adjustment and a clean-record badge in another ward. No grades.
5. Switch role → officer: the same WO shows numbered risk flags → **Draft noting** → cited Marathi note-sheet. Switch to auditor: the same figure traces to the CSV row and sha256.

---

## 14. Open questions & risks

| # | Item | Mitigation |
|---|---|---|
| 1 | Answer-key definitions (overrun %, double-billing window) are unknown | Keep thresholds in `config.yaml`, document the chosen values, report counts per rule |
| 2 | Claude cost / rate limits on 6.5k complaints | Haiku, batches of 25, disk cache, keyword fallback, `--sample` mode |
| 3 | Rate card methods vs `work_type` mapping may be incomplete | Unknown methods → `cost` findings skipped and logged in the review queue |
| 4 | Severity not explicit in complaints | Derived from category + SLA hours (§4.4); documented |
| 5 | Voronoi ward polygons are approximate | Label as approximate; prefer the dataset `ward_code` when present |
| 6 | Defamation perception even with synthetic data | Neutral templates, no ranks, right of reply, synthetic banner |
| 7 | Marathi quality of generated text | Templates for all structured text; Claude only for narrative; native-speaker review of templates |
| 8 | RTI PIO details vary by ward/department | Disclaimer: verify before filing |

---

## 15. Implementation status (what was built, and where it differs from the text above)

### 15.1 Run it
```bash
bash scripts/fetch_data.sh                       # dataset -> data/
cd backend && python -m venv .venv && .venv/Scripts/pip install -e ".[test]"
.venv/Scripts/python -m pipeline.run --force     # ~6 s: load, parse, geocode, promote, link, findings, planner
.venv/Scripts/python -m uvicorn app.main:app --port 8000
cd ../frontend && npm install && npm run dev     # http://localhost:3000
cd ../backend && .venv/Scripts/python -m pytest  # 57 tests
cd ../frontend && node scripts/check-i18n.mjs && npx tsc --noEmit
```
Log in from the header with one of the three panels (§16); browsing needs no login. Demo accounts: `python -m live.seed --demo --tickets`.
No `ANTHROPIC_API_KEY` is needed: every Claude path has a deterministic fallback (§9).

### 15.2 Built and verified
All of §6.1-6.10, the API in §7 and the routes in §8 (except `/ask` is a page, plus `/contractors`).
Verified by 57 backend tests (rules on fixtures, append-only and tamper detection, public/officer separation,
banned-word scan, number guard, budget cap, concurrency), an i18n key check (427 keys x 3 languages), `tsc`,
and a real-browser pass over every page (console errors, failed requests, screenshots at 360 px and 1366 px).

Headline numbers on the synthetic data: 45 `possible_double_billing` (exactly the 45 work orders with no linked
complaint), 114 `rate_card_overrun`, 493 `dlp_breach`, 9 `clean_record` (contractor x ward), 3,165 issues from 6,501
complaints, 435 issues with no repair linked, and ₹3.07 Cr of ₹13.4 Cr billed on repairs that failed within 30 days.

### 15.3 Deviations (the code is right; the earlier text is superseded)
| Area | Spec said | Built | Why |
|---|---|---|---|
| Complaint categories | List in §6.1 | The dataset's own 6 categories + `Other` | The data uses "Open or broken manhole", "Broken paver blocks", etc. |
| Category promotion | Two sources agree, or conf >= 0.85 | Also promotes when the parsed category matches the **linked work order's `work_type`** | The data contains many more mislabelled complaints than the stated 18%; the WO is an independent BMC record. 1,530 claims still go to the review queue. |
| Road snapping | Within max(200 m, uncertainty) | Only from **GPS** (<= 60 m accuracy); never from a locality name | Never claim precision the source lacks (§1.3). WO-linked complaints take the WO's road. |
| `clean_record` | >= 90% on time; zero overrun, double-billing **or DLP** | >= 70% on time (city average is 50%); no overrun, double-billing **or drift** findings; DLP **not** counted | 90% certifies nobody; `roads.csv` has no original-contractor field, so a DLP bill is not attributable to a contractor. |
| `dlp_breach` severity | Medium | Medium for surface repairs, **low** for drainage/desilting | A road-surface warranty may not cover drain work. |
| Scorecard wording | One strength, one improvement | A strength is named **only if** the contractor meets/beats the expected level, otherwise "closest to the expected level"; same for "to improve" | Calling the least-bad metric a strength is misleading (found and fixed during build). |
| Planner rain factor R | 7-day rainfall before as-of | Same, but the as-of date is a parameter | At the default as-of (2025-10-05) R is ~0; try `as_of=2025-07-08` (heavy-rain spell). |
| Planner rationale | Template + optional Claude polish | Template only | Numbers must come from the model of record; polish adds risk without value. |
| Narratives | Claude Sonnet | Claude if a key is set **and** the output passes the number/neutrality guard; otherwise a localized template | Works offline; guaranteed neutral. **The live Claude paths are untested here (no API key in the build environment)**; they are covered only by the guard unit tests. |
| Complaint timeline | Not specified | Events sorted chronologically; a note when a report was filed *after* the work was completed (364 complaints) | The raw order contradicted itself. |
| Frontend libs | next-intl, Recharts, SWR-style | Small custom i18n context, CSS bars, a `useApi` hook | Smaller JS for 3G; no extra dependencies. |
| Map | Leaflet | Leaflet; colour = repair failure **rate**, dashes = warranty, thickness = open issue | "Any failed repair" coloured almost every road. |
| Audit `ward` filter | - | Takes `K/E` (slash) while other routes also accept `K-E` | Known inconsistency (audit page uses a plain text field). |

### 15.4 Known limits
- Not exercised: live Claude calls (§15.3), offline photo queue, SSO / SMS OTP, official ward boundaries (Voronoi approximation).
- The review queue is large (about 1,700 pending) because every disagreement between a parsed claim and its sources is queued, by design.
- Thresholds in `backend/rules/config.yaml` are starting values; tune against the judges' answer key once published.
- The `POST /api/rti-draft` text is for demonstration only (synthetic records); PIO details must be verified before real use.

---

## 16. Accounts, complaint tickets and tasks (the DFD workflow)

Implements the supplied data-flow diagrams: three login processes (1.1 Citizen, 1.2 Officer, 1.3 Contractor) replacing
"1.0 User Authentication", and 2.0 Raise Complaint → 3.0 Verify → 4.0 Assign Contractor → 5.0 Submit Repair Report →
6.0 Review & Update Status, over a User database (D1), Complaint database (D2) and Repair Evidence & Bills store (D3).

### 16.1 Logins and roles
- **No login is ever needed to browse.** The citizen login appears only when someone raises a complaint; the officer and
  contractor panels are reached from **Log in**. Each role, once logged in, lands on its own panel and still sees every
  public page.
- **Three panels, one user table** (`app_user`, role ∈ citizen | officer | contractor). Each panel's endpoint
  (`POST /api/auth/{role}/login`) authenticates only that role. Citizens self-register with a mobile number and password
  (purpose stated at capture, consent required; the number is never shown publicly and the API only returns it masked).
  Officers and contractors are provisioned; contractor accounts are linked to an empanelled `contractor_id`.
- Passwords: scrypt with a per-user salt. Sessions: random bearer tokens stored only as SHA-256, with expiry (citizen 14
  days, officer 12 h, contractor 3 days) and revocation on logout. Failed logins are throttled (5 per 15 minutes per
  account) and errors never reveal whether an account exists.
- The client cannot claim a role: the old `X-Role` header is ignored and role checks run server-side on every request.
- **Separation of duties:** officer accounts with `can_act = 0` (the seeded Chief Auditor account) can see the console and
  audit trail but cannot verify, assign, approve or promote anything, and receive no operational notifications.

### 16.2 Complaint ticket (`CMP-000001`) and task (`TSK-000001`) lifecycles
| Ticket status | Set by | Next |
|---|---|---|
| `submitted` | Citizen raises it: category, description, 1 to 5 locations (GPS or map pins) and/or a locality, up to 6 photos and 2 videos | `verified`, `rejected` or `duplicate` (officer) |
| `verified` | Officer, who may correct the category, and sees our parser's reading of the text and nearby possible duplicates | `assigned` when put in a task |
| `assigned` → `in_progress` → `work_submitted` | Officer creates a task; contractor starts it; contractor submits the repair report | Officer review |
| `resolved` | Officer approves the task's report: **every complaint in the task, and complaints closed as duplicates of them, are resolved and their citizens notified** | Final |
| `rejected` / `duplicate` | Officer, with a reason: not a BMC road, not a road issue, not enough information, duplicate of CMP-x, or other (with a note) | Final; a duplicate resolves with its original |

A task bundles one or more verified complaints **from one ward** for one contractor: `assigned → in_progress → submitted
→ completed`, or `submitted → rework` (sent back with a reason) → resubmitted, or `cancelled` (its complaints return to
the verified pool). A complaint can be in only one active task; this is re-checked inside the write lock.

### 16.3 Accountability built into the workflow
- **Pre-award checks** (the Risk Flagger of agents.md §9) when the officer picks a contractor: on-time rate and 30-day
  durability against what is expected for the same mix of jobs, past bills above the rate-card range, findings in this
  ward, a clean-record certificate where earned, and any complaint whose road is still under another contractor's
  warranty (DLP). The suggested method has the lowest observed reopen rate, with no cold mix on busy roads. The estimate
  is the rate card × typical area in the ward, and the due date is the SLA of the most urgent complaint. The checks shown
  are recorded in the task's log.
- **Report checks** when the contractor submits: bill vs standard rate for the reported method and area (the same 1.30×
  rule as §6.4), bill vs task estimate, DLP roads, and missing evidence or bill documents. Neutral statements, never verdicts.
- The approved bill becomes public on the complaint once the officer approves (award values are public). Pending bills
  and bill documents never are.
- Contractors reply to findings about their own firm from their panel, and the reply is shown next to the finding.

### 16.4 Privacy and evidence
- Public views never include the citizen's identity. Descriptions are scrubbed of phone numbers, e-mail addresses and
  vehicle registration numbers, and locations are rounded to about 100 m. The owner, officers and the assigned contractor
  see the exact points and the original text.
- File types are decided by content (magic bytes), with size and count limits. Photo originals keep their metadata
  internally; the **only** public copy is re-encoded with orientation applied and EXIF/GPS removed. Videos and bills are
  never public. Private files are served through 1-hour HMAC-signed links (`Content-Security-Policy: sandbox`, `nosniff`).
- Photos of rejected complaints are not public. Repair after-photos become public when the work is approved.
- A citizen photo is an inspection prompt, not proof (stated on the form).

### 16.5 Records
- Live tables (`app_user`, `auth_session`, `ticket`, `ticket_location`, `media`, `task`, `task_ticket`, `repair_report`,
  `notification`, `ticket_event`) are created on API start and are **never** dropped by `pipeline.run --force`.
- `ticket_event` is the tracking log for both tickets and tasks: append-only (UPDATE and DELETE blocked by triggers) and
  hash-chained like `fact`. Every write takes SQLite's write lock first (`BEGIN IMMEDIATE`), so concurrent requests cannot
  fork the chain or reuse IDs. Officers verify it from the audit trail (`GET /api/audit/live/verify`).
- In-app notifications, stored as kind + parameters and rendered in the reader's language, implement the DFD's
  acknowledgement, verification-status, assignment and resolution flows.

### 16.6 API (additions)
`POST /api/auth/{citizen|officer|contractor}/login`, `POST /api/auth/citizen/register`, `POST /api/auth/logout`, `GET /api/auth/me` ·
`GET|POST /api/tickets`, `GET /api/tickets/{id}`, `POST /api/tickets/{id}/verify|reject` ·
`GET|POST /api/tasks`, `POST /api/tasks/preview`, `GET /api/tasks/{id}`, `POST /api/tasks/{id}/start|report|approve|send-back|cancel` ·
`GET /api/me/notifications`, `POST /api/me/notifications/read` · `POST /api/contractor/reply` ·
`GET /api/media/{id}/public|original` · `GET /api/live/options` · `GET /api/audit/live`, `GET /api/audit/live/verify`.

### 16.7 Verification
`backend/tests/test_live.py` covers:
- panel and role isolation, registration rules, logout, throttling, hashed storage, and public browsing with bogus tokens;
- uploads: a planted EXIF marker is absent from the public copy, orientation is kept, the original is retained, HTML
  disguised as a JPEG is rejected, and limits are enforced;
- signed links: tampered and expired links are refused, and videos are never public;
- PII scrubbing; verification by acting officers only; duplicates resolving with their original;
- the full assign → report → approve flow resolving every complaint; send-back and cancel; notifications; contractor
  right of reply;
- tamper detection on the event log, live data surviving a pipeline rebuild, and 8 concurrent complaints without a
  forked log or duplicate IDs.

Mutation checks: re-introducing EXIF in public copies, letting the auditor act, making videos public, or trusting `X-Role`
again each make the suite fail. `frontend/e2e/workflow.mjs` drives the whole DFD in a real browser.

### 16.8 Not done
SMS OTP or SSO; e-mail or SMS notifications (in-app only); the offline photo queue; a citizen "the problem came back"
reopen within 30 days (the natural next step for the durability metric); RTI drafts for `CMP-` complaints (RTI covers the
2025 records).
