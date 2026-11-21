// Records video + screenshot evidence of every Ward Ledger feature with Playwright.
//   Stack for this run (isolated from the dev servers on 3000/8000):  UI :3100   API :8100
//   node record.mjs            -> output/videos/raw/*.webm, output/shots/*.png, output/manifest.json
//   node record.mjs 07 08      -> only scenes whose id starts with 07 or 08 (manifest is merged)
import { chromium } from "playwright";
import { mkdirSync, existsSync, readFileSync, writeFileSync, renameSync, rmSync } from "node:fs";

const BASE = process.env.BASE || "http://localhost:3100";
const API = process.env.API || "http://localhost:8100/api";
const PW = process.env.WL_DEMO_PASSWORD || "wardledger-demo";
const OUT = process.env.OUT_DIR || "output";
const RAW = `${OUT}/videos/raw`;
const SHOTS = `${OUT}/shots`;
[RAW, SHOTS].forEach((d) => mkdirSync(d, { recursive: true }));
const only = process.argv.slice(2);

const manifestPath = process.env.MANIFEST || `${OUT}/manifest.json`;
const manifest = existsSync(manifestPath) && only.length ? JSON.parse(readFileSync(manifestPath, "utf8")) : { scenes: [] };

const DESKTOP = { width: 1440, height: 900 };
const MOBILE = { width: 390, height: 844 };
const problems = [];

// ---------- page-level helpers ----------
const INIT = () => {
  const css = document.createElement("style");
  css.textContent = `nextjs-portal{display:none!important}
  #__cap{position:fixed;left:50%;bottom:18px;transform:translateX(-50%);z-index:2147483647;max-width:86%;padding:10px 20px;border-radius:10px;
    background:rgba(20,18,12,.92);color:#fff;font:600 17px/1.35 Inter,system-ui,sans-serif;box-shadow:0 6px 24px rgba(0,0,0,.35);pointer-events:none;text-align:center;display:none}
  #__cap b{color:#f5a623;margin-right:8px}
  #__cur{position:fixed;left:0;top:0;width:22px;height:22px;margin:-11px 0 0 -11px;border-radius:50%;background:rgba(245,166,35,.55);border:2px solid #b45309;
    z-index:2147483647;pointer-events:none;transition:transform .05s linear,background .1s}
  #__cur.dn{background:rgba(220,38,38,.65)}`;
  const mount = () => {
    if (document.getElementById("__cap")) return;
    document.documentElement.appendChild(css);
    const cap = document.createElement("div"); cap.id = "__cap";
    const cur = document.createElement("div"); cur.id = "__cur";
    document.documentElement.append(cap, cur);
    const set = (t) => { if (t) { cap.innerHTML = t; cap.style.display = "block"; } else cap.style.display = "none"; };
    window.__setCap = (t) => { sessionStorage.setItem("__cap", t || ""); set(t); };
    set(sessionStorage.getItem("__cap"));
    const pos = JSON.parse(sessionStorage.getItem("__pos") || "[40,40]");
    cur.style.transform = `translate(${pos[0]}px,${pos[1]}px)`;
    addEventListener("mousemove", (e) => { cur.style.transform = `translate(${e.clientX}px,${e.clientY}px)`; sessionStorage.setItem("__pos", JSON.stringify([e.clientX, e.clientY])); }, true);
    addEventListener("mousedown", () => cur.classList.add("dn"), true);
    addEventListener("mouseup", () => cur.classList.remove("dn"), true);
  };
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", mount); else mount();
};

async function pick(sel, re) { // select by regex on the visible option text
  const opts = await sel.locator("option").allInnerTexts();
  const hit = opts.find((o) => re.test(o));
  if (!hit) throw new Error("no option matching " + re);
  await sel.selectOption({ label: hit });
}
const pause = (p, ms = 1100) => p.waitForTimeout(ms);
const cap = (p, step, text) => p.evaluate(([s, t]) => window.__setCap && window.__setCap(t ? `<b>${s}</b>${t}` : ""), [step, text]).catch(() => {});
async function go(p, path, ms = 900) {
  await p.goto(BASE + path, { waitUntil: "networkidle", timeout: 60000 });
  await pause(p, ms);
}
async function hc(p, loc, { ms = 700, force = false } = {}) { // human-looking click
  await loc.scrollIntoViewIfNeeded();
  const b = await loc.boundingBox();
  if (b) { await p.mouse.move(b.x + b.width / 2, b.y + b.height / 2, { steps: 18 }); await pause(p, 250); }
  await loc.click({ force });
  await pause(p, ms);
}
async function type(p, loc, text, ms = 45) {
  await loc.scrollIntoViewIfNeeded();
  const b = await loc.boundingBox();
  if (b) await p.mouse.move(b.x + 30, b.y + b.height / 2, { steps: 14 });
  await loc.click();
  await loc.pressSequentially(text, { delay: ms });
  await pause(p, 400);
}
async function scrollThrough(p, steps = 3, each = 1400, frac = 0.75) {
  for (let i = 0; i < steps; i++) {
    await p.evaluate((f) => window.scrollBy({ top: innerHeight * f, behavior: "smooth" }), frac);
    await pause(p, each);
  }
}
const toTop = async (p) => { await p.evaluate(() => window.scrollTo({ top: 0, behavior: "smooth" })); await pause(p, 900); };
async function login(p, role, id, pw = PW) {
  await go(p, `/login/${role}`, 600);
  const label = role === "citizen" ? "Mobile number" : role === "officer" ? "Employee ID" : "Contractor login ID";
  await type(p, p.getByLabel(label, { exact: true }), id, 55);
  await type(p, p.getByLabel("Password", { exact: true }), pw, 35);
  await hc(p, p.locator("main form button[type=submit], main form button:not([type])").last(), { ms: 300 });
  await p.waitForURL((u) => !u.pathname.startsWith("/login"), { timeout: 30000 });
  await pause(p, 1200);
}
async function logout(p) {
  await hc(p, p.getByRole("button", { name: "Log out" }), { ms: 300 });
  await p.waitForURL(`${BASE}/`);
  await pause(p, 700);
}

