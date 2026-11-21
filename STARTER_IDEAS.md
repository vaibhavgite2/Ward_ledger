# Starter ideas: Follow the Rupee

Pick one, finish it, demo it. A narrow tool that works beats a half-built platform. All data is synthetic and all contractors are fictional.

## 1. Ward money trail (the core brief)
For any ward, show where the monsoon repair money went: budget vs spend, spend by contractor and repair type, and how much went on fixes that failed within 30 days.
- Claude writes a one-page plain-language summary a corporator or citizen can read.

## 2. Repair auditor
Flag suspicious work orders and explain each flag in one line.
- Cost per sqm or per job vs `rate_card.csv`
- Same road, same work, billed twice within a few days, with no complaint linked
- Repairs on roads still under DLP (`roads.csv` `under_dlp = Y`) that BMC paid for
- Missed SLAs and re-opened fixes

## 3. Contractor scorecard
A fair scorecard for each contractor: speed (SLA), durability (re-open rate), cost vs rate card, volume. Fair means it accounts for context, such as low-lying wards or heavy-rain weeks, and doesn't just punish whoever did the most work.

## 4. Next rupee planner
Given a ward's remaining budget, recommend what to fix first and with which method.
- Rank open issues by risk: severity, flood hotspot, rain and tide, traffic, accidents, nearby schools and hospitals.
- Prefer methods that last (re-open rate by method) over the cheapest patch.

## 5. Complaint to work order linker (supporting step)
Clean up raw complaints so the money trail starts from real issues.
- De-duplicate across channels, parse Marathi, Hindi and Hinglish, geocode with `localities.csv`, drop noise.
- Link each issue to its work order, or flag it as never fixed.

## 6. Citizen accountability bot
A citizen asks "What happened to my complaint?" in their own language. Claude answers with the work order, contractor, cost, whether it met the SLA and whether it held up.

## Prompts to start with

```
You are an auditor for a Mumbai ward. Here are work orders and the standard
rate card. Flag any job that looks over-billed, double-billed or billed to BMC
while the road was under its Defect Liability Period. For each flag give the
work order id and a one-line reason. Be fair: don't flag normal variation.
```

```
Write a plain-language scorecard for this contractor for a citizen audience.
Cover speed, how long the repairs lasted, cost vs the rate card, and one
thing they should improve. Keep it under 120 words and avoid accusations.
```

## Judging rubric (suggested)

| Criterion | Weight | How to check |
|---|---|---|
| Audit accuracy | 25% | Flags checked against the judges' answer key |
| Fair accountability | 20% | Scorecards are clear, evidence-based and not misleading |
| Budget recommendation | 20% | Next-rupee ranking checked against the judges' answer key, sensible methods |
| Connects the trail | 15% | Complaints to issues to work orders, handles messy input |
| Usable by a real person | 10% | Could a ward officer, corporator or citizen act on it? |
| Demo and clarity | 10% | Working demo, clear explanation |
