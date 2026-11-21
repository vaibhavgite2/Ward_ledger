// Narrated product-demo video (target 3-4 min): local offline TTS (Windows SAPI) + the Playwright scene recordings.
//   node demo_video.mjs          needs: output/manifest.json with .mp4 per scene (run convert.mjs first)
import ffmpegPath from "ffmpeg-static";
import { chromium } from "playwright";
import { execFileSync } from "node:child_process";
import { readFileSync, writeFileSync, mkdirSync, existsSync, rmSync } from "node:fs";
import { resolve } from "node:path";

const OUT = "output";
const W = `${OUT}/demo`;
rmSync(W, { recursive: true, force: true });
mkdirSync(`${W}/seg`, { recursive: true });
const man = JSON.parse(readFileSync(`${OUT}/manifest.json`, "utf8"));
const mp4 = (id) => { const s = man.scenes.find((x) => x.id.startsWith(id)); if (!s?.mp4 || !existsSync(s.mp4)) throw new Error("no mp4 for scene " + id); return s.mp4; };
const ff = (args) => execFileSync(ffmpegPath, ["-y", "-loglevel", "error", ...args], { stdio: "inherit" });
const dur = (f) => { try { execFileSync(ffmpegPath, ["-i", f], { stdio: ["ignore", "ignore", "pipe"] }); } catch (e) { const m = /Duration: (\d+):(\d+):([\d.]+)/.exec(String(e.stderr)); return +m[1] * 3600 + +m[2] * 60 + +m[3]; } };

// Spoken text uses spaced letters (R T I, G P S) so the voice reads acronyms letter by letter.
const SEGS = [
  { id: "00-intro", card: "intro", text: "Every monsoon, Mumbai spends crores of rupees repairing its roads. But citizens can't see where the money goes, officers can't see a contractor's history, and contractors can't answer back. Aapla Shahar fixes that: one transparent record, from the first complaint to the repaired road." },
  { id: "01-home", clips: ["01"], text: "The public home page needs no login. It shows the headline numbers for all twenty four wards: the repair budget, the amount billed, and how much was spent on repairs that failed within thirty days. Anyone can search a complaint, or pick their ward." },
  { id: "02-complaints", clips: ["02"], text: "Every complaint is public and can be filtered by status, ward and category. Open any recorded complaint to see what happened, the repair that followed, and the source rows behind every claim." },
  { id: "03-map", clips: ["03"], text: "The map colours each road by how often its repairs failed. Dashed roads are still under warranty, so a fresh repair there should be the original contractor's cost, not the taxpayer's." },
  { id: "04-wards", clips: ["04"], text: "Ward comparison puts all twenty four wards side by side. Each ward page then traces the money from complaint to repair, by contractor, by method and by month." },
  { id: "05-contractors", clips: ["05"], text: "Contractors get a public civic trust scorecard. Every finding cites its evidence, a clean record is always shown, and the firm can reply right next to any finding. We describe what the records show. We never accuse." },
  { id: "06-ask", clips: ["06"], text: "Citizens can simply ask. Type a complaint number, or describe the problem in Marathi, Hindi or English. Answers come only from promoted records, with their sources, and when data is missing the assistant says so and offers an R T I draft." },
  { id: "07-rti", clips: ["07"], text: "One click produces a ready to file R T I application, in Marathi and English, with the right public information officer, the ten rupee fee, and the thirty day clock. It only asks for public documents." },
  { id: "09-citizen", clips: ["09"], text: "Now the live workflow. A citizen registers with just a mobile number, then raises a complaint with a description, a G P S location, a map pin, a photo and a video. They get a tracking page straight away." },
  { id: "10-officer", clips: ["10"], text: "The ward officer verifies the complaint, then assigns a task to a contractor. Pre award checks show the contractor's record and the estimate against the rate card, before anything is awarded." },
  { id: "11-contractor", clips: ["11"], text: "The contractor starts the work and submits a resolution report, with after photos, the area repaired, and the bill. They can also post a right of reply to any finding about their firm." },
  { id: "12-resolved", clips: ["12", "13"], text: "The officer reviews the bill against the standard rate and approves. Every complaint in the task is resolved, and the citizen is notified. The public page then shows the after photo, the approved bill, and the full history." },
  { id: "13-support", clips: ["14"], text: "To avoid duplicates, neighbours can support an existing complaint instead. One vote per citizen. The count is public, the voters stay private." },
  { id: "14-console", clips: ["15"], text: "In the officer console, every work order carries numbered risk flags, each citing its evidence: billing on a road still under warranty, cost above the rate card, a missed S L A. One click drafts the file noting paragraph, for the officer to review, edit and sign." },
  { id: "15-budget", clips: ["16"], text: "The budget planner ranks open issues with a transparent weighted score: flood hotspots, rainfall, accidents, nearby schools and hospitals. It respects an eighty percent allocation cap, and it is advisory only. Officers decide." },
  { id: "16-audit", clips: ["17"], text: "For auditors, an append only, hash chained log of every fact: its source file, row, hash, and who promoted it. Verify the chain, filter it, export it to C S V. No fact enters the system without a rule or a named human." },
  { id: "17-mobile", clips: ["08", "18"], text: "Everything switches between Marathi, Hindi and English, and works on a phone, where most citizens will use it." },
  { id: "18-outro", card: "outro", text: "Aapla Shahar. Every rupee, every repair, every record, in public view." },
];
// Subtitle text with the spaced acronyms put back
const pretty = (t) => t.replace(/R T I/g, "RTI").replace(/G P S/g, "GPS").replace(/S L A/g, "SLA").replace(/C S V/g, "CSV").replace(/Aapla Shahar/g, "Apla Shahar");

