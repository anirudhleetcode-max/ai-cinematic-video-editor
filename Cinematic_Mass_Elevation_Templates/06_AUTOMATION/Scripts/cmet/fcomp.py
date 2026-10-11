"""Reusable Fusion node-graph components shared by the 40 templates.

Coordinates follow Fusion conventions: points are normalised (0..1, origin
bottom-left, y up). All timing is in frames and refers to CONTROLS.* user
controls via Simple Expressions so the published timing sliders work.
"""
from __future__ import annotations

from .fusion import (FuID, Grad, Graph, Tool, C, ctl, clamp01, prog, e_out, e_in, e_inout, decay, step, window,
                     shake, Raw, Call, Ordered)
from collections import OrderedDict

A = "ACCENT"  # accent colour holder tool name


def rgb3(c):
    if isinstance(c, str):
        c = c.lstrip("#")
        return tuple(int(c[i:i + 2], 16) / 255 for i in (0, 2, 4))
    return tuple(c)


# ---------------------------------------------------------------- basics --
def frame_inputs(t: Tool, g: Graph):
    t.set(Width=g.W, Height=g.H, UseFrameFormatSettings=1)
    return t


def solid(g: Graph, name, c, alpha=1.0):
    r, gg, b = rgb3(c)
    t = g.add("Background", name)
    frame_inputs(t, g)
    t.set(TopLeftRed=r, TopLeftGreen=gg, TopLeftBlue=b, TopLeftAlpha=alpha)
    return t


def accent_holder(g: Graph, c, label="Accent Color"):
    """A tiny solid whose colour other nodes read through expressions."""
    t = solid(g, A, c)
    t.pos = (110, -66)
    g.publish(t, "TopLeftRed", label, page="Look", group=90, cid="AccentRed")
    g.publish(t, "TopLeftGreen", label, page="Look", group=90, cid="AccentGreen")
    g.publish(t, "TopLeftBlue", label, page="Look", group=90, cid="AccentBlue")
    return t


def accent_solid(g: Graph, name, gain=1.0, alpha=1.0):
    """Solid that follows the ACCENT colour (times gain)."""
    t = g.add("Background", name)
    frame_inputs(t, g)
    t.expr("TopLeftRed", f"{A}.TopLeftRed*{gain}", 1)
    t.expr("TopLeftGreen", f"{A}.TopLeftGreen*{gain}", 1)
    t.expr("TopLeftBlue", f"{A}.TopLeftBlue*{gain}", 1)
    t.set(TopLeftAlpha=alpha)
    return t


def gradient_bg(g: Graph, name, stops, gtype="Linear", start=(0.5, 1.0), end=(0.5, 0.0)):
    t = g.add("Background", name)
    frame_inputs(t, g)
    t.set(Type=FuID("Gradient"), GradientType=FuID(gtype), Start=list(start), End=list(end),
          Gradient=Grad([(p, (*rgb3(c), a)) for p, c, a in stops]))
    return t


def ellipse(g: Graph, name, center=(0.5, 0.5), w=0.5, h=0.5, soft=0.2, invert=False, border=None, angle=0.0):
    t = g.add("EllipseMask", name)
    t.set(SoftEdge=soft, Center=list(center), Width=w, Height=h, Angle=angle,
          MaskWidth=g.W, MaskHeight=g.H, UseFrameFormatSettings=1)
    if invert:
        t.set(Invert=1)
    if border is not None:
        t.set(BorderWidth=border)
    return t


def rect(g: Graph, name, center=(0.5, 0.5), w=0.5, h=0.5, soft=0.0, invert=False, angle=0.0):
    t = g.add("RectangleMask", name)
    t.set(SoftEdge=soft, Center=list(center), Width=w, Height=h, Angle=angle, MaskWidth=g.W, MaskHeight=g.H,
          UseFrameFormatSettings=1)
    if invert:
        t.set(Invert=1)
    return t


def bitmap_mask(g: Graph, name, image: Tool, channel="Alpha", paint=None, prev=None):
    t = g.add("BitmapMask", name)
    t.conn("Image", image)
    t.set(Channel=FuID(channel))
    if paint:
        t.set(PaintMode=FuID(paint))
    if prev is not None:
        t.conn("EffectMask", prev, "Mask")
    return t


