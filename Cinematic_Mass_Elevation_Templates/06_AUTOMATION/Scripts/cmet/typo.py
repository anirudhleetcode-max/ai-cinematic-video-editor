"""Typography for the reference renderer: text sprites, procedural materials
(bevel normals + lighting + environment reflection), and a small 3D plane
projection system used for whole-title, per-letter and fragment animation.
"""
from __future__ import annotations

import math
import os
import unicodedata
from dataclasses import dataclass, field

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont, features

from .core import F32, col, fft_noise, sample, blur

HERE = os.path.dirname(os.path.abspath(__file__))
FONT_DIR = os.path.normpath(os.path.join(HERE, "..", "..", "..", "02_SHARED_ASSETS", "Fonts"))

# Logical font keys -> (relative file, PIL variation name or None, Fusion family, Fusion style)
FONTS = {
    "anton": ("anton/Anton-Regular.ttf", None, "Anton", "Regular"),
    "bebas": ("bebasneue/BebasNeue-Regular.ttf", None, "Bebas Neue", "Regular"),
    "blackops": ("blackopsone/BlackOpsOne-Regular.ttf", None, "Black Ops One", "Regular"),
    "russo": ("russoone/RussoOne-Regular.ttf", None, "Russo One", "Regular"),
    "cinzel_deco": ("cinzeldecorative/CinzelDecorative-Black.ttf", None, "Cinzel Decorative", "Black"),
    "cinzel": ("cinzel/Cinzel[wght].ttf", b"Black", "Cinzel", "Black"),
    "cinzel_bold": ("cinzel/Cinzel[wght].ttf", b"Bold", "Cinzel", "Bold"),
    "audiowide": ("audiowide/Audiowide-Regular.ttf", None, "Audiowide", "Regular"),
    "staatliches": ("staatliches/Staatliches-Regular.ttf", None, "Staatliches", "Regular"),
    "marcellus": ("marcellussc/MarcellusSC-Regular.ttf", None, "Marcellus SC", "Regular"),
    "orbitron": ("orbitron/Orbitron[wght].ttf", b"Black", "Orbitron", "Black"),
    "orbitron_med": ("orbitron/Orbitron[wght].ttf", b"Medium", "Orbitron", "Medium"),
    "teko": ("teko/Teko[wght].ttf", b"SemiBold", "Teko", "SemiBold"),
    "teko_light": ("teko/Teko[wght].ttf", b"Light", "Teko", "Light"),
    "telugu": ("ramabhadra/Ramabhadra-Regular.ttf", None, "Ramabhadra", "Regular"),
    "telugu_sans": ("notosanstelugu/NotoSansTelugu[wdth,wght].ttf", b"Bold", "Noto Sans Telugu", "Bold"),
    "inter_black": (None, None, "Inter", "Black"),
}

_font_cache: dict = {}


def needs_shaping(text: str) -> bool:
    """True for scripts that need complex shaping (Indic etc.)."""
    for ch in text:
        o = ord(ch)
        if 0x0900 <= o <= 0x0DFF or 0x1000 <= o <= 0x109F:
            return True
    return False


def load_font(key: str, px: int, text: str = "") -> ImageFont.FreeTypeFont:
    if needs_shaping(text) and key not in ("telugu", "telugu_sans"):
        key = "telugu"
    rel, var, _, _ = FONTS.get(key, FONTS["anton"])
    ck = (key, px)
    if ck in _font_cache:
        return _font_cache[ck]
    if rel is None:
        path = "/usr/share/fonts/truetype/inter/Inter-Black.ttf"
        if not os.path.exists(path):
            rel = FONTS["anton"][0]
            path = os.path.join(FONT_DIR, rel)
    else:
        path = os.path.join(FONT_DIR, rel)
    layout = ImageFont.Layout.RAQM if features.check("raqm") else ImageFont.Layout.BASIC
    f = ImageFont.truetype(path, px, layout_engine=layout)
    if var:
        try:
            f.set_variation_by_name(var)
        except Exception:
            pass
    _font_cache[ck] = f
    return f


