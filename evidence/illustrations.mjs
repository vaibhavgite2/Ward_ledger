// Original flat-style vector illustrations for the problem-statement deck, rendered to transparent PNGs with Playwright.
import { chromium } from "playwright";
import { mkdirSync } from "node:fs";

const OUT = "output/ppt_assets";
mkdirSync(OUT, { recursive: true });

const INK = "#1F1A12", AMBER = "#F5A623", DEEP = "#C77700", ROAD = "#3B3B3F", ROAD2 = "#55555B", SKIN = "#D9A066", TEAL = "#2A9D8F", NAVY = "#2B3A55", RED = "#C0392B", GOLD = "#FFC53D", PAPER = "#FFFFFF";

const coin = (x, y, r = 28, t = "₹") => `<circle cx="${x}" cy="${y}" r="${r}" fill="${GOLD}" stroke="${DEEP}" stroke-width="4"/><circle cx="${x}" cy="${y}" r="${r * 0.72}" fill="none" stroke="${DEEP}" stroke-width="2" opacity=".6"/><text x="${x}" y="${y + r * 0.36}" font-family="Cambria,serif" font-weight="700" font-size="${r * 1.05}" text-anchor="middle" fill="${INK}">${t}</text>`;
const qmark = (x, y, s = 60, c = "#fff") => `<text x="${x}" y="${y}" font-family="Cambria,serif" font-weight="700" font-size="${s}" fill="${c}" text-anchor="middle">?</text>`;

// A person (Raju). scale/translate via transform at call site. Origin = feet centre (0,0), ~300 tall.
const person = ({ shirt = TEAL, pants = NAVY, hat = null, prop = "" } = {}) => `
  <ellipse cx="0" cy="4" rx="60" ry="9" fill="#000" opacity=".22"/>
  <rect x="-38" y="-130" width="30" height="128" rx="12" fill="${pants}"/><rect x="8" y="-130" width="30" height="128" rx="12" fill="${pants}"/>
  <rect x="-44" y="-12" width="40" height="14" rx="7" fill="#111"/><rect x="4" y="-12" width="40" height="14" rx="7" fill="#111"/>
  <rect x="-58" y="-250" width="116" height="136" rx="38" fill="${shirt}"/>
  <rect x="-84" y="-240" width="30" height="112" rx="15" fill="${shirt}" transform="rotate(8 -70 -240)"/>
  <rect x="54" y="-240" width="30" height="112" rx="15" fill="${shirt}" transform="rotate(-8 70 -240)"/>
  <circle cx="-76" cy="-124" r="15" fill="${SKIN}"/><circle cx="76" cy="-124" r="15" fill="${SKIN}"/>
  <rect x="-12" y="-272" width="24" height="26" rx="8" fill="${SKIN}"/>
  <circle cx="0" cy="-300" r="42" fill="${SKIN}"/>
  <path d="M-42 -306 Q-40 -350 0 -350 Q42 -350 42 -306 Q20 -330 -42 -306Z" fill="#1b1b1b"/>
  <circle cx="-15" cy="-298" r="4.5" fill="${INK}"/><circle cx="15" cy="-298" r="4.5" fill="${INK}"/>
  <path d="M-14 -280 Q0 -272 14 -280" stroke="${INK}" stroke-width="4" fill="none" stroke-linecap="round"/>
  ${hat || ""}${prop}`;

const svgs = {};