def masked(t: Tool, mask: Tool):
    return t.conn("EffectMask", mask, "Mask")


def merge(g: Graph, name, bg, fg, mode="Normal", blend=None, center=None, size=None, additive=None, angle=None):
    t = g.add("Merge", name)
    t.conn("Background", bg).conn("Foreground", fg)
    t.set(PerformDepthMerge=0)
    if mode != "Normal":
        t.set(ApplyMode=FuID(mode))
    if additive is not None:
        t.set(SubtractiveAdditive=additive)
    if blend is not None:
        (t.expr("Blend", blend, 1) if isinstance(blend, str) else t.set(Blend=blend))
    if center is not None:
        (t.expr("Center", center, [0.5, 0.5]) if isinstance(center, str) else t.set(Center=list(center)))
    if size is not None:
        (t.expr("Size", size, 1) if isinstance(size, str) else t.set(Size=size))
    if angle is not None:
        (t.expr("Angle", angle, 0) if isinstance(angle, str) else t.set(Angle=angle))
    return t


def xf(g: Graph, name, inp, center=None, size=None, angle=None, edges=None):
    t = g.add("Transform", name)
    t.conn("Input", inp)
    if center is not None:
        (t.expr("Center", center, [0.5, 0.5]) if isinstance(center, str) else t.set(Center=list(center)))
    if size is not None:
        (t.expr("Size", size, 1) if isinstance(size, str) else t.set(Size=size))
    if angle is not None:
        (t.expr("Angle", angle, 0) if isinstance(angle, str) else t.set(Angle=angle))
    if edges is not None:
        t.set(Edges=edges)
    return t


def blur(g: Graph, name, inp, size, blend=None):
    t = g.add("Blur", name)
    t.conn("Input", inp)
    (t.expr("XBlurSize", size, 1) if isinstance(size, str) else t.set(XBlurSize=size))
    if blend is not None:
        (t.expr("Blend", blend, 1) if isinstance(blend, str) else t.set(Blend=blend))
    return t


def softglow(g: Graph, name, inp, size=12, gain="1", threshold=0.4):
    t = g.add("SoftGlow", name)
    t.conn("Input", inp)
    t.set(Threshold=threshold, XGlowSize=size)
    (t.expr("Gain", gain, 1) if isinstance(gain, str) else t.set(Gain=gain))
    return t


def dirblur(g: Graph, name, inp, length, angle=0.0, btype=0):
    t = g.add("DirectionalBlur", name)
    t.conn("Input", inp)
    t.set(Type=btype, Angle=angle)
    (t.expr("Length", length, 0) if isinstance(length, str) else t.set(Length=length))
    return t


def cc(g: Graph, name, inp, gain=None, sat=None, lift=None, gamma=None, contrast=None):
    t = g.add("ColorCorrector", name)
    t.conn("Input", inp)
    for k, v in (("MasterRGBGain", gain), ("MasterSaturation", sat), ("MasterRGBLift", lift),
                 ("MasterRGBGamma", gamma), ("MasterRGBContrast", contrast)):
        if v is not None:
            (t.expr(k, v, 1) if isinstance(v, str) else t.setk(k, v))
    return t


def bc(g: Graph, name, inp, gain=None, sat=None, contrast=None, lift=None, gamma=None):
    t = g.add("BrightnessContrast", name)
    t.conn("Input", inp)
    for k, v in (("Gain", gain), ("Saturation", sat), ("Contrast", contrast), ("Lift", lift), ("Gamma", gamma)):
        if v is not None:
            (t.expr(k, v, 1) if isinstance(v, str) else t.setk(k, v))
    return t


def noise(g: Graph, name, c1, c2, detail=6, scale=4.0, seethe_rate=0.05, contrast=1.0, brightness=0.0,
          center=None, angle=0.0, xscale=None, discontinuous=False):
    t = g.add("FastNoise", name)
    frame_inputs(t, g)
    r1, g1, b1 = rgb3(c1)
    r2, g2, b2 = rgb3(c2)
    t.set(Detail=detail, XScale=scale, SeetheRate=seethe_rate, Contrast=contrast, Brightness=brightness,
          Angle=angle, Color1Red=r1, Color1Green=g1, Color1Blue=b1, Color1Alpha=1.0,
          Color2Red=r2, Color2Green=g2, Color2Blue=b2, Color2Alpha=1.0)
    if discontinuous:
        t.set(Discontinuous=1)
    if center is not None:
        t.expr("Center", center, [0.5, 0.5])
    return t