// ---------- scene runner ----------
async function scene(id, title, desc, opts, fn) {
  if (only.length && !only.some((o) => id.startsWith(o))) return;
  console.log(`\n== ${id} ${title}`);
  const t0 = Date.now();
  const vp = opts.mobile ? MOBILE : DESKTOP;
  const ctx = await browser.newContext({
    viewport: vp,
    recordVideo: { dir: RAW, size: vp },
    geolocation: { latitude: geo.lat, longitude: geo.lon, accuracy: 12 },
    permissions: ["geolocation"],
    deviceScaleFactor: 1,
    hasTouch: !!opts.mobile,
  });
  await ctx.addInitScript(() => localStorage.setItem("wl.lang", "en"));
  await ctx.addInitScript(INIT);
  const p = await ctx.newPage();
  const rec = { id, title, desc, mobile: !!opts.mobile, shots: [], notes: [], status: "ok" };
  p.on("pageerror", (e) => problems.push(`[${id}] pageerror: ${String(e).slice(0, 160)}`));
  p.on("response", (r) => r.url().startsWith(API) && r.status() >= 500 && problems.push(`[${id}] HTTP ${r.status()} ${r.url().replace(API, "")}`));
  const ctxApi = {
    shot: async (name, caption, full = false) => {
      await p.evaluate(() => { const c = document.getElementById("__cap"), u = document.getElementById("__cur"); c && (c.dataset.d = c.style.display, c.style.display = "none"); u && (u.style.display = "none"); }).catch(() => {});
      const file = `${id}-${String(rec.shots.length + 1).padStart(2, "0")}-${name}.png`;
      await p.screenshot({ path: `${SHOTS}/${file}`, fullPage: full });
      await p.evaluate(() => { const c = document.getElementById("__cap"), u = document.getElementById("__cur"); c && (c.style.display = c.dataset.d || "none"); u && (u.style.display = ""); }).catch(() => {});
      rec.shots.push({ file, caption });
    },
    soft: async (label, f) => { try { await f(); } catch (e) { const m = `${label}: ${String(e).split("\n")[0].slice(0, 140)}`; rec.notes.push(m); console.log("  ! " + m); } },
  };
  try {
    await fn(p, ctxApi);
  } catch (e) {
    rec.status = "FAILED: " + String(e).split("\n").slice(0, 2).join(" | ");
    console.log("  FAILED " + rec.status);
    await p.screenshot({ path: `${OUT}/FAILED-${id}.png` }).catch(() => {});
  }
  await cap(p, "", "");
  await pause(p, 600);
  const vid = p.video();
  await ctx.close();
  const dest = `${RAW}/${id}.webm`;
  try { rmSync(dest, { force: true }); renameSync(await vid.path(), dest); rec.video = dest; } catch (e) { rec.status += " (no video: " + e.message + ")"; }
  rec.seconds = Math.round((Date.now() - t0) / 1000);
  const i = manifest.scenes.findIndex((s) => s.id === id);
  if (i >= 0) manifest.scenes[i] = rec; else manifest.scenes.push(rec);
  manifest.scenes.sort((a, b) => a.id.localeCompare(b.id));
  writeFileSync(manifestPath, JSON.stringify(manifest, null, 2));
  console.log(`   ${rec.status} - ${rec.shots.length} shots, ${rec.seconds}s${rec.notes.length ? `, ${rec.notes.length} soft issues` : ""}`);
}

// ---------- setup ----------
const ke = await (await fetch(`${API}/roads/geojson?ward=K/E`)).json();
const [lon0, lat0] = ke.features[3].geometry.coordinates[0];
const geo = { lat: lat0, lon: lon0 };
const browser = await chromium.launch({ headless: process.env.HEADED !== "1", args: process.env.HEADED === "1" ? ["--window-size=1500,1000", "--window-position=20,20"] : [] });
const mobileNo = "97" + String(Date.now()).slice(-8);
const citizenPw = "citizen-pass-" + Date.now().toString(36);
const state = {};