// ---------- hero: dusk skyline, road, pothole, scooter, Raju (left third kept clear for the title) ----------
svgs.hero = { w: 1920, h: 1080, bg: true, svg: `
<defs><linearGradient id="sky" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#141B30"/><stop offset=".55" stop-color="#3B3F63"/><stop offset="1" stop-color="#F2A65A"/></linearGradient></defs>
<rect width="1920" height="1080" fill="url(#sky)"/>
<circle cx="1500" cy="380" r="120" fill="#FFD9A0" opacity=".85"/>
${[...Array(40)].map((_, i) => `<circle cx="${(i * 197) % 1920}" cy="${(i * 83) % 330 + 20}" r="${1 + (i % 3) * 0.7}" fill="#fff" opacity=".55"/>`).join("")}
<g fill="#111522">${[[0, 560, 140, 300], [150, 480, 110, 380], [270, 600, 150, 260], [430, 520, 120, 340], [560, 450, 100, 410], [670, 590, 160, 270], [840, 500, 120, 360], [970, 430, 130, 430], [1110, 560, 110, 300], [1230, 470, 140, 390], [1380, 580, 120, 280], [1510, 440, 150, 420], [1670, 530, 120, 330], [1800, 600, 120, 260]].map(([x, y, w, h]) => `<rect x="${x}" y="${y}" width="${w}" height="${h}"/>`).join("")}</g>
<g fill="#FFD27A" opacity=".8">${[...Array(90)].map((_, i) => `<rect x="${(i * 61) % 1900 + 10}" y="${540 + ((i * 47) % 280)}" width="9" height="13" opacity="${i % 3 ? 0.9 : 0.25}"/>`).join("")}</g>
<polygon points="0,1080 0,860 1920,860 1920,1080" fill="#2A2A2E"/>
<polygon points="620,1080 780,860 1920,860 1920,1080" fill="${ROAD}"/>
<g stroke="#FFD84D" stroke-width="10" stroke-dasharray="70 56"><line x1="1190" y1="1080" x2="1250" y2="860"/></g>
<rect x="0" y="840" width="1920" height="22" fill="#6B6B72"/>
<ellipse cx="1040" cy="975" rx="150" ry="40" fill="#0d0d0f"/><ellipse cx="1040" cy="968" rx="168" ry="46" fill="none" stroke="#7a7a80" stroke-width="10"/>
<path d="M880 985 l-60 18 M1200 985 l70 16 M1040 925 l-8 -44" stroke="#111" stroke-width="5" fill="none"/>
<g transform="translate(1500 950) rotate(-84)">
  <circle cx="-70" cy="-6" r="42" fill="#111"/><circle cx="-70" cy="-6" r="20" fill="#777"/><circle cx="90" cy="-6" r="42" fill="#111"/><circle cx="90" cy="-6" r="20" fill="#777"/>
  <path d="M-70 -6 L-30 -120 L40 -120 L90 -6" stroke="${RED}" stroke-width="30" fill="none" stroke-linejoin="round" stroke-linecap="round"/>
  <rect x="-40" y="-170" width="110" height="34" rx="14" fill="${INK}"/><rect x="60" y="-196" width="14" height="86" rx="6" fill="#888"/>
</g>
<g transform="translate(560 1010) scale(1.05)">${person()}</g>
<g transform="translate(650 440)"><rect x="0" y="0" width="520" height="150" rx="34" fill="#fff"/><polygon points="30,110 30,200 -20,190" fill="#fff" transform="translate(0 20) rotate(0)"/>
  <text x="260" y="62" font-family="Cambria,serif" font-style="italic" font-weight="700" font-size="44" text-anchor="middle" fill="${INK}">Where did my tax</text>
  <text x="260" y="116" font-family="Cambria,serif" font-style="italic" font-weight="700" font-size="44" text-anchor="middle" fill="${INK}">money go?</text></g>
${coin(1330, 560, 34)}${coin(1420, 470, 26)}${coin(1240, 450, 22)}
${qmark(1100, 780, 80, "#FFD27A")}${qmark(1250, 720, 56, "#FFD27A")}` };

// ---------- Raju alone (transparent) ----------
svgs.raju = { w: 800, h: 1000, svg: `<g transform="translate(400 940) scale(1.7)">${person()}</g>
 <g transform="translate(440 90)"><rect x="0" y="0" width="330" height="120" rx="30" fill="${AMBER}"/><polygon points="60,120 120,120 70,170" fill="${AMBER}"/>
 <text x="165" y="52" font-family="Cambria,serif" font-weight="700" font-size="34" text-anchor="middle" fill="${INK}">Who fixed it?</text><text x="165" y="94" font-family="Cambria,serif" font-weight="700" font-size="34" text-anchor="middle" fill="${INK}">At what cost?</text></g>
 ${qmark(110, 260, 110, DEEP)}${qmark(690, 420, 80, DEEP)}` };

