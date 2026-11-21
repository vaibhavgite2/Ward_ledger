# The Ward Ledger — Agent Architecture

> This document defines every AI agent in the system: what it does, what it reads, what it writes, its tools, its guardrails, and how it fits into the pipeline.

---

## Architectural Principle

The model **never writes facts**. It produces **claims**. A separate promotion step — by rule or named human — creates facts. All agents operate within this boundary.

```
Ingest Agents → Extraction Agents → Resolution Agents → Promotion Layer → Serving Agents
                                                              ↕
                                                       Human Review Queue
```

---

## Agent Index

| # | Agent | Layer | Writes To | Trigger |
|---|---|---|---|---|
| 1 | Harvester | Ingest | `source_doc` store | Scheduled / manual |
| 2 | OCR Extractor | Extraction | `claim` table | New `source_doc` |
| 3 | Vision Table Reconstructor | Extraction | `claim` table | OCR output |
| 4 | Complaint Parser | Extraction | `parsed_complaint` | New complaint row |
| 5 | Social Signal Classifier | Extraction | `parsed_social` | New social post |
| 6 | Geocoder | Resolution | `work_record.geom` (claim) | Parsed location text |
| 7 | Entity Resolver | Resolution | `contractor` canonical + adjudication queue | New contractor mention |
| 8 | Rule Engine | Promotion | `fact` (auto) + `review_queue` | Nightly / on-demand |
| 9 | Risk Flagger | Officer Console | `flag` (officer-only) | Pre-award trigger |
| 10 | File Noting Drafter | Officer Console | Draft text (never committed) | Officer action |
| 11 | RTI Draft Generator | Citizen / Audit | Draft RTI text | Citizen action |
| 12 | Budget Planner | Officer / Citizen | Recommendation (advisory only) | On-demand |
| 13 | Citizen Accountability Bot | Citizen | Natural-language reply | Citizen query |
| 14 | Audit Trail Renderer | Audit | Read-only export | Auditor request |

---

## 1. Harvester Agent

**Role:** Collect, deduplicate, and hash-address source documents.

**What it does:**
- Polls BMC tender portal, work-order publications, budget books, GIS layers
- Downloads PDFs/CSVs, computes `sha256` content hash
- Skips if hash already in `source_doc` store (immutable, never re-harvests same bytes)
- Stores: `{doc_id: sha256, url, fetched_at, doc_type}`

**Reads:** External URLs (BMC portal, GIS feeds)  
**Writes:** `source_doc` table (append-only)  
**Tools:** HTTP fetch, file hash  
**Guardrails:**
- No login credentials stored in-process — env-injected only
- If live portal unavailable: use staged PDFs from `data/` directory
- Never modifies a stored document

**Hackathon shortcut:** Pre-stage ~30 real PDFs from K/East ward. Skip live harvesting.

---

## 2. OCR Extractor Agent

**Role:** Extract text spans with positions from scanned PDFs.

**What it does:**
- Runs layout-aware OCR on each page of a `source_doc`
- Preserves bounding boxes for every text span
- Handles mixed Devanagari + English (keeps bilingual labels as-is, e.g. `दोष दायित्व कालावधी`)
- Emits raw text spans → feeds Vision Table Reconstructor for tabular pages

**Reads:** `source_doc` bytes  
**Writes:** `claim` rows with `extractor='ocr-v{n}'`, `page_no`, `bbox`, `confidence`  
**Tools:** OCR engine (Tesseract / cloud OCR)  
**Guardrails:**
- Never translates Marathi labels — keeps originals as first-class fields
- Confidence below 0.4 → `value_text` stored but rendered as "unverified" in UI
- Prompt hash stored with every claim for reproducibility

---

## 3. Vision Table Reconstructor Agent

**Role:** Recover table structure that OCR destroys.

