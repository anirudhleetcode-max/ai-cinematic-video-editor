"""Builds an ASS (Advanced SubStation) script for all titles, captions and animated text, which the
final pass burns in with libass. Text extents are measured with the actual TTFs (Pillow) so
safe-area checks are real."""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from PIL import ImageFont

from ..config import get_settings
from ..registry.text import TEXT_ANIMATIONS, TEXT_STYLES
from ..schemas import CaptionSpec, TextItem

FONT_FILES = {
    ("Inter", False, False): "Inter_400Regular.ttf", ("Inter", True, False): "Inter_700Bold.ttf",
    ("Montserrat", False, False): "Montserrat_500Medium.ttf", ("Montserrat", True, False): "Montserrat_800ExtraBold.ttf",
    ("Playfair Display", False, False): "PlayfairDisplay_400Regular.ttf", ("Playfair Display", False, True): "PlayfairDisplay_400Regular_Italic.ttf",
    ("Playfair Display", True, False): "PlayfairDisplay_700Bold.ttf", ("Playfair Display", True, True): "PlayfairDisplay_400Regular_Italic.ttf",
    ("Bebas Neue", False, False): "BebasNeue_400Regular.ttf", ("Bebas Neue", True, False): "BebasNeue_400Regular.ttf",
}


@lru_cache(maxsize=64)
def _font(family: str, bold: bool, italic: bool, px: int) -> ImageFont.FreeTypeFont:
    fn = FONT_FILES.get((family, bold, italic)) or FONT_FILES.get((family, bold, False)) or "Inter_400Regular.ttf"
    return ImageFont.truetype(str(get_settings().fonts_dir / fn), px)


def measure(text: str, family: str, bold: bool, italic: bool, px: int, tracking: float) -> tuple[int, int]:
    fnt = _font(family, bold, italic, max(4, px))
    lines = text.split("\\N")
    w = max((fnt.getlength(l) + tracking * max(0, len(l) - 1) for l in lines), default=0)
    asc, desc = fnt.getmetrics()
    return int(w), int((asc + desc) * len(lines) * 1.1)


def ass_color(hex_: str, alpha: float = 0.0) -> str:
    h = hex_.lstrip("#")
    r, g, b = h[0:2], h[2:4], h[4:6]
    return f"&H{int(alpha * 255):02X}{b}{g}{r}".upper()


def _t(sec: float) -> str:
    sec = max(0.0, sec)
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    return f"{int(h)}:{int(m):02d}:{s:05.2f}"


def _esc(s: str) -> str:
    return s.replace("\\", "").replace("{", "(").replace("}", ")").replace("\n", "\\N")


@dataclass
class SafeArea:
    left: float
    right: float
    top: float
    bottom: float


def safe_area(w: int, h: int) -> SafeArea:
    if h > w:  # vertical platforms: leave room for app UI at top/bottom
        return SafeArea(0.07 * w, 0.07 * w, 0.12 * h, 0.2 * h)
    return SafeArea(0.06 * w, 0.06 * w, 0.07 * h, 0.08 * h)


def _anchor(position: str, w: int, h: int, sa: SafeArea, tw: int, th: int) -> tuple[int, int, int]:
    """Return (an, x, y) for \\an alignment + \\pos."""
    if position == "center":
        return 5, w // 2, h // 2
    if position == "top":
        return 8, w // 2, int(sa.top)
    if position == "bottom":
        return 2, w // 2, int(h - sa.bottom)
    if position == "upper_left":
        return 7, int(sa.left), int(sa.top)
    if position == "lower_right":
        return 3, int(w - sa.right), int(h - sa.bottom)
    # lower_third / lower_left
    return 1, int(sa.left), int(h - sa.bottom - (0.06 * h if position == "lower_third" else 0))