# ----------------------------------------------------------- typography --
def title_text(g: Graph, name, text, font, style, size, tracking=1.05, color=(1, 1, 1), line_spacing=1.0,
               publish_label="Main Title", group=10, publish=True):
    t = g.add("TextPlus", name)
    frame_inputs(t, g)
    r, gg, b = rgb3(color)
    t.set(StyledText=text, Font=font, Style=style, Size=size, CharacterSpacing=tracking, LineSpacing=line_spacing,
          VerticalJustificationNew=3, HorizontalJustificationNew=3, Red1=r, Green1=gg, Blue1=b, Alpha1=1.0)
    if publish:
        pre = publish_label.replace(" ", "")
        g.publish(t, "StyledText", publish_label, page="Text", default=None, cid=f"{pre}Text")
        g.publish(t, "Font", f"{publish_label} Font", page="Text", group=group + 100, cid=f"{pre}Font")
        g.publish(t, "Style", f"{publish_label} Style", page="Text", group=group + 100, cid=f"{pre}Style")
        g.publish(t, "Size", f"{publish_label} Size", page="Text", default=size, cid=f"{pre}Size")
        g.publish(t, "CharacterSpacing", f"{publish_label} Letter Spacing", page="Text", default=tracking,
                  cid=f"{pre}Tracking")
        g.publish(t, "LineSpacing", f"{publish_label} Line Spacing", page="Text", default=line_spacing,
                  cid=f"{pre}Leading")
        g.publish(t, "HorizontalJustificationNew", f"{publish_label} Alignment", page="Text", cid=f"{pre}Align")
        g.publish(t, "Red1", f"{publish_label} Color", page="Text", group=group, cid=f"{pre}Red")
        g.publish(t, "Green1", f"{publish_label} Color", page="Text", group=group, cid=f"{pre}Green")
        g.publish(t, "Blue1", f"{publish_label} Color", page="Text", group=group, cid=f"{pre}Blue")
    return t


def fill_material(g: Graph, name, text: Tool, stops, gtype="Linear", start=(0.5, 0.62), end=(0.5, 0.38)):
    """Gradient 'material' clipped to the title alpha (Background + Bitmap mask)."""
    m = bitmap_mask(g, f"{name}Matte", text)
    t = gradient_bg(g, name, stops, gtype, start, end)
    masked(t, m)
    return t


def edge_light(g: Graph, name, text: Tool, dx, dy, color=None, accent=False, blur_px=1.5, gain=1.0):
    """Bevel/rim approximation: title alpha minus a shifted copy -> lit edge."""
    sh = xf(g, f"{name}Shift", text, center=(0.5 + dx, 0.5 + dy))
    m1 = bitmap_mask(g, f"{name}MaskA", text)
    m2 = bitmap_mask(g, f"{name}MaskB", sh, paint="Subtract", prev=m1)
    if accent:
        s = accent_solid(g, f"{name}Color", gain)
    else:
        s = solid(g, f"{name}Color", color or (1, 1, 1))
    masked(s, m2)
    return blur(g, f"{name}Soft", s, blur_px) if blur_px else s


def extrusion_stack(g: Graph, name, base: Tool, text: Tool, layers=8, dx=0.0, dy=-0.0016, color=(0.02, 0.02, 0.025),
                    depth_ctl="ExtrusionDepth"):
    """2.5D extrusion: N darkened copies of the title stacked with offsets
    scaled by CONTROLS.ExtrusionDepth (0 disables)."""
    side = solid(g, f"{name}Side", color)
    sm = bitmap_mask(g, f"{name}SideMatte", text)
    masked(side, sm)
    cur = base
    for i in range(layers, 0, -1):
        k = i / layers
        cur = merge(g, f"{name}L{i}", cur, side,
                    center=f"Point(0.5 + {dx * i:.5f}*{ctl(depth_ctl)}, 0.5 + {dy * i:.5f}*{ctl(depth_ctl)})",
                    blend=f"min({ctl(depth_ctl)}*4, 1) * {0.55 + 0.45 * (1 - k):.3f}")
    return cur