// ---------- three-panel story: money -> patch -> pothole again ----------
svgs.bag = { w: 600, h: 520, svg: `
 <path d="M200 150 Q300 20 400 150 L440 200 Q520 260 500 400 Q480 500 300 500 Q120 500 100 400 Q80 260 160 200Z" fill="#2E7D5B" stroke="${INK}" stroke-width="8" stroke-linejoin="round"/>
 <rect x="230" y="130" width="140" height="34" rx="14" fill="#1E5A41" stroke="${INK}" stroke-width="6"/>
 <text x="300" y="380" font-family="Cambria,serif" font-weight="700" font-size="170" text-anchor="middle" fill="${GOLD}" stroke="${INK}" stroke-width="5">₹</text>
 ${coin(120, 440, 40)}${coin(500, 450, 34)}${coin(470, 120, 28)}` };
svgs.patch = { w: 600, h: 520, svg: `
 <polygon points="30,470 570,470 600,520 0,520" fill="#2A2A2E"/><rect x="0" y="360" width="600" height="130" fill="${ROAD}"/>
 <rect x="170" y="400" width="260" height="70" rx="12" fill="#1E1E22" stroke="#9a9aa0" stroke-width="5" stroke-dasharray="14 8"/>
 <g transform="translate(90 290)"><polygon points="0,110 60,110 30,0" fill="#FF7A1A"/><rect x="-6" y="106" width="72" height="14" fill="${INK}"/><rect x="10" y="40" width="40" height="16" fill="#fff"/></g>
 <g transform="translate(470 290)"><polygon points="0,110 60,110 30,0" fill="#FF7A1A"/><rect x="-6" y="106" width="72" height="14" fill="${INK}"/><rect x="10" y="40" width="40" height="16" fill="#fff"/></g>
 <g transform="translate(300 440) scale(.62)">${person({ shirt: "#E4572E", pants: "#33415C", hat: `<path d="M-52 -330 Q0 -392 52 -330Z" fill="${GOLD}" stroke="${INK}" stroke-width="5"/><rect x="-60" y="-332" width="120" height="14" rx="6" fill="${GOLD}" stroke="${INK}" stroke-width="5"/>` })}</g>` };
svgs.pothole = { w: 600, h: 520, svg: `
 <rect x="0" y="330" width="600" height="190" fill="${ROAD}"/><polygon points="0,330 600,330 600,300 0,300" fill="${ROAD2}"/>
 <ellipse cx="300" cy="420" rx="200" ry="56" fill="#0d0d0f"/><ellipse cx="300" cy="412" rx="222" ry="64" fill="none" stroke="#85858b" stroke-width="12"/>
 <path d="M96 440 l-70 24 M512 440 l80 20 M300 348 l-6 -60 M180 368 l-50 -50 M430 366 l52 -48" stroke="#16161a" stroke-width="7" fill="none" stroke-linecap="round"/>
 <path d="M240 330 q10 -60 60 -90 q50 30 60 90" fill="#E7F0FF" opacity=".0"/>
 ${qmark(300, 230, 150, DEEP)}${qmark(120, 250, 70, DEEP)}${qmark(490, 260, 80, DEEP)}` };

