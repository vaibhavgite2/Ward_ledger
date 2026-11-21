// Builds output/Apla-Shahar-Feature-Evidence.pptx from output/manifest.json (run convert.mjs first).
import pptxgen from "pptxgenjs";
import { readFileSync, existsSync } from "node:fs";
import { resolve } from "node:path";

const OUT = "output";
const man = JSON.parse(readFileSync(`${OUT}/manifest.json`, "utf8"));
const problems = existsSync(`${OUT}/problems.txt`) ? readFileSync(`${OUT}/problems.txt`, "utf8").trim() : "";
const scenes = man.scenes;

const INK = "1F1A12", AMBER = "C77700", PAPER = "FFFFFF", MUTED = "5C564A", GREEN = "2F7D4F", RED = "B3402A";
const FONT_H = "Cambria", FONT_B = "Calibri";
const W = 13.333, H = 7.5;

const pptx = new pptxgen();
pptx.layout = "LAYOUT_WIDE"; // 13.33 x 7.5 in (LAYOUT_16x9 is only 10 x 5.625)
pptx.title = "Apla Shahar (The Ward Ledger) - Feature Evidence";
pptx.author = "Ward Ledger evidence run";

function pngSize(file) { const b = readFileSync(file); return { w: b.readUInt32BE(16), h: b.readUInt32BE(20) }; }
function contain(file, bx, by, bw, bh) {
  const { w, h } = pngSize(file);
  const r = Math.min(bw / w, bh / h);
  return { x: bx + (bw - w * r) / 2, y: by + (bh - h * r) / 2, w: w * r, h: h * r };
}
const T = (s, text, o) => s.addText(text, { isTextBox: true, ...o });
const footer = (s, n) => { T(s, "Apla Shahar · feature evidence · synthetic data", { x: 0.5, y: 7.08, w: 8, h: 0.3, fontFace: FONT_B, fontSize: 10, color: MUTED }); T(s, String(n), { x: 12.2, y: 7.08, w: 0.6, h: 0.3, fontFace: FONT_B, fontSize: 10, color: MUTED, align: "right" }); };
let n = 0;
const declared = new Set();
const newSlide = (bg = PAPER, section = "Overview") => {
  if (!declared.has(section)) { pptx.addSection({ title: section }); declared.add(section); }
  const s = pptx.addSlide({ sectionTitle: section }); s.background = { color: bg }; n++; return s;
};
const SHORT = { "01": "Public home", "02": "Complaints", "03": "Map", "04": "Wards", "05": "Contractors", "06": "Ask", "07": "RTI draft", "08": "Languages",
  "09": "Citizen raises a complaint", "10": "Officer verifies and assigns", "11": "Contractor report", "12": "Officer approval", "13": "Citizen sees the result",
  "14": "Support a complaint", "15": "Officer console", "16": "Budget planner", "17": "Audit trail", "18": "Mobile" };
const heading = (s, text, sub) => {
  T(s, text, { x: 0.5, y: 0.3, w: 12.3, h: 0.75, fontFace: FONT_H, fontSize: 36, bold: true, color: INK, margin: 0, fit: "shrink" });
  if (sub) T(s, sub, { x: 0.5, y: 1.05, w: 12.3, h: 0.45, fontFace: FONT_B, fontSize: 14, color: MUTED, valign: "top", margin: 0, fit: "shrink" });
};

