// Problem-statement deck: "Apla Shahar - the problem, and Raju's story". New file; does not touch the evidence deck.
//   NODE_PATH=$PWD/node_modules node build_problem_ppt.mjs
import pptxgen from "pptxgenjs";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { homedir } from "node:os";

const A = "output/ppt_assets", S = "output/shots";
const OUTFILE = "output/Apla-Shahar-Problem-and-Raju-Story.pptx";
const FH = "Cambria", FB = "Calibri";
const INK = "1F1A12", AMBER = "C77700", BRIGHT = "F5A623", MUTED = "5C564A", TINT = "F2F2F0", GREEN = "2F7D4F", RED = "B3402A", BLUE = "1E5A8C", WHITE = "FFFFFF";

// ---- real numbers, read from the running app's API (isolated stack on :8100) ----
const wards = await (await fetch("http://localhost:8100/api/wards?lang=en")).json();
const sum = (k) => wards.reduce((a, w) => a + w[k], 0);
const budget = sum("budget_inr"), billed = sum("spend_inr"), failed = sum("failed_inr");
const cr = (x) => x / 1e7;
const ke = wards.find((w) => w.ward_code === "K/E");
const worst = [...wards].sort((a, b) => b.failed_pct - a.failed_pct).slice(0, 10);
console.log(`budget ${cr(budget).toFixed(2)} Cr, billed ${cr(billed).toFixed(2)} Cr, failed ${cr(failed).toFixed(2)} Cr, K/E failed ${ke.failed_pct}% sla ${ke.sla_pct}%`);

const THEME = { name: "Apla Shahar", headFontFace: FH, bodyFontFace: FB,
  colors: { dk1: INK, lt1: WHITE, dk2: "3B3326", lt2: TINT, accent1: AMBER, accent2: GREEN, accent3: RED, accent4: BLUE, accent5: "7A5C99", accent6: MUTED, hlink: BLUE, folHlink: "7A5C99" } };

const pptx = new pptxgen();
pptx.layout = "LAYOUT_WIDE"; // 13.33 x 7.5 in
pptx.title = "Apla Shahar: the problem, and Raju's story";
pptx.author = "Apla Shahar team";
pptx.theme = { headFontFace: FH, bodyFontFace: FB };

const foot = (color) => ({ text: { text: "Apla Shahar · the problem and Raju's story · synthetic data", options: { x: 0.6, y: 7.05, w: 9, h: 0.3, fontFace: FB, fontSize: 10, color, margin: 0 } } });
const num = (color) => ({ x: 12.2, y: 7.05, w: 0.6, h: 0.3, fontFace: FB, fontSize: 10, color, align: "right", margin: 0 });
pptx.defineSlideMaster({ title: "LIGHT", background: { color: WHITE }, objects: [foot(MUTED), { placeholder: { options: { name: "title", type: "title", x: 0.6, y: 0.35, w: 12.1, h: 0.85, fontFace: FH, fontSize: 36, bold: true, color: INK, margin: 0, valign: "top" }, text: "" } }], slideNumber: num(MUTED) });
pptx.defineSlideMaster({ title: "DARK", background: { color: INK }, objects: [foot("B8B2A4"), { placeholder: { options: { name: "title", type: "title", x: 0.6, y: 0.35, w: 12.1, h: 0.85, fontFace: FH, fontSize: 36, bold: true, color: WHITE, margin: 0, valign: "top" }, text: "" } }], slideNumber: num("B8B2A4") });
pptx.defineSlideMaster({ title: "COVER", background: { color: INK }, objects: [{ placeholder: { options: { name: "title", type: "title", x: 0.7, y: 0.7, w: 7.4, h: 1.3, fontFace: FH, fontSize: 66, bold: true, color: WHITE, margin: 0, valign: "top" }, text: "" } }] });

