"""Typography engine registries: text styles and text animations (rendered to ASS by render/text_ass.py)."""
from __future__ import annotations

from .base import Definition, Registry, e, f

TEXT_STYLES = Registry("text_style")
TEXT_ANIMATIONS = Registry("text_animation")

# font family names as exposed by the bundled OFL TTFs in packages/fonts
FONTS = {"inter": "Inter", "montserrat": "Montserrat", "playfair": "Playfair Display", "bebas": "Bebas Neue"}


def _style(id_, name, tags, *, font, size, bold=False, italic=False, upper=False, tracking=0.0, color="#FFFFFF", outline=0.0,
           outline_color="#000000", shadow=1.5, shadow_alpha=0.55, box=False, box_color="#000000", box_alpha=0.45, accent="#F2B544", desc=""):
    spec = dict(font=FONTS[font], size=size, bold=bold, italic=italic, upper=upper, tracking=tracking, color=color, outline=outline,
                outline_color=outline_color, shadow=shadow, shadow_alpha=shadow_alpha, box=box, box_color=box_color, box_alpha=box_alpha, accent=accent)
    TEXT_STYLES.register(Definition(id_, name, "text_style", (
        f("size_scale", 1.0, 0.5, 2.0, 0.1), f("tracking", tracking, 0, 20, 1), f("outline", outline, 0, 8, 0.5), f("shadow", shadow, 0, 8, 0.5),
        e("case", "upper" if upper else "as_is", "as_is", "upper", "lower"),
    ), tuple(tags), desc, 1.0, lambda p, _s=spec: {**_s, **p}))


# size is a fraction of output height
_style("premium_title", "Premium Title", ("premium", "elegant", "cinematic", "title", "event"), font="inter", size=0.075, bold=True, upper=True, tracking=8,
       desc="Wide-tracked uppercase sans; the default cinematic title.")
_style("elegant_serif", "Elegant Serif", ("elegant", "wedding", "luxury", "serif", "title"), font="playfair", size=0.085, italic=True, shadow=1.0)
_style("bold_impact", "Bold Impact", ("bold", "hype", "sports", "energetic", "title"), font="bebas", size=0.16, tracking=2, shadow=2.0)
_style("minimal_lower_third", "Minimal Lower Third", ("minimal", "lower_third", "corporate", "documentary"), font="inter", size=0.038, bold=True, box=True, box_alpha=0.55, shadow=0)
_style("documentary_caption", "Documentary Caption", ("documentary", "caption", "minimal"), font="inter", size=0.042, shadow=1.2)
_style("cinematic_subtitle", "Cinematic Subtitle", ("subtitle", "cinematic", "caption"), font="inter", size=0.045, shadow=2.0, shadow_alpha=0.7)
_style("social_caption", "Social Caption", ("social", "instagram", "tiktok", "reel", "caption", "bold"), font="montserrat", size=0.06, bold=True, upper=True,
       outline=4.0, shadow=0, accent="#FFE14D")
_style("kinetic_bold", "Kinetic Bold", ("kinetic", "hype", "music", "bold"), font="montserrat", size=0.1, bold=True, upper=True, outline=0, shadow=2.5)
_style("chapter_title", "Chapter Title", ("chapter", "section", "documentary", "minimal"), font="inter", size=0.05, bold=True, upper=True, tracking=12, shadow=1.0)
_style("credits", "Credits", ("credits", "ending", "minimal"), font="inter", size=0.036, tracking=3, shadow=1.0)
_style("quote", "Quote", ("quote", "serif", "emotional"), font="playfair", size=0.06, italic=True, shadow=1.5)
_style("neon", "Neon", ("neon", "night", "music", "glow"), font="montserrat", size=0.09, bold=True, upper=True, color="#FFFFFF", outline=3.0,
       outline_color="#FF3FD2", shadow=0)
_style("lyric", "Lyric", ("lyric", "music", "karaoke"), font="montserrat", size=0.058, bold=True, outline=2.0, shadow=0, accent="#7FE3FF")
_style("corporate_clean", "Corporate Clean", ("corporate", "clean", "business"), font="inter", size=0.06, bold=True, shadow=0.8, color="#FFFFFF")
_style("wedding_script", "Wedding Script", ("wedding", "romantic", "serif", "elegant"), font="playfair", size=0.1, italic=True, shadow=1.0, color="#FFF6EC")
_style("end_card", "End Card", ("ending", "logo", "brand", "title"), font="inter", size=0.07, bold=True, upper=True, tracking=10, shadow=0.5)


def _anim(id_, name, tags, params=(), desc=""):
    TEXT_ANIMATIONS.register(Definition(id_, name, "text_animation", (f("in_dur", 0.6, 0.1, 2.5, 0.1), f("out_dur", 0.4, 0.0, 2.0, 0.1), *params),
                                        tuple(tags), desc, 1.0, None))


_anim("fade", "Fade", ("subtle", "minimal", "elegant"))
_anim("fade_up", "Fade Up", ("subtle", "premium", "elegant"), (f("distance", 0.03, 0.0, 0.15, 0.01),))
_anim("slide_left", "Slide In Left", ("dynamic",), (f("distance", 0.08, 0.02, 0.3, 0.02),))
_anim("slide_right", "Slide In Right", ("dynamic",), (f("distance", 0.08, 0.02, 0.3, 0.02),))
_anim("scale_in", "Scale In", ("premium", "cinematic"), (f("from_scale", 0.85, 0.3, 1.5, 0.05),))
_anim("tracking_reveal", "Tracking Reveal", ("premium", "cinematic", "luxury"), (f("from_tracking", 30.0, 5, 80, 5),))
_anim("typewriter", "Typewriter", ("tech", "documentary"), (f("cps", 18.0, 4, 60, 2),))
_anim("mask_reveal", "Mask Reveal (wipe)", ("premium", "modern", "clean"), (e("direction", "left", "left", "right", "up"),))
_anim("blur_reveal", "Blur Reveal", ("dreamy", "cinematic", "soft"), (f("from_blur", 12.0, 2, 40, 2),))
_anim("split_reveal", "Split Reveal", ("modern", "dynamic"), (f("distance", 0.05, 0.01, 0.2, 0.01),))
_anim("bounce", "Bounce", ("playful", "social"), (f("overshoot", 1.15, 1.02, 1.5, 0.02),))
_anim("elastic", "Elastic", ("playful", "energetic"), (f("overshoot", 1.25, 1.05, 1.6, 0.05),))
_anim("pop", "Pop", ("social", "hype", "energetic"), (f("overshoot", 1.12, 1.0, 1.4, 0.02),))
_anim("kinetic_words", "Kinetic (word pop)", ("kinetic", "hype", "music"), (f("word_gap", 0.18, 0.05, 1.0, 0.01),))
_anim("word_by_word", "Word by Word", ("kinetic", "caption", "social"), (f("word_gap", 0.25, 0.05, 1.0, 0.01),))
_anim("char_by_char", "Character by Character", ("kinetic", "tech"), (f("char_gap", 0.04, 0.01, 0.2, 0.01),))
_anim("line_by_line", "Line by Line", ("documentary", "credits"), (f("line_gap", 0.5, 0.1, 2.0, 0.1),))
_anim("karaoke", "Karaoke Highlight", ("caption", "lyric", "karaoke", "social"), ())
_anim("static", "None (static)", ("minimal",), ())
