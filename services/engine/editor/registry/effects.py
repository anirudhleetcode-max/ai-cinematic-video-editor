"""Parameterised effect engine. Each effect renders to an FFmpeg filter-graph fragment of the form
`[in]...[out]` built from clamped numeric parameters. ctx = {w, h, dur, fps}."""
from __future__ import annotations

from .base import Definition, Registry, e, f, i, num

EFFECTS = Registry("effect")


def _chain(chain: str):
    """Simple single-input effect: returns '[{i}]chain[{o}]'."""
    return lambda p, ctx, a, b: f"[{a}]{chain.format(**{k: num(v) if isinstance(v, float) else v for k, v in p.items()}, **ctx)}[{b}]"


def _reg(id_, name, cat, params, render, tags=(), desc="", cost=1.0):
    EFFECTS.register(Definition(id_, name, cat, tuple(params), tuple(tags), desc, cost, render))


# ---- blur ------------------------------------------------------------------------------------
_reg("gaussian_blur", "Gaussian Blur", "blur", [f("sigma", 4.0, 0.5, 30, 0.5)], _chain("gblur=sigma={sigma}"), ("soft", "dreamy"))
_reg("directional_blur", "Directional Blur", "blur", [f("angle", 0.0, 0, 180, 15), f("radius", 6.0, 1, 30, 1)],
     _chain("dblur=angle={angle}:radius={radius}"), ("motion", "speed", "energetic"))
_reg("motion_blur", "Motion Blur (temporal)", "blur", [i("frames", 3, 2, 9)], _chain("tmix=frames={frames}"), ("motion", "smooth", "energetic"), cost=1.5)
_reg("box_blur", "Lens Blur (box)", "blur", [i("radius", 4, 1, 25)], _chain("boxblur=luma_radius={radius}:luma_power=2"), ("soft",))


def _zoom_blur(p, ctx, a, b):
    s = 1 + p["strength"] * 0.08
    return (f"[{a}]format=gbrp,split=3[zb0][zb1][zb2];[zb1]scale=iw*{num(s)}:-1,crop={ctx['w']}:{ctx['h']}[zb1s];"
            f"[zb2]scale=iw*{num(s * s)}:-1,crop={ctx['w']}:{ctx['h']}[zb2s];"
            f"[zb0][zb1s]blend=all_mode=average[zb01];[zb01][zb2s]blend=all_opacity=0.33:all_mode=normal,format=yuv420p[{b}]")


_reg("zoom_blur", "Zoom / Radial Blur", "blur", [f("strength", 0.5, 0.1, 1, 0.1)], _zoom_blur, ("impact", "energetic", "radial"), cost=2.5)


# ---- glow ------------------------------------------------------------------------------------
def _glow(p, ctx, a, b):
    thr = p["threshold"]
    return (f"[{a}]format=gbrp,split[gl0][gl1];[gl1]curves=all='0/0 {num(thr)}/0 1/1',gblur=sigma={num(p['radius'])}[gl1b];"
            f"[gl0][gl1b]blend=all_mode=screen:all_opacity={num(p['intensity'])},format=yuv420p[{b}]")


_reg("soft_glow", "Soft Glow", "glow", [f("threshold", 0.6, 0.3, 0.9, 0.05), f("radius", 12.0, 3, 40, 1), f("intensity", 0.35, 0.05, 1, 0.05)], _glow,
     ("cinematic", "dreamy", "wedding", "soft"), cost=2.0)
_reg("bloom", "Highlight Bloom", "glow", [f("threshold", 0.75, 0.5, 0.95, 0.05), f("radius", 20.0, 5, 60, 1), f("intensity", 0.5, 0.1, 1, 0.05)], _glow,
     ("cinematic", "concert", "night"), cost=2.0)