let n = 0;
const declared = new Set();
function slide(master, section, title, notes) {
  if (!declared.has(section)) { pptx.addSection({ title: section }); declared.add(section); }
  const s = pptx.addSlide({ masterName: master, sectionTitle: section });
  n++;
  if (title) s.addText(title, { placeholder: "title" });
  if (notes) s.addNotes(notes);
  return s;
}
const T = (s, text, o) => s.addText(text, { isTextBox: true, margin: 0, fontFace: FB, color: INK, ...o });
const R = (s, o) => s.addShape(o.shape || pptx.ShapeType.roundRect, { rectRadius: 0.12, line: { color: o.fill, width: 0 }, ...o });
const dims = (f) => { const b = readFileSync(f); return { w: b.readUInt32BE(16), h: b.readUInt32BE(20) }; };
function img(s, f, bx, by, bw, bh, o = {}) { // contain inside a box; returns the placed rectangle
  const { w, h } = dims(f), r = Math.min(bw / w, bh / h), pw = w * r, ph = h * r, x = bx + (bw - pw) / 2, y = by + (bh - ph) / 2;
  if (o.frame) R(s, { x: x - 0.06, y: y - 0.06, w: pw + 0.12, h: ph + 0.12, fill: "D9D6CE", rectRadius: 0.05 });
  s.addImage({ path: f, x, y, w: pw, h: ph, altText: o.alt || "" });
  return { x, y, w: pw, h: ph };
}
const icon = (s, name, x, y, size, alt) => s.addImage({ path: `${A}/i_${name}.png`, x, y, w: size, h: size, altText: alt || name });
const stat = (s, x, y, w, h, big, label, color = AMBER, size = 36) => {
  R(s, { x, y, w, h, fill: TINT });
  T(s, big, { x: x + 0.25, y: y + 0.15, w: w - 0.5, h: h * 0.55, fontFace: FH, fontSize: size, bold: true, color, valign: "middle" });
  T(s, label, { x: x + 0.25, y: y + h * 0.6, w: w - 0.5, h: h * 0.35, fontSize: 14, color: MUTED, valign: "top" });
};
const chartFonts = (c = INK) => ({ catAxisLabelFontFace: "+mn-lt", valAxisLabelFontFace: "+mn-lt", dataLabelFontFace: "+mn-lt", legendFontFace: "+mn-lt", titleFontFace: "+mj-lt", catAxisLabelColor: c, valAxisLabelColor: c, dataLabelColor: c, legendColor: c });

// =========================== 1. cover ===========================
{
  const s = slide("COVER", "Cover", "Apla Shahar", "Opening. The question every taxpayer asks: where did my money go? Today we walk through the problem, and then one citizen, Raju, shows how Apla Shahar answers it.");
  s.addImage({ path: `${A}/hero.png`, x: 0, y: 0, w: 13.333, h: 7.5, altText: "Dusk skyline over a Mumbai road; a man stands beside a pothole and a fallen scooter and asks where his tax money went", sizing: { type: "cover", w: 13.333, h: 7.5 } });
  s.addText("Apla Shahar", { placeholder: "title" });
  T(s, "Where did your tax money go?", { x: 0.7, y: 1.95, w: 7.4, h: 0.6, fontFace: FH, fontSize: 28, color: BRIGHT, italic: true });
  T(s, "The problem, and how one citizen, Raju, finally gets answers", { x: 0.7, y: 2.7, w: 6.6, h: 0.9, fontSize: 18, color: "E9E5DA", valign: "top" });
  T(s, "Raju is a fictional citizen. All data in this deck is synthetic.", { x: 0.7, y: 6.85, w: 7, h: 0.3, fontSize: 11, color: "CFC9BB" });
}

// =========================== 2. the problem in three panels ===========================
{
  const s = slide("LIGHT", "The problem", "A pothole, a promise, and no way to check", "Three moments every Mumbai resident knows. Money is allocated. A patch is billed. The pothole returns. And nobody outside the office can see any of it.");
  const cols = [
    ["bag", "1  Money is allocated", "The monsoon repair budget is approved for 24 wards."],
    ["patch", "2  A repair is billed", "A patch goes down, the contractor is paid, the file closes."],
    ["pothole", "3  The pothole is back", "Did the repair last? Who paid twice? Nobody outside the office can tell."],
  ];
  cols.forEach(([k, h, d], i) => {
    const x = 0.6 + i * 4.2;
    img(s, `${A}/${k}.png`, x, 1.45, 3.6, 3.1, { alt: h });
    T(s, h, { x, y: 4.7, w: 3.7, h: 0.4, fontFace: FH, fontSize: 20, bold: true });
    T(s, d, { x, y: 5.15, w: 3.7, h: 0.8, fontSize: 14, color: MUTED, valign: "top" });
    if (i < 2) s.addShape(pptx.ShapeType.rightArrow, { x: x + 3.7, y: 2.7, w: 0.45, h: 0.5, fill: { color: AMBER }, line: { color: AMBER, width: 0 } });
  });
  R(s, { x: 0.6, y: 6.1, w: 12.1, h: 0.75, fill: TINT });
  T(s, "Raju pays for all three steps, and can see none of them.", { x: 0.9, y: 6.1, w: 11.5, h: 0.75, fontFace: FH, fontSize: 20, italic: true, valign: "middle" });
}