// ---- 1. voice-over (offline SAPI) ----
writeFileSync(`${W}/script.json`, JSON.stringify(SEGS.map(({ id, text }) => ({ id, text })), null, 1), "utf8");
writeFileSync(`${W}/tts.ps1`, `param($json,$outdir)
Add-Type -AssemblyName System.Speech
$segs = Get-Content $json -Raw -Encoding UTF8 | ConvertFrom-Json
$s = New-Object System.Speech.Synthesis.SpeechSynthesizer
$s.SelectVoice('Microsoft Zira Desktop'); $s.Rate = 2; $s.Volume = 100
foreach ($g in $segs) { $s.SetOutputToWaveFile((Join-Path $outdir ($g.id + '.wav'))); $s.Speak($g.text); $s.SetOutputToNull() }
`, "utf8");
execFileSync("powershell", ["-NoProfile", "-ExecutionPolicy", "Bypass", "-File", resolve(`${W}/tts.ps1`), resolve(`${W}/script.json`), resolve(`${W}/seg`)], { stdio: "inherit" });
for (const s of SEGS) { s.narr = dur(`${W}/seg/${s.id}.wav`); }
console.log("narration total: " + SEGS.reduce((a, s) => a + s.narr, 0).toFixed(1) + "s");

// ---- 2. title cards ----
const b = await chromium.launch();
const pg = await b.newPage({ viewport: { width: 1440, height: 900 } });
const card = async (f, html) => { await pg.setContent(`<body style="margin:0;width:1440px;height:900px;background:#1f1a12;color:#fff;font-family:Georgia,serif;display:flex;flex-direction:column;justify-content:center;padding:0 120px;box-sizing:border-box">${html}</body>`); await pg.screenshot({ path: f }); };
await card(`${W}/intro.png`, `<div style="color:#f5a623;font:700 24px system-ui;letter-spacing:.2em">PRODUCT DEMO</div><h1 style="font-size:104px;margin:18px 0 6px">Apla Shahar</h1><div style="font:italic 30px Georgia;color:#f5a623;margin-bottom:26px">The Ward Ledger</div><div style="font:400 36px/1.4 system-ui;color:#d6d3d1">Where did your tax money go?<br>Every rupee in public road repairs, from complaint to repair.</div>`);
await card(`${W}/outro.png`, `<h1 style="font-size:84px;margin:0 0 28px">Apla Shahar</h1><div style="font:400 34px/1.5 system-ui;color:#d6d3d1">Every rupee. Every repair. Every record.<br>In public view.</div><div style="margin-top:60px;font:400 22px system-ui;color:#a8a29e">All data in this demo is synthetic; all contractors are fictional.</div>`);
await b.close();