// tiny test fixtures for uploads
const pngCtx = await browser.newContext({ viewport: { width: 640, height: 400 } });
const pngPage = await pngCtx.newPage();
await pngPage.setContent(`<body style="margin:0;background:linear-gradient(#6b6b6b,#3c3c3c);width:640px;height:400px;font:700 44px system-ui;color:#fcd34d;display:flex;align-items:center;justify-content:center">pothole - K/E ward</body>`);
const png = await pngPage.screenshot();
await pngPage.setContent(`<body style="margin:0;background:linear-gradient(#444,#222);width:640px;height:400px;font:700 44px system-ui;color:#86efac;display:flex;align-items:center;justify-content:center">after repair - hot mix</body>`);
const pngAfter = await pngPage.screenshot();
await pngCtx.close();
const mp4 = Buffer.concat([Buffer.from([0, 0, 0, 0x18]), Buffer.from("ftypmp42"), Buffer.alloc(4), Buffer.from("mp42isom"), Buffer.alloc(400)]);
const pdf = Buffer.from("%PDF-1.4\n1 0 obj << /Type /Catalog >> endobj\ntrailer << /Root 1 0 R >>\n%%EOF\n");

// =====================================================================
// PUBLIC FEATURES (no login)
// =====================================================================
await scene("01-home", "Public home: headline numbers and search", "Anyone can open the site with no login. Headline monsoon numbers for all 24 wards, search by complaint ID or place, and a ward picker.", {}, async (p, s) => {
  await go(p, "/");
  await cap(p, "1", "Public home page: no login needed");
  await s.shot("hero", "Hero with search, 'Raise a complaint', 'Use my location' and ward picker");
  await pause(p, 1200);
  await s.soft("carousel", async () => { await hc(p, p.getByRole("button", { name: /next/i }).first(), { ms: 1400 }); await hc(p, p.getByRole("button", { name: /next/i }).first(), { ms: 1400 }); });
  await cap(p, "2", "Headline numbers across all 24 wards");
  await scrollThrough(p, 2, 1500, 0.7);
  await s.shot("stats", "Budget, billed amount, repairs that failed within 30 days, issues with no repair linked", true);
  await toTop(p);
  await cap(p, "3", "Search by complaint ID or place");
  await type(p, p.locator("main input[type=text], main input:not([type])").first(), "BMC25-003412");
  await hc(p, p.getByRole("button", { name: "Search" }), { ms: 1800 });
  await s.shot("search-result", "Search lands on the complaint record");
  await go(p, "/");
  await cap(p, "4", "Pick your ward");
  await s.soft("ward select", async () => { await pick(p.locator("main select").first(), /K\/E/); await pause(p, 1800); });
  await s.shot("ward-picked", "Ward picker opens that ward's page");
});

await scene("02-complaints", "Complaints: app tickets and the 2025 BMC records", "Every complaint raised in the app is public and filterable by status, ward and category; the recorded 2025 BMC complaints each have a record page showing what happened, the repair and the source rows.", {}, async (p, s) => {
  await go(p, "/complaints");
  await cap(p, "1", "Complaints raised in this app (live workflow)");
  await s.shot("app-tab", "Complaints raised in this app, with status and support counts");
  await scrollThrough(p, 1, 1200);
  await toTop(p);
  await cap(p, "2", "Filter by status, ward and category");
  const sels = p.locator("main select");
  await s.soft("filters", async () => {
    await pick(sels.nth(1), /K\/E/); await pause(p, 1400);
    await pick(sels.nth(2), /pothole|road/i); await pause(p, 1400);
    await pick(sels.nth(0), /resolved|open/i); await pause(p, 1400);
  });
  await s.shot("filtered", "Filtered list: ward, category and status");
  await s.soft("search", async () => {
    await cap(p, "3", "Search by complaint ID");
    await type(p, p.getByPlaceholder("CMP-000001"), "CMP-000003"); await pause(p, 1500);
  });
  await s.shot("searched", "Search narrows the list to one complaint");
  await cap(p, "4", "A recorded 2025 BMC complaint: what happened, the repair, what the records show");
  await go(p, "/complaint/BMC25-003412", 1200);
  await s.shot("record-top", "Complaint record: what happened and the repair");
  await scrollThrough(p, 2, 1700, 0.8);
  await s.shot("record-evidence", "What the records show, with source references", true);
});

await scene("03-map", "Map of roads and repairs", "Ward polygons and road segments coloured by how often repairs failed; dashed lines are under warranty (DLP); thick lines have open issues; tapping a road opens its history.", {}, async (p, s) => {
  await go(p, "/map", 2500);
  await cap(p, "1", "All wards: road colour shows how often repairs failed");
  await s.shot("overview", "Map overview with legend");
  await s.soft("ward zoom", async () => {
    await cap(p, "2", "Pick a ward to zoom in");
    await pick(p.locator("main select").first(), /K\/E/); await pause(p, 3000);
  });
  await s.shot("ward-zoom", "Ward K/E zoomed in");
  await s.soft("road click", async () => {
    await cap(p, "3", "Tap a road to see its history");
    const roads = p.locator("path.leaflet-interactive");
    const c = await roads.count(); console.log("   road paths:", c);
    await hc(p, roads.nth(Math.min(5, c - 1)), { ms: 1500, force: true });
  });
  await s.shot("road-popup", "Road popup with link to the road page");
  await s.soft("open road", async () => { await hc(p, p.getByRole("link", { name: /Open road page/ }).first(), { ms: 2000 }); });
  await s.shot("road-page", "Road page with repair history");
});