// =========================== 3. the scale ===========================
{
  const s = slide("LIGHT", "The problem", `₹${cr(failed).toFixed(2)} Cr of repairs failed in 30 days`, "The scale of it, from the dataset: about a quarter of what was billed went on repairs that failed within thirty days. And hundreds of complaints never had a repair linked at all.");
  s.addChart(pptx.charts.DOUGHNUT, [{ name: "Billed", labels: ["Held up", "Failed within 30 days"], values: [+(cr(billed) - cr(failed)).toFixed(2), +cr(failed).toFixed(2)] }], {
    x: 0.6, y: 1.4, w: 6.1, h: 5.4, holeSize: 58, chartColors: [GREEN, RED], showPercent: true, showValue: false, showLegend: true, legendPos: "b", legendFontSize: 14,
    dataLabelFontSize: 16, dataLabelColor: WHITE, showTitle: true, title: `Where the ₹${cr(billed).toFixed(2)} Cr billed went`, titleFontSize: 16, titleColor: INK, dataBorder: { pt: 2, color: "FFFFFF" }, ...chartFonts(INK), dataLabelColor: WHITE,
  });
  const cards = [[`₹${cr(budget).toFixed(2)} Cr`, "repair budget across 24 wards", INK], ["2,499", "repairs billed this season", INK], ["611", "repairs that failed within 30 days", RED], ["435", "issues with no repair linked", RED]];
  cards.forEach(([b, l, c], i) => stat(s, 7.1 + (i % 2) * 2.95, 1.6 + Math.floor(i / 2) * 2.45, 2.75, 2.25, b, l, c));
  T(s, "Source: the app's own records (budget books, work orders, complaints).", { x: 7.1, y: 6.55, w: 5.6, h: 0.3, fontSize: 11, color: MUTED });
}

// =========================== 4. every ward ===========================
{
  const s = slide("LIGHT", "The problem", "It is not one bad ward", "Failed-repair spend is a citywide pattern. Raju's own ward, K E, sits at twenty four percent. The ten worst wards run between twenty six and forty percent.");
  const rows = [...worst.map((w) => [w.ward_code, w.failed_pct]), ["K/E", ke.failed_pct]];
  s.addChart(pptx.charts.BAR, [{ name: "Share of billed money that failed within 30 days (%)", labels: rows.map((r) => r[0]), values: rows.map((r) => r[1]) }], {
    x: 0.6, y: 1.4, w: 7.6, h: 5.45, barDir: "bar", chartColors: [...worst.map(() => AMBER), BLUE], showValue: true, dataLabelFormatCode: '0"%"', dataLabelFontSize: 13, dataLabelPosition: "outEnd",
    catAxisOrientation: "maxMin", valAxisHidden: true, valGridLine: { style: "none" }, catGridLine: { style: "none" }, catAxisLabelFontSize: 14, valAxisMaxVal: 48, valAxisMinVal: 0,
    showTitle: true, title: "Failed-repair share of billed money, by ward (10 worst + Raju's ward)", titleFontSize: 14, titleColor: INK, showLegend: false, ...chartFonts(INK),
  });
  stat(s, 8.6, 1.6, 4.1, 2.0, `${ke.failed_pct}%`, "of Raju's ward K/E billing failed within 30 days", BLUE);
  stat(s, 8.6, 3.85, 4.1, 2.0, `${Math.round((100 * failed) / billed)}%`, "citywide: failed within 30 days", RED);
  T(s, `Ward K/E met its repair deadline on ${ke.sla_pct}% of jobs.`, { x: 8.6, y: 6.1, w: 4.1, h: 0.7, fontSize: 14, color: MUTED, valign: "top" });
}

