# Ward Ledger

### Follow the Rupee: Mumbai Monsoon Roads 🌧️💰

**The dataset and challenge for Claude Impact Lab Mumbai**
Saturday, 21 November 2026 · ATLAS SkillTech University, Mumbai · Theme: accountability and budgeting

> ⚠️ **Everything in this repo is synthetic.** It looks and behaves like real Mumbai civic data, but it is **not BMC data**. It has no real citizens in it, and **all contractors are fictional**. Ward codes, locality names, arterial roads, well-known flooding spots and major public hospitals are real names, used only for realism. Every coordinate, boundary, amount, date and record is made up. Don't use it to judge any real person, contractor or department.

---

## The problem

Every monsoon, Mumbai spends crores fixing the same roads. Citizens complain, repairs get logged, and the potholes come back. Nobody can easily answer three questions:

1. **Where did the money go?**
2. **Did the fix last?**
3. **Who is responsible?**

## Your challenge

> **Build a Claude-powered tool that shows where each ward's road repair money went, whether the work held up, and where the next rupee should go.**

A strong solution will:

| | Step | What it means |
|---|---|---|
| 🔗 | **Connect** | Turn messy, duplicated, multilingual complaints into clean issues, and link them to the work orders that fixed them (or didn't). |
| 🔍 | **Audit** | Check repairs against SLAs, the rate card and how long the fix held up. Flag anything that doesn't add up. |
| 📋 | **Hold to account** | A fair, plain-language scorecard for every contractor and every ward that a citizen or corporator can read. |
| 🧭 | **Budget smarter** | Recommend where each ward should spend next, based on risk: rain, flooding, tides, traffic, accidents, and nearby schools and hospitals. |

Complaint clean-up (de-duplication, multilingual parsing, geocoding) is a supporting step, not the goal.

---

## What's inside

| File | Rows | What it is |
|---|---:|---|
| `data/wards.csv` + `wards.geojson` | 24 | BMC wards (A to T), approximate boundaries, monsoon repair budget |
| `data/work_orders.csv` | 2,499 | Repair jobs: contractor, method, area, cost, SLA, re-opened |
| `data/rate_card.csv` | 10 | Standard rate per repair method (per sqm or per job) |
| `data/contractors.csv` | 8 | Fictional contractors |
| `data/complaints.csv` | 6,501 | MyBMC app, 1916 helpline, portal and walk-in complaints (Jun to early Oct 2025) |
| `data/complaints_sample_200.csv` | 200 | Complaints from a heavy-rain spell (7 to 8 Jul), handy for quick prompting |
| `data/social_posts.csv` | 650 | X, WhatsApp and Instagram posts in mixed languages, with noise |
| `data/roads.csv` + `roads.geojson` | 291 | Road segments, incl. last resurfaced date and Defect Liability Period (DLP) status |
| `data/localities.csv` | 118 | Localities with lat/lon and aliases (incl. Devanagari) |
| `data/flood_hotspots.csv` | 28 | Chronic waterlogging spots |
| `data/rainfall_daily.csv` | 244 | Daily rainfall, Santacruz and Colaba |
| `data/tides.csv` | 244 | Daily high tides, big-tide flag (>= 4.5 m) |
| `data/traffic.csv` | 291 | Peak-hour volume, speed and congestion per road segment |
| `data/accidents.csv` | 420 | Road accidents (2024 to 2025) with probable cause |
| `data/facilities.csv` | 160 | Hospitals and municipal schools with their nearest road |

📖 Every column is explained in **[DATA_DICTIONARY.md](DATA_DICTIONARY.md)**.
💡 Build ideas, starter prompts and the judging rubric are in **[STARTER_IDEAS.md](STARTER_IDEAS.md)**.

### How the money trail connects

```
complaints ──(linked_complaint_ids)──> work_orders ──(road_id)──> roads (DLP, resurfaced)
                                           │
                     contractor_id ────────┼──── repair_method ──> rate_card
                                           │
                                       ward_code ──> wards (budget)
```

---

## Quick start

**1. Get the data**

```bash
git clone https://github.com/SumeetGDoshi/Claude-Impact-Labs-data-2.git
cd Claude-Impact-Labs-data-2
```

**2. Take a first look**

```python
import pandas as pd

wo = pd.read_csv("data/work_orders.csv")
rate = pd.read_csv("data/rate_card.csv")
print(wo.groupby("contractor_name")["cost_inr"].sum().sort_values(ascending=False))
```

**3. Bring in Claude**

Open the folder in Claude Code and try:

```
Read data/work_orders.csv and data/rate_card.csv. Pick one contractor and
write a fair, plain-language scorecard a citizen could read: speed, how long
the repairs lasted, cost vs the rate card, and one thing to improve.
Under 120 words, no accusations.
```

That's your first prototype. Now make it better. 🚀

---

## Tips for the day

- **Go narrow and finish.** One tool that works beats a half-built platform.
- **Start with `complaints_sample_200.csv`** while you're prompting, then scale up.
- **Show your evidence.** Every flag or score should point to the work orders behind it.
- **Be fair.** Account for context like low-lying wards or heavy-rain weeks before blaming anyone.
- **Think about the user.** Could a ward officer, corporator or citizen act on what you built?

## Scale note

Amounts are realistic per job (a pothole patch costs thousands of rupees, a cave-in repair a couple of lakh), but total spend across the city is about ₹13 crore for the season. That's smaller than real BMC road spending, because only complaint-driven monsoon repairs are included. Ward budgets in `wards.csv` are sized against this spend, so budget vs spend comparisons work.

## Answer key

The judges' answer key and the generator script will be published here after the event.

---

## About

Built for **Claude Impact Lab Mumbai**, a full-day civic hackathon run by the Claude Community in Mumbai, supported by Anthropic.

Organised by **Sumeet Doshi**, Claude Community Ambassador, Anthropic
[LinkedIn](https://www.linkedin.com/in/sumeet-doshi/) · [X](https://x.com/thecodershow)

## License

Data and docs released under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
