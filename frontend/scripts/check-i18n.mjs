// Fails if (a) a static t("key") call has no catalog entry, (b) the language catalogs differ in keys,
// (c) a catalog value is empty. Dynamic keys like t("sev." + x) are checked by prefix.
// Usage (from frontend/): node scripts/check-i18n.mjs
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

const root = fileURLToPath(new URL("..", import.meta.url));
const load = (f) => JSON.parse(readFileSync(join(root, "messages", f), "utf8"));
const langs = ["en", "mr", "hi"];
const cat = {};
for (const l of langs) cat[l] = { ...load(`${l}.json`), ...load(`officer.${l}.json`) };

let bad = 0;
const fail = (m) => {
  bad++;
  console.error("FAIL:", m);
};

const base = new Set(Object.keys(cat.en));
for (const l of langs.slice(1)) {
  for (const k of base) if (!(k in cat[l])) fail(`${l} is missing key ${k}`);
  for (const k of Object.keys(cat[l])) if (!base.has(k)) fail(`${l} has extra key ${k}`);
}
for (const l of langs) for (const [k, v] of Object.entries(cat[l])) if (!String(v).trim()) fail(`${l}.${k} is empty`);

function walk(dir, out = []) {
  for (const f of readdirSync(dir)) {
    if (f === "node_modules" || f === ".next") continue;
    const p = join(dir, f);
    if (statSync(p).isDirectory()) walk(p, out);
    else if (/\.(tsx?|jsx?)$/.test(f)) out.push(p);
  }
  return out;
}
const files = ["app", "components", "lib"].flatMap((d) => walk(join(root, d)));
let used = 0;
for (const f of files) {
  const src = readFileSync(f, "utf8");
  for (const m of src.matchAll(/\bt\(\s*"([A-Za-z0-9_.]+)"\s*[,)]/g)) {
    used++;
    if (!base.has(m[1])) fail(`${f.replace(root, "")}: unknown key "${m[1]}"`);
  }
  for (const m of src.matchAll(/\bt\(\s*"([A-Za-z0-9_.]+\.)"\s*\+/g)) {
    used++;
    if (![...base].some((k) => k.startsWith(m[1]))) fail(`${f.replace(root, "")}: no keys with prefix "${m[1]}"`);
  }
  for (const m of src.matchAll(/\["[^"]*",\s*"([a-z]+\.[A-Za-z0-9_.]+)"\]/g)) {
    used++;
    if (!base.has(m[1])) fail(`${f.replace(root, "")}: unknown key "${m[1]}" (in a table)`);
  }
}
console.log(`${base.size} keys x ${langs.length} languages, ${used} key references checked in ${files.length} files`);
process.exit(bad ? 1 : 0);