def _neon(p, ctx, a, b):
    return (f"[{a}]format=gbrp,split[n0][n1];[n1]eq=saturation={num(1 + p['saturation'])},curves=all='0/0 0.55/0 1/1',gblur=sigma={num(p['radius'])}[n1b];"
            f"[n0][n1b]blend=all_mode=addition:all_opacity={num(p['intensity'])},format=yuv420p[{b}]")


_reg("neon_glow", "Neon Glow", "glow", [f("saturation", 1.0, 0, 2, 0.25), f("radius", 10.0, 3, 30, 1), f("intensity", 0.5, 0.1, 1, 0.1)], _neon,
     ("neon", "night", "music", "hype"), cost=2.0)


def _halation(p, ctx, a, b):
    return (f"[{a}]format=gbrp,split[h0][h1];[h1]curves=all='0/0 0.7/0 1/1',colorchannelmixer=rr=1:gg=0.25:bb=0.1,gblur=sigma={num(p['radius'])}[h1b];"
            f"[h0][h1b]blend=all_mode=screen:all_opacity={num(p['intensity'])},format=yuv420p[{b}]")


_reg("halation", "Halation", "glow", [f("radius", 8.0, 2, 30, 1), f("intensity", 0.3, 0.05, 0.8, 0.05)], _halation, ("film", "vintage", "cinematic"), cost=2.0)


# ---- distortion ------------------------------------------------------------------------------
_reg("lens_distortion", "Lens Distortion", "distortion", [f("k1", -0.12, -0.5, 0.5, 0.02), f("k2", 0.02, -0.3, 0.3, 0.02)],
     _chain("lenscorrection=k1={k1}:k2={k2}"), ("lens", "subtle"))
_reg("barrel", "Barrel Distortion", "distortion", [f("amount", 0.2, 0.02, 0.6, 0.02)], lambda p, c, a, b: f"[{a}]lenscorrection=k1={num(p['amount'])}:k2={num(p['amount'] / 4)}[{b}]",
     ("lens", "fisheye"))
_reg("fisheye", "Fisheye", "distortion", [f("amount", 0.5, 0.2, 1.0, 0.05)],
     lambda p, c, a, b: f"[{a}]lenscorrection=k1={num(-p['amount'] * 0.6)}:k2={num(-p['amount'] * 0.15)},scale={c['w']}*{num(1 + p['amount'] * 0.3)}:-2,crop={c['w']}:{c['h']}[{b}]",
     ("lens", "skate", "extreme"))
_reg("chromatic_aberration", "Chromatic Aberration", "distortion", [i("shift", 4, 1, 20)],
     lambda p, c, a, b: f"[{a}]rgbashift=rh={p['shift']}:bh=-{p['shift']}:edge=smear[{b}]", ("rgb", "glitch", "music", "lens"))


def _wave(p, ctx, a, b):
    amp, freq, spd = num(p["amplitude"]), num(p["frequency"]), num(p["speed"])
    return (f"[{a}]format=yuv444p,geq=lum='lum(X+{amp}*sin(2*PI*Y/{freq}+T*{spd}),Y)':"
            f"cb='cb(X+{amp}*sin(2*PI*Y/{freq}+T*{spd}),Y)':cr='cr(X+{amp}*sin(2*PI*Y/{freq}+T*{spd}),Y)',format=yuv420p[{b}]")


_reg("wave", "Wave / Ripple", "distortion", [f("amplitude", 6.0, 1, 30, 1), f("frequency", 80.0, 20, 300, 10), f("speed", 4.0, 0, 12, 1)], _wave,
     ("water", "dream", "ripple"), cost=6.0)


# ---- light -----------------------------------------------------------------------------------
def _light_leak(p, ctx, a, b):
    col = {"warm": "0xff9a3c", "gold": "0xffd27a", "red": "0xff4a3c", "magenta": "0xff4fd0", "cool": "0x6fb7ff"}[p["color"]]
    return (f"gradients=s={ctx['w']}x{ctx['h']}:r={ctx['fps']}:c0={col}:c1=black:x0=0:y0=0:x1={ctx['w']}:y1={ctx['h']}:"
            f"speed={num(p['speed'])}:d={num(ctx['dur'] + 1)},format=gbrp[lk_{b}];"
            f"[{a}]format=gbrp[lb_{b}];[lb_{b}][lk_{b}]blend=all_mode=screen:all_opacity={num(p['intensity'])}:shortest=1,format=yuv420p[{b}]")