def impact_flash(g: Graph, name, bg, color=(1, 0.95, 0.85), peak=0.5, frames=6, offset=0):
    s = solid(g, f"{name}Color", color)
    return merge(g, name, bg, s, mode="Screen",
                 blend=f"{peak}*{ctl('ImpactIntensity')}*{decay(ctl('ImpactFrame') + f' + {offset}', frames)}")


def light_spot(g: Graph, name, bg, color, center, w, h, soft=0.3, blend="1", mode="Screen", accent=False, gain=1.0):
    s = accent_solid(g, f"{name}Color", gain) if accent else solid(g, f"{name}Color", color)
    e = ellipse(g, f"{name}Shape", center, w, h, soft)
    masked(s, e)
    return merge(g, name, bg, s, mode=mode, blend=blend)


def shock_ring(g: Graph, name, bg, color=None, center=(0.5, 0.5), max_size=1.6, frames=18, border=0.012,
               soft=0.03, peak=0.9, accent=True, offset=0):
    """Expanding ring keyed to CONTROLS.ImpactFrame (independent of the title)."""
    s = accent_solid(g, f"{name}Color", 1.4) if accent else solid(g, f"{name}Color", color)
    u = prog(f"{ctl('ImpactFrame')} + {offset}", frames)
    sz = f"(0.02 + {max_size}*{e_out(u, 2)})"
    e = g.add("EllipseMask", f"{name}Shape")
    e.set(SoftEdge=soft, Center=list(center), BorderWidth=border, MaskWidth=g.W, MaskHeight=g.H,
          UseFrameFormatSettings=1)
    e.expr("Width", sz, 0.1)
    e.expr("Height", f"{sz}*1.7778", 0.1)
    masked(s, e)
    return merge(g, name, bg, s, mode="Screen",
                 blend=f"{peak}*{ctl('ImpactIntensity')}*{step(ctl('ImpactFrame') + f' + {offset}')}*(1-{u})")


def particles(g: Graph, name, bg, number=60, lifespan=90, velocity=0.02, angle=90, angle_var=25, size=0.6,
              color=(1, 0.6, 0.25), region="CubeRgn", region_size=(1.6, 0.2, 0.4), center_y=-0.1,
              turbulence=0.4, glow=6, mode="Screen", start=None, number_expr=None):
    """pEmitter -> pTurbulence -> pRender -> SoftGlow -> merged.
    Particle count follows CONTROLS.ParticleIntensity."""
    r, gg, b = rgb3(color)
    em = g.add("pEmitter", f"{name}Emitter")
    em.expr("Number", number_expr or f"{number}*{ctl('ParticleIntensity')}", number)
    em.set(Lifespan=lifespan, LifespanVariance=lifespan * 0.3, Velocity=velocity, VelocityVariance=velocity * 0.6,
           Angle=angle, AngleVariance=angle_var, Region=FuID(region))
    em.setk("ParticleStyle.ColorControls", 1)
    em.setk("ParticleStyle.Red", r)
    em.setk("ParticleStyle.Green", gg)
    em.setk("ParticleStyle.Blue", b)
    em.setk("ParticleStyle.Size", size)
    em.setk("ParticleStyle.SizeVariance", size * 0.6)
    if region == "CubeRgn":
        em.setk("CubeRgn.Width", region_size[0])
        em.setk("CubeRgn.Height", region_size[1])
        em.setk("CubeRgn.Depth", region_size[2])
    elif region == "SphereRgn":
        em.setk("SphereRgn.Radius", region_size[0])
    em.setk("Transform3DOp.Translate.Y", center_y)
    last = em
    if turbulence:
        tb = g.add("pTurbulence", f"{name}Turb")
        tb.conn("Input", last)
        tb.set(XStrength=turbulence, YStrength=turbulence, ZStrength=turbulence * 0.5)
        last = tb
    rd = g.add("pRender", f"{name}Render")
    rd.conn("Input", last)
    frame_inputs(rd, g)
    out = rd
    if glow:
        out = softglow(g, f"{name}Glow", rd, glow, gain=f"1.2*{ctl('GlowStrength')}", threshold=0.1)
    blend = f"min({ctl('ParticleIntensity')}, 1)"
    if start is not None:
        blend += f"*{step(start)}"
    return merge(g, name, bg, out, mode=mode, blend=blend)