// ---------- the four people ----------
const bust = (shirt, extra = "", hat = "") => `
 <circle cx="200" cy="200" r="190" fill="${shirt}" opacity=".16"/>
 <path d="M70 360 Q70 250 200 250 Q330 250 330 360 Z" fill="${shirt}"/>
 <rect x="180" y="215" width="40" height="44" rx="14" fill="${SKIN}"/>
 <circle cx="200" cy="170" r="66" fill="${SKIN}"/>
 <path d="M134 160 Q136 96 200 96 Q264 96 266 160 Q232 128 134 160Z" fill="#1b1b1b"/>
 <circle cx="178" cy="172" r="7" fill="${INK}"/><circle cx="222" cy="172" r="7" fill="${INK}"/>
 <path d="M178 200 Q200 214 222 200" stroke="${INK}" stroke-width="6" fill="none" stroke-linecap="round"/>
 ${hat}${extra}`;
svgs.citizen = { w: 400, h: 400, svg: bust(TEAL, `<rect x="262" y="262" width="60" height="100" rx="12" fill="${INK}"/><rect x="268" y="272" width="48" height="76" rx="6" fill="#9ED8FF"/><circle cx="292" cy="355" r="4" fill="#9ED8FF"/>`) };
svgs.officer = { w: 400, h: 400, svg: bust("#3A5BA0", `<polygon points="200,252 184,270 200,330 216,270" fill="${RED}"/><rect x="258" y="262" width="76" height="98" rx="8" fill="#fff" stroke="${INK}" stroke-width="5"/><g stroke="${INK}" stroke-width="5"><line x1="272" y1="286" x2="320" y2="286"/><line x1="272" y1="304" x2="320" y2="304"/><line x1="272" y1="322" x2="304" y2="322"/></g>`) };
svgs.contractor = { w: 400, h: 400, svg: bust("#E4572E", `<rect x="130" y="290" width="140" height="22" rx="8" fill="${GOLD}" opacity=".9"/>`, `<path d="M124 130 Q200 40 276 130Z" fill="${GOLD}" stroke="${INK}" stroke-width="6"/><rect x="112" y="124" width="176" height="20" rx="9" fill="${GOLD}" stroke="${INK}" stroke-width="6"/>`) };
svgs.auditor = { w: 400, h: 400, svg: bust("#6B4E9B", `<circle cx="290" cy="300" r="40" fill="#E8F3FF" stroke="${INK}" stroke-width="9"/><line x1="318" y1="330" x2="356" y2="372" stroke="${INK}" stroke-width="14" stroke-linecap="round"/>`, `<path d="M140 150 q60 -34 120 0" fill="none"/><rect x="146" y="158" width="46" height="30" rx="10" fill="none" stroke="${INK}" stroke-width="5"/><rect x="208" y="158" width="46" height="30" rx="10" fill="none" stroke="${INK}" stroke-width="5"/><line x1="192" y1="172" x2="208" y2="172" stroke="${INK}" stroke-width="5"/>`) };