@dataclass
class Glyph:
    text: str
    box: tuple  # x0, y0, x1, y1 in sprite pixels (ink box, padded)
    center: tuple  # rest centre in sprite pixels
    index: int


class TextSprite:
    """Rasterised title mask with per-glyph boxes.

    cap_px: desired cap height in pixels. tracking: extra spacing in em.
    """

    def __init__(self, text: str, font_key: str, cap_px: float, tracking: float = 0.05,
                 line_spacing: float = 1.0, align: str = "center", pad: float = 0.5, upper: bool = False):
        text = text.upper() if upper and not needs_shaping(text) else text
        self.text = text
        probe = load_font(font_key, 200, text)
        bb = probe.getbbox("H")
        cap200 = max(1, bb[3] - bb[1])
        size = max(8, int(round(200 * cap_px / cap200)))
        font = load_font(font_key, size, text)
        self.font = font
        self.size = size
        shaped = needs_shaping(text)
        lines = text.split("\n")
        asc, desc = font.getmetrics()
        line_h = (asc + desc) * line_spacing
        trk = tracking * size
        # layout: list of (glyph_text, x, y_baseline)
        items = []
        widths = []
        for li, line in enumerate(lines):
            x = 0.0
            row = []
            units = line.split(" ") if shaped else list(line)
            for ui, u in enumerate(units):
                if shaped:
                    if ui > 0:
                        x += font.getlength(" ") + trk
                    row.append((u, x))
                    x += font.getlength(u)
                else:
                    row.append((u, x))
                    x += font.getlength(u) + trk
            if row and not shaped:
                x -= trk
            widths.append(x)
            items.append(row)
        maxw = max(widths) if widths else 1
        padpx = int(pad * cap_px) + 8
        W = int(maxw + 2 * padpx)
        H = int(line_h * len(lines) + 2 * padpx)
        img = Image.new("L", (W, H), 0)
        dr = ImageDraw.Draw(img)
        self.glyphs: list[Glyph] = []
        gi = 0
        for li, row in enumerate(items):
            off = {"left": 0, "right": maxw - widths[li]}.get(align, (maxw - widths[li]) / 2)
            ybase = padpx + li * line_h
            for (u, x) in row:
                if u.strip() == "":
                    continue
                px_ = padpx + off + x
                dr.text((px_, ybase), u, font=font, fill=255)
                gb = font.getbbox(u)
                x0, y0, x1, y1 = px_ + gb[0], ybase + gb[1], px_ + gb[2], ybase + gb[3]
                self.glyphs.append(Glyph(u, (x0, y0, x1, y1), ((x0 + x1) / 2, (y0 + y1) / 2), gi))
                gi += 1
        m = np.asarray(img, dtype=F32) / 255.0
        ys, xs = np.nonzero(m > 0.02)
        if len(xs) == 0:
            xs, ys = np.array([W // 2]), np.array([H // 2])
        self.ink = (xs.min(), ys.min(), xs.max(), ys.max())
        self.mask = m
        self.h, self.w = m.shape
        self.anchor = ((self.ink[0] + self.ink[2]) / 2, (self.ink[1] + self.ink[3]) / 2)
        self.ink_w = self.ink[2] - self.ink[0]
        self.ink_h = self.ink[3] - self.ink[1]
        self.cap_px = cap_px
        self._dist = None

    @property
    def dist(self):
        if self._dist is None:
            # 4x supersampled distance field avoids stair-stepping on diagonals
            hh, ww = self.mask.shape
            up = cv2.resize(self.mask, (ww * 4, hh * 4), interpolation=cv2.INTER_CUBIC)
            b = (up > 0.5).astype(np.uint8)
            d = cv2.distanceTransform(b, cv2.DIST_L2, cv2.DIST_MASK_PRECISE).astype(F32) / 4.0
            self._dist = cv2.resize(d, (ww, hh), interpolation=cv2.INTER_AREA)
        return self._dist


def fit_cap(text_lines_chars: int, frame_w: int, frame_h: int, font_key: str, text: str,
            target_w=0.62, max_cap=0.2, tracking=0.05):
    """Choose a cap height so the title spans ~target_w of the frame width."""
    probe = TextSprite(text, font_key, 100, tracking=tracking, pad=0.1)
    cap = 100 * (frame_w * target_w) / max(1, probe.ink_w)
    return float(min(cap, frame_h * max_cap))


# --------------------------------------------------------------------------
# Materials
# --------------------------------------------------------------------------
@dataclass
class Material:
    base: tuple = (0.05, 0.05, 0.06)
    spec: tuple = (1.0, 1.0, 1.0)
    spec_power: float = 40.0
    spec_gain: float = 1.0
    diffuse: float = 0.8
    ambient: float = 0.12
    metal: float = 0.0  # environment reflection weight
    env_sky: tuple = (0.9, 0.9, 0.95)
    env_horizon: tuple = (0.1, 0.1, 0.12)
    env_ground: tuple = (0.25, 0.2, 0.15)
    env_sharp: float = 18.0
    bevel: float = 0.07  # in cap-heights
    bevel_round: bool = True
    bevel_strength: float = 1.0
    texture: str = "none"  # none|stone|brushed|grain|obsidian|ice|concrete|facets
    tex_amount: float = 0.3
    bump: float = 0.0
    rim: tuple = (1.0, 0.8, 0.6)
    rim_gain: float = 0.0
    seed: int = 3


def _normals(sprite: TextSprite, m: Material):
    bev = max(1.0, m.bevel * sprite.cap_px)
    d = sprite.dist
    h = np.clip(d / bev, 0, 1)
    if m.bevel_round:
        h = np.sin(h * math.pi / 2)
    h = cv2.GaussianBlur(h, (0, 0), 1.3)
    tex = None
    if m.texture != "none" or m.bump > 0:
        tex = material_texture(sprite, m)
        if m.bump > 0:
            h = h + tex * m.bump * (m.bevel * sprite.cap_px) * 0.08
    h = h.astype(F32)
    gx = cv2.Sobel(h, cv2.CV_32F, 1, 0, ksize=3) / 8.0
    gy = cv2.Sobel(h, cv2.CV_32F, 0, 1, ksize=3) / 8.0
    k = bev * m.bevel_strength
    nx, ny, nz = -gx * k, -gy * k, np.ones_like(gx)
    inv = 1.0 / np.sqrt(nx * nx + ny * ny + 1)
    return nx * inv, ny * inv, nz * inv, h, tex


def material_texture(sprite: TextSprite, m: Material):
    hh, ww = sprite.mask.shape
    s = hh / max(1.0, sprite.cap_px)
    if m.texture == "stone":
        a = sample(fft_noise(256, 1.7, m.seed), hh, ww, 3.0 * s * 0.6)
        b = sample(fft_noise(256, 1.2, m.seed + 1), hh, ww, 9.0 * s * 0.6)
        r = sample(fft_noise(256, 2.0, m.seed + 2, True), hh, ww, 2.0 * s * 0.6)
        return np.clip(a * 0.6 + b * 0.4 - (r > 0.92) * 0.5, 0, 1)
    if m.texture == "concrete":
        a = sample(fft_noise(256, 1.4, m.seed), hh, ww, 6.0 * s * 0.6)
        b = sample(fft_noise(256, 0.6, m.seed + 4), hh, ww, 30 * s * 0.6)
        return np.clip(a * 0.5 + b * 0.5, 0, 1)
    if m.texture == "brushed":
        return sample(fft_noise(256, 1.0, m.seed), hh, ww, 4.0 * s * 0.6, stretch=(40.0, 1.0))
    if m.texture == "obsidian":
        return sample(fft_noise(256, 2.6, m.seed), hh, ww, 2.0 * s * 0.6)
    if m.texture == "ice":
        a = sample(fft_noise(256, 2.0, m.seed, True), hh, ww, 3.0 * s * 0.6)
        return np.clip(a ** 3, 0, 1)
    if m.texture == "facets":
        # piecewise-flat facets from a coarse Voronoi label map
        rng = np.random.default_rng(m.seed)
        n = 220
        seeds = np.zeros((hh, ww), np.uint8) + 1
        pts = np.stack([rng.integers(0, ww, n), rng.integers(0, hh, n)], 1)
        for x, y in pts:
            seeds[y, x] = 0
        _, lab = cv2.distanceTransformWithLabels(seeds, cv2.DIST_L2, 5, labelType=cv2.DIST_LABEL_PIXEL)
        vals = rng.random(n + 2).astype(F32)
        return vals[np.clip(lab, 0, n + 1)]
    return sample(fft_noise(256, 0.8, m.seed), hh, ww, 20 * s * 0.6)


class ShadedText:
    """Caches normals for a sprite+material; shade() relights per frame."""

    def __init__(self, sprite: TextSprite, mat: Material):
        self.sprite = sprite
        self.mat = mat
        self.nx, self.ny, self.nz, self.h, self.tex = _normals(sprite, mat)
        hh, ww = sprite.mask.shape
        ys, xs = np.mgrid[0:hh, 0:ww].astype(F32)
        self.u = (xs - sprite.anchor[0]) / max(1.0, sprite.ink_w)  # ~ -0.5..0.5 over the word
        self.v = (ys - sprite.anchor[1]) / max(1.0, sprite.ink_h)
        self.edge = np.clip(1 - sprite.dist / max(1.0, 0.06 * sprite.cap_px), 0, 1) * sprite.mask

    def shade(self, light=(-0.4, -0.7, 0.6), env_shift=0.0, sweep=None, rim_dir=(0.0, -1.0),
              rim_gain=None, base=None, emissive=None, light_gain=1.0):
        m = self.mat
        L = np.array(light, F32)
        L /= np.linalg.norm(L)
        nx, ny, nz = self.nx, self.ny, self.nz
        ndl = np.clip(nx * L[0] + ny * L[1] + nz * L[2], 0, 1)
        Hv = L + np.array([0, 0, 1], F32)
        Hv /= np.linalg.norm(Hv)
        ndh = np.clip(nx * Hv[0] + ny * Hv[1] + nz * Hv[2], 0, 1)
        spec = ndh ** m.spec_power * m.spec_gain
        basec = col(base if base is not None else m.base)
        alb = basec[None, None, :]
        if self.tex is not None and m.tex_amount > 0:
            alb = alb * (1 - m.tex_amount + m.tex_amount * 2 * self.tex[..., None])
        rgb = alb * (m.ambient + m.diffuse * ndl[..., None]) * light_gain
        if m.metal > 0:
            # reflection vector of view (0,0,1)
            ry = 2 * nz * ny  # screen-space vertical component (down positive)
            rx = 2 * nz * nx
            yy = ry + self.v * 0.9 + env_shift
            sky = col(m.env_sky)
            hor = col(m.env_horizon)
            gnd = col(m.env_ground)
            s_up = 1 / (1 + np.exp(m.env_sharp * (yy - 0.0)))  # 1 when looking up
            env = sky[None, None, :] * s_up[..., None] + gnd[None, None, :] * (1 - s_up[..., None])
            band = np.exp(-((yy) * m.env_sharp * 0.6) ** 2)
            env = env * (1 - band[..., None] * 0.85) + hor[None, None, :] * band[..., None] * 0.85
            env = env * (0.85 + 0.3 * np.clip(rx * 0.5 + 0.5, 0, 1))[..., None]
            tintc = basec / max(1e-3, basec.max())
            rgb = rgb * (1 - m.metal) + env * tintc[None, None, :] * m.metal * light_gain
        rgb = rgb + spec[..., None] * col(m.spec)[None, None, :] * light_gain
        rg = m.rim_gain if rim_gain is None else rim_gain
        if rg > 0:
            facing = np.clip(nx * rim_dir[0] + ny * rim_dir[1], 0, 1)
            rim = (facing ** 0.7) * (1 - nz) * 2.2 + self.edge * 0.25 * facing
            rgb = rgb + rim[..., None] * col(m.rim)[None, None, :] * rg
        if sweep is not None:
            pos, width, ang, gain = sweep
            ca, sa = math.cos(ang), math.sin(ang)
            d = self.u * ca + self.v * sa * 0.35 - pos
            band = np.exp(-(d / width) ** 2) * gain
            fres = 0.35 + 0.65 * (1 - nz) + 0.4 * spec
            rgb = rgb + (band * fres)[..., None] * col(m.spec)[None, None, :]
        if emissive is not None:
            rgb = rgb + emissive
        return rgb.astype(F32), self.sprite.mask


# --------------------------------------------------------------------------
# 3D plane projection
# --------------------------------------------------------------------------
def rot_matrix(rx, ry, rz):
    rx, ry, rz = map(math.radians, (rx, ry, rz))
    cx, sx, cy, sy, cz, sz = math.cos(rx), math.sin(rx), math.cos(ry), math.sin(ry), math.cos(rz), math.sin(rz)
    Rx = np.array([[1, 0, 0], [0, cx, -sx], [0, sx, cx]])
    Ry = np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]])
    Rz = np.array([[cz, -sz, 0], [sz, cz, 0], [0, 0, 1]])
    return Rz @ Ry @ Rx


