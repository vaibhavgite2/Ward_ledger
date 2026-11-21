// webm -> mp4 per scene (PowerPoint-friendly), title cards, and one combined demo video.
import ffmpegPath from "ffmpeg-static";
import { chromium } from "playwright";
import { execFileSync } from "node:child_process";
import { readFileSync, writeFileSync, mkdirSync, existsSync, statSync } from "node:fs";

const OUT = "output";
const man = JSON.parse(readFileSync(`${OUT}/manifest.json`, "utf8"));
mkdirSync(`${OUT}/videos/cards`, { recursive: true });
const ff = (args) => execFileSync(ffmpegPath, ["-y", "-loglevel", "error", ...args], { stdio: "inherit" });
const esc = (s) => s.replace(/&/g, "&amp;").replace(/</g, "&lt;");

// 1. per-scene mp4 (constant 30fps, yuv420p, even dims)
for (const s of man.scenes) {
  if (!s.video || !existsSync(s.video)) continue;
  s.mp4 = `${OUT}/videos/${s.id}-${s.title.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "").slice(0, 40)}.mp4`;
  ff(["-i", s.video, "-c:v", "libx264", "-preset", "medium", "-crf", "24", "-r", "30", "-pix_fmt", "yuv420p", "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2", "-movflags", "+faststart", "-an", s.mp4]);
  console.log("mp4", s.mp4, (statSync(s.mp4).size / 1e6).toFixed(1) + " MB");
}

// 2. title cards
const b = await chromium.launch();
const page = await b.newPage({ viewport: { width: 1440, height: 900 } });
const card = async (file, html) => { await page.setContent(`<body style="margin:0;width:1440px;height:900px;background:#1f1a12;color:#fff;font-family:Georgia,serif;display:flex;flex-direction:column;justify-content:center;padding:0 120px;box-sizing:border-box">${html}</body>`); await page.screenshot({ path: file }); };
await card(`${OUT}/videos/cards/intro.png`, `<div style="color:#f5a623;font:700 22px system-ui;letter-spacing:.2em">FEATURE EVIDENCE PACK</div><h1 style="font-size:92px;margin:18px 0 4px">Apla Shahar</h1><div style="font:italic 28px Georgia;color:#f5a623;margin-bottom:22px">The Ward Ledger</div><div style="font:400 30px/1.4 system-ui;color:#d6d3d1">Every feature, recorded end to end with Playwright.<br>${man.scenes.length} scenes · synthetic Mumbai K/East data</div>`);
for (const s of man.scenes) {
  s.card = `${OUT}/videos/cards/${s.id}.png`;
  await card(s.card, `<div style="color:#f5a623;font:700 26px system-ui;letter-spacing:.15em">SCENE ${s.id.slice(0, 2)}</div><h1 style="font-size:64px;margin:16px 0 28px;line-height:1.1">${esc(s.title)}</h1><div style="font:400 28px/1.45 system-ui;color:#d6d3d1;max-width:1100px">${esc(s.desc)}</div>`);
}
await b.close();

if (!process.env.FAST) {
// 3. combined video: card (3s) + scene, all normalised to 1440x900 @30fps
const parts = [];
const fit = "scale=1440:900:force_original_aspect_ratio=decrease,pad=1440:900:(ow-iw)/2:(oh-ih)/2:color=0x1f1a12,setsar=1,fps=30,format=yuv420p";
const seg = (i, file, isImg) => { const f = `${OUT}/videos/cards/_p${String(i).padStart(2, "0")}.mp4`; ff([...(isImg ? ["-loop", "1", "-t", i === 0 ? "3" : "3.5"] : []), "-i", file, "-vf", fit, "-c:v", "libx264", "-crf", "24", "-pix_fmt", "yuv420p", "-an", f]); parts.push(f); };
let k = 0;
seg(k++, `${OUT}/videos/cards/intro.png`, true);
for (const s of man.scenes) { if (!s.mp4) continue; seg(k++, s.card, true); seg(k++, s.mp4, false); }
writeFileSync(`${OUT}/videos/cards/list.txt`, parts.map((f) => `file '${f.replace(`${OUT}/videos/cards/`, "")}'`).join("\n"));
ff(["-f", "concat", "-safe", "0", "-i", `${OUT}/videos/cards/list.txt`, "-c", "copy", "-movflags", "+faststart", `${OUT}/apla-shahar-full-recording.mp4`]);
console.log("combined", `${OUT}/apla-shahar-full-recording.mp4`, (statSync(`${OUT}/apla-shahar-full-recording.mp4`).size / 1e6).toFixed(1) + " MB");

}
// durations
for (const s of man.scenes) if (s.mp4) {
  try { execFileSync(ffmpegPath, ["-i", s.mp4], { stdio: ["ignore", "ignore", "pipe"] }); } catch (e) { const m = /Duration: (\d+):(\d+):([\d.]+)/.exec(String(e.stderr)); if (m) s.duration = Math.round(+m[1] * 3600 + +m[2] * 60 + +m[3]); }
}
writeFileSync(`${OUT}/manifest.json`, JSON.stringify(man, null, 2));
