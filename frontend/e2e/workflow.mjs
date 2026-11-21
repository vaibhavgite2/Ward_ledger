// End-to-end test of the complaint workflow (DFD 1.1-1.3 and 2.0-6.0) in a real browser.
//
//   Needs: the API and UI running against a database seeded with  python -m live.seed --demo --tickets
//   Run from a folder where `playwright` is installed (npm i -D playwright && npx playwright install chromium):
//     BASE=http://localhost:3000 API=http://localhost:8000/api node e2e/workflow.mjs
//   Env: BASE, API, WL_DEMO_PASSWORD (default wardledger-demo), OUT (screenshot folder).
import { createRequire } from "node:module";
import { mkdirSync } from "node:fs";
import { pathToFileURL } from "node:url";

const require = createRequire(pathToFileURL(process.cwd() + "/").href);
const { chromium } = require("playwright");

const BASE = process.env.BASE || "http://localhost:3000";
const API = process.env.API || "http://localhost:8000/api";
const PW = process.env.WL_DEMO_PASSWORD || "wardledger-demo";
const OUT = process.env.OUT || "e2e-shots";
mkdirSync(OUT, { recursive: true });

const mobile = "97" + String(Date.now()).slice(-8); // a fresh citizen every run
const citizenPw = "citizen-pass-" + Date.now().toString(36);
const problems = [];
let step = 0;
let current = null; // the page in use, for a screenshot if a step fails

const ke = await (await fetch(`${API}/roads/geojson?ward=K/E`)).json();
const [lon, lat] = ke.features[3].geometry.coordinates[0];

const browser = await chromium.launch();
async function session(mobileView) {
  const ctx = await browser.newContext({
    viewport: mobileView ? { width: 390, height: 844 } : { width: 1366, height: 900 },
    geolocation: { latitude: lat, longitude: lon, accuracy: 12 },
    permissions: ["geolocation"],
  });
  await ctx.addInitScript(() => localStorage.setItem("wl.lang", "en"));
  const page = await ctx.newPage();
  current = page;
  page.on("pageerror", (e) => problems.push(`pageerror: ${String(e).slice(0, 200)}`));
  page.on("console", (m) => m.type() === "error" && !/tile\.openstreetmap|favicon/.test(m.text()) && problems.push(`console: ${m.text().slice(0, 200)}`));
  page.on("response", (r) => r.url().startsWith(API) && r.status() >= 500 && problems.push(`HTTP ${r.status()} ${r.url().replace(API, "")}`));
  return { ctx, page };
}
async function shot(page, name) {
  await page.screenshot({ path: `${OUT}/${String(++step).padStart(2, "0")}-${name}.png`, fullPage: true });
}
const ok = (msg) => console.log("  ok  " + msg);
async function login(page, role, id, pw) {
  await page.goto(`${BASE}/login/${role}`);
  await page.getByLabel(role === "citizen" ? "Mobile number" : role === "officer" ? "Employee ID" : "Contractor login ID", { exact: true }).fill(id);
  await page.getByLabel("Password", { exact: true }).fill(pw);
  await page.locator("main form button[type=submit], main form button:not([type])").last().click();
  await page.waitForURL((u) => !u.pathname.startsWith("/login"), { timeout: 20000 });
}
async function logout(page) {
  await page.getByRole("button", { name: "Log out" }).click();
  await page.waitForURL(`${BASE}/`);
}

const png = await (async () => {
  const { page, ctx } = await session(false);
  await page.setContent("<body style='background:#555;width:400px;height:300px'><h1 style='color:#fc0'>pothole</h1></body>");
  const b = await page.screenshot();
  await ctx.close();
  return b;
})();
const mp4 = Buffer.concat([Buffer.from([0, 0, 0, 0x18]), Buffer.from("ftypmp42"), Buffer.alloc(4), Buffer.from("mp42isom"), Buffer.alloc(400)]);
const pdf = Buffer.from("%PDF-1.4\n1 0 obj << /Type /Catalog >> endobj\ntrailer << /Root 1 0 R >>\n%%EOF\n");