def polyline_mask(g: Graph, name, pts, border=0.003, soft=0.002, closed=False):
    """Open polyline drawn as a stroke (BorderWidth). pts: list of (x,y) 0..1."""
    t = g.add("PolylineMask", name)
    plist = [OrderedDict(Linear=True, X=round(x - 0.5, 5), Y=round(y - 0.5, 5)) for x, y in pts]
    t.set(SoftEdge=soft, BorderWidth=border, MaskWidth=g.W, MaskHeight=g.H, UseFrameFormatSettings=1)
    t.setk("Polyline", Call("Polyline", OrderedDict(Closed=closed, Points=plist)))
    return t


# ---------------------------------------------------------- finishing ----
def camera_rig(g: Graph, name, inp, push_from=1.0, push_to=1.06, shake_frames=10, shake_amp=0.006,
               push_start=None, push_dur=None):
    """Whole-frame camera: slow push + impact shake (CONTROLS.ShakeAmount)."""
    ps = push_start or ctl("AnimStart")
    pdur = push_dur or f"({ctl('ExitStart')} + {ctl('ExitDuration')} - {ps})"
    u = prog(ps, pdur)
    d = decay(ctl("ImpactFrame"), shake_frames)
    sx = shake(f"{shake_amp}*{ctl('ShakeAmount')}*{d}", 1.9, 1.0)
    sy = shake(f"{shake_amp}*{ctl('ShakeAmount')}*{d}", 2.3, 2.7)
    return xf(g, name, inp, center=f"Point(0.5 + {sx}, 0.5 + {sy})",
              size=f"{push_from} + ({push_to} - {push_from})*{e_inout(u)}", edges=1)


def title_placement(g: Graph, name, inp, size_expr="1", center_extra_x="0", center_extra_y="0", angle_extra="0"):
    """Applies TEXT_POSITION / TEXT_SCALE / TEXT_ROTATION controls."""
    return xf(g, name, inp,
              center=f"Point({ctl('TextPosX')} + {center_extra_x}, {ctl('TextPosY')} + {center_extra_y})",
              size=f"{ctl('TextScale')} * ({size_expr})",
              angle=f"{ctl('TextRotation')} + {angle_extra}")


def finish(g: Graph, inp, vignette=0.55, letterbox=True, grain=True, sat=None, gain=None):
    cur = inp
    if vignette:
        v = solid(g, "VignetteColor", (0, 0, 0))
        e = ellipse(g, "VignetteShape", (0.5, 0.5), 1.25, 1.25, 0.45, invert=True)
        masked(v, e)
        cur = merge(g, "Vignette", cur, v, blend=vignette)
    if sat is not None or gain is not None:
        cur = cc(g, "Grade", cur, gain=gain, sat=sat)
    if grain:
        fg = g.add("FilmGrain", "Grain")
        fg.conn("Input", cur)
        cur = fg
    if letterbox:
        lb = solid(g, "LetterboxColor", (0, 0, 0))
        r = rect(g, "LetterboxShape", (0.5, 0.5), 1.0, 0.7438, 0.0, invert=True)
        masked(lb, r)
        cur = merge(g, "Letterbox", cur, lb, blend=f"{ctl('Letterbox')}")
    return cur


def exit_fade(prefix_blend="1"):
    """Blend expression for a title that has finished its exit."""
    return f"{prefix_blend}*(1 - {prog(ctl('ExitStart'), ctl('ExitDuration'))})"


