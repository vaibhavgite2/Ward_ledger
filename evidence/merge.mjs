import { readFileSync, writeFileSync, existsSync } from "node:fs";
const sc = new Map();
for (const f of ["output/manifest.json", "output/m_a.json", "output/m_b.json", "output/m_c.json", "output/m_d.json"])
  if (existsSync(f)) for (const s of JSON.parse(readFileSync(f, "utf8")).scenes) sc.set(s.id, s);
const scenes = [...sc.values()].sort((a, b) => a.id.localeCompare(b.id));
writeFileSync("output/manifest.json", JSON.stringify({ scenes }, null, 2));
console.log(scenes.map((s) => `${s.id} ${s.status.slice(0, 20)} shots=${s.shots.length}`).join("\n"));