**What it does:**
- Receives pages flagged as tabular (detected by layout analysis)
- Sends page image to Claude Vision with structured prompt: "identify rows, columns, cell values and their bounding boxes"
- Reconciles with OCR text spans
- Emits one claim per cell: `field_path='table.{row}.{col}'`, `value_text`, `bbox`
- Key targets: item/quantity/rate/amount tables in work orders; awarded amounts in tenders

**Reads:** Page images from `source_doc`  
**Writes:** `claim` table with `extractor='claude-vision-v{n}'`  
**Tools:** Claude Vision API (multimodal)  
**Guardrails:**
- Never infers a value not visually present in the image
- If cell is ambiguous → `confidence < 0.5`, flag for human review
- `prompt_hash` logged with every batch for model-version audit trail

---

## 4. Complaint Parser Agent

**Role:** Clean, classify, and geocode raw citizen complaints.

**What it does:**
- Parses free-text descriptions across en / hi-en / mr / hi
- Re-classifies complaint category (18% are wrong in source data)
- Deduplicates across channels (same issue reported via app + helpline + social)
- Geocodes `locality_text` → `(lat, lon)` using `localities.csv` gazetteer + alias matching
- Fills blank `ward_code` (~7% of rows) from geocoded coordinates + ward polygons
- Links cleaned complaint to `work_orders.linked_complaint_ids`

**Reads:** `complaints.csv`, `localities.csv`, `wards.geojson`, `work_orders.csv`  
**Writes:** `parsed_complaint` table, links to `work_orders`  
**Tools:** Claude (multilingual NLP), PostGIS point-in-polygon  
**Guardrails:**
- Duplicate detection: same location + same category within 48h = candidate duplicate, not auto-merge
- Geocoding uncertainty stored: `geocode_confidence`, `geocode_method`
- Social posts are **not** treated as complaints unless cross-referenced with app/helpline data
- Citizen PII: anonymised `complainant_id` only, never stored with location

**Prompt template:**
```
You are a BMC complaint analyst. Given this complaint text, output:
1. Canonical category (from: Pothole | Waterlogging | Open manhole | Drain overflow | Road cave-in | Road damage | Other)
2. Confidence (0-1)
3. Locality mentioned (exact text)
4. Language detected
5. Is this a duplicate of another complaint? (Y/N — only if complaint_ids provided)
One-line reason for each. Do not add information not in the text.
```

---

## 5. Social Signal Classifier Agent

**Role:** Filter genuine civic signals from social noise.

**What it does:**
- Classifies each social post: `genuine_complaint | thank_you | sarcasm | forward | noise | media_report`
- Extracts: location mention, issue type, urgency indicators
- Cross-references with complaints: does a matching complaint exist?
- If no complaint exists and post appears genuine + high engagement → surface to officer queue

**Reads:** `social_posts.csv`, `parsed_complaint`  
**Writes:** `parsed_social` with classification + confidence  
**Tools:** Claude (sentiment, language detection, entity extraction)  
**Guardrails:**
- Output is **signal only** — never feeds directly into work order creation
- Posts with engagement < 5 and no geocodable location → low priority
- Anonymised author handles only — no PII linkage

---

## 6. Geocoder Agent

**Role:** Translate prose location descriptions into spatial geometries.

**What it does:**
- Input: "resurfacing of road from X Junction to Y Marg, Ward K/East"
- Output: `LINESTRING` geometry (not a point) + `uncertainty_m`
- Uses: `localities.csv` aliases, `roads.geojson` name-matching, ward polygon containment check
- Citizen pin → buffer → candidate work orders → citizen confirmation step

**Reads:** `localities.csv`, `roads.geojson`, `wards.geojson`  
**Writes:** `work_record.geom` (as a claim, not a fact until promoted)  
**Tools:** PostGIS, string similarity (`pg_trgm`), Claude (parse location prose)  
**Guardrails:**
- Always stores `uncertainty_m` alongside coordinates
- Never asserts a point precision not supported by the source text
- Ambiguous locations → candidate list for human confirmation, not auto-resolved

---

## 7. Entity Resolver Agent

**Role:** Canonicalise contractor identities across messy name variations.