# --------------------------------------------------------------- 3D ------
def text3d_rig(g: Graph, name, text, font, style, size=0.5, extrusion=0.15, bevel=0.02, color=(0.8, 0.6, 0.3),
               spec=(1, 0.9, 0.7), spec_exp=40, rot_y="0", rot_x="0", tz="0", cam_z="4", cam_x="0", cam_y="0",
               key_rot=(-30, -35), key_color=(1, 0.95, 0.85), key_int=1.2, amb=0.15, rim=True,
               rim_color=(0.6, 0.75, 1.0)):
    """Genuine 3D extruded title: Text3D + Blinn + lights + camera + Renderer3D."""
    mat = g.add("MtlBlinn", f"{name}Mtl")
    r, gg, b = rgb3(color)
    sr, sg, sb = rgb3(spec)
    mat.setk("Diffuse.Color.Red", r)
    mat.setk("Diffuse.Color.Green", gg)
    mat.setk("Diffuse.Color.Blue", b)
    mat.setk("Specular.Color.Red", sr)
    mat.setk("Specular.Color.Green", sg)
    mat.setk("Specular.Color.Blue", sb)
    mat.setk("Specular.Intensity", 1.0)
    mat.setk("Specular.Exponent", spec_exp)
    t3 = g.add("Text3D", f"{name}Text3D")
    t3.set(StyledText=text, Font=font, Style=style, Size=size, CharacterSpacing=1.05, ExtrusionStyle=1)
    t3.expr("ExtrusionDepth", f"{extrusion}*{ctl('ExtrusionDepth')}", extrusion)
    t3.expr("BevelDepth", f"{bevel}*{ctl('BevelAmount')}", bevel)
    t3.expr("BevelWidth", f"{bevel}*{ctl('BevelAmount')}", bevel)
    t3.conn("MaterialInput", mat, "MaterialOutput")
    t3.expr("Transform3DOp.Rotate.Y", rot_y, 0)
    t3.expr("Transform3DOp.Rotate.X", rot_x, 0)
    t3.expr("Transform3DOp.Translate.Z", tz, 0)
    t3.expr("Transform3DOp.Translate.X", f"({ctl('TextPosX')} - 0.5)*4", 0)
    t3.expr("Transform3DOp.Translate.Y", f"({ctl('TextPosY')} - 0.5)*2.25", 0)
    t3.expr("Transform3DOp.Rotate.Z", ctl("TextRotation"), 0)
    t3.expr("Transform3DOp.Scale.X", ctl("TextScale"), 1)
    g.publish(t3, "StyledText", "Main Title (3D)", page="Text", cid="MainTitle3DText")
    g.publish(t3, "Font", "3D Title Font", page="Text", cid="MainTitle3DFont")
    g.publish(t3, "Style", "3D Title Style", page="Text", cid="MainTitle3DStyle")
    g.publish(mat, "Diffuse.Color.Red", "Material Color", page="Look", group=20, cid="MtlRed")
    g.publish(mat, "Diffuse.Color.Green", "Material Color", page="Look", group=20, cid="MtlGreen")
    g.publish(mat, "Diffuse.Color.Blue", "Material Color", page="Look", group=20, cid="MtlBlue")
    cam = g.add("Camera3D", f"{name}Camera")
    cam.expr("Transform3DOp.Translate.Z", cam_z, 4)
    cam.expr("Transform3DOp.Translate.X", cam_x, 0)
    cam.expr("Transform3DOp.Translate.Y", cam_y, 0)
    key = g.add("LightDirectional", f"{name}Key")
    kr, kg, kb = rgb3(key_color)
    key.set(Red=kr, Green=kg, Blue=kb, Intensity=key_int)
    key.setk("Transform3DOp.Rotate.X", key_rot[0])
    key.setk("Transform3DOp.Rotate.Y", key_rot[1])
    ambl = g.add("LightAmbient", f"{name}Ambient")
    ambl.set(Intensity=amb)
    m3 = g.add("Merge3D", f"{name}Scene")
    m3.conn("SceneInput1", t3).conn("SceneInput2", cam).conn("SceneInput3", key).conn("SceneInput4", ambl)
    if rim:
        rl = g.add("LightSpot", f"{name}Rim")
        rr, rg, rb = rgb3(rim_color)
        rl.set(Red=rr, Green=rg, Blue=rb, Intensity=2.0, ConeAngle=40)
        rl.setk("Transform3DOp.Translate.Z", -3)
        rl.setk("Transform3DOp.Translate.Y", 1.5)
        m3.conn("SceneInput5", rl)
    rnd = g.add("Renderer3D", f"{name}Render")
    frame_inputs(rnd, g)
    rnd.conn("SceneInput", m3)
    rnd.set(RendererType=FuID("RendererOpenGL"), CameraSelector=FuID(f"{name}Camera"))
    rnd.setk("RendererOpenGL.LightingEnabled", 1)
    rnd.setk("RendererOpenGL.Supersampling", 2)
    return rnd