@dataclass
class Cam:
    """Simple pinhole camera. Plane z=0 at distance `dist` maps 1:1 at zoom 1."""
    W: int
    H: int
    fov_scale: float = 1.6  # focal length in frame widths
    zoom: float = 1.0       # dolly: >1 moves closer
    pan: tuple = (0.0, 0.0)  # pixels
    roll: float = 0.0
    tilt: float = 0.0        # degrees, rotates the world about X (low angle > 0)
    yaw: float = 0.0

    @property
    def f(self):
        return self.fov_scale * self.W

    def project(self, P):
        """P: (N,3) world points in pixels around frame centre (y down)."""
        D = self.f
        R = rot_matrix(self.tilt, self.yaw, self.roll)
        Q = P @ R.T
        Z = D / self.zoom + Q[:, 2]
        Z = np.maximum(Z, D * 0.02)
        x = self.W / 2 + self.f * Q[:, 0] / Z + self.pan[0]
        y = self.H / 2 + self.f * Q[:, 1] / Z + self.pan[1]
        return np.stack([x, y], 1), Z


def plane_points(box, anchor, pos, scale, rot, local=None, z=0.0):
    """3D world coords of the 4 corners of `box` (sprite px) for a sprite placed
    at world `pos` (x,y,z px), uniform `scale`, rotation (rx,ry,rz) about anchor.
    `local` = optional per-piece (dx,dy,dz,rx,ry,rz,s,cx,cy) about piece centre."""
    x0, y0, x1, y1 = box
    pts = np.array([[x0, y0], [x1, y0], [x1, y1], [x0, y1]], np.float64)
    P = np.zeros((4, 3))
    P[:, 0] = pts[:, 0]
    P[:, 1] = pts[:, 1]
    P[:, 2] = z
    if local is not None:
        dx, dy, dz, lrx, lry, lrz, ls, pcx, pcy = local
        c = np.array([pcx, pcy, 0])
        P = (P - c) * ls
        P = P @ rot_matrix(lrx, lry, lrz).T + c + np.array([dx, dy, dz])
    P[:, 0] -= anchor[0]
    P[:, 1] -= anchor[1]
    P = P * scale
    P = P @ rot_matrix(*rot).T
    return P + np.array(pos, np.float64)