// ---- 3. cut each segment: fit visuals to narration ----
const NORM = "scale=1440:900:force_original_aspect_ratio=decrease,pad=1440:900:(ow-iw)/2:(oh-ih)/2:color=0x1f1a12,setsar=1,fps=30,format=yuv420p";
let t = 0;
const srt = [];
const fmt = (x) => { const h = Math.floor(x / 3600), m = Math.floor((x % 3600) / 60), s = x % 60; return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}:${s.toFixed(3).padStart(6, "0").replace(".", ",")}`; };
const MAXSPEED = 3.2, TAIL = 0.35;
const files = [];
SEGS.forEach((s, i) => {
  const out = `${W}/seg/${String(i).padStart(2, "0")}.mp4`;
  const wav = `${W}/seg/${s.id}.wav`;
  let segDur = s.narr + TAIL, vArgs, vf;
  if (s.card) {
    vArgs = ["-loop", "1", "-t", String(segDur), "-i", `${W}/${s.card}.png`];
    vf = `[0:v]${NORM}[v]`;
  } else {
    const srcs = s.clips.map(mp4);
    const clipDur = srcs.reduce((a, f) => a + dur(f), 0);
    const speed = Math.min(MAXSPEED, Math.max(0.85, clipDur / segDur));
    const vlen = clipDur / speed;
    if (vlen > segDur) segDur = vlen;                      // never cut the action: let the picture finish
    s.speed = +speed.toFixed(2); s.clipDur = Math.round(clipDur);
    vArgs = srcs.flatMap((f) => ["-i", f]);
    const norm = srcs.map((_, k) => `[${k}:v]${NORM}[n${k}]`).join(";");
    const cat = srcs.length > 1 ? `${srcs.map((_, k) => `[n${k}]`).join("")}concat=n=${srcs.length}:v=1:a=0[c]` : "[n0]null[c]";
    vf = `${norm};${cat};[c]setpts=PTS/${speed},tpad=stop_mode=clone:stop_duration=${Math.max(0, segDur - vlen) + 1}[v]`;
  }
  ff([...vArgs, "-i", wav, "-filter_complex", `${vf};[${s.card ? 1 : s.clips.length}:a]apad,aresample=44100,aformat=channel_layouts=stereo[a]`, "-map", "[v]", "-map", "[a]",
    "-t", segDur.toFixed(3), "-c:v", "libx264", "-preset", "medium", "-crf", "22", "-pix_fmt", "yuv420p", "-r", "30", "-c:a", "aac", "-b:a", "160k", out]);
  files.push(out);
  srt.push(`${i + 1}\n${fmt(t + 0.15)} --> ${fmt(t + s.narr + 0.1)}\n${pretty(s.text)}\n`);
  console.log(`${s.id.padEnd(14)} narr ${s.narr.toFixed(1)}s  seg ${segDur.toFixed(1)}s${s.speed ? `  clip ${s.clipDur}s @${s.speed}x` : ""}`);
  t += segDur;
});
writeFileSync(`${W}/list.txt`, files.map((f) => `file '${f.replace(`${W}/`, "")}'`).join("\n"));
const final = `${OUT}/Apla-Shahar-Product-Demo.mp4`;
ff(["-f", "concat", "-safe", "0", "-i", `${W}/list.txt`, "-c", "copy", "-movflags", "+faststart", final]);
writeFileSync(`${OUT}/Apla-Shahar-Product-Demo.srt`, srt.join("\n"), "utf8");
writeFileSync(`${OUT}/Apla-Shahar-Product-Demo-script.txt`, SEGS.map((s) => `[${s.id}]\n${pretty(s.text)}\n`).join("\n"), "utf8");
console.log(`\n${final}  total ${Math.floor(t / 60)}:${String(Math.round(t % 60)).padStart(2, "0")}`);
