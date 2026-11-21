# The Ward Ledger — Developer & Project Guide

> **Project Name:** The Ward Ledger (Follow the Rupee: Mumbai Monsoon Roads)  
> **Target Event/Context:** Claude Impact Lab Mumbai · Saturday, 21 Nov 2026 · ATLAS SkillTech University  
> **Core Theme:** Civic Accountability, Public Finance Transparency & Decision Support  
> **Synthetic Data Notice:** All records, coordinates, contractors, costs, and citizen IDs are realistic synthetics. Real ward names, localities, hospitals, and arterial roads are used for authenticity.

---

## 1. Executive Summary & The Core Pivot

### The Problem
Every monsoon, Mumbai spends crores fixing roads. Potholes return within weeks, public anger flares, and nobody can easily answer:
1. **Where did the money go?**
2. **Did the fix last?**
3. **Who is responsible?**

### Why Most Civic Tech Fails
Most civic projects are built as **hostile watchdogs** pointing fingers at municipal officers and publishing contractor blacklists. No municipal commissioner or engineer ever adopts software whose primary output is their own public embarrassment.

### The Winning Pivot: An Officer's Shield
Instead of an audit watchdog, **The Ward Ledger is built as an Executive Engineer’s decision-support shield**.
- Engineering officers clear files for works they did not physically supervise.
- Municipal Chief Auditor objections arrive 18 months later against the officer who signed.
- **The Ward Ledger protects the officer** by flagging pre-award risks, detecting duplicate billings on roads still under Defect Liability Periods (DLP), checking contractor overrun histories, and auto-drafting formal bilingual **file notings with exact document citations**.
- A citizen transparency portal and an auditor trail then cost nothing extra because they read the exact same data spine.

---

## 2. System Architecture: One Spine, Three Faces

```
                            ┌────────────────────────────────────────┐
                            │               DATA SPINE               │
                            │   Claims (AI) ──> Promotion ──> Facts  │
                            └───────────────────┬────────────────────┘
                                                │
         ┌──────────────────────────────────────┼──────────────────────────────────────┐
         ▼                                      ▼                                      ▼
┌──────────────────┐                  ┌──────────────────┐                  ┌──────────────────┐
│  OFFICER CONSOLE │                  │  CITIZEN WINDOW  │                  │   AUDIT TRAIL    │
│ (Desktop 1366x768│                  │ (Mobile/3G/Map)  │                  │ (Immutable Log)  │
│  Decision Shield)│                  │ (Public Facts)   │                  │ (Chain of Cust.) │
└──────────────────┘                  └──────────────────┘                  └──────────────────┘
```

1. **Officer Console (Pre-Award & Operations):**
   - File-shaped, dense data view (not cards/tiles).
   - Pre-award risk flags with document citations.
   - SLA and Defect Liability Period (DLP) countdown clocks.
   - **Hero Feature:** Auto-drafted bilingual file noting (Marathi/English) ready for the engineer's file sheet.
2. **Citizen Window (Public Window):**
   - Map-first interface (mobile-friendly, low-bandwidth).
   - Citizen drops a pin or enters a complaint ID.
   - Plain-language status: Which contractor repaired it, what was billed, did SLA pass, is it still under warranty?
   - **Hero Feature:** One-click Section 6(1) Right to Information (RTI) application generator.
3. **Audit Trail (Municipal Chief Auditor):**
   - Boring on purpose: looks like an append-only terminal/log.
   - Every figure carries its source document SHA-256 hash, page number, bounding box, extraction model version, and promoter ID.

---

## 3. The Core Architectural Rule: Claims vs. Facts

**The AI model NEVER writes facts directly to the database.** It only writes **claims**.

```
[Ingest Docs] ──> [Claude / OCR] ──> [claim table]
                                           │
                        ┌──────────────────┴──────────────────┐
                        ▼                                     ▼
             Rule Satisfied (e.g., 2 sources)         Human Review Queue
                        │                                     │
                        └──────────────► [fact table] ◄───────┘
                                          (Immutable)
```

### PostgreSQL Schema
```sql
-- Canonical work record (only facts attach here)
CREATE TABLE work_record (
  work_id          UUID PRIMARY KEY,
  ward_code        TEXT,              -- e.g. 'K/E', 'G/N'
  department       TEXT,              -- roads | swd | swm | hydraulic
  tender_ref       TEXT,
  work_order_ref   TEXT,
  contractor_id    UUID REFERENCES contractor,
  geom             GEOMETRY(LINESTRING, 4326),
  dlp_expires_on   DATE
);

-- What LLMs & extractors output: Claims ONLY
CREATE TABLE claim (
  claim_id      UUID PRIMARY KEY,
  work_id       UUID,
  field_path    TEXT,          -- e.g. 'cost_inr', 'contractor_name'
  value_text    TEXT,
  value_num     NUMERIC,
  source_doc    UUID,          -- sha256 of original PDF
  page_no       INT,
  bbox          BOX,           -- UI highlight region
  extractor     TEXT,          -- 'claude-vision-v1' | 'tesseract'
  prompt_hash   TEXT,          -- Audit reproducibility
  confidence    REAL,
  extracted_at  TIMESTAMPTZ DEFAULT NOW()
);

-- Promoted facts (append-only, immutable, supersedes chain)
CREATE TABLE fact (
  fact_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  work_id       UUID REFERENCES work_record,
  field_path    TEXT,
  value         JSONB,
  from_claim    UUID REFERENCES claim,
  promoted_by   TEXT,          -- 'rule:two-source-agree' | 'user:ae-4471'
  promoted_at   TIMESTAMPTZ DEFAULT NOW(),
  supersedes    UUID REFERENCES fact
);
```