_reg("light_leak", "Light Leak", "light", [e("color", "warm", "warm", "gold", "red", "magenta", "cool"), f("intensity", 0.3, 0.05, 0.8, 0.05), f("speed", 0.02, 0.005, 0.1, 0.005)],
     _light_leak, ("film", "wedding", "warm", "dreamy", "travel"), cost=2.0)
_reg("flash", "Flash", "light", [f("at", 0.0, 0, 1, 0.1), f("length", 0.15, 0.04, 0.6, 0.02), f("strength", 0.6, 0.1, 1, 0.1)],
     lambda p, c, a, b: f"[{a}]eq=brightness='{num(p['strength'])}*max(0,1-abs(t-{num(p['at'] * c['dur'])})/{num(p['length'])})':eval=frame[{b}]",
     ("impact", "beat", "hype", "music"))
_reg("exposure_pulse", "Exposure Pulse", "light", [f("rate", 2.0, 0.25, 8, 0.25), f("strength", 0.08, 0.02, 0.3, 0.02)],
     lambda p, c, a, b: f"[{a}]eq=brightness='{num(p['strength'])}*pow(max(0,sin(PI*t*{num(p['rate'])})),8)':eval=frame[{b}]", ("beat", "music", "hype"))
_reg("glow_pulse", "Glow Pulse", "light", [f("rate", 1.0, 0.25, 4, 0.25), f("strength", 0.2, 0.05, 0.6, 0.05)],
     lambda p, c, a, b: f"[{a}]eq=contrast='1+{num(p['strength'])}*0.5*(1+sin(2*PI*t*{num(p['rate'])}))':saturation='1+{num(p['strength'])}*0.5*(1+sin(2*PI*t*{num(p['rate'])}))':eval=frame[{b}]",
     ("beat", "music"))


def _flare(p, ctx, a, b):
    return (f"gradients=s={ctx['w']}x{ctx['h']}:r={ctx['fps']}:type=radial:c0=0xfff2d0:c1=black:"
            f"x0={int(ctx['w'] * p['x'])}:y0={int(ctx['h'] * p['y'])}:x1={int(ctx['w'] * p['x'] + ctx['w'] * p['size'])}:y1={int(ctx['h'] * p['y'])}:d={num(ctx['dur'] + 1)},format=gbrp[fl_{b}];"
            f"[{a}]format=gbrp[fb_{b}];[fb_{b}][fl_{b}]blend=all_mode=screen:all_opacity={num(p['intensity'])}:shortest=1,format=yuv420p[{b}]")


_reg("flare", "Lens Flare (soft)", "light", [f("x", 0.8, 0, 1, 0.1), f("y", 0.2, 0, 1, 0.1), f("size", 0.35, 0.1, 0.8, 0.05), f("intensity", 0.35, 0.1, 0.8, 0.05)],
     _flare, ("sun", "golden", "travel", "cinematic"), cost=2.0)

# ---- stylisation -----------------------------------------------------------------------------
_reg("film_grain", "Film Grain", "stylize", [i("strength", 8, 2, 30), e("motion", "temporal", "temporal", "static")],
     lambda p, c, a, b: f"[{a}]noise=alls={p['strength']}:allf={'t+u' if p['motion'] == 'temporal' else 'u'}[{b}]", ("film", "vintage", "cinematic", "texture"))