// =========================== 5. four blind spots ===========================
{
  const s = slide("LIGHT", "The problem", "Four people. Four blind spots.", "Each person in the system is working half blind. Citizens cannot see outcomes. Officers cannot see history at the moment of award. Contractors have no place to answer. Auditors cannot trust a record anyone could edit. Apla Shahar gives each of them one thing.");
  const who = [
    ["citizen", "Citizen", "Complaints vanish. No way to see who fixed what, or what it cost.", "A public money trail, complaint tracking, answers in Marathi."],
    ["officer", "Ward officer", "Awards work without the contractor's history; hand-writes file notes.", "Cited risk flags, pre-award checks, a drafted file note."],
    ["contractor", "Contractor", "Judged on rumour, with no place to put the facts.", "A public scorecard with a clean-record view and right of reply."],
    ["auditor", "Auditor", "Records that anyone can edit, with no trail.", "An append-only, hash-chained log you can verify and export."],
  ];
  who.forEach(([k, name, today, gets], i) => {
    const x = 0.6 + i * 3.1;
    R(s, { x, y: 1.5, w: 2.9, h: 5.3, fill: TINT });
    img(s, `${A}/${k}.png`, x + 0.6, 1.65, 1.7, 1.7, { alt: name });
    T(s, name, { x: x + 0.25, y: 3.45, w: 2.4, h: 0.4, fontFace: FH, fontSize: 20, bold: true, align: "center" });
    T(s, "TODAY", { x: x + 0.25, y: 3.95, w: 2.4, h: 0.25, fontSize: 11, bold: true, color: RED });
    T(s, today, { x: x + 0.25, y: 4.2, w: 2.4, h: 1.05, fontSize: 14, valign: "top" });
    T(s, "WITH APLA SHAHAR", { x: x + 0.25, y: 5.3, w: 2.4, h: 0.25, fontSize: 11, bold: true, color: GREEN });
    T(s, gets, { x: x + 0.25, y: 5.55, w: 2.4, h: 1.15, fontSize: 14, valign: "top" });
  });
}

// =========================== 6. meet Raju ===========================
{
  const s = slide("DARK", "Meet Raju", "Meet Raju", "Raju lives in Marol, Andheri East, ward K E. A pothole outside his lane has already thrown two scooters. He has three questions nobody can answer for him today.");
  img(s, `${A}/raju.png`, 0.9, 1.4, 4.2, 5.3, { alt: "Raju, a citizen standing with question marks around him" });
  T(s, "Raju lives in Marol, Andheri East (Ward K/E).", { x: 5.7, y: 1.5, w: 7.0, h: 0.6, fontFace: FH, fontSize: 20, color: WHITE });
  T(s, "A pothole outside his lane has already thrown two scooters.", { x: 5.7, y: 2.2, w: 7, h: 0.5, fontSize: 18, color: "E9E5DA" });
  ["Who fixed my road?", "What did it cost?", "Will it hold through the monsoon?"].forEach((q, i) => {
    R(s, { x: 5.7, y: 3.2 + i * 1.05, w: 6.6, h: 0.85, fill: "3B3326" });
    T(s, "?", { x: 5.95, y: 3.2 + i * 1.05, w: 0.5, h: 0.85, fontFace: FH, fontSize: 32, bold: true, color: BRIGHT, valign: "middle" });
    T(s, q, { x: 6.6, y: 3.2 + i * 1.05, w: 5.6, h: 0.85, fontFace: FH, fontSize: 22, color: WHITE, valign: "middle" });
  });
  T(s, "Raju is a fictional citizen. All data is synthetic.", { x: 5.7, y: 6.55, w: 7, h: 0.3, fontSize: 11, color: "B8B2A4" });
}