def light_sweep(g: Graph, name, bg, title_img: Tool, start, dur, angle=25.0, width=0.06, color=(1, 0.95, 0.85),
                peak=0.8, accent=False):
    """Specular band that travels across the title (clipped to title alpha)."""
    u = prog(start, dur)
    band = g.add("RectangleMask", f"{name}Band")
    band.set(SoftEdge=width * 0.8, Width=width, Height=2.0, Angle=angle, MaskWidth=g.W, MaskHeight=g.H,
             UseFrameFormatSettings=1)
    band.expr("Center", f"Point(-0.2 + 1.4*{e_inout(u)}, 0.5)", [0.5, 0.5])
    clip = bitmap_mask(g, f"{name}Clip", title_img, paint="Multiply", prev=band)
    s = accent_solid(g, f"{name}Color", 1.2) if accent else solid(g, f"{name}Color", color)
    masked(s, clip)
    return merge(g, name, bg, s, mode="Screen",
                 blend=f"{peak}*{ctl('GlowStrength')}*{clamp01(f'{u}*20')}*(1-{clamp01(f'({u}-0.95)*20')})")


def subtitle_text(g: Graph, name, text, font, style, size, tracking=1.3, color=(0.85, 0.85, 0.85),
                  label="Subtitle", group=11, y_off=-0.14):
    t = title_text(g, name, text, font, style, size, tracking, color, publish_label=label, group=group)
    return t, xf(g, f"{name}Place", t, center=f"Point({ctl('TextPosX')}, {ctl('TextPosY')} + {y_off})")


def std_controls(g: Graph, p, extra=None):
    """CONTROLS node seeded from the template's default timing params."""
    return g.controls(timing=dict(AnimStart=p["ANIMATION_START"], AnimDuration=p["ANIMATION_DURATION"],
                                  ImpactFrame=p["IMPACT_FRAME"], HoldDuration=p["HOLD_DURATION"],
                                  ExitStart=p["EXIT_START"], ExitDuration=p["EXIT_DURATION"]), extra=extra)


def shard_polys(n=8, seed=3, box=(0.05, 0.3, 0.95, 0.7)):
    """Irregular convex shards tiling `box` (x0,y0,x1,y1 normalised): a jittered
    grid of quads, returned as lists of (x,y) points. Used to fracture a title
    in Fusion with closed PolylineMasks."""
    import random
    r = random.Random(seed)
    cols = max(2, int(round(n / 2)))
    rows = 2
    x0, y0, x1, y1 = box
    xs = [x0 + (x1 - x0) * i / cols for i in range(cols + 1)]
    ys = [y0 + (y1 - y0) * j / rows for j in range(rows + 1)]
    grid = {}
    for i, x in enumerate(xs):
        for j, y in enumerate(ys):
            jx = 0 if i in (0, cols) else r.uniform(-0.35, 0.35) * (x1 - x0) / cols
            jy = 0 if j in (0, rows) else r.uniform(-0.3, 0.3) * (y1 - y0) / rows
            grid[(i, j)] = (x + jx, y + jy)
    polys = []
    for i in range(cols):
        for j in range(rows):
            polys.append([grid[(i, j)], grid[(i + 1, j)], grid[(i + 1, j + 1)], grid[(i, j + 1)]])
    return polys


def closed_poly_mask(g: Graph, name, pts, soft=0.001):
    t = g.add("PolylineMask", name)
    plist = [OrderedDict(Linear=True, X=round(x - 0.5, 5), Y=round(y - 0.5, 5)) for x, y in pts]
    t.set(SoftEdge=soft, MaskWidth=g.W, MaskHeight=g.H, UseFrameFormatSettings=1)
    t.setk("Polyline", Call("Polyline", OrderedDict(Closed=True, Points=plist)))
    return t