_reg("vignette", "Vignette", "stylize", [f("angle", 0.45, 0.1, 1.2, 0.05)], _chain("vignette=angle={angle}"), ("cinematic", "moody", "focus"))
_reg("scanlines", "Scanlines", "stylize", [i("spacing", 4, 2, 12), f("opacity", 0.25, 0.05, 0.8, 0.05)],
     lambda p, c, a, b: f"[{a}]drawgrid=w=iw:h={p['spacing']}:t=1:c=black@{num(p['opacity'])}[{b}]", ("retro", "vhs", "digital"))


def _vhs(p, ctx, a, b):
    s = p["strength"]
    return (f"[{a}]rgbashift=rh={int(2 + 6 * s)}:bh=-{int(2 + 6 * s)},eq=saturation={num(1.25 + 0.3 * s)}:contrast={num(1.05)},"
            f"noise=alls={int(6 + 18 * s)}:allf=t,gblur=sigma={num(0.6 + s)},drawgrid=w=iw:h=3:t=1:c=black@{num(0.12 + 0.2 * s)}[{b}]")


_reg("vhs", "VHS", "stylize", [f("strength", 0.5, 0.1, 1, 0.1)], _vhs, ("retro", "vintage", "vhs", "nostalgic"), cost=2.0)


def _glitch(p, ctx, a, b):
    s = p["strength"]
    # periodic blocky displacement + RGB split; `rate` glitches per second
    return (f"[{a}]rgbashift=rh={int(3 + 12 * s)}:gv={int(2 + 6 * s)}:bh=-{int(3 + 12 * s)}:edge=wrap,"
            f"noise=alls={int(10 * s)}:allf=t,"
            f"eq=contrast='1+{num(0.3 * s)}*gt(sin(2*PI*t*{num(p['rate'])}),0.85)':eval=frame[{b}]")


_reg("glitch", "Glitch", "stylize", [f("strength", 0.5, 0.1, 1, 0.1), f("rate", 2.0, 0.5, 8, 0.5)], _glitch, ("glitch", "digital", "hype", "tech"), cost=1.5)
_reg("pixelate", "Digital Distortion (pixelate)", "stylize", [i("block", 12, 4, 64, 4)],
     lambda p, c, a, b: f"[{a}]pixelize=w={p['block']}:h={p['block']}[{b}]", ("digital", "censor", "glitch"))
_reg("sharpen", "Sharpen", "stylize", [f("amount", 0.8, 0.1, 2.5, 0.1)], _chain("unsharp=5:5:{amount}:5:5:0"), ("detail", "crisp"))
_reg("letterbox", "Cinematic Letterbox", "stylize", [e("ratio", "2.39", "2.39", "2.0", "1.85")],
     lambda p, c, a, b: (lambda bar: f"[{a}]drawbox=x=0:y=0:w=iw:h={bar}:c=black:t=fill,drawbox=x=0:y=ih-{bar}:w=iw:h={bar}:c=black:t=fill[{b}]")(
         max(0, int((c["h"] - c["w"] / float(p["ratio"])) / 2))), ("cinematic", "film", "widescreen"))
_reg("black_white", "Black & White", "stylize", [f("contrast", 1.15, 0.8, 1.6, 0.05)], _chain("hue=s=0,eq=contrast={contrast}"), ("bw", "monochrome", "documentary"))
_reg("mirror", "Mirror", "stylize", [e("axis", "horizontal", "horizontal", "vertical")],
     lambda p, c, a, b: (f"[{a}]split[m0][m1];[m1]{'hflip' if p['axis'] == 'horizontal' else 'vflip'},crop={'iw/2:ih:0:0' if p['axis'] == 'horizontal' else 'iw:ih/2:0:0'}[m1c];"
                         f"[m0][m1c]overlay={'W/2:0' if p['axis'] == 'horizontal' else '0:H/2'}[{b}]"), ("kaleidoscope", "music", "trippy"))


def render_effect(effect_id: str, params: dict, ctx: dict, a: str, b: str) -> str:
    d = EFFECTS.get(effect_id)
    return d.render(d.resolve(params), ctx, a, b)