// 1. title
{
  const s = newSlide(INK);
  T(s, "FEATURE EVIDENCE PACK", { x: 0.8, y: 1.6, w: 11, h: 0.4, fontFace: FONT_B, fontSize: 16, bold: true, color: AMBER, charSpacing: 6 });
  T(s, "Apla Shahar", { x: 0.8, y: 2.1, w: 11.5, h: 1.3, fontFace: FONT_H, fontSize: 60, bold: true, color: "FFFFFF" });
  T(s, "Where did your tax money go? Every feature, recorded end to end in a real browser. (Product name: Apla Shahar; repository: The Ward Ledger.)", { x: 0.8, y: 3.5, w: 11, h: 0.9, fontFace: FONT_B, fontSize: 22, color: "D6D3D1" });
  const shots = scenes.reduce((a, c) => a + c.shots.length, 0);
  T(s, `${scenes.length} recorded scenes · ${shots} screenshots · 1 narrated demo video · synthetic Mumbai K/East data`, { x: 0.8, y: 5.4, w: 11.5, h: 0.4, fontFace: FONT_B, fontSize: 14, color: AMBER });
  T(s, `Run: ${new Date().toISOString().slice(0, 10)}`, { x: 0.8, y: 5.85, w: 8, h: 0.4, fontFace: FONT_B, fontSize: 14, color: "A8A29E" });
}

// 2. method
{
  const s = newSlide();
  heading(s, "How this evidence was produced", "Reproducible, isolated, and honest about what it is");
  const rows = [
    ["Browser automation", "Playwright (Chromium), scripted in evidence/record.mjs; one recorded browser context per scene"],
    ["Isolation", "Separate ports: UI :3100 (production build) and API :8100; your dev servers on :3000 / :8000 were not touched"],
    ["Data", "Fresh SQLite database built by the pipeline + demo accounts and tickets; a temporary instance folder for uploads"],
    ["Claude", "No API key: every Claude path runs its deterministic fallback, so drafts and answers are repeatable"],
    ["Actors", "Citizen, ward officer (ae-4471), contractor (ct05), auditor (audit-01) - the real login panels, not shortcuts"],
    ["Artifacts", "output/videos/*.mp4 (per scene), Apla-Shahar-Product-Demo.mp4 (narrated, 3:37), output/shots/*.png, manifest.json"],
  ];
  s.addTable(rows.map(([a, b]) => [{ text: a, options: { bold: true, color: INK, fontFace: FONT_B, fontSize: 14 } }, { text: b, options: { color: INK, fontFace: FONT_B, fontSize: 14 } }]),
    { x: 0.5, y: 1.7, w: 12.3, colW: [2.4, 9.9], border: { type: "solid", color: "E7E5DF", pt: 1 }, fill: { color: "FFFFFF" }, margin: 0.12, rowH: 0.78 });
  footer(s, n);
}

// 3. trust model
{
  const s = newSlide();
  heading(s, "The trust model the demo exercises", "From AGENTS.md: the model never writes facts, only claims");
  const cards = [
    ["Claims, then facts", "Nothing is a fact until a rule or a named human promotes it. Shown in the audit trail (promoted by rule:source-csv@v1 or user:ID) and the review queue."],
    ["Flags, not scores", "Officer-only risk flags with numbered evidence and source references. Public scorecards describe facts and never accuse."],
    ["Right of reply", "Contractors answer any finding; the reply is shown next to it. A clean-record view is mandatory."],
    ["Append-only audit", "Hash-chained fact log with filters, chain verification and CSV export. Every human action is logged with the officer ID."],
  ];
  cards.forEach(([t, d], i) => {
    const x = 0.5 + (i % 2) * 6.25, y = 1.8 + Math.floor(i / 2) * 2.45;
    s.addShape(pptx.ShapeType.roundRect, { x, y, w: 6.0, h: 2.25, fill: { color: "FFFFFF" }, line: { color: "E7E5DF" }, rectRadius: 0.08 });
    T(s, t, { x: x + 0.25, y: y + 0.15, w: 5.5, h: 0.5, fontFace: FONT_H, fontSize: 20, bold: true, color: INK });
    T(s, d, { x: x + 0.25, y: y + 0.7, w: 5.5, h: 1.45, fontFace: FONT_B, fontSize: 14, color: MUTED, valign: "top" });
  });
  footer(s, n);
}