// =========================== 7. the journey ===========================
{
  const s = slide("LIGHT", "Meet Raju", "Raju's journey, in eight steps", "Eight steps, each one a feature we demonstrated live in a browser: see the money, check the road, complain, support rather than duplicate, ask in Marathi, officer acts on evidence, repair verified, and RTI if ignored.");
  const steps = [
    ["eye", "See the money", "Public home: budget, billed, failed repairs. No login."],
    ["pin", "Check his road", "Map of failed repairs and roads under warranty."],
    ["camera", "Raise a complaint", "Mobile number, GPS, map pin, photo and video."],
    ["people", "Support, don't duplicate", "\"I have this problem too\": one vote each."],
    ["chat", "Ask in Marathi", "Answers only from the records, with sources."],
    ["flag", "Officer acts on evidence", "Verifies, checks the contractor, assigns."],
    ["check", "Repair verified", "Bill vs rate card, approved, Raju notified."],
    ["doc", "RTI if ignored", "One-click draft with officer, fee and clock."],
  ];
  R(s, { x: 1.0, y: 2.62, w: 11.3, h: 0.1, fill: "D9D6CE", rectRadius: 0.05 });
  steps.forEach(([k, h, d], i) => {
    const x = 0.6 + i * 1.5;
    icon(s, k, x + 0.17, 2.15, 1.0, h);
    T(s, String(i + 1), { x, y: 1.55, w: 1.35, h: 0.45, fontFace: FH, fontSize: 24, bold: true, color: AMBER, align: "center" });
    T(s, h, { x, y: 3.35, w: 1.4, h: 0.85, fontSize: 14, bold: true, align: "center", valign: "top" });
    T(s, d, { x, y: 4.25, w: 1.4, h: 1.9, fontSize: 12, color: MUTED, align: "center", valign: "top" });
  });
  R(s, { x: 0.6, y: 6.2, w: 12.1, h: 0.65, fill: TINT });
  T(s, "Every step below was recorded end to end in a real browser, with video and screenshots.", { x: 0.9, y: 6.2, w: 11.5, h: 0.65, fontSize: 16, italic: true, valign: "middle" });
}

// =========================== 8. see the money (K/E flags) ===========================
{
  const s = slide("LIGHT", "How Apla Shahar helps", "Steps 1–2 · Raju sees where the money went", "Raju opens his ward page. Of one hundred sixty five repairs in K E, sixty four missed their deadline, thirty nine failed within thirty days, and thirty never had a repair linked. These counts come from the officer console's flag chips for the same ward.");
  const flags = [["Missed deadline (SLA)", 64], ["Failed within 30 days", 39], ["No repair linked", 30], ["Billed on road under warranty", 7], ["Estimate drift", 4], ["Cost above rate card", 4], ["Possible double billing", 2]];
  s.addChart(pptx.charts.BAR, [{ name: "Work orders", labels: flags.map((f) => f[0]), values: flags.map((f) => f[1]) }], {
    x: 0.6, y: 1.4, w: 6.3, h: 5.45, barDir: "bar", chartColors: [RED, RED, AMBER, AMBER, AMBER, AMBER, AMBER], showValue: true, dataLabelFontSize: 14, dataLabelPosition: "outEnd", catAxisOrientation: "maxMin",
    valAxisHidden: true, valGridLine: { style: "none" }, catGridLine: { style: "none" }, catAxisLabelFontSize: 13, valAxisMaxVal: 76, showLegend: false,
    showTitle: true, title: "Ward K/E: 165 work orders, by flag", titleFontSize: 14, titleColor: INK, ...chartFonts(INK),
  });
  const p = img(s, `${S}/04-wards-03-ward-summary.png`, 7.3, 1.55, 5.4, 3.4, { frame: true, alt: "Public ward page for K/E" });
  T(s, "The public ward page (screenshot from the running app)", { x: 7.3, y: p.y + p.h + 0.12, w: 5.4, h: 0.3, fontSize: 11, color: MUTED });
  stat(s, 7.3, 5.3, 5.4, 1.5, "64 of 165", "repairs missed their deadline in Raju's ward", RED);
}

// =========================== 9. complain ===========================
{
  const s = slide("LIGHT", "How Apla Shahar helps", "Steps 3–4 · Raju complains, and is heard", "Raju registers with only his mobile number, adds a description, GPS location, a pin, a photo and a video, and gets a tracking page. If a neighbour already reported it, he supports that complaint instead of filing a duplicate.");
  img(s, `${S}/09-citizen-raise-04-form-filled.png`, 0.6, 1.45, 5.9, 3.95, { frame: true, alt: "Complaint form with GPS, pin, photo and video" });
  img(s, `${S}/09-citizen-raise-05-ticket.png`, 6.85, 1.45, 5.9, 3.95, { frame: true, alt: "Tracking page for the complaint" });
  T(s, "Raising the complaint", { x: 0.6, y: 5.45, w: 5.9, h: 0.3, fontSize: 12, color: MUTED, align: "center" });
  T(s, "Tracking page, straight away", { x: 6.85, y: 5.45, w: 5.9, h: 0.3, fontSize: 12, color: MUTED, align: "center" });
  [["camera", "Photo and video", "Evidence attached on the spot"], ["pin", "GPS plus a map pin", "Exact enough, public view blurred to 100 m"], ["people", "Support, don't duplicate", "One vote each; voters stay private"]].forEach(([k, h, d], i) => {
    const x = 0.6 + i * 4.1;
    icon(s, k, x, 5.95, 0.8, h);
    T(s, h, { x: x + 0.95, y: 5.95, w: 3.0, h: 0.4, fontSize: 16, bold: true });
    T(s, d, { x: x + 0.95, y: 6.35, w: 3.0, h: 0.5, fontSize: 12, color: MUTED, valign: "top" });
  });
}