await scene("04-wards", "Ward comparison and the money trail", "All 24 wards side by side (budget, billed, failed spend, SLA); a ward page shows the money trail from complaint to repair, by contractor, method and month.", {}, async (p, s) => {
  await go(p, "/wards", 1200);
  await cap(p, "1", "Compare all 24 wards");
  await s.shot("compare", "Ward comparison table", true);
  await s.soft("sort", async () => {
    await cap(p, "2", "Click a column to sort");
    for (const re of [/Failed/i, /Used/i]) await hc(p, p.getByRole("button", { name: re }).or(p.locator("th", { hasText: re })).first(), { ms: 1300 });
  });
  await s.shot("sorted", "Sorted by a column");
  await cap(p, "3", "Open a ward: summary and money trail");
  await go(p, "/ward/K%2FE", 1500);
  await s.shot("ward-summary", "Ward K/E summary");
  await scrollThrough(p, 3, 1700, 0.8);
  await s.shot("ward-full", "From complaint to repair, by contractor, by method, by month", true);
});

await scene("05-contractors", "Contractor scorecards (public) with right of reply", "Each empanelled firm has a civic trust scorecard with a mandatory clean-record view, findings that cite their evidence, and the firm's own reply. Facts only, no accusation.", {}, async (p, s) => {
  await go(p, "/contractors", 1200);
  await cap(p, "1", "Empanelled contractors, ranked by trust score");
  await s.shot("list", "Contractors list with civic trust scores");
  await s.soft("open", async () => { await hc(p, p.getByRole("link", { name: /Deccan Paving/ }).first(), { ms: 2000 }); });
  if (!p.url().includes("/contractor/")) await go(p, "/contractor/CT05", 1500);
  await cap(p, "2", "Scorecard: clean record, by ward, findings");
  await s.shot("scorecard", "Contractor scorecard");
  await scrollThrough(p, 3, 1700, 0.8);
  await s.shot("findings", "Findings with evidence and the contractor's reply", true);
  await cap(p, "3", "Facts only: 'We describe what the records show. We do not make accusations.'");
  await pause(p, 1800);
});

await scene("06-ask", "Ask: plain-language answers from the records", "A citizen types a complaint ID or describes the problem in Marathi, Hindi or English; the bot answers only from promoted records, cites sources, and offers an RTI draft when something is missing.", {}, async (p, s) => {
  await go(p, "/ask", 1000);
  const box = p.locator("main input").first();
  await cap(p, "1", "Ask by complaint ID");
  await type(p, box, "BMC25-003412");
  await hc(p, p.getByRole("button", { name: "Ask", exact: true }), { ms: 2500 });
  await s.shot("answer-id", "Answer for a complaint ID: contractor, cost, SLA, DLP, with sources", true);
  await cap(p, "2", "Or describe it in your own words");
  await box.fill("");
  await type(p, box, "pothole near Andheri station");
  await hc(p, p.getByRole("button", { name: "Ask", exact: true }), { ms: 2500 });
  await s.shot("answer-text", "Free-text question resolved to candidate complaints/roads", true);
  await cap(p, "3", "Marathi works too");
  await s.soft("marathi chip", async () => { await hc(p, p.getByRole("button", { name: /अंधेरी/ }).or(p.getByText(/माझ्या अंधेरीच्या/)).first(), { ms: 2500 }); });
  await s.shot("answer-marathi", "Question and answer in Marathi", true);
  await s.soft("rti link", async () => { await cap(p, "4", "Missing data? Offer an RTI draft"); await hc(p, p.getByRole("link", { name: /RTI/ }).last(), { ms: 1500 }); });
});

await scene("07-rti", "RTI draft generator", "One click produces a Section 6(1) RTI application in Marathi and English: right Public Information Officer, ₹10 fee, 30-day clock, first-appeal path, asking only for public documents.", {}, async (p, s) => {
  await go(p, "/rti", 1000);
  await cap(p, "1", "Enter a complaint ID, work-order or road ID");
  await type(p, p.locator("main input").first(), "BMC25-003412");
  await s.shot("input", "RTI input");
  await hc(p, p.getByRole("button", { name: "Create draft" }), { ms: 2200 });
  await cap(p, "2", "Ready-to-file draft with PIO, fee, 30-day clock and appeal path");
  await s.shot("draft", "Generated RTI draft (Marathi)", true);
  await scrollThrough(p, 2, 1700, 0.8);
  await s.soft("english tab", async () => { await cap(p, "3", "Switch to English"); await toTop(p); await hc(p, p.getByRole("tab", { name: "English" }), { ms: 1800 }); });
  await s.shot("draft-en", "Same draft in English, 'for citizen verification'", true);
  await s.soft("copy", async () => { await hc(p, p.getByRole("button", { name: /Copy text/ }), { ms: 1200 }); });
});