// 4. coverage matrix
{
  const s = newSlide();
  heading(s, "Coverage at a glance", "One row per recorded scene; the video file name is the evidence");
  const head = ["#", "Feature", "Result", "Shots", "Video"].map((t) => ({ text: t, options: { bold: true, color: "FFFFFF", fill: { color: INK }, fontFace: FONT_B, fontSize: 11 } }));
  const body = scenes.map((c) => {
    const ok = c.status === "ok";
    const soft = c.notes.length ? ` (${c.notes.length} minor)` : "";
    return [
      { text: c.id.slice(0, 2), options: { fontSize: 10 } },
      { text: c.title, options: { fontSize: 10 } },
      { text: (ok ? "Recorded" : "FAILED") + soft, options: { fontSize: 10, bold: true, color: ok ? (c.notes.length ? "A16207" : GREEN) : RED } },
      { text: String(c.shots.length), options: { fontSize: 10, align: "center" } },
      { text: c.mp4 ? c.mp4.replace(`${OUT}/videos/`, "") + (c.duration ? ` · ${c.duration}s` : "") : "-", options: { fontSize: 9, color: MUTED } },
    ];
  });
  s.addTable([head, ...body], { x: 0.5, y: 1.55, w: 12.3, colW: [0.5, 5.0, 1.6, 0.7, 4.5], border: { type: "solid", color: "E7E5DF", pt: 0.75 }, fill: { color: "FFFFFF" }, margin: [0.03, 0.08, 0.03, 0.08], fontFace: FONT_B, rowH: 0.27 });
  footer(s, n);
}

// 5+. per scene
const cover = (c) => (c.shots[0] ? `${OUT}/shots/${c.shots[0].file}` : null);
for (const c of scenes) {
  const sec = `${c.id.slice(0, 2)} ${SHORT[c.id.slice(0, 2)] || c.title}`;
  const short = `${c.id.slice(0, 2)} · ${SHORT[c.id.slice(0, 2)] || c.title}`;
  // video slide
  {
    const s = newSlide(PAPER, sec);
    heading(s, short);
    s.addNotes(`${c.title}. ${c.desc}`);
    T(s, c.desc, { x: 0.5, y: 1.05, w: 12.3, h: 0.75, margin: 0, fontFace: FONT_B, fontSize: 14, color: MUTED, valign: "top", fit: "shrink" });
    const vx = 0.5, vy = 1.85, vw = c.mobile ? 3.0 : 8.4, vh = c.mobile ? 5.05 : 5.25;
    if (c.mp4 && existsSync(c.mp4)) {
      const abs = resolve(c.mp4);
      const cv = cover(c);
      s.addMedia({ type: "video", path: abs, x: vx, y: vy, w: vw, h: vh, ...(cv ? { cover: "data:image/png;base64," + readFileSync(cv).toString("base64") } : {}) });
    }
    const tx = vx + vw + 0.35, tw = 12.8 - tx;
    T(s, "Evidence", { x: tx, y: 1.85, w: tw, h: 0.35, fontFace: FONT_B, fontSize: 13, bold: true, color: AMBER });
    T(s, [
      { text: `Video: ${c.mp4 ? c.mp4.replace(`${OUT}/`, "") : "n/a"}`, options: { breakLine: true } },
      { text: `Length: ${c.duration || c.seconds}s`, options: { breakLine: true } },
      { text: `Screenshots: ${c.shots.length}`, options: { breakLine: true } },
      { text: `Result: ${c.status === "ok" ? "recorded end to end" : c.status}`, options: { color: c.status === "ok" ? GREEN : RED } },
    ], { x: tx, y: 2.2, w: tw, h: 1.5, fontFace: FONT_B, fontSize: 12, color: INK, valign: "top", paraSpaceAfter: 4 });
    T(s, "What you will see", { x: tx, y: 3.8, w: tw, h: 0.35, fontFace: FONT_B, fontSize: 13, bold: true, color: AMBER });
    T(s, c.shots.slice(0, 6).map((sh) => ({ text: sh.caption, options: { bullet: true, breakLine: true } })), { x: tx, y: 4.15, w: tw, h: 2.8, fontFace: FONT_B, fontSize: 11, color: INK, valign: "top", paraSpaceAfter: 3, fit: "shrink" });
    footer(s, n);
  }
  // screenshot slides (2 per slide)
  const list = c.shots;
  const per = c.mobile ? 4 : 2;
  for (let i = 0; i < list.length; i += per) {
    const chunk = list.slice(i, i + per);
    const s = newSlide(PAPER, sec);
    heading(s, short, `Screenshots ${i + 1}-${i + chunk.length} of ${list.length}`);
    const gap = 0.25, bw = (12.3 - gap * (chunk.length - 1)) / chunk.length, by = 1.6, bh = 4.95;
    chunk.forEach((sh, k) => {
      const f = `${OUT}/shots/${sh.file}`;
      const bx = 0.5 + k * (bw + gap);
      s.addShape(pptx.ShapeType.rect, { x: bx, y: by, w: bw, h: bh, fill: { color: "FFFFFF" }, line: { color: "E7E5DF", pt: 1 } });
      const r = contain(f, bx + 0.05, by + 0.05, bw - 0.1, bh - 0.1);
      s.addImage({ path: resolve(f), ...r });
      T(s, sh.caption, { x: bx, y: by + bh + 0.05, w: bw, h: 0.45, fontFace: FONT_B, fontSize: 12, color: INK, align: "center", valign: "top", fit: "shrink" });
    });
    footer(s, n);
  }
}