**Decision hierarchy (hard keys first):**
1. **GSTIN match** → PAN at chars 3–12 → same legal entity (definitive)
2. **Registered address** exact match
3. **Trigram similarity** on normalised name (strip: Pvt Ltd, Co, Works, &, punctuation)
4. **Below threshold** → `adjudication_queue` (human review)

**What it does:**
- For each new contractor mention, run hierarchy top-down
- If resolved → link to canonical `contractor_id`
- If unresolved → insert into `adjudication_queue` with similarity candidates ranked
- **Demo the adjudication queue** — it's the signal to municipal audiences that you understand defamation risk

**Reads:** `contractors.csv`, `claim.value_text` (contractor names), external GSTIN registry (Phase 1+)  
**Writes:** `contractor` canonical table, `adjudication_queue`  
**Tools:** `pg_trgm`, PostGIS, Claude (name normalisation)  
**Guardrails:**
- Never auto-merges without hard key match
- Adjudication queue entries are visible to officers before any scorecard computes
- Flagged firms get right-of-reply field attached to their canonical record

---

## 8. Rule Engine (Promotion Agent)

**Role:** Auto-promote claims to facts where rules are satisfied; queue the rest for human review.

**Auto-promotion rules:**
- Two independent documents agree on the same `field_path` value within tolerance → promote as `rule:two-source-agree`
- SLA breach: `completed_at - assigned_at > sla_hours` → fact, cited from `work_orders.csv`
- DLP breach: `road.under_dlp = Y` AND new `work_order` on same `road_id` → flag fact
- Reopened: `reopened_within_30d = Y` → durability claim promoted immediately

**What it does:**
- Runs nightly and on-demand
- For each unresolved claim group: check all promotion rules
- Passes → `fact` row with `promoted_by='rule:...'`, `promoted_at`, `from_claim`
- Fails → `review_queue` row with candidate claims for human

**Reads:** `claim`, `work_orders`, `roads`, `wards`  
**Writes:** `fact` (append-only), `review_queue`  
**Tools:** SQL rule evaluation, Python rule engine  
**Guardrails:**
- Facts never overwritten — corrections create new fact row with `supersedes=` pointer
- Rule version logged in `promoted_by` field
- Human promotions logged with officer ID: `promoted_by='user:ae-4471'`

---

## 9. Risk Flagger Agent

**Role:** Compute pre-award risk flags for officer console only. Never public.

**Flags computed** (each citing its supporting facts + source docs):

| Flag | Logic |
|---|---|
| `cost_overrun_history` | `final_bill > awarded_amount * 1.15` on ≥2 prior `work_orders` for this `contractor_id` |
| `silent_extension` | `completed_at` slipped AND no LD penalty in `work_orders.engineer_remark` |
| `related_bidders` | Shared PAN-within-GSTIN OR shared address across bidders on same tender |
| `dlp_breach` | New WO on `road_id` where `roads.under_dlp = Y` |
| `single_bid_award` | Qualified bid count < 3 |
| `estimate_drift` | `cost_inr / area_sqm > ward_median_rate * 1.20` for same `repair_method` |
| `clean_record` | No flags across ≥3 completed WOs, bills within 5% of rate card |

**Output format:** Numbered flag list, each with: flag name | triggering facts | source documents | page refs  
Never: a composite score. Never: shown on citizen face.

**Reads:** `fact`, `work_orders`, `roads`, `contractors`, `rate_card`  
**Writes:** `flag` table (officer-only, non-public)  
**Tools:** SQL aggregation, Claude (narrative generation)  
**Guardrails:**
- Output stays inside officer console — never serialised to citizen API
- Positive `clean_record` flag is mandatory — system must balance accusation with certification
- Context adjustment: low-lying ward + heavy-rain week → `estimate_drift` threshold relaxed

---

## 10. File Noting Drafter Agent

**Role:** Draft the note-sheet paragraph an officer submits to file.