// =========================== 10. language + ask ===========================
{
  const s = slide("LIGHT", "How Apla Shahar helps", "Step 5 · Raju asks in his own language", "Raju switches the whole app to Marathi and asks in his own words. The answer comes only from promoted records, with sources. If data is missing, the assistant says so and offers an RTI draft.");
  [["chat", "Marathi, Hindi, English", "One switch changes every label."], ["robot", "Answers from records only", "Each answer cites its sources; it describes facts and never accuses."], ["doc", "Missing data? It says so", "Then offers a ready RTI draft instead of guessing."]].forEach(([k, h, d], i) => {
    const y = 1.6 + i * 1.8;
    icon(s, k, 0.6, y, 1.1, h);
    T(s, h, { x: 1.95, y, w: 4.0, h: 0.5, fontFace: FH, fontSize: 20, bold: true });
    T(s, d, { x: 1.95, y: y + 0.55, w: 4.0, h: 0.9, fontSize: 14, color: MUTED, valign: "top" });
  });
  img(s, `${S}/06-ask-03-answer-marathi.png`, 6.3, 1.45, 6.4, 5.4, { frame: true, alt: "Marathi question and answer in the Ask page" });
}

// =========================== 11. officer red flags ===========================
{
  const s = slide("LIGHT", "How Apla Shahar helps", "The officer sees red flags, with evidence", "One work order in Raju's ward, W O 25 01389 on Marol Maroshi Road, was billed sixty thousand seven hundred eighty five rupees against a standard rate of forty five thousand, thirty five percent over. It took seventy six hours against a twenty four hour target, and was billed on a road still under warranty. Each flag cites its evidence, and the contractor can reply.");
  s.addChart(pptx.charts.BAR, [{ name: "Rupees", labels: ["Billed", "Standard rate"], values: [60785, 45000] }], {
    x: 0.6, y: 1.4, w: 4.6, h: 3.6, barDir: "col", chartColors: [RED, GREEN], showValue: true, dataLabelFormatCode: "₹#,##0", dataLabelFontSize: 14, dataLabelPosition: "outEnd", valAxisHidden: true, valGridLine: { style: "none" },
    catGridLine: { style: "none" }, catAxisLabelFontSize: 14, valAxisMaxVal: 72000, valAxisMinVal: 0, showLegend: false, showTitle: true, title: "WO25-01389: 35% above the standard rate", titleFontSize: 14, titleColor: INK, ...chartFonts(INK),
  });
  stat(s, 0.6, 5.2, 2.2, 1.65, "76 h", "vs a 24 h target", RED);
  stat(s, 3.0, 5.2, 2.2, 1.65, "DLP", "road still under warranty", AMBER);
  img(s, `${S}/15-officer-console-03-flags.png`, 5.6, 1.45, 7.1, 5.4, { frame: true, alt: "Officer console showing numbered, cited flags for a work order" });
}

