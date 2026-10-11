#!/usr/bin/env python3
"""Build the contact sheet, HTML catalog and Markdown catalog from manifests."""
from __future__ import annotations

import html
import json
import os
import sys

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from cmet.export import ROOT, TPL  # noqa: E402

FONT = os.path.join(ROOT, "02_SHARED_ASSETS", "Fonts", "teko", "Teko[wght].ttf")


def manifests():
    out = []
    for d in sorted(os.listdir(TPL)):
        mp = os.path.join(TPL, d, "manifest.json")
        if os.path.exists(mp):
            m = json.load(open(mp, encoding="utf-8"))
            m["_dir"] = d
            out.append(m)
    return out


def contact_sheet(ms, cols=5, tw=480, th=270):
    rows = (len(ms) + cols - 1) // cols
    pad, lab = 12, 46
    W = cols * (tw + pad) + pad
    H = rows * (th + lab + pad) + pad + 90
    sheet = Image.new("RGB", (W, H), (10, 10, 12))
    dr = ImageDraw.Draw(sheet)
    fbig = ImageFont.truetype(FONT, 56)
    fs = ImageFont.truetype(FONT, 30)
    fx = ImageFont.truetype(FONT, 22)
    dr.text((pad, 14), f"CINEMATIC MASS ELEVATION TEMPLATES - {len(ms)} TEMPLATES", font=fbig, fill=(235, 200, 150))
    for i, m in enumerate(ms):
        r, c = divmod(i, cols)
        x = pad + c * (tw + pad)
        y = 90 + pad + r * (th + lab + pad)
        tp = os.path.join(TPL, m["_dir"], m["thumbnail"]) if m.get("thumbnail") else None
        if tp and os.path.exists(tp):
            im = Image.open(tp).convert("RGB").resize((tw, th), Image.LANCZOS)
            sheet.paste(im, (x, y))
        else:
            dr.rectangle([x, y, x + tw, y + th], outline=(80, 80, 80))
            dr.text((x + 20, y + th // 2), "NO PREVIEW", font=fs, fill=(160, 80, 80))
        badge = "3D" if m["true_3d"] else "2.5D"
        dr.text((x, y + th + 4), f"{m['id']}  {m['name'].upper()}", font=fs, fill=(230, 230, 230))
        dr.text((x + tw - 60, y + th + 10), badge, font=fx, fill=(240, 180, 90) if m["true_3d"] else (150, 170, 200))
    out = os.path.join(ROOT, "03_PREVIEWS", "Contact_Sheets", "contact_sheet_all.jpg")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    sheet.save(out, quality=88)
    return out


def html_catalog(ms):
    cats = sorted({m["category"] for m in ms})
    cards = []
    for m in ms:
        d = m["_dir"]
        v = m["verification"]
        ok_src = v["structure"] == "PASS"
        ok_prv = v["preview"] == "PASS"
        prev = f"01_TEMPLATES/{d}/{m['preview']}" if m.get("preview") else ""
        thumb = f"01_TEMPLATES/{d}/{m['thumbnail']}" if m.get("thumbnail") else ""
        ex = m.get("extra_parameters") or {}
        extra = ("<dt>Template-specific parameters</dt><dd>" + html.escape(", ".join(
            f"{k} (default {v['default']})" for k, v in ex.items())) + "</dd>") if ex else ""
        nl = m.get("fusion_notes") or []
        notes = ("<dt>Fusion notes &amp; limitations</dt><dd><ul>" + "".join(
            f"<li>{html.escape(n)}</li>" for n in nl) + "</ul></dd>") if nl else ""
        cards.append(f"""
<article class="card" data-cat="{html.escape(m['category'])}" data-depth="{'3d' if m['true_3d'] else '25d'}">
  <button class="thumb" data-video="{html.escape(prev)}" aria-label="Play preview of {html.escape(m['name'])}">
    <img src="{html.escape(thumb)}" alt="{html.escape(m['name'])} thumbnail" loading="lazy">
    <span class="play">&#9654;</span>
  </button>
  <div class="meta">
    <h2><span class="id">{m['id']}</span> {html.escape(m['name'])}</h2>
    <p class="cat">{html.escape(m['category'])} &middot; {m['duration_seconds']:.1f}s &middot;
       <span class="badge {'b3d' if m['true_3d'] else 'b25'}">{'3D (Text3D)' if m['true_3d'] else '2.5D'}</span></p>
    <p class="concept">{html.escape(m['concept'])}</p>
    <details>
      <summary>Design, controls &amp; limitations</summary>
      <img class="strip" src="03_PREVIEWS/Contact_Sheets/per_template/{d}_strip.jpg" alt="Six-frame strip of {html.escape(m['name'])}: build-up, pre-impact, impact, hold, exit, end" loading="lazy">
      <dl>
        <dt>Entrance</dt><dd>{html.escape(m['design']['entrance'])}</dd>
        <dt>Impact / reveal</dt><dd>{html.escape(m['design']['reveal'])}</dd>
        <dt>Camera</dt><dd>{html.escape(m['design']['camera'])}</dd>
        <dt>Material</dt><dd>{html.escape(m['design']['material'])}</dd>
        <dt>Exit</dt><dd>{html.escape(m['design']['exit'])}</dd>
        <dt>Timing</dt><dd>impact frame {m['phases']['impact_frame']}, hold {m['phases']['hero_hold'][0]}&ndash;{m['phases']['hero_hold'][1]}, exit {m['phases']['exit'][0]}&ndash;{m['phases']['exit'][1]} ({m['duration_frames']} frames)</dd>
        <dt>Fusion controls ({len(m['fusion_published_controls'])})</dt><dd>{html.escape(', '.join(dict.fromkeys(m['fusion_published_controls'])))}</dd>
        {extra}
        {notes}
        <dt>Unconfirmed Fusion inputs</dt><dd>{len(m.get('unconfirmed_fusion_inputs', []))} &mdash; check in Resolve (listed in README)</dd>
      </dl>
    </details>
    <ul class="checks">
      <li class="{'ok' if v['lua_parse'] == 'PASS' else 'bad'}">Fusion source parses (Lua)</li>
      <li class="{'ok' if ok_src else 'bad'}">Graph structure checks</li>
      <li class="{'ok' if ok_prv else 'bad'}">Preview media checks</li>
      <li class="na">Resolve: not tested</li>
    </ul>
    <p class="links">
      <a href="01_TEMPLATES/{d}/README.md">README</a> &middot;
      <a href="01_TEMPLATES/{d}/{m['fusion_macro']}">.setting</a> &middot;
      <a href="01_TEMPLATES/{d}/{m['fusion_composition']}">.comp</a> &middot;
      <a href="01_TEMPLATES/{d}/{m['parameters']}">controls</a> &middot;
      <a href="01_TEMPLATES/{d}/{m['sound_design']}">sound</a>
    </p>
  </div>
</article>""")
    opts = "".join(f'<option value="{html.escape(c)}">{html.escape(c)}</option>' for c in cats)
    n3 = sum(1 for m in ms if m["true_3d"])
    page = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Mass Elevation Templates</title>
<style>
:root {{ --bg:#0b0b0d; --panel:#141418; --ink:#ecebe8; --mute:#9a978f; --acc:#e8b26a; --ok:#7fc98f; --bad:#e07a6a; }}
@media (prefers-color-scheme: light) {{ :root:not([data-theme="dark"]) {{ --bg:#f4f2ee; --panel:#ffffff; --ink:#1b1a18; --mute:#5f5c56; --acc:#9a5d12; --ok:#2e7d3e; --bad:#b03a2a; }} }}
:root[data-theme="dark"] {{ --bg:#0b0b0d; --panel:#141418; --ink:#ecebe8; --mute:#9a978f; --acc:#e8b26a; }}
* {{ box-sizing:border-box; }}
body {{ margin:0; background:var(--bg); color:var(--ink); font:15px/1.45 system-ui,-apple-system,Segoe UI,Roboto,sans-serif; }}
header {{ padding:28px 16px 8px; max-width:1500px; margin:auto; }}
h1 {{ margin:0 0 6px; font-size:28px; letter-spacing:.04em; }}
header p {{ margin:4px 0; color:var(--mute); max-width:900px; }}
.controls {{ display:flex; gap:10px; flex-wrap:wrap; margin:14px 0; }}
select, input {{ background:var(--panel); color:var(--ink); border:1px solid #444; border-radius:6px; padding:7px 9px; }}
main {{ display:grid; grid-template-columns:repeat(auto-fill,minmax(320px,1fr)); gap:16px; padding:8px 16px 40px; max-width:1500px; margin:auto; }}
.card {{ background:var(--panel); border-radius:10px; overflow:hidden; border:1px solid rgba(128,128,128,.18); }}
.thumb {{ position:relative; display:block; width:100%; padding:0; border:0; background:#000; cursor:pointer; aspect-ratio:16/9; }}
.thumb img {{ width:100%; height:100%; object-fit:cover; display:block; }}
.play {{ position:absolute; right:10px; bottom:8px; color:#fff; background:rgba(0,0,0,.55); border-radius:50%; width:34px; height:34px; display:grid; place-items:center; }}
.meta {{ padding:10px 14px 14px; }}
.meta h2 {{ margin:0; font-size:18px; }}
.id {{ color:var(--acc); font-variant-numeric:tabular-nums; }}
.cat {{ margin:2px 0 6px; color:var(--mute); font-size:13px; }}
.concept {{ margin:6px 0; font-size:14px; }}
.badge {{ padding:1px 7px; border-radius:10px; font-size:12px; border:1px solid currentColor; }}
.b3d {{ color:var(--acc); }} .b25 {{ color:var(--mute); }}
.checks {{ list-style:none; padding:0; margin:6px 0; font-size:13px; display:flex; flex-wrap:wrap; gap:4px 12px; }}
.checks li::before {{ content:"\\25CF  "; }}
.ok {{ color:var(--ok); }} .bad {{ color:var(--bad); }} .na {{ color:var(--mute); }}
.links {{ margin:6px 0 0; font-size:13px; }}
details {{ margin:8px 0; font-size:13px; }}
summary {{ cursor:pointer; color:var(--acc); }}
.strip {{ width:100%; display:block; margin:8px 0; border-radius:4px; }}
dl {{ margin:0; }} dt {{ font-weight:600; margin-top:6px; }} dd {{ margin:2px 0 0; color:var(--mute); }}
dd ul {{ margin:2px 0; padding-left:18px; }}
a {{ color:var(--acc); }}
dialog {{ border:0; padding:0; background:#000; max-width:min(1280px,96vw); width:100%; }}
dialog video {{ width:100%; display:block; }}
dialog::backdrop {{ background:rgba(0,0,0,.8); }}
.close {{ position:absolute; right:8px; top:6px; background:rgba(0,0,0,.6); color:#fff; border:0; font-size:20px; cursor:pointer; }}
</style></head><body>
<header>
<h1>Cinematic Mass Elevation Templates</h1>
<p>{len(ms)} editable DaVinci Resolve / Fusion title templates ({n3} with genuine Text3D geometry, {len(ms) - n3} 2.5D).
Each card links the Fusion macro (<code>.setting</code>), the flat composition (<code>.comp</code>), its controls and its sound cue sheet.
Click a thumbnail to play its 1080p preview.</p>
<p><strong>Previews</strong> come from the project's Python reference renderer, not from Resolve.
<strong>Resolve compatibility has not been tested</strong> (no Resolve in the build environment). See COMPATIBILITY_REPORT.md and 05_RESOLVE_IMPORT/Import_Instructions.md.</p>
<div class="controls">
<select id="cat"><option value="">All categories</option>{opts}</select>
<select id="depth"><option value="">3D + 2.5D</option><option value="3d">3D only</option><option value="25d">2.5D only</option></select>
<input id="q" type="search" placeholder="Search name or concept">
</div>
</header>
<main id="grid">{''.join(cards)}</main>
<dialog id="dlg"><button class="close" aria-label="Close">&times;</button><video id="vid" controls playsinline></video></dialog>
<script>
const dlg=document.getElementById('dlg'), vid=document.getElementById('vid');
document.querySelectorAll('.thumb').forEach(b=>b.addEventListener('click',()=>{{ if(!b.dataset.video) return; vid.src=b.dataset.video; dlg.showModal(); vid.play().catch(()=>{{}}); }}));
dlg.querySelector('.close').onclick=()=>dlg.close();
dlg.addEventListener('close',()=>{{ vid.pause(); vid.removeAttribute('src'); vid.load(); }});
function f(){{ const c=document.getElementById('cat').value, d=document.getElementById('depth').value, q=document.getElementById('q').value.toLowerCase();
 document.querySelectorAll('.card').forEach(el=>{{ const ok=(!c||el.dataset.cat===c)&&(!d||el.dataset.depth===d)&&(!q||el.textContent.toLowerCase().includes(q)); el.style.display=ok?'':'none'; }}); }}
['cat','depth','q'].forEach(i=>document.getElementById(i).addEventListener('input',f));
</script></body></html>"""
    out = os.path.join(ROOT, "TEMPLATE_CATALOG.html")
    open(out, "w", encoding="utf-8").write(page)
    return out


def md_catalog(ms):
    L = ["# Template Catalog", "",
         f"{len(ms)} templates. Browse visually in `TEMPLATE_CATALOG.html` (opens locally, no server) or the contact "
         "sheet `03_PREVIEWS/Contact_Sheets/contact_sheet_all.jpg`.", "",
         "Verification columns: **Src** = Fusion source parses in a real Lua interpreter and passes structural "
         "checks; **Prev** = preview MP4 passes ffprobe/duration/size/non-black/motion/exposure checks; "
         "**Resolve** = opened inside DaVinci Resolve (not possible in the build environment).", "",
         "| # | Template | Category | Dur | Depth | Concept | Src | Prev | Resolve | Files |",
         "|---|---|---|---|---|---|---|---|---|---|"]
    for m in ms:
        d = m["_dir"]
        v = m["verification"]
        L.append(f"| {m['id']} | **{m['name']}** | {m['category']} | {m['duration_seconds']:.1f}s | "
                 f"{'3D' if m['true_3d'] else '2.5D'} | {m['concept']} | "
                 f"{'PASS' if v['structure'] == 'PASS' else 'FAIL'} | {'PASS' if v['preview'] == 'PASS' else 'FAIL'} | "
                 f"not tested | [README](01_TEMPLATES/{d}/README.md) / "
                 f"[.setting](01_TEMPLATES/{d}/{m['fusion_macro']}) / "
                 f"[preview](01_TEMPLATES/{d}/{m['preview']}) |")
    L.append("")
    out = os.path.join(ROOT, "TEMPLATE_CATALOG.md")
    open(out, "w", encoding="utf-8").write("\n".join(L))
    return out


def main():
    ms = manifests()
    print("manifests:", len(ms))
    print(contact_sheet(ms))
    print(html_catalog(ms))
    print(md_catalog(ms))
    # thumbnails gallery copy
    tdir = os.path.join(ROOT, "03_PREVIEWS", "Thumbnails")
    os.makedirs(tdir, exist_ok=True)
    for m in ms:
        if m.get("thumbnail"):
            src = os.path.join(TPL, m["_dir"], m["thumbnail"])
            im = cv2.imread(src)
            cv2.imwrite(os.path.join(tdir, f"{m['_dir']}.jpg"), cv2.resize(im, (480, 270), interpolation=cv2.INTER_AREA),
                        [cv2.IMWRITE_JPEG_QUALITY, 85])


if __name__ == "__main__":
    main()