def _bbox(an: int, x: int, y: int, tw: int, th: int) -> tuple[int, int, int, int]:
    col = (an - 1) % 3  # 0 left 1 center 2 right
    row = 2 - (an - 1) // 3  # 0 top 1 middle 2 bottom
    x0 = x - (0 if col == 0 else tw // 2 if col == 1 else tw)
    y0 = y - (0 if row == 0 else th // 2 if row == 1 else th)
    return x0, y0, x0 + tw, y0 + th


class AssBuilder:
    def __init__(self, w: int, h: int):
        self.w, self.h = w, h
        self.sa = safe_area(w, h)
        self.styles: dict[str, str] = {}
        self.events: list[str] = []
        self.violations: list[dict] = []
        self.boxes: list[dict] = []

    def _style_line(self, name: str, s: dict, px: int) -> str:
        primary = ass_color(s["color"])
        outline = ass_color(s["outline_color"])
        back = ass_color(s["box_color"] if s["box"] else "#000000", s["box_alpha"] if s["box"] else s["shadow_alpha"])
        border_style = 3 if s["box"] else 1
        return (f"Style: {name},{s['font']},{px},{primary},{ass_color(s['accent'])},{outline},{back},{-1 if s['bold'] else 0},{-1 if s['italic'] else 0},"
                f"0,0,100,100,{s['tracking']:.1f},0,{border_style},{s['outline'] if not s['box'] else max(6, px * 0.25):.1f},{s['shadow']:.1f},5,0,0,0,1")

    def add(self, item: TextItem) -> None:
        sd = TEXT_STYLES.get(item.style if TEXT_STYLES.has(item.style) else "premium_title")
        s = sd.render(sd.resolve({k: v for k, v in item.params.items() if k in {p.name for p in sd.params}}))
        an_def = TEXT_ANIMATIONS.get(item.animation if TEXT_ANIMATIONS.has(item.animation) else "fade")
        ap = an_def.resolve(item.params)
        px = int(self.h * s["size"] * s["size_scale"] * item.scale)
        text = item.text
        if s["case"] == "upper":
            text = text.upper()
        elif s["case"] == "lower":
            text = text.lower()
        text = _esc(text)
        # auto-wrap to the safe width (break at the most central space)
        max_w = self.w - self.sa.left - self.sa.right
        tw, th = measure(text, s["font"], s["bold"], s["italic"], px, s["tracking"])
        while tw > max_w and px > 12:
            if "\\N" not in text and " " in text:
                words = text.split(" ")
                mid = min(range(1, len(words)), key=lambda k: abs(len(" ".join(words[:k])) - len(" ".join(words[k:]))))
                text = " ".join(words[:mid]) + "\\N" + " ".join(words[mid:])
            else:
                px = int(px * 0.92)
            tw, th = measure(text, s["font"], s["bold"], s["italic"], px, s["tracking"])
        sname = f"S_{item.style}_{px}"
        self.styles[sname] = self._style_line(sname, s, px)
        an, x, y = _anchor(item.position, self.w, self.h, self.sa, tw, th)
        bb = _bbox(an, x, y, tw, th)
        self.boxes.append({"id": item.id, "bbox": bb})
        if bb[0] < self.sa.left - 1 or bb[2] > self.w - self.sa.right + 1 or bb[1] < self.sa.top * 0.5 or bb[3] > self.h - self.sa.bottom * 0.5:
            self.violations.append({"id": item.id, "bbox": bb, "safe": vars(self.sa)})
        self._emit(item, text, sname, an, x, y, tw, th, ap, s)

    def _ev(self, start, end, style, tags, text, layer=0):
        self.events.append(f"Dialogue: {layer},{_t(start)},{_t(end)},{style},,0,0,0,,{{{tags}}}{text}")

    def _emit(self, it: TextItem, text: str, st: str, an: int, x: int, y: int, tw: int, th: int, ap: dict, s: dict) -> None:
        a = it.animation
        i_ms, o_ms = int(ap["in_dur"] * 1000), int(ap["out_dur"] * 1000)
        dur_ms = int((it.end - it.start) * 1000)
        base = f"\\an{an}\\pos({x},{y})"
        fad = f"\\fad({i_ms},{o_ms})"
        if a == "static":
            return self._ev(it.start, it.end, st, base, text)
        if a == "fade":
            return self._ev(it.start, it.end, st, base + fad, text)
        if a in ("fade_up", "slide_left", "slide_right", "split_reveal"):
            d = ap.get("distance", 0.03)
            dx, dy = {"fade_up": (0, d * self.h), "slide_left": (-d * self.w, 0), "slide_right": (d * self.w, 0), "split_reveal": (0, d * self.h)}[a]
            if a == "split_reveal" and "\\N" in text:
                l1, l2 = text.split("\\N", 1)
                self._ev(it.start, it.end, st, f"\\an{an}\\move({x},{int(y - dy)},{x},{y - th // 4},0,{i_ms}){fad}", l1)
                return self._ev(it.start, it.end, st, f"\\an{an}\\move({x},{int(y + dy)},{x},{y + th // 4},0,{i_ms}){fad}", l2)
            return self._ev(it.start, it.end, st, f"\\an{an}\\move({int(x + dx)},{int(y + dy)},{x},{y},0,{i_ms}){fad}", text)
        if a == "scale_in":
            fs = int(ap["from_scale"] * 100)
            return self._ev(it.start, it.end, st, base + fad + f"\\fscx{fs}\\fscy{fs}\\t(0,{i_ms},0.5,\\fscx100\\fscy100)", text)
        if a == "tracking_reveal":
            return self._ev(it.start, it.end, st, base + fad + f"\\fsp{ap['from_tracking']:.0f}\\t(0,{int(i_ms * 2)},0.4,\\fsp{s['tracking']:.0f})", text)
        if a == "blur_reveal":
            return self._ev(it.start, it.end, st, base + fad + f"\\blur{ap['from_blur']:.0f}\\t(0,{i_ms},\\blur0)", text)
        if a == "mask_reveal":
            x0, y0, x1, y1 = _bbox(an, x, y, tw, th)
            pad = 8
            if ap["direction"] == "up":
                c0, c1 = f"\\clip({x0 - pad},{y1 + pad},{x1 + pad},{y1 + pad})", f"\\clip({x0 - pad},{y0 - pad},{x1 + pad},{y1 + pad})"
            elif ap["direction"] == "right":
                c0, c1 = f"\\clip({x1 + pad},{y0 - pad},{x1 + pad},{y1 + pad})", f"\\clip({x0 - pad},{y0 - pad},{x1 + pad},{y1 + pad})"
            else:
                c0, c1 = f"\\clip({x0 - pad},{y0 - pad},{x0 - pad},{y1 + pad})", f"\\clip({x0 - pad},{y0 - pad},{x1 + pad},{y1 + pad})"
            return self._ev(it.start, it.end, st, base + f"\\fad(0,{o_ms}){c0}\\t(0,{i_ms},0.6,{c1})", text)
        if a in ("bounce", "elastic", "pop"):
            ov = int(ap["overshoot"] * 100)
            k = i_ms
            seq = (f"\\fscx0\\fscy0\\t(0,{int(k * 0.55)},\\fscx{ov}\\fscy{ov})\\t({int(k * 0.55)},{int(k * 0.8)},\\fscx{200 - ov}\\fscy{200 - ov})"
                   f"\\t({int(k * 0.8)},{k},\\fscx100\\fscy100)")
            if a == "elastic":
                seq += f"\\t({k},{int(k * 1.3)},\\fscx{100 + (ov - 100) // 3}\\fscy{100 + (ov - 100) // 3})\\t({int(k * 1.3)},{int(k * 1.6)},\\fscx100\\fscy100)"
            return self._ev(it.start, it.end, st, base + f"\\fad(80,{o_ms})" + seq, text)
        if a in ("typewriter", "char_by_char"):
            gap = 1000 / ap["cps"] if a == "typewriter" else ap["char_gap"] * 1000
            out, t = [], 0.0
            for ch in text.replace("\\N", "\n"):
                if ch == "\n":
                    out.append("\\N")
                    continue
                out.append(f"{{\\alpha&HFF&\\t({int(t)},{int(t) + 1},\\alpha&H00&)}}{ch}")
                t += gap
            return self._ev(it.start, it.end, st, base + f"\\fad(0,{o_ms})", "".join(out))
        if a in ("word_by_word", "kinetic_words"):
            gap = ap["word_gap"] * 1000
            words = text.replace("\\N", " \\N ").split(" ")
            out, t = [], 0.0
            for wd in words:
                if wd == "\\N":
                    out.append("\\N")
                    continue
                if a == "kinetic_words":
                    out.append(f"{{\\alpha&HFF&\\fscx70\\fscy70\\t({int(t)},{int(t) + 1},\\alpha&H00&)\\t({int(t)},{int(t + 180)},\\fscx112\\fscy112)\\t({int(t + 180)},{int(t + 300)},\\fscx100\\fscy100)}}{wd} ")
                else:
                    out.append(f"{{\\alpha&HFF&\\t({int(t)},{int(t + 120)},\\alpha&H00&)}}{wd} ")
                t += gap
            return self._ev(it.start, it.end, st, base + f"\\fad(0,{o_ms})", "".join(out).rstrip())
        if a == "line_by_line":
            lines = text.split("\\N")
            for k, ln in enumerate(lines):
                yy = y - th // 2 + int(th / len(lines) * (k + 0.5)) if an in (4, 5, 6) else y + int(th / len(lines) * k)
                self._ev(it.start + k * ap["line_gap"], it.end, st, f"\\an{an}\\pos({x},{yy}){fad}", ln)
            return
        if a == "karaoke":
            words = text.split(" ")
            per = max(10, int(dur_ms / 10 / max(1, len(words))))
            return self._ev(it.start, it.end, st, base + "\\fad(100,100)", "".join(f"{{\\kf{per}}}{wd} " for wd in words).rstrip())
        return self._ev(it.start, it.end, st, base + fad, text)

    def add_captions(self, cap: CaptionSpec) -> None:
        """Group words into caption lines (<= 42 chars / 3.5 s) and animate per caption style."""
        if not cap.enabled or not cap.words:
            return
        style = cap.style
        groups, cur = [], []
        for wd in cap.words:
            cur.append(wd)
            txt = " ".join(x["w"] for x in cur)
            if len(txt) > 38 or (cur[-1]["t1"] - cur[0]["t0"]) > 3.2 or wd["w"].endswith((".", "?", "!")):
                groups.append(cur)
                cur = []
        if cur:
            groups.append(cur)
        anim = {"karaoke": "karaoke", "word_highlight": "karaoke", "bounce": "bounce", "pop": "pop", "kinetic": "kinetic_words", "scale": "scale_in"}.get(style, "fade")
        tstyle = {"karaoke": "social_caption", "word_highlight": "social_caption", "bounce": "social_caption", "pop": "social_caption",
                  "kinetic": "kinetic_bold", "cinematic_subtitle": "cinematic_subtitle"}.get(style, "documentary_caption")
        for k, g in enumerate(groups):
            t0, t1 = g[0]["t0"], max(g[-1]["t1"], g[0]["t0"] + 0.6)
            item = TextItem(id=f"cap_{k}", kind="caption", text=" ".join(x["w"] for x in g), start=t0, end=t1, style=tstyle, animation=anim,
                            position="bottom", params={"in_dur": 0.15, "out_dur": 0.1})
            if anim == "karaoke":
                self._karaoke(item, g, tstyle)
            else:
                self.add(item)

    def _karaoke(self, item: TextItem, words: list[dict], style: str) -> None:
        sd = TEXT_STYLES.get(style)
        s = sd.render(sd.resolve({}))
        px = int(self.h * s["size"])
        sname = f"S_{style}_{px}"
        self.styles[sname] = self._style_line(sname, s, px)
        an, x, y = _anchor("bottom", self.w, self.h, self.sa, 0, 0)
        parts, prev = [], item.start
        for wd in words:
            gap = max(0, int((wd["t0"] - prev) * 100))
            if gap:
                parts.append(f"{{\\k{gap}}}")
            parts.append(f"{{\\kf{max(5, int((wd['t1'] - wd['t0']) * 100))}}}{_esc(wd['w'].upper() if s['upper'] else wd['w'])} ")
            prev = wd["t1"]
        self._ev(item.start, item.end + 0.2, sname, f"\\an{an}\\pos({x},{y})\\fad(80,80)", "".join(parts).rstrip())

    def script(self) -> str:
        head = (f"[Script Info]\nScriptType: v4.00+\nPlayResX: {self.w}\nPlayResY: {self.h}\nWrapStyle: 2\nScaledBorderAndShadow: yes\n\n"
                "[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, "
                "StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n")
        body = "\n".join(self.styles.values())
        ev = "\n\n[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n" + "\n".join(self.events) + "\n"
        return head + body + ev

    def write(self, path: Path) -> Path:
        path.write_text(self.script(), encoding="utf-8")
        return path


def write_srt(words: list[dict], path: Path) -> Path:
    """Plain SRT/VTT export of caption words grouped into lines."""
    groups, cur = [], []
    for wd in words:
        cur.append(wd)
        if len(" ".join(x["w"] for x in cur)) > 40 or wd["w"].endswith((".", "?", "!")):
            groups.append(cur)
            cur = []
    if cur:
        groups.append(cur)

    def ts(x: float, sep: str) -> str:
        h, r = divmod(x, 3600)
        m, s = divmod(r, 60)
        return f"{int(h):02d}:{int(m):02d}:{int(s):02d}{sep}{int((s % 1) * 1000):03d}"

    srt = "".join(f"{k + 1}\n{ts(g[0]['t0'], ',')} --> {ts(g[-1]['t1'], ',')}\n{' '.join(x['w'] for x in g)}\n\n" for k, g in enumerate(groups))
    path.write_text(srt, encoding="utf-8")
    vtt = "WEBVTT\n\n" + "".join(f"{ts(g[0]['t0'], '.')} --> {ts(g[-1]['t1'], '.')}\n{' '.join(x['w'] for x in g)}\n\n" for g in groups)
    path.with_suffix(".vtt").write_text(vtt, encoding="utf-8")
    return path