await scene("08-language", "Marathi / Hindi / English across the whole UI", "A single language switch changes every label; Marathi is the default for citizens.", {}, async (p, s) => {
  await go(p, "/", 1000);
  const sel = () => p.locator("header select").first();
  await cap(p, "1", "English");
  await s.shot("en", "Home in English");
  for (const [v, label] of [["mr", "मराठी (Marathi)"], ["hi", "हिन्दी (Hindi)"]]) {
    await s.soft(v, async () => {
      await cap(p, "2", `Switch language: ${label}`);
      await sel().scrollIntoViewIfNeeded();
      const b = await sel().boundingBox(); await p.mouse.move(b.x + 20, b.y + 15, { steps: 15 });
      await sel().selectOption(v); await pause(p, 1800);
      await s.shot(v, `Home in ${label}`);
      await go(p, "/wards", 800);
      await s.shot(v + "-wards", `Wards page in ${label}`);
      await go(p, "/", 600);
    });
  }
  await sel().selectOption("en");
});

// =====================================================================
// LIVE COMPLAINT WORKFLOW (citizen -> officer -> contractor -> officer -> citizen)
// =====================================================================
await scene("09-citizen-raise", "Citizen registers and raises a complaint", "A citizen registers with a mobile number, raises a complaint with category, description, GPS location plus a map pin, a photo and a video, and gets a tracking page.", {}, async (p, s) => {
  await go(p, "/complaints", 1000);
  await cap(p, "1", "Browsing is open; raising a complaint needs a citizen login");
  await hc(p, p.getByRole("link", { name: "Raise a complaint" }).first(), { ms: 1300 });
  await s.shot("needs-login", "Raising a complaint asks for the citizen login");
  await hc(p, p.getByRole("link", { name: "Citizen login" }), { ms: 1000 });
  await cap(p, "2", "Create a citizen account with just a mobile number");
  await hc(p, p.getByRole("tab", { name: "Create account" }), { ms: 600 });
  await type(p, p.getByLabel("Mobile number", { exact: true }), mobileNo, 50);
  await type(p, p.getByLabel("Your name (optional)", { exact: true }), "Demo Citizen", 50);
  await type(p, p.getByLabel("Password", { exact: true }), citizenPw, 30);
  await hc(p, p.getByRole("checkbox"), { ms: 500 });
  await s.shot("register", "Citizen registration");
  await hc(p, p.getByRole("button", { name: "Create account" }).last(), { ms: 500 });
  await p.waitForURL(/\/complaints\/new/);
  await pause(p, 1200);
  await cap(p, "3", "Category and description");
  await p.locator("main select").first().selectOption("Pothole"); await pause(p, 500);
  await type(p, p.locator("main textarea").first(), "Deep pothole outside the school gate; two scooters fell this morning.", 28);
  await cap(p, "4", "Location: GPS plus a pin on the map");
  await hc(p, p.getByRole("button", { name: "Use my current location" }), { ms: 1200 });
  await p.getByText("from GPS").waitFor();
  const map = p.locator(".leaflet-container").first();
  await map.scrollIntoViewIfNeeded(); await pause(p, 600);
  const box = await map.boundingBox();
  await p.mouse.move(box.x + box.width * 0.6, box.y + box.height * 0.6, { steps: 20 });
  await p.mouse.click(box.x + box.width * 0.6, box.y + box.height * 0.6);
  await p.getByText("pin on map").waitFor();
  await pause(p, 1000);
  await s.shot("location", "GPS location and a map pin added", true);
  await cap(p, "5", "Attach a photo and a video");
  await p.locator("input[type=file][multiple]").first().setInputFiles([
    { name: "pothole.png", mimeType: "image/png", buffer: png },
    { name: "clip.mp4", mimeType: "video/mp4", buffer: mp4 },
  ]);
  await pause(p, 1500);
  await s.shot("form-filled", "Completed complaint form with media", true);
  await hc(p, p.getByRole("button", { name: "Submit complaint" }), { ms: 500 });
  await p.waitForURL(/\/ticket\/CMP-\d{6}/, { timeout: 30000 });
  state.ticket = p.url().match(/CMP-\d{6}/)[0];
  await p.getByText("Your complaint was received").waitFor();
  await cap(p, "6", `Complaint ${state.ticket} received: awaiting verification`);
  await pause(p, 1500);
  await s.shot("ticket", `Tracking page for ${state.ticket}`, true);
  await scrollThrough(p, 1, 1500);
  await logout(p);
});