**What it does:**
- Given a `work_id` or `contractor_id`, assembles all relevant facts + flags
- Drafts a formal note-sheet paragraph in the format the BMC office already uses
- Each assertion is a numbered sub-para citing: document name, page number, highlighted bbox ref
- Bilingual: Marathi paragraph by default, English toggle
- Output is a **draft** — officer reviews, edits, and signs; system does not submit

**Output structure:**
```
Para 1: Work reference, contractor, awarded amount [Doc: WO25-00042, p.3]
Para 2: Flag 1 — cost overrun on prior work [Doc: WO25-00018, p.7; WO25-00031, p.4]
Para 3: Flag 2 — DLP breach on RD0142 [Doc: roads-dlp-register, p.12]
Para 4: Recommendation (accept / conditional / refer to committee)
```

**Reads:** `fact`, `flag`, `source_doc` (for page refs), `work_orders`  
**Writes:** Draft text only — to officer session, never to `fact` table  
**Tools:** Claude (long-form bilingual drafting), citation formatter  
**Guardrails:**
- Every assertion must have a `from_claim` → `source_doc` + `page_no` chain
- Unsourced assertions are blocked — cannot appear in draft
- Officer must explicitly submit; system never auto-files

**Value prop:** Saves ~40 minutes per file review. This is the demo's climax.

---

## 11. RTI Draft Generator Agent

**Role:** Draft a ready-to-file RTI application for a citizen.

**What it does:**
- Given a complaint or work order of interest, drafts Section 6(1) RTI application
- Pre-fills: correct Public Information Officer for the ward/department, fee (₹10), 30-day clock, first-appeal path
- Requests specific documents: tender notice, work order, measurement book, completion certificate, contractor payment record
- Output: printable draft in Marathi + English

**Reads:** `work_orders`, `wards`, `parsed_complaint`, `fact`  
**Writes:** Draft text only — to citizen session  
**Tools:** Claude (legal drafting, bilingual), RTI PIO directory lookup  
**Guardrails:**
- Entirely lawful — requests only public information
- Never asserts fraud — draft requests documents "for citizen verification"
- Accuracy note: PIO details change; advise citizen to verify current officer before filing

---

## 12. Budget Planner Agent

**Role:** Recommend where the next rupee should go in a ward.

**Scoring model** (transparent, not black-box):

```
Priority Score = Σ weighted factors:
  + complaint_severity (1–5)          × 0.25
  + flood_hotspot_overlap             × 0.20
  + rainfall_risk (current season)    × 0.15
  + accident_severity_on_road         × 0.15
  + hospital/school proximity         × 0.10
  + congestion_index                  × 0.10
  + days_since_last_repair            × 0.05

Context discounts:
  - road under_dlp → deprioritise (fix is contractor's cost)
  - method durability → prefer hot mix / mastic over cold mix for high-traffic roads
  - remaining_budget constraint enforced
```

**Output:** Ranked list of open issues, recommended repair method, estimated cost vs rate card, rationale in plain language.

**Reads:** `work_orders`, `complaints` (open/unlinked), `roads`, `flood_hotspots`, `rainfall_daily`, `tides`, `accidents`, `facilities`, `traffic`, `rate_card`, `wards` (budget remaining)  
**Writes:** `budget_recommendation` (advisory, versioned, not a fact)  
**Tools:** Claude (narrative + scoring), Python (weighted scoring), PostGIS (proximity)  
**Guardrails:**
- Context-adjusted: low-lying ward flag reduces weight of estimate_drift flags
- Heavy-rain week flag reduces expected durability of cold-mix patches → upgrade recommendation
- Always shows remaining budget and assumes no more than 80% allocation at once

---

## 13. Citizen Accountability Bot

**Role:** Answer a citizen's question about their complaint or a road in plain language.

**What it does:**
- Input: complaint ID, or free-text query ("What happened to my pothole complaint on SV Road?")
- Resolves to complaint → linked work order → contractor → cost → SLA outcome → DLP status
- Answers in the citizen's language (Marathi default, en/hi/hi-en supported)
- If complaint was never fixed: says so, offers RTI draft