try {
  // 1. Anyone can browse; login only when raising a complaint
  console.log("citizen (mobile)");
  let { page, ctx } = await session(true);
  await page.goto(`${BASE}/complaints`);
  await page.getByText("CMP-0000", { exact: false }).first().waitFor();
  ok("complaints section visible without login");
  await shot(page, "complaints-public");
  await page.getByRole("link", { name: "Raise a complaint" }).first().click();
  await page.getByText("please log in as a citizen").waitFor();
  ok("raising a complaint asks for the citizen login");
  await page.getByRole("link", { name: "Citizen login" }).click();
  await page.getByRole("tab", { name: "Create account" }).click();
  await page.getByLabel("Mobile number", { exact: true }).fill(mobile);
  await page.getByLabel("Your name (optional)", { exact: true }).fill("E2E Citizen");
  await page.getByLabel("Password", { exact: true }).fill(citizenPw);
  await page.getByRole("checkbox").check();
  await page.getByRole("button", { name: "Create account" }).last().click();
  await page.waitForURL(/\/complaints\/new/);
  ok("registered and returned to the complaint form");

  // 2. Raise a complaint: category, description, GPS + a map pin, photo + video
  await page.locator("main select").first().selectOption("Pothole");
  await page.locator("main textarea").first().fill("Deep pothole outside the school gate; two scooters fell this morning.");
  await page.getByRole("button", { name: "Use my current location" }).click();
  await page.getByText("from GPS").waitFor();
  const map = page.locator(".leaflet-container").first();
  await map.scrollIntoViewIfNeeded(); // raw mouse clicks only land inside the viewport
  const box = await map.boundingBox();
  await page.mouse.click(box.x + box.width * 0.6, box.y + box.height * 0.6);
  await page.getByText("pin on map").waitFor();
  ok("current location and a second pin added");
  await page.locator("input[type=file][multiple]").first().setInputFiles([
    { name: "pothole.png", mimeType: "image/png", buffer: png },
    { name: "clip.mp4", mimeType: "video/mp4", buffer: mp4 },
  ]);
  await shot(page, "raise-form");
  await page.getByRole("button", { name: "Submit complaint" }).click();
  await page.waitForURL(/\/ticket\/CMP-\d{6}/, { timeout: 30000 });
  const ticketId = page.url().match(/CMP-\d{6}/)[0];
  await page.getByText("Your complaint was received").waitFor();
  await page.getByText("Awaiting verification").first().waitFor();
  ok(`complaint ${ticketId} raised`);
  await shot(page, "ticket-raised");
  await logout(page);
  await ctx.close();

  // 3. Officer verifies (DFD 3.0) and assigns a task with pre-award checks (4.0)
  console.log("officer");
  ({ page, ctx } = await session(false));
  await login(page, "officer", "ae-4471", PW);
  await page.waitForURL(/\/officer\/K-E\/complaints/);
  await page.getByRole("button", { name: new RegExp(ticketId) }).click();
  await page.getByText("Officer actions").waitFor();
  await page.getByRole("button", { name: "Verify complaint" }).click();
  await page.getByRole("link", { name: "Assign to a contractor" }).waitFor();
  ok("verified");
  await page.getByRole("link", { name: "Assign to a contractor" }).click();
  await page.waitForURL(/\/officer\/K-E\/tasks/);
  await page.getByRole("checkbox", { checked: true }).first().waitFor(); // preselected from the complaint
  await page.locator("main section select").first().selectOption("CT05");
  await page.getByRole("button", { name: /Check the contractor/ }).click();
  await page.getByText("Finished on time in").waitFor();
  await shot(page, "pre-award-checks");
  ok("pre-award checks shown");
  await page.getByRole("button", { name: /^3\. Assign/ }).click();
  await page.waitForURL(/\/tasks\/TSK-\d{6}/);
  const taskId = page.url().match(/TSK-\d{6}/)[0];
  ok(`task ${taskId} assigned to CT05`);
  await logout(page);
  await ctx.close();

  // 4. Contractor starts and submits the repair report (5.0)
  console.log("contractor");
  ({ page, ctx } = await session(false));
  await login(page, "contractor", "ct05", PW);
  await page.waitForURL(/\/tasks$/);
  await page.getByRole("link", { name: new RegExp(taskId) }).click();
  await page.getByRole("button", { name: "Start work" }).click();
  await page.getByText("In progress").first().waitFor();
  await page.getByPlaceholder("What was done").fill("Pothole cut to shape, cleaned, tack coat applied and filled with hot mix; rolled.");
  await page.getByLabel("Area repaired (sqm)", { exact: true }).fill("2.5");
  await page.getByLabel("Bill amount (₹)", { exact: true }).fill("6900");
  await page.getByLabel("Photos or videos of the finished work", { exact: true }).setInputFiles([{ name: "after.png", mimeType: "image/png", buffer: png }]);
  await page.getByLabel("Bill documents (PDF or photo)", { exact: true }).setInputFiles([{ name: "bill.pdf", mimeType: "application/pdf", buffer: pdf }]);
  await page.getByRole("button", { name: "Submit report" }).click();
  await page.getByText("Report submitted").first().waitFor();
  ok("repair report submitted");
  await shot(page, "report-submitted");
  await logout(page);
  await ctx.close();

  // 5. Officer approves: the task completes and every complaint in it is resolved (6.0)
  console.log("officer review");
  ({ page, ctx } = await session(false));
  await login(page, "officer", "ae-4471", PW);
  await page.goto(`${BASE}/tasks/${taskId}`);
  await page.getByText("within the normal range").or(page.getByText("above the standard rate")).first().waitFor();
  await page.getByRole("button", { name: /Approve and resolve/ }).click();
  await page.getByText("Completed").first().waitFor();
  ok("approved");
  await shot(page, "task-approved");
  await logout(page);
  await ctx.close();

  // 6. The citizen sees the result and the notification; the public sees it too
  console.log("citizen again");
  ({ page, ctx } = await session(true));
  await login(page, "citizen", mobile, citizenPw);
  await page.waitForURL(/\/me/);
  await page.getByText("has been resolved").first().waitFor();
  await page.getByText("Resolved").first().waitFor();
  ok("citizen notified and complaint shown as resolved");
  await shot(page, "citizen-panel");
  await logout(page);
  await page.goto(`${BASE}/ticket/${ticketId}`);
  await page.getByText("After the repair").waitFor();
  await page.getByText("Approved bill").waitFor();
  ok("public view shows the resolution, approved bill and after-photo");
  await shot(page, "ticket-public-resolved");
  await ctx.close();
} catch (e) {
  problems.push("FAILED: " + String(e).split("\n").slice(0, 4).join(" | "));
  if (current) await current.screenshot({ path: `${OUT}/FAILED.png`, fullPage: true }).catch(() => {});
}
await browser.close();
if (problems.length) {
  console.log("\nproblems:\n  " + [...new Set(problems)].join("\n  "));
  process.exit(1);
}
console.log("\nend-to-end workflow OK");
