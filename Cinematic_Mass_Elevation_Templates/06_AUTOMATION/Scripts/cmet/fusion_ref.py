"""Reference table of Fusion tool IDs and input IDs used by the generator,
with an evidence level for each. Used by the validator to report how much of
every composition rests on confirmed vs. unconfirmed identifiers.

Evidence levels
  S  seen in real pasted node text / official documentation excerpts
  K  widely-used knowledge of real Fusion files, not re-confirmed this session
  ?  uncertain; Fusion silently drops unknown *inputs* on load, so a wrong
     input name loses that setting but does not break the file. An unknown
     *tool ID* is a load error, so only S/K tool IDs are allowed.

None of this was verified inside Resolve/Fusion (not installed in the build
environment). See COMPATIBILITY_REPORT.md.
"""

TOOLS = {
    "Background": ("S", {
        "Width": "S", "Height": "S", "UseFrameFormatSettings": "S", "Type": "S", "GradientType": "S",
        "Start": "S", "End": "S", "Gradient": "K", "TopLeftRed": "S", "TopLeftGreen": "S", "TopLeftBlue": "S",
        "TopLeftAlpha": "S", "EffectMask": "K", "Depth": "K",
    }),
    "TextPlus": ("S", {
        "Width": "K", "Height": "K", "UseFrameFormatSettings": "K", "StyledText": "S", "Font": "S", "Style": "S",
        "Size": "S", "CharacterSpacing": "K", "LineSpacing": "K", "HorizontalJustificationNew": "S",
        "VerticalJustificationNew": "S", "Center": "K", "Red1": "S", "Green1": "S", "Blue1": "S", "Alpha1": "K",
        "Enabled2": "K", "Red2": "K", "Green2": "K", "Blue2": "K", "Alpha2": "K", "Thickness2": "K",
    }),
    "Merge": ("S", {
        "Background": "S", "Foreground": "S", "ApplyMode": "S", "PerformDepthMerge": "S", "Center": "K",
        "Size": "K", "Angle": "K", "Blend": "K", "SubtractiveAdditive": "K", "AlphaGain": "K", "EffectMask": "K",
    }),
    "Transform": ("K", {
        "Input": "K", "Center": "K", "Pivot": "K", "Size": "K", "Angle": "K", "Edges": "K", "UseSizeAndAspect": "K",
        "XSize": "K", "YSize": "K", "Aspect": "K",
    }),
    "Blur": ("K", {"Input": "K", "XBlurSize": "K", "YBlurSize": "K", "LockXY": "K", "Blend": "K", "EffectMask": "K"}),
    "SoftGlow": ("S", {"Input": "K", "XGlowSize": "S", "Threshold": "S", "Gain": "S", "Blend": "K"}),
    "Glow": ("K", {"Input": "K", "XGlowSize": "S", "Glow": "K", "Blend": "K"}),
    "FastNoise": ("S", {
        "Width": "K", "Height": "K", "UseFrameFormatSettings": "K", "Detail": "S", "XScale": "S", "Seethe": "S",
        "SeetheRate": "S", "Contrast": "K", "Brightness": "K", "Center": "K", "Angle": "K", "Color1Red": "K",
        "Color1Green": "K", "Color1Blue": "K", "Color1Alpha": "K", "Color2Red": "K", "Color2Green": "K",
        "Color2Blue": "K", "Color2Alpha": "K", "Discontinuous": "K", "Inverted": "K", "EffectMask": "K",
    }),
    "ColorCorrector": ("S", {
        "Input": "K", "MasterRGBGain": "K", "MasterRGBLift": "K", "MasterRGBGamma": "K", "MasterRGBContrast": "K",
        "MasterSaturation": "K", "MasterRedGain": "K", "MasterGreenGain": "K", "MasterBlueGain": "K", "Blend": "K",
        "EffectMask": "K",
    }),
    "BrightnessContrast": ("S", {
        "Input": "K", "Gain": "K", "Lift": "K", "Gamma": "K", "Contrast": "K", "Brightness": "K", "Saturation": "K",
        "ClipBlack": "K", "Blend": "K", "EffectMask": "K",
    }),
    "RectangleMask": ("S", {
        "Center": "S", "Width": "S", "Height": "S", "SoftEdge": "S", "Invert": "S", "BorderWidth": "S",
        "MaskWidth": "S", "MaskHeight": "S", "UseFrameFormatSettings": "S", "Angle": "K", "CornerRadius": "K",
        "Level": "K", "PaintMode": "K", "EffectMask": "K",
    }),
    "EllipseMask": ("S", {
        "Center": "S", "Width": "S", "Height": "S", "SoftEdge": "S", "Invert": "S", "BorderWidth": "S",
        "MaskWidth": "S", "MaskHeight": "S", "UseFrameFormatSettings": "S", "Angle": "K", "Level": "K",
        "PaintMode": "K", "EffectMask": "K",
    }),
    "BitmapMask": ("K", {"Image": "K", "Channel": "K", "Low": "K", "High": "K", "PaintMode": "K", "Invert": "K",
                         "EffectMask": "K", "SoftEdge": "K"}),
    "pEmitter": ("S", {
        "Number": "S", "Lifespan": "S", "NumberVariance": "K", "LifespanVariance": "K", "Velocity": "K",
        "VelocityVariance": "K", "Angle": "K", "AngleVariance": "K", "AngleZ": "K", "Region": "S",
        "ParticleStyle.Size": "S", "ParticleStyle.SizeVariance": "K", "ParticleStyle.ColorControls": "S",
        "ParticleStyle.Red": "K", "ParticleStyle.Green": "K", "ParticleStyle.Blue": "K", "ParticleStyle.Alpha": "K",
        "Style": "?", "SphereRgn.Radius": "K", "CubeRgn.Width": "K", "CubeRgn.Height": "K", "CubeRgn.Depth": "K",
        "LineRgn.Start": "?", "LineRgn.End": "?", "Position": "?",
    }),
    "pRender": ("K", {"Input": "K", "Width": "?", "Height": "?", "UseFrameFormatSettings": "?", "OutputMode": "?"}),
    "pTurbulence": ("K", {"Input": "K", "XStrength": "?", "YStrength": "?", "ZStrength": "?", "Density": "?"}),
    "pDirectionalForce": ("K", {"Input": "K", "Strength": "?", "Direction": "?"}),
    "DirectionalBlur": ("S", {"Input": "K", "Type": "K", "Length": "S", "Angle": "S", "Center": "K", "Glow": "K"}),
    "Displace": ("K", {"Input": "K", "Foreground": "?", "Type": "K", "Center": "K", "RefractionStrength": "K",
                       "XRefraction": "K", "YRefraction": "K"}),
    "FilmGrain": ("K", {"Input": "K", "Size": "?", "Strength": "?"}),
    "ChannelBoolean": ("S", {}),
    "Text3D": ("S", {
        "StyledText": "K", "Font": "K", "Style": "K", "Size": "K", "CharacterSpacing": "K", "ExtrusionDepth": "S",
        "BevelDepth": "K", "BevelWidth": "K", "ExtrusionStyle": "K", "MaterialInput": "K",
        "Transform3DOp.Translate.X": "K", "Transform3DOp.Translate.Y": "K", "Transform3DOp.Translate.Z": "K",
        "Transform3DOp.Rotate.X": "S", "Transform3DOp.Rotate.Y": "K", "Transform3DOp.Rotate.Z": "K",
        "Transform3DOp.Scale.X": "K",
    }),
    "Camera3D": ("S", {"Transform3DOp.Translate.X": "K", "Transform3DOp.Translate.Y": "K",
                       "Transform3DOp.Translate.Z": "K", "Transform3DOp.Rotate.X": "S", "Transform3DOp.Rotate.Y": "K",
                       "Transform3DOp.Rotate.Z": "K", "AoV": "?", "FLength": "?"}),
    "Merge3D": ("S", {"SceneInput1": "S", "SceneInput2": "S", "SceneInput3": "S", "SceneInput4": "S",
                      "SceneInput5": "S", "SceneInput6": "S"}),
    "Renderer3D": ("S", {"SceneInput": "S", "RendererType": "S", "CameraSelector": "S", "Width": "K", "Height": "K",
                         "UseFrameFormatSettings": "K", "RendererOpenGL.Supersampling": "?",
                         "RendererSoftware.LightingEnabled": "?", "RendererOpenGL.LightingEnabled": "?"}),
    "LightDirectional": ("S", {"Red": "K", "Green": "K", "Blue": "K", "Intensity": "K",
                               "Transform3DOp.Rotate.X": "S", "Transform3DOp.Rotate.Y": "K"}),
    "LightAmbient": ("K", {"Red": "K", "Green": "K", "Blue": "K", "Intensity": "K"}),
    "LightSpot": ("S", {"Red": "K", "Green": "K", "Blue": "K", "Intensity": "K", "ConeAngle": "K",
                        "PenumbraAngle": "K", "Dropoff": "K", "Transform3DOp.Translate.X": "K",
                        "Transform3DOp.Translate.Y": "K", "Transform3DOp.Translate.Z": "K"}),
    "LightPoint": ("K", {"Red": "K", "Green": "K", "Blue": "K", "Intensity": "K", "Transform3DOp.Translate.X": "K",
                         "Transform3DOp.Translate.Y": "K", "Transform3DOp.Translate.Z": "K"}),
    "MtlBlinn": ("K", {"Diffuse.Color.Red": "K", "Diffuse.Color.Green": "K", "Diffuse.Color.Blue": "K",
                       "Specular.Color.Red": "K", "Specular.Color.Green": "K", "Specular.Color.Blue": "K",
                       "Specular.Intensity": "K", "Specular.Exponent": "K", "Diffuse.Opacity": "K"}),
    "Transform3D": ("K", {"SceneInput": "K", "Transform3DOp.Translate.X": "K", "Transform3DOp.Translate.Y": "K",
                          "Transform3DOp.Translate.Z": "K", "Transform3DOp.Rotate.X": "S",
                          "Transform3DOp.Rotate.Y": "K", "Transform3DOp.Rotate.Z": "K",
                          "Transform3DOp.Scale.X": "K"}),
    "ImagePlane3D": ("K", {"MaterialInput": "K", "Transform3DOp.Translate.Z": "K", "Transform3DOp.Scale.X": "K"}),
    "Shape3D": ("K", {}),
    "PolylineMask": ("K", {"Polyline": "K", "BorderWidth": "S", "SoftEdge": "S", "MaskWidth": "S",
                           "MaskHeight": "S", "UseFrameFormatSettings": "S", "Level": "K", "PaintMode": "K",
                           "EffectMask": "K", "Center": "K"}),
    "Highlight": ("K", {"Input": "K"}),
    "CornerPositioner": ("K", {"Input": "K"}),
}

ALLOWED_TOOL_EVIDENCE = {"S", "K"}


def input_evidence(tool_id, inp):
    t = TOOLS.get(tool_id)
    if t is None:
        return None
    return t[1].get(inp, "?")