**Example output:**
> "तुमची तक्रार BMC25-003412 ही Sahyadri Infra Works यांना दिली होती. काम 7 जुलैला पूर्ण झाले. खर्च: ₹24,500. SLA पूर्ण: होय. 30 दिवसांत पुन्हा उघडले: नाही. हा रस्ता अजून Defect Liability Period मध्ये आहे."

**Reads:** `parsed_complaint`, `work_orders`, `fact`, `contractors`, `roads`  
**Writes:** None (read-only)  
**Tools:** Claude (multilingual generation), complaint-to-WO linker  
**Guardrails:**
- Only surfaces facts already public (award value, completion date, penalty levied)
- Never infers fraud from data — describes facts only
- If data is missing: "We don't have this information yet. You can file an RTI." + RTI draft link

---

## 14. Audit Trail Renderer Agent

**Role:** Produce the immutable, boring, chronological log that an auditor trusts.

**What it does:**
- Renders the full fact chain for a work record: every promoted fact, with its claim, source doc, page, extractor, promoter, timestamp
- Filterable by: ward, contractor, date range, field path
- Exportable as CSV/PDF
- Corrections shown inline as: `[SUPERSEDED by fact_id:xyz on 2025-08-14 by user:ae-4471]`

**Design rule:** If it looks designed, it looks editable. It must look like a log.

**Reads:** `fact`, `claim`, `source_doc`, `work_record`  
**Writes:** None (read-only export)  
**Tools:** SQL queries, PDF renderer  
**Guardrails:**
- Hash verification on every exported fact chain
- No summarisation, no interpretation — raw log only
- Export includes `extractor_version` and `prompt_hash` for every extracted value

---

## Agent Workflow Map

### Pre-Award Officer Flow

```
Officer selects tender → Risk Flagger runs →
  Flags display (numbered, cited) →
    File Noting Drafter generates draft →
      Officer edits + signs → File submitted (outside system)
```

### Citizen Complaint-to-Answer Flow

```
Citizen drops pin / enters complaint ID →
  Complaint Parser resolves location →
    Citizen Accountability Bot queries fact table →
      Returns bilingual summary →
        [optional] RTI Draft Generator → printable application
```

### Ingest-to-Fact Pipeline Flow

```
Harvester fetches PDF →
  OCR Extractor + Vision Table Reconstructor emit claims →
    Geocoder resolves location claims →
      Entity Resolver canonicalises contractor claims →
        Rule Engine auto-promotes agreeing claims →
          Human review queue for disagreements →
            Facts promoted → available to all serving agents
```

### Budget Planning Flow

```
Officer selects ward →
  Budget Planner reads: open complaints + roads + risk layers + remaining budget →
    Scoring model ranks open issues →
      Context-adjusted recommendations with method and cost →
        Officer reviews and assigns work orders (outside system)
```

---

## Data Access Matrix

| Agent | work_orders | complaints | roads | contractors | rate_card | wards | flood/rain/tides | accidents | facilities | traffic | source_doc | claim | fact | flag |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Harvester | — | — | — | — | — | — | — | — | — | — | W | — | — | — |
| OCR Extractor | R | — | — | — | — | — | — | — | — | — | R | W | — | — |
| Vision Reconstructor | — | — | — | — | — | — | — | — | — | — | R | W | — | — |
| Complaint Parser | R | R/W | — | — | — | R | — | — | — | — | — | W | — | — |
| Social Classifier | — | R | — | — | — | — | — | — | — | — | — | W | — | — |
| Geocoder | R | R | R | — | — | R | — | — | — | — | — | W | — | — |
| Entity Resolver | R | — | — | R/W | — | — | — | — | — | — | — | W | — | — |
| Rule Engine | R | — | R | R | R | R | — | — | — | — | — | R | W | — |
| Risk Flagger | R | — | R | R | R | R | R | R | R | R | R | — | R | W |
| File Noting Drafter | R | — | — | R | — | — | — | — | — | — | R | — | R | R |
| RTI Generator | R | R | — | — | — | R | — | — | — | — | — | — | R | — |
| Budget Planner | R | R | R | — | R | R | R | R | R | R | — | — | R | — |
| Accountability Bot | R | R | R | R | — | — | — | — | — | — | — | — | R | — |
| Audit Renderer | R | — | — | R | — | — | — | — | — | — | R | R | R | — |