// =========================== 12. budget ===========================
{
  const s = slide("LIGHT", "How Apla Shahar helps", "Money left to spend wisely", "The budget planner shows that ward K E has about nine lakh rupees left of ninety one lakh, and ranks sixty nine open issues by flood risk, rainfall, accidents, and nearby schools and hospitals. It respects an eighty percent allocation cap and it is advisory only: officers decide.");
  s.addChart(pptx.charts.BAR, [{ name: "₹ lakh", labels: ["Budget", "Billed to date", "Remaining"], values: [91.0, 81.96, 9.04] }], {
    x: 0.6, y: 1.4, w: 5.4, h: 3.9, barDir: "col", chartColors: [BLUE, AMBER, GREEN], showValue: true, dataLabelFormatCode: '0.00" L"', dataLabelFontSize: 14, dataLabelPosition: "outEnd", valAxisHidden: true, valGridLine: { style: "none" },
    catGridLine: { style: "none" }, catAxisLabelFontSize: 14, valAxisMaxVal: 108, valAxisMinVal: 0, showLegend: false, showTitle: true, title: "Ward K/E budget planner (₹ lakh)", titleFontSize: 14, titleColor: INK, ...chartFonts(INK),
  });
  stat(s, 0.6, 5.5, 1.7, 1.35, "69", "open issues ranked", INK);
  stat(s, 2.45, 5.5, 1.7, 1.35, "80%", "allocation cap", INK);
  stat(s, 4.3, 5.5, 1.7, 1.35, "Advisory", "officers decide", GREEN, 22);
  img(s, `${S}/16-budget-01-summary.png`, 6.4, 1.45, 6.3, 5.4, { frame: true, alt: "Budget planner summary for ward K/E" });
}

// =========================== 13. contractors ===========================
{
  const s = slide("LIGHT", "How Apla Shahar helps", "Fair to contractors, too", "Contractors get a public scorecard. A clean record is always shown, every finding cites evidence, and the firm's reply sits next to the finding. The app describes what the records show. It never accuses.");
  [["check", "Clean record always shown", "Positive evidence is as visible as the flags."], ["doc", "Findings cite evidence", "Source rows and documents, not opinion."], ["chat", "Right of reply", "The firm's answer sits beside the finding."]].forEach(([k, h, d], i) => {
    const y = 1.6 + i * 1.5;
    icon(s, k, 0.6, y, 1.0, h);
    T(s, h, { x: 1.85, y, w: 3.9, h: 0.45, fontFace: FH, fontSize: 18, bold: true });
    T(s, d, { x: 1.85, y: y + 0.5, w: 3.7, h: 0.8, fontSize: 14, color: MUTED, valign: "top" });
  });
  R(s, { x: 0.6, y: 6.1, w: 5.0, h: 0.75, fill: TINT });
  T(s, "We describe what the records show. We never accuse.", { x: 0.85, y: 6.1, w: 4.6, h: 0.75, fontFace: FH, fontSize: 16, italic: true, valign: "middle" });
  img(s, `${S}/05-contractors-02-scorecard.png`, 5.95, 1.45, 3.4, 5.4, { frame: true, alt: "Contractor scorecard" });
  img(s, `${S}/11-contractor-report-06-reply-sent.png`, 9.45, 1.45, 3.3, 5.4, { frame: true, alt: "Contractor reply recorded against a finding" });
}

// =========================== 14. trust by design ===========================
{
  const s = slide("LIGHT", "Why it can be trusted", "AI proposes; rules or people decide", "Documents are read into claims. A claim only becomes a fact when a rule or a named human promotes it. Facts are append only and hash chained; corrections supersede, nothing is overwritten. Auditors can verify the chain and export it.");
  const nodes = [["doc", "Source documents", "PDFs and records"], ["robot", "AI reads them", "Produces claims, never facts"], ["check", "Rule or human", "Promotes a claim"], ["lock", "Fact, append-only", "Never overwritten"], ["chain", "Audit trail", "Verify and export"]];
  nodes.forEach(([k, h, d], i) => {
    const x = 0.6 + i * 2.5;
    icon(s, k, x + 0.5, 1.5, 1.0, h);
    T(s, h, { x: x - 0.1, y: 2.6, w: 2.2, h: 0.4, fontFace: FH, fontSize: 16, bold: true, align: "center" });
    T(s, d, { x: x - 0.1, y: 3.0, w: 2.2, h: 0.5, fontSize: 12, color: MUTED, align: "center", valign: "top" });
    if (i < 4) s.addShape(pptx.ShapeType.rightArrow, { x: x + 1.85, y: 1.8, w: 0.5, h: 0.4, fill: { color: AMBER }, line: { color: AMBER, width: 0 } });
  });
  img(s, `${S}/17-audit-02-log.png`, 0.6, 3.75, 6.3, 3.1, { frame: true, alt: "Audit log rows with source file, row, hash and promoter" });
  ["The model never writes facts, only claims.", "Flags, never a composite score, and officer-only.", "Corrections supersede; nothing is overwritten.", "Every human action is logged with an officer ID."].forEach((t, i) => {
    T(s, [{ text: t, options: { bullet: true } }], { x: 7.3, y: 3.95 + i * 0.7, w: 5.4, h: 0.6, fontSize: 16, valign: "middle" });
  });
}