---

## 4. Comprehensive Dataset Reference

All files are located in `data/` in standard UTF-8 CSV / GeoJSON formats.

```
data/
├── work_orders.csv           (2,499 rows)  - The central transaction ledger
├── complaints.csv            (6,501 rows)  - Raw multi-channel citizen complaints
├── complaints_sample_200.csv (200 rows)    - Curated sample for quick prompt testing
├── contractors.csv           (8 rows)      - Empanelled contractors list
├── rate_card.csv             (10 rows)     - Official BMC rate benchmarks
├── roads.csv & roads.geojson (291 rows)    - Road geometries, surfaces, & DLP statuses
├── wards.csv & wards.geojson (24 wards)    - Ward budgets, population, boundaries
├── localities.csv            (118 rows)    - Gazetteer with Devanagari aliases for geocoding
├── flood_hotspots.csv        (28 rows)     - Chronic flood points & depth metrics
├── rainfall_daily.csv        (244 rows)    - Daily monsoon rainfall (Santacruz/Colaba)
├── tides.csv                 (244 rows)    - Daily high tides & height flags (>=4.5m)
├── traffic.csv               (291 rows)    - Peak speeds & congestion index per road
├── accidents.csv             (420 rows)    - Pothole/uneven road accident records
├── facilities.csv            (160 rows)    - Hospitals & schools with access roads
└── social_posts.csv          (650 rows)    - Raw citizen social posts (mixed noise)
```

### Relational Schema Graph
```
complaints.linked_complaint_ids ──► work_orders.work_order_id
work_orders.road_id             ──► roads.road_id
work_orders.contractor_id       ──► contractors.contractor_id
work_orders.repair_method       ──► rate_card.repair_method
work_orders.ward_code           ──► wards.ward_code
roads.road_id                   ──► traffic.road_id, accidents.road_id
localities.ward_code            ──► wards.ward_code
```

### Critical Data Quirks to Handle in Code
1. **Unassigned Wards (~7% of complaints):** `ward_code` is blank. Must be resolved by geocoding `locality_text` using `localities.csv` or Point-in-Polygon against `wards.geojson`.
2. **Category Misclassification (~18% of complaints):** Citizens misreport (e.g. reporting a broken water pipe or manhole as a pothole). Claude parses the multilingual `description` to standardize canonical categories.
3. **Multilingual Free Text:** Text in `complaints.csv` and `social_posts.csv` blends English, Hinglish (`"paani bhar gaya hai"`), Marathi (`"खड्डा पडला आहे"`), and Hindi.
4. **Rate Card Variance:** `cost_inr` varies naturally by ±20% to 30% depending on site conditions; only flag variances exceeding 20-30% of standard benchmark.
5. **Defect Liability Period (DLP):** If `roads.under_dlp == 'Y'`, any work order billed to BMC on that road is a **potential financial irregularity** (contractor is legally obligated to repair free of cost).

---

## 5. The 14 Agents Pipeline

| # | Agent Name | Layer | Primary Responsibility | Input ➔ Output |
|---|---|---|---|---|
| 1 | **Harvester** | Ingest | Hash-address source PDFs/CSVs (SHA-256) | PDF/CSV ➔ `source_doc` |
| 2 | **OCR Extractor** | Extraction | Layout-aware OCR, Devanagari labels, bbox | `source_doc` ➔ `claim` |
| 3 | **Vision Table Reconstructor** | Extraction | Reconstruct messy tables (items, qty, rates) | Tabular PDF page ➔ structured claims |
| 4 | **Complaint Parser** | Extraction | Cleans category, extracts locality, dedupes | `complaints.csv` ➔ `parsed_complaint` |
| 5 | **Social Signal Classifier** | Extraction | Filters spam/sarcasm, tags genuine civic alerts | `social_posts.csv` ➔ `parsed_social` |
| 6 | **Geocoder** | Resolution | Translates prose to LineString geometries | Locality/prose ➔ `geom` with `uncertainty_m` |
| 7 | **Entity Resolver** | Resolution | Canonicalizes contractor names across scripts | Name mentions ➔ Canonical ID / Adjudication Queue |
| 8 | **Rule Engine (Promoter)** | Promotion | Auto-promotes verified claims; queues discrepancies | `claim` ➔ `fact` / `review_queue` |
| 9 | **Risk Flagger** | Console | Computes 7 non-blackbox risk flags for officers | `fact` + `work_orders` ➔ `flag` |
| 10 | **File Noting Drafter** | Console | Drafts formal bilingual note-sheet for signing | Work ID + Flags ➔ Note paragraph with citations |
| 11 | **RTI Generator** | Citizen | Drafts Section 6(1) RTI application with PIO details | Work ID / Complaint ➔ Legal RTI draft |
| 12 | **Budget Planner** | Planning | Recommends optimal allocation of next rupee | Ward risk layers ➔ Prioritized repair list |
| 13 | **Accountability Bot** | Citizen | Answers citizen queries in plain Marathi/English | Complaint query ➔ Fact-checked summary |
| 14 | **Audit Trail Renderer**| Audit | Emits immutable chronological provenance log | Work ID ➔ Full audit chain export |