def warp_to(canvas_rgb, canvas_a, src_rgb, src_a, src_box, dst_pts, opacity=1.0, add=False):
    """Warp src crop (box in src coords) so its corners land on dst_pts; composite."""
    H, W = canvas_a.shape
    x0, y0, x1, y1 = [int(round(v)) for v in src_box]
    x0, y0 = max(0, x0), max(0, y0)
    x1, y1 = min(src_a.shape[1], x1), min(src_a.shape[0], y1)
    if x1 - x0 < 2 or y1 - y0 < 2 or opacity <= 0.002:
        return
    bx0, by0 = np.floor(dst_pts.min(0)).astype(int)
    bx1, by1 = np.ceil(dst_pts.max(0)).astype(int)
    bx0, by0 = max(bx0, 0), max(by0, 0)
    bx1, by1 = min(bx1 + 1, W), min(by1 + 1, H)
    if bx1 - bx0 < 1 or by1 - by0 < 1:
        return
    src = np.float32([[0, 0], [x1 - x0, 0], [x1 - x0, y1 - y0], [0, y1 - y0]])
    dst = (dst_pts - np.array([bx0, by0])).astype(np.float32)
    M = cv2.getPerspectiveTransform(src, dst)
    size = (bx1 - bx0, by1 - by0)
    a = cv2.warpPerspective(np.ascontiguousarray(src_a[y0:y1, x0:x1]), M, size, flags=cv2.INTER_LINEAR,
                            borderMode=cv2.BORDER_CONSTANT) * opacity
    rgb = cv2.warpPerspective(np.ascontiguousarray(src_rgb[y0:y1, x0:x1]), M, size, flags=cv2.INTER_LINEAR,
                              borderMode=cv2.BORDER_CONSTANT)
    sl = (slice(by0, by1), slice(bx0, bx1))
    if add:
        canvas_rgb[sl] += rgb * a[..., None]
    else:
        canvas_rgb[sl] = canvas_rgb[sl] * (1 - a[..., None]) + rgb * a[..., None]
        canvas_a[sl] = canvas_a[sl] + a * (1 - canvas_a[sl])