await scene("10-officer-verify-assign", "Officer verifies the complaint and assigns a task (pre-award checks)", "The ward officer reviews the complaint queue, verifies it, then creates a task for a contractor. Pre-award checks show the contractor's record and a cost estimate before assigning.", {}, async (p, s) => {
  if (!state.ticket) throw new Error("no ticket from scene 09");
  await login(p, "officer", "ae-4471");
  await p.waitForURL(/\/officer\/K-E\/complaints/);
  await cap(p, "1", "Officer console: ward complaint queue by stage");
  await s.shot("queue", "Complaint queue: awaiting verification / ready to assign / resolved");
  await hc(p, p.getByRole("button", { name: new RegExp(state.ticket) }), { ms: 1500 });
  await p.getByText("Officer actions").waitFor();
  await cap(p, "2", "Review photo, location and support; then verify");
  await s.shot("detail", "Complaint detail with officer actions", true);
  await hc(p, p.getByRole("button", { name: "Verify complaint" }), { ms: 1500 });
  await p.getByRole("link", { name: "Assign to a contractor" }).waitFor();
  await s.shot("verified", "Complaint verified; assign link appears");
  await hc(p, p.getByRole("link", { name: "Assign to a contractor" }), { ms: 1500 });
  await p.waitForURL(/\/officer\/K-E\/tasks/);
  await p.getByRole("checkbox", { checked: true }).first().waitFor();
  await cap(p, "3", "Create a task: pick the contractor");
  await p.locator("main section select").first().selectOption("CT05"); await pause(p, 800);
  await hc(p, p.getByRole("button", { name: /Check the contractor/ }), { ms: 1200 });
  await p.getByText("Finished on time in").waitFor();
  await cap(p, "4", "Pre-award checks: contractor record, DLP overlap, cost estimate vs rate card");
  await scrollThrough(p, 1, 1500, 0.5);
  await s.shot("pre-award", "Pre-award checks before assigning", true);
  await hc(p, p.getByRole("button", { name: /^3\. Assign/ }), { ms: 800 });
  await p.waitForURL(/\/tasks\/TSK-\d{6}/);
  state.task = p.url().match(/TSK-\d{6}/)[0];
  await cap(p, "5", `Task ${state.task} assigned to the contractor`);
  await pause(p, 1500);
  await s.shot("task-assigned", `Task ${state.task} assigned`, true);
  await logout(p);
});

await scene("11-contractor-report", "Contractor starts work, submits the report, replies to findings", "The contractor sees assigned tasks, starts work, submits evidence (after photo, area, bill with PDF) and can post a reply that appears next to any finding about the firm.", {}, async (p, s) => {
  if (!state.task) throw new Error("no task from scene 10");
  await login(p, "contractor", "ct05");
  await p.waitForURL(/\/tasks$/);
  await cap(p, "1", "Contractor panel: tasks and findings about the firm");
  await s.shot("panel", "My tasks and findings about my firm");
  await hc(p, p.getByRole("link", { name: new RegExp(state.task) }).first(), { ms: 1500 });
  await cap(p, "2", "Start work");
  await s.shot("assigned", "Assigned task");
  await hc(p, p.getByRole("button", { name: "Start work" }), { ms: 1200 });
  await p.getByText("In progress").first().waitFor();
  await cap(p, "3", "Submit the resolution report with evidence and bill");
  await type(p, p.getByPlaceholder("What was done"), "Pothole cut to shape, cleaned, tack coat applied and filled with hot mix; rolled.", 22);
  await type(p, p.getByLabel("Area repaired (sqm)", { exact: true }), "2.5");
  await type(p, p.getByLabel("Bill amount (₹)", { exact: true }), "6900");
  await p.getByLabel("Photos or videos of the finished work", { exact: true }).setInputFiles([{ name: "after.png", mimeType: "image/png", buffer: pngAfter }]);
  await p.getByLabel("Bill documents (PDF or photo)", { exact: true }).setInputFiles([{ name: "bill.pdf", mimeType: "application/pdf", buffer: pdf }]);
  await pause(p, 1200);
  await s.shot("report-form", "Resolution report form", true);
  await hc(p, p.getByRole("button", { name: "Submit report" }), { ms: 800 });
  await p.getByText("Report submitted").first().waitFor();
  await cap(p, "4", "Report submitted: waiting for the officer's review");
  await pause(p, 1500);
  await s.shot("submitted", "Report submitted", true);
  await go(p, "/tasks", 1000);
  await s.soft("reply", async () => {
    await cap(p, "5", "Right of reply: the firm answers a finding");
    await scrollThrough(p, 1, 1200, 0.5);
    await hc(p, p.getByRole("button", { name: "Reply" }).first(), { ms: 800 });
    await type(p, p.locator("main textarea").last(), "Utility trench was dug by the gas utility after our handover; photos attached for the officer.", 25);
    await s.shot("reply-form", "Contractor reply form", false);
    await hc(p, p.getByRole("button", { name: /Send|Submit|Save|Post/ }).last(), { ms: 1500 });
    await s.shot("reply-sent", "Reply recorded against the finding");
  });
  await logout(p);
});