// ---------- journey / flow icons (round badges, transparent) ----------
const badge = (color, inner) => `<circle cx="128" cy="128" r="120" fill="${color}"/>${inner}`;
const W_ = "#fff";
const icons = {
  eye: badge(NAVY, `<path d="M40 128 Q128 50 216 128 Q128 206 40 128Z" fill="${W_}"/><circle cx="128" cy="128" r="34" fill="${NAVY}"/><circle cx="128" cy="128" r="14" fill="${W_}"/>`),
  pin: badge(RED, `<path d="M128 40 Q196 40 196 108 Q196 150 128 222 Q60 150 60 108 Q60 40 128 40Z" fill="${W_}"/><circle cx="128" cy="108" r="26" fill="${RED}"/>`),
  camera: badge(TEAL, `<rect x="48" y="86" width="160" height="106" rx="18" fill="${W_}"/><rect x="92" y="68" width="72" height="28" rx="8" fill="${W_}"/><circle cx="128" cy="140" r="34" fill="${TEAL}"/><circle cx="128" cy="140" r="18" fill="${W_}"/>`),
  people: badge("#7A5C99", `<circle cx="92" cy="104" r="24" fill="${W_}"/><circle cx="164" cy="104" r="24" fill="${W_}"/><path d="M48 192 Q48 142 92 142 Q136 142 136 192Z" fill="${W_}"/><path d="M120 192 Q120 142 164 142 Q208 142 208 192Z" fill="${W_}" opacity=".85"/>`),
  chat: badge(DEEP, `<rect x="44" y="60" width="168" height="110" rx="26" fill="${W_}"/><polygon points="84,170 84,214 128,170" fill="${W_}"/><text x="94" y="146" font-family="Cambria,serif" font-weight="700" font-size="64" fill="${DEEP}">A</text><text x="138" y="146" font-family="Nirmala UI,Mangal,sans-serif" font-weight="700" font-size="60" fill="${DEEP}">अ</text>`),
  clock: badge("#1E5A8C", `<circle cx="128" cy="128" r="74" fill="${W_}"/><path d="M128 78 V128 L162 148" stroke="#1E5A8C" stroke-width="14" fill="none" stroke-linecap="round"/>`),
  check: badge("#2F7D4F", `<path d="M62 132 L110 178 L196 82" stroke="${W_}" stroke-width="26" fill="none" stroke-linecap="round" stroke-linejoin="round"/>`),
  doc: badge(INK, `<path d="M70 44 H150 L190 84 V212 H70Z" fill="${W_}"/><path d="M150 44 V84 H190" fill="#D8D8D8"/><g stroke="${INK}" stroke-width="10" stroke-linecap="round"><line x1="94" y1="124" x2="166" y2="124"/><line x1="94" y1="152" x2="166" y2="152"/><line x1="94" y1="180" x2="140" y2="180"/></g>`),
  lock: badge(NAVY, `<rect x="66" y="112" width="124" height="96" rx="16" fill="${W_}"/><path d="M92 112 V86 Q92 52 128 52 Q164 52 164 86 V112" stroke="${W_}" stroke-width="18" fill="none"/><circle cx="128" cy="156" r="14" fill="${NAVY}"/>`),
  chain: badge("#1E5A8C", `<rect x="44" y="98" width="88" height="60" rx="30" fill="none" stroke="${W_}" stroke-width="18"/><rect x="124" y="98" width="88" height="60" rx="30" fill="none" stroke="${W_}" stroke-width="18"/>`),
  coin: badge(DEEP, `<circle cx="128" cy="128" r="78" fill="${GOLD}" stroke="${W_}" stroke-width="8"/><text x="128" y="160" font-family="Cambria,serif" font-weight="700" font-size="96" text-anchor="middle" fill="${INK}">₹</text>`),
  robot: badge("#7A5C99", `<rect x="58" y="86" width="140" height="104" rx="24" fill="${W_}"/><circle cx="102" cy="136" r="16" fill="#7A5C99"/><circle cx="154" cy="136" r="16" fill="#7A5C99"/><line x1="128" y1="86" x2="128" y2="54" stroke="${W_}" stroke-width="10"/><circle cx="128" cy="48" r="12" fill="${W_}"/><rect x="100" y="166" width="56" height="10" rx="5" fill="#7A5C99"/>`),
  flag: badge(RED, `<line x1="82" y1="48" x2="82" y2="214" stroke="${W_}" stroke-width="14" stroke-linecap="round"/><path d="M86 56 H190 L166 94 L190 132 H86Z" fill="${W_}"/>`),
};
for (const [k, inner] of Object.entries(icons)) svgs["i_" + k] = { w: 256, h: 256, svg: inner };

// ---------- render ----------
const b = await chromium.launch();
for (const [name, d] of Object.entries(svgs)) {
  const page = await b.newPage({ viewport: { width: d.w, height: d.h } });
  await page.setContent(`<body style="margin:0;background:${d.bg ? "#000" : "transparent"}"><svg xmlns="http://www.w3.org/2000/svg" width="${d.w}" height="${d.h}" viewBox="0 0 ${d.w} ${d.h}">${d.svg}</svg></body>`);
  await page.screenshot({ path: `${OUT}/${name}.png`, omitBackground: !d.bg });
  await page.close();
}
await b.close();
console.log("rendered", Object.keys(svgs).length, "illustrations to", OUT);