**Key:** R = Read, W = Write, — = No access  
`flag` table: **officer-console only** — no citizen or public API access

---

## Frontend Agents (UI Logic)

### Officer Console Frontend
- **State:** Session-scoped, no persistent citizen data
- **Components:** Work-order table (sortable by DLP expiry, SLA deadline), Flag panel (numbered, cited), Draft noting editor (pre-filled by agent, editable), Source-page viewer (PDF with bbox highlight overlay), Marathi/English toggle (shell-level, all labels switch)
- **API calls:** `GET /works?ward={}&sorted_by=dlp_expiry`, `GET /flags/{work_id}`, `POST /draft-noting/{work_id}`, `GET /source/{doc_id}?page={}&bbox={}`

### Citizen Window Frontend
- **State:** Anonymous browse; authenticated for photo filing
- **Components:** Map (ward polygons + road segments), Pin-drop → candidate work list → confirm, Work summary card (plain language, bilingual), Photo capture (in-app only, offline queue), RTI draft button
- **API calls:** `GET /works/near?lat={}&lon={}&radius=200`, `GET /work/{id}/summary?lang=mr`, `POST /citizen-report` (authenticated), `GET /rti-draft/{work_id}`
- **Performance target:** Works on 2GB Android, 3G, offline photo queue with sync on reconnect

### Audit Trail Frontend
- **State:** Read-only, authenticated auditor
- **Components:** Chronological log table, Filters (ward / contractor / date / field_path), Hash verification panel, CSV/PDF export
- **API calls:** `GET /audit?ward={}&contractor={}&from={}&to={}`, `GET /audit/{work_id}/chain`, `GET /audit/export?format=csv`

---

## Backend Agents (API + DB Logic)

### Core API (FastAPI)
- **`/works`** — Read-only work records with facts (never raw claims)
- **`/claims`** — Auditor-only endpoint; returns full provenance chain
- **`/flags`** — Officer-only; risk flags with citations
- **`/draft-noting`** — Generates and returns draft text; never persists
- **`/rti-draft`** — Generates RTI application text
- **`/citizen-report`** — Accepts photo + location + description; queues for review
- **`/audit`** — Append-only log queries

### DB Layer
- PostgreSQL + PostGIS (ward polygons, road geometries, point-in-polygon, buffer queries)
- `pg_trgm` (contractor name similarity)
- Append-only `fact` and `source_doc` tables — no UPDATE or DELETE allowed at DB level
- Hash chain enforced by DB trigger on `fact.supersedes`

---

## Administration Agent (Human-in-Loop)

### Review Queue Dashboard (Internal)
- Shows: unresolved claims, adjudication queue entries (contractor identity), low-confidence extractions, citizen photo reports awaiting triage
- Actions: Approve promotion, Reject claim, Merge contractor records, Assign inspection
- Audit log: every human action logged with officer ID and timestamp
- **This dashboard is the safety valve** — no fact enters the system without either a rule or a named human

---

## Guardrails Summary

| Principle | Implementation |
|---|---|
| Model never scores | Only flags (binary) with citations — no composite score |
| Model never facts | All LLM output is `claim` → promotion required |
| Citizen photo ≠ evidence | Framed as inspection trigger; noted in UI copy |
| Public face = public facts | Citizen API filters to only promoted, public-domain facts |
| Defamation protection | Scores stay in officer console; right-of-reply on every flag |
| Reproducibility | `prompt_hash` + `extractor_version` on every claim |
| Auditability | Append-only, hash-chained, corrections supersede |
| Data minimisation | Citizen PII stripped at render; EXIF retained internally only |