// closing: findings + reproduce
{
  const s = newSlide(PAPER, "Wrap-up");
  heading(s, "Notes and how to reproduce", "What to know when reading this evidence");
  const minor = scenes.flatMap((c) => c.notes.map((x) => `[${c.id}] ${x}`));
  const lines = [
    "All data is synthetic; all contractors are fictional. Dates run at the dataset 'today' of 2025-10-05 for analytics; live tickets carry the real run date.",
    "Claude paths ran in deterministic-fallback mode (no API key), so draft noting, RTI text and bot answers are rule-based, not live LLM output.",
    "E-mail is logged to the email_outbox table, not sent (no SMTP configured). In-app notifications are real.",
    `Server-side or page errors during the run: ${problems ? problems.split("\n").length : 0}.`,
    ...(minor.length ? ["Minor scene issues (optional steps that did not complete): " + minor.slice(0, 6).join(" | ")] : []),
    "Reproduce: start API on :8100 and UI on :3100 with an isolated DB, then  cd evidence && node record.mjs && node convert.mjs && node build_ppt.mjs",
  ];
  T(s, lines.map((t) => ({ text: t, options: { bullet: true, breakLine: true } })), { x: 0.5, y: 1.7, w: 12.3, h: 5.1, fontFace: FONT_B, fontSize: 15, color: INK, valign: "top", paraSpaceAfter: 10, fit: "shrink" });
  footer(s, n);
}

const file = `${OUT}/Apla-Shahar-Feature-Evidence.pptx`;
await pptx.writeFile({ fileName: file });
import { createRequire } from "node:module";
import { homedir } from "node:os";
const { applyTheme } = createRequire(import.meta.url)(`${homedir()}/.claude/skills/pptx/scripts/apply_theme.js`);
await applyTheme(file, { name: "Apla Shahar", headFontFace: FONT_H, bodyFontFace: FONT_B,
  colors: { dk1: INK, lt1: "FFFFFF", dk2: "3B3326", lt2: "F2F2F0", accent1: "C77700", accent2: "2F7D4F", accent3: "B3402A", accent4: "1E5A8C", accent5: "7A5C99", accent6: "5C564A", hlink: "1E5A8C", folHlink: "7A5C99" } });
console.log("wrote", file, "slides:", n);