class Layer:
    """Premultiplied-free RGBA accumulation layer (rgb straight-composited)."""

    def __init__(self, H, W):
        self.rgb = np.zeros((H, W, 3), F32)
        self.a = np.zeros((H, W), F32)

    def premul(self):
        return self.rgb  # rgb already premultiplied by construction of warp_to


def place_sprite(layer: Layer, cam: Cam, rgb, alpha, box, anchor, pos, scale, rot, local=None,
                 opacity=1.0, z=0.0, add=False):
    P = plane_points(box, anchor, pos, scale, rot, local, z)
    pts, Z = cam.project(P)
    if (Z <= cam.f * 0.03).any():
        return
    warp_to(layer.rgb, layer.a, rgb, alpha, box, pts, opacity, add)


def place_extruded(layer: Layer, cam: Cam, face_rgb, alpha, box, anchor, pos, scale, rot, depth_px,
                   side_col, slices=18, side_light=None, opacity=1.0):
    """Genuine-geometry approximation of an extruded solid by stacking
    perspective-projected slices back-to-front (used for 3D previews)."""
    side = col(side_col)
    if side_light is None:
        side_light = lambda k: 0.35 + 0.65 * k
    for i in range(slices):
        k = i / max(1, slices - 1)
        zoff = depth_px * (1 - k)
        c = side * side_light(k)
        srgb = np.empty_like(face_rgb)
        srgb[...] = c
        place_sprite(layer, cam, srgb, alpha, box, anchor, pos, scale, rot, None, opacity, z=zoff)
    place_sprite(layer, cam, face_rgb, alpha, box, anchor, pos, scale, rot, None, opacity, z=0.0)


def fragments(sprite: TextSprite, n=40, seed=5):
    """Voronoi-fracture the sprite mask. Returns list of (box, centre, mask)."""
    rng = np.random.default_rng(seed)
    hh, ww = sprite.mask.shape
    ys, xs = np.nonzero(sprite.mask > 0.3)
    idx = rng.choice(len(xs), size=min(n, len(xs)), replace=False)
    seeds = np.ones((hh, ww), np.uint8)
    for i in idx:
        seeds[ys[i], xs[i]] = 0
    _, lab = cv2.distanceTransformWithLabels(seeds, cv2.DIST_L2, 5, labelType=cv2.DIST_LABEL_CCOMP)
    out = []
    for L in np.unique(lab[sprite.mask > 0.02]):
        mk = (lab == L)
        yy, xx = np.nonzero(mk & (sprite.mask > 0.02))
        if len(xx) < 12:
            continue
        x0, y0, x1, y1 = xx.min() - 2, yy.min() - 2, xx.max() + 3, yy.max() + 3
        fm = (mk.astype(F32) * sprite.mask)
        out.append(((x0, y0, x1, y1), ((x0 + x1) / 2, (y0 + y1) / 2), fm))
    return out
