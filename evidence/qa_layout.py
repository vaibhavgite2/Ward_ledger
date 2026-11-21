"""Geometry QA for a pptx when no renderer is available: off-slide shapes and estimated text overflow."""
import math
import sys
from pptx import Presentation
from pptx.util import Emu

path = sys.argv[1]
prs = Presentation(path)
W, H = prs.slide_width, prs.slide_height
issues = 0
for i, slide in enumerate(prs.slides, 1):
    for sh in slide.shapes:
        if sh.left is None:
            continue
        r, b = sh.left + sh.width, sh.top + sh.height
        if sh.left < -Emu(1000) or sh.top < -Emu(1000) or r > W + Emu(1000) or b > H + Emu(1000):
            print(f"slide {i}: OFF-SLIDE {sh.name} ({sh.left/914400:.2f},{sh.top/914400:.2f}) {sh.width/914400:.2f}x{sh.height/914400:.2f}")
            issues += 1
        if not sh.has_text_frame or not sh.text_frame.text.strip():
            continue
        wi, hi = sh.width / 914400, sh.height / 914400
        need = 0.0
        for p in sh.text_frame.paragraphs:
            txt = "".join(r.text for r in p.runs)
            if not txt:
                continue
            size = next((r.font.size.pt for r in p.runs if r.font.size), 18)
            bold = any(r.font.bold for r in p.runs)
            serif = any((r.font.name or "").startswith("Cambria") for r in p.runs)
            cw = size * (0.56 if serif and bold else 0.52 if serif else 0.5 if bold else 0.47) / 72  # avg char width, inches
            per_line = max(1, int(wi / cw))
            lines = math.ceil(len(txt) / per_line)
            need += lines * size * 1.2 / 72
        if need > hi * 1.08 and hi > 0.2:
            print(f"slide {i}: TEXT MAY OVERFLOW {sh.name!r} need~{need:.2f}in have {hi:.2f}in :: {sh.text_frame.text[:60]!r}")
            issues += 1
print(f"{len(prs.slides)} slides checked, {issues} potential issue(s)")