await scene("12-officer-approve", "Officer reviews the report and approves; complaint resolved", "The officer sees the report against the standard rate, then approves; every complaint in the task becomes resolved and the citizen is notified (e-mail is logged to the outbox in demo).", {}, async (p, s) => {
  if (!state.task) throw new Error("no task");
  await login(p, "officer", "ae-4471");
  await go(p, `/tasks/${state.task}`, 1500);
  await p.getByText("within the normal range").or(p.getByText("above the standard rate")).first().waitFor();
  await cap(p, "1", "Review the contractor's report against the rate card");
  await s.shot("review", "Report review with bill vs standard rate", true);
  await scrollThrough(p, 1, 1500, 0.6);
  await hc(p, p.getByRole("button", { name: /Approve and resolve/ }), { ms: 800 });
  await p.getByText("Completed").first().waitFor();
  await cap(p, "2", "Approved: every complaint in the task is resolved");
  await pause(p, 1500);
  await s.shot("approved", "Task completed", true);
  await logout(p);
});

await scene("13-citizen-result", "Citizen gets the result; the public sees it too", "The citizen is notified in-app; the public ticket page shows the after-photo, approved bill and history, with the citizen's identity hidden.", {}, async (p, s) => {
  if (!state.ticket) throw new Error("no ticket");
  await login(p, "citizen", mobileNo, citizenPw);
  await p.waitForURL(/\/me/);
  await p.getByText("has been resolved").first().waitFor();
  await cap(p, "1", "My complaints: notification and resolved status");
  await s.shot("my-complaints", "Citizen panel: resolved + notification", true);
  await logout(p);
  await go(p, `/ticket/${state.ticket}`, 1200);
  await p.getByText("After the repair").waitFor();
  await cap(p, "2", "Public view: after-photo, approved bill, full history");
  await s.shot("public-resolved", "Public ticket page after resolution", true);
  await scrollThrough(p, 2, 1700, 0.8);
});

await scene("14-support", "'I have this problem too': one vote per citizen", "Instead of filing a duplicate, a citizen supports an existing open complaint; the count is public, voters are not. Your own complaints and closed ones cannot be supported.", {}, async (p, s) => {
  const m2 = "96" + String(Date.now()).slice(-8), pw2 = "citizen-pass-" + Date.now().toString(36);
  const r = await fetch(`${API}/auth/citizen/register`, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ mobile: m2, password: pw2, display_name: "Neighbour", consent: true, lang: "en" }) });
  if (!r.ok) throw new Error("register failed " + r.status);
  await login(p, "citizen", m2, pw2);
  await go(p, "/complaints", 1200);
  await cap(p, "1", "Open complaints raised by other citizens");
  await s.shot("list", "Open complaints with support counts");
  for (const t of ["CMP-000005", "CMP-000006", "CMP-000004"]) {
    await go(p, `/ticket/${t}`, 1000);
    const btn = p.getByRole("button", { name: /I have this problem too/ });
    if (await btn.count()) {
      await cap(p, "2", "Support an existing complaint instead of filing a duplicate");
      await s.shot("before", `${t} before supporting`);
      await hc(p, btn.first(), { ms: 1800 });
      await cap(p, "3", "One vote per citizen; the count is public, the voters are not");
      await s.shot("after", `${t} after supporting: count updated`);
      break;
    }
  }
  await logout(p);
});

// =====================================================================
// OFFICER CONSOLE (risk flags, noting, review queue, budget) AND AUDIT
// =====================================================================
await scene("15-officer-console", "Officer console: work orders, cited risk flags, draft noting, review queue", "Ward work orders sorted by warranty (DLP), with numbered risk flags each citing its evidence; one click drafts the file-noting paragraph; the review queue holds claims awaiting a named human.", {}, async (p, s) => {
  await login(p, "officer", "ae-4471");
  await go(p, "/officer/K-E", 1500);
  await cap(p, "1", "Work orders, warranty-first, with risk flag chips");
  await s.shot("work-orders", "Ward K/E work orders and flag chips");
  await s.soft("filter", async () => {
    await cap(p, "2", "Filter by a flag: billed on a road still under warranty (DLP)");
    await hc(p, p.getByRole("button", { name: /Billed on road under DLP/ }), { ms: 1600 });
  });
  await s.shot("filtered", "Filtered by DLP flag");
  await hc(p, p.locator("main table tbody tr").first(), { ms: 1500 });
  await cap(p, "3", "Numbered flags, each with evidence and source references");
  await s.shot("flags", "Work-order detail: facts + numbered cited flags", true);
  await p.getByText("Flags, numbered").scrollIntoViewIfNeeded(); await pause(p, 1500);
  await s.soft("draft", async () => {
    await cap(p, "4", "Draft the file-noting paragraph (a draft: the officer reviews and signs)");
    await p.evaluate(() => window.scrollTo({ top: 0, behavior: "smooth" })); await pause(p, 900);
    await hc(p, p.getByRole("button", { name: "Draft noting" }), { ms: 3000 });
    await s.shot("draft-noting", "Draft noting with a numbered, cited paragraph", true);
  });
  await s.soft("close draft", async () => { await hc(p, p.getByRole("button", { name: /Close/ }).last(), { ms: 800 }); });
  await s.soft("queue", async () => {
    await go(p, "/officer/K-E", 1000);
    await cap(p, "5", "Review queue: claims waiting for a named human");
    await hc(p, p.getByRole("button", { name: /pending/ }).first(), { ms: 2000 });
    await s.shot("review-queue", "Review queue", false);
    await scrollThrough(p, 1, 1500, 0.6);
  });
  await logout(p);
});