// =========================== 15. before / after ===========================
{
  const s = slide("LIGHT", "Wrap-up", "Raju's story: before and after", "Same pothole, same Raju. Before: a complaint that vanished, no cost, no contractor, no language, no recourse. After: tracked end to end with evidence, public bills against the rate card, a scorecard with a right of reply, his own language, and a one-click RTI.");
  const rows = [["His complaint vanishes", "Tracked from raised to resolved, with photo evidence"], ["No idea what was spent", "Bill vs standard rate, public"], ["Contractor unknown", "Scorecard with clean record and right of reply"], ["English-only paperwork", "Marathi, Hindi and English"], ["No recourse", "One-click RTI draft, ready to file"]];
  R(s, { x: 0.6, y: 1.5, w: 5.6, h: 0.65, fill: RED });
  T(s, "Before", { x: 0.85, y: 1.5, w: 5.1, h: 0.65, fontFace: FH, fontSize: 22, bold: true, color: WHITE, valign: "middle" });
  R(s, { x: 7.1, y: 1.5, w: 5.6, h: 0.65, fill: GREEN });
  T(s, "With Apla Shahar", { x: 7.35, y: 1.5, w: 5.1, h: 0.65, fontFace: FH, fontSize: 22, bold: true, color: WHITE, valign: "middle" });
  rows.forEach(([a, b], i) => {
    const y = 2.4 + i * 0.88;
    R(s, { x: 0.6, y, w: 5.6, h: 0.72, fill: TINT });
    T(s, a, { x: 0.85, y, w: 5.1, h: 0.72, fontSize: 16, valign: "middle" });
    s.addShape(pptx.ShapeType.rightArrow, { x: 6.4, y: y + 0.13, w: 0.5, h: 0.46, fill: { color: AMBER }, line: { color: AMBER, width: 0 } });
    R(s, { x: 7.1, y, w: 5.6, h: 0.72, fill: TINT });
    T(s, b, { x: 7.35, y, w: 5.1, h: 0.72, fontSize: 16, valign: "middle" });
  });
}

// =========================== 16. close ===========================
{
  const s = slide("DARK", "Wrap-up", "", "Close. Every rupee, every repair, every record, in public view: for Raju, and for everyone.");
  s.addImage({ path: `${A}/hero.png`, x: 0, y: 0, w: 13.333, h: 7.5, altText: "Dusk skyline over a Mumbai road", sizing: { type: "cover", w: 13.333, h: 7.5 } });
  R(s, { shape: pptx.ShapeType.rect, x: 0, y: 0, w: 13.333, h: 7.5, fill: INK, transparency: 28, rectRadius: 0 });
  T(s, "Every rupee. Every repair. Every record.", { x: 0.9, y: 1.7, w: 11.5, h: 1.8, fontFace: FH, fontSize: 48, bold: true, color: WHITE, valign: "top" });
  T(s, "In public view, for Raju and for everyone.", { x: 0.9, y: 3.6, w: 11, h: 0.6, fontFace: FH, fontSize: 26, italic: true, color: BRIGHT });
  ["18 scenes recorded end to end in a real browser", "Citizen → officer → contractor → citizen, in one workflow", "The AI proposes. Rules or named people decide."].forEach((t, i) => {
    R(s, { x: 0.9 + i * 3.95, y: 5.0, w: 3.75, h: 1.2, fill: INK, transparency: 15 });
    T(s, t, { x: 1.1 + i * 3.95, y: 5.0, w: 3.35, h: 1.2, fontSize: 16, color: WHITE, valign: "middle" });
  });
}

await pptx.writeFile({ fileName: OUTFILE });
const { applyTheme } = createRequire(import.meta.url)(`${homedir()}/.claude/skills/pptx/scripts/apply_theme.js`);
await applyTheme(OUTFILE, THEME);
console.log("wrote", OUTFILE, "slides:", n);