---

## 6. Key Algorithms & Mathematical Rules

### A. Non-Blackbox Risk Flags (No opaque AI scores)
The AI **never produces an opaque score (e.g. 0.78)**. Instead, it evaluates binary, defensible rules:
1. **`cost_overrun_history` (High):** Contractor had `final_bill > awarded_amount * 1.15` on ≥2 prior works.
2. **`silent_extension` (High):** Completion date extended with no liquidated damages (LD) penalty recorded.
3. **`related_bidders` (High):** Shared PAN-within-GSTIN (characters 3–12) or shared registered address among tender competitors.
4. **`dlp_breach` (Medium):** Work billed to BMC on a road segment where `roads.under_dlp == 'Y'`.
5. **`single_bid_award` (Medium):** Tender awarded with fewer than 3 technically qualified bids.
6. **`estimate_drift` (Medium):** `cost_inr / area_sqm` exceeds ward median by >20% for the same repair method.
7. **`clean_record` (Positive):** Contractor has ≥3 completed works with bills within 5% of rate card and 0 SLA breaches. *(Crucial for fairness and political longevity).*

### B. Contractor Entity Resolution Hierarchy
Prevents defamation when matching names like *"M/s A. B. Constructions"* vs *"AB Construction Pvt Ltd"*:
```
1. GSTIN Match (Characters 3 to 12 match PAN) ──► DEFINITIVE MATCH (Merge)
2. Registered Address Match                  ──► DEFINITIVE MATCH (Merge)
3. Trigram String Similarity (pg_trgm > 0.85) ──► CANDIDATE MATCH (Score)
4. Score < 0.85                               ──► ADJUDICATION QUEUE (Human Review)
```

### C. Next-Rupee Budget Allocation Formula
Used by the Budget Planner Agent to allocate limited ward repair funds:
$$\text{Priority Score} = 0.25 S + 0.20 F + 0.15 R + 0.15 A + 0.10 P + 0.10 C + 0.05 D$$
* $S$: Complaint severity (1 to 5)
* $F$: Flood hotspot overlap (0 or 1)
* $R$: Monsoon rainfall risk
* $A$: Accident frequency on road
* $P$: Proximity to hospital/school (within 250m)
* $C$: Congestion index (0 to 10)
* $D$: Days since last repair
* *DLP Discount:* If road is under DLP, priority is discounted (cost belongs to contractor, not BMC).

---

## 7. Recommended Technology Stack

| Layer | Recommended Choice | Reason |
|---|---|---|
| **Backend API** | **FastAPI (Python 3.11+)** | High performance, native async, Pydantic data validation |
| **Data & Geo** | **PostgreSQL + PostGIS + pg_trgm** | Spatial geometry buffers, road containment, fuzzy string matching |
| **LLM & Reasoning**| **Claude 3.5 Sonnet / Haiku** | Superior reasoning, multilingual (Marathi/Hindi), table reconstruction |
| **Frontend** | **Next.js / React OR Streamlit** | Fast iteration; Leaflet / MapLibre for maps |
| **ORM / Query** | **SQLAlchemy 2.0 / Pandas** | Rapid aggregation across CSVs and database tables |

---

## 8. Step-by-Step Developer Quick Start

### 1. Verify Repository Structure
```bash
git clone https://github.com/vaibhavgite2/Ward_ledger.git
cd Ward_ledger
ls -la
```

### 2. Inspecting Data in Python
```python
import pandas as pd

wo = pd.read_csv("data/work_orders.csv")
roads = pd.read_csv("data/roads.csv")
rate_card = pd.read_csv("data/rate_card.csv")

# Find immediate DLP violations (repairs paid by BMC on active warranty roads)
dlp_roads = set(roads[roads["under_dlp"] == "Y"]["road_id"])
dlp_violations = wo[wo["road_id"].isin(dlp_roads)]
print(f"Potential DLP breaches found: {len(dlp_violations)} jobs totaling ₹{dlp_violations['cost_inr'].sum():,}")
```

### 3. Core Developer Files
- [`context.md`](context.md): Deep-dive into problem statement, municipal adoption strategy, and data dictionary.
- [`agents.md`](agents.md): Exhaustive specifications, input/output schemas, and system prompt templates for all 14 agents.
- [`DATA_DICTIONARY.md`](DATA_DICTIONARY.md): Column-by-column breakdown of all CSVs and GeoJSON files.
- [`STARTER_IDEAS.md`](STARTER_IDEAS.md): Hackathon ideas, sample prompts, and judging criteria.