await scene("16-budget", "Budget planner: where the next rupee should go", "A transparent weighted score ranks open issues by severity, flood hotspots, rainfall, accidents, hospital/school proximity, traffic and age; it respects the 80% allocation cap and is advisory only.", {}, async (p, s) => {
  await login(p, "officer", "ae-4471");
  await go(p, "/officer/K-E/budget", 1500);
  await cap(p, "1", "Budget, billed, remaining, 80% cap, rainfall and open issues");
  await s.shot("summary", "Budget planner summary");
  await scrollThrough(p, 1, 1500, 0.4);
  await s.soft("why", async () => {
    await cap(p, "2", "'Why this rank': the factor breakdown in plain language");
    await hc(p, p.getByText("Why this rank").first(), { ms: 1800 });
  });
  await s.shot("why-rank", "Factor breakdown for one issue", false);
  await scrollThrough(p, 2, 1500, 0.7);
  await s.shot("plan", "Ranked plan with method, estimated cost and funding", true);
  await logout(p);
});

await scene("17-audit", "Audit trail: append-only, hash-chained, exportable", "An auditor sees every promoted fact with its source file, row, sha256, extractor and promoter. The chain can be verified, filtered and exported to CSV, and every human action is logged. Public users and citizens cannot open it.", {}, async (p, s) => {
  await go(p, "/audit", 1200);
  await cap(p, "1", "Access control: the audit trail needs an officer login");
  await s.shot("locked", "Anonymous visitors are asked to log in");
  await login(p, "officer", "audit-01");
  await go(p, "/audit", 2000);
  await cap(p, "2", "Append-only log: every fact with source file, row, hash and promoter");
  await s.shot("log", "Audit log rows");
  await scrollThrough(p, 1, 1500, 0.5);
  await toTop(p);
  await s.soft("filter", async () => {
    await cap(p, "3", "Filter by ward, contractor, date or subject");
    await type(p, p.getByPlaceholder("K/E"), "K/E");
    await type(p, p.getByPlaceholder("cost_inr"), "sla_hours");
    await hc(p, p.getByRole("button", { name: /Apply filters/ }), { ms: 2200 });
    await s.shot("filtered", "Filtered to ward K/E, field sla_hours");
  });
  await s.soft("verify", async () => {
    await cap(p, "4", "Verify the hash chain");
    await hc(p, p.getByRole("button", { name: /Verify chain/ }), { ms: 2500 });
    await s.shot("verify", "Hash chain verification result");
  });
  await s.soft("export", async () => {
    await cap(p, "5", "Export CSV");
    const [dl] = await Promise.all([p.waitForEvent("download", { timeout: 60000 }), p.getByRole("button", { name: /Export CSV/ }).click()]);
    state.csv = dl.suggestedFilename();
    await dl.saveAs(`${OUT}/audit-export.csv`);
    await pause(p, 1000);
  });
  await s.soft("action log", async () => {
    await cap(p, "6", "Every human action is logged with the officer ID");
    await hc(p, p.getByText("show action log"), { ms: 2000 });
    await s.shot("action-log", "Action log");
  });
  await s.soft("live log", async () => {
    await cap(p, "7", "Complaint and task log (append-only)");
    await hc(p, p.getByText("Complaint and task log (append-only)").first(), { ms: 2000 });
    await s.shot("live-log", "Complaint and task event log", false);
  });
  await logout(p);
});

await scene("18-mobile", "Mobile-first citizen experience", "The citizen window is built for a 2GB Android on 3G: a single-column layout, big targets, map pin-drop and the same bilingual answers.", { mobile: true }, async (p, s) => {
  await go(p, "/", 1200);
  await cap(p, "1", "Phone layout (390 px wide)");
  await s.shot("home", "Home on a phone");
  await scrollThrough(p, 2, 1300, 0.7);
  await go(p, "/complaints", 1200);
  await s.shot("complaints", "Complaints list on a phone");
  await go(p, "/ask", 1000);
  await type(p, p.locator("main input").first(), "BMC25-003412", 40);
  await hc(p, p.getByRole("button", { name: "Ask", exact: true }), { ms: 2500 });
  await s.shot("ask", "Ask on a phone", true);
  await go(p, "/map", 2500);
  await s.shot("map", "Map on a phone");
  await go(p, "/complaints/new", 1200);
  await s.shot("new", "Raise-a-complaint form on a phone (login-gated)");
});

await browser.close();
writeFileSync(`${OUT}/problems.txt`, [...new Set(problems)].join("\n"));
console.log("\nproblems:", problems.length ? "\n  " + [...new Set(problems)].join("\n  ") : "none");
console.log("state:", JSON.stringify({ ...state, mobileNo }));
