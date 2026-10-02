"""Deterministic natural-language prompt understanding → StyleIntent.

This works offline with no AI provider. An optional LLM provider can refine the result; its output is
validated against the same schema and merged field-by-field (see director/providers.py)."""
from __future__ import annotations

import re

from ..schemas import StyleIntent

WORDNUM = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
           "fifteen": 15, "twenty": 20, "thirty": 30, "forty": 40, "forty-five": 45, "fifty": 50, "sixty": 60, "ninety": 90,
           "first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5, "last": -1}

PLATFORMS = [
    (r"instagram\s*(reel|reels)|\breels?\b", "instagram_reel", "9:16"),
    (r"tik\s*tok", "tiktok", "9:16"),
    (r"(youtube\s*)?shorts\b", "shorts", "9:16"),
    (r"instagram\s*(post|feed)", "instagram_post", "4:5"),
    (r"\bsquare\b|1:1", "square", "1:1"),
    (r"\b(vertical|portrait)\b|9:16", "vertical", "9:16"),
    (r"4:5", "instagram_post", "4:5"),
    (r"youtube", "youtube", "16:9"),
    (r"presentation|projector|event screen|led wall", "presentation", "16:9"),
    (r"\bcinema\b|cinemascope|21:9|anamorphic", "cinema", "21:9"),
    (r"16:9|landscape|widescreen", "landscape", "16:9"),
]

STORY = [
    (r"wedding|bride|groom", "wedding"), (r"travel|trip|journey|vacation|holiday", "travel"),
    (r"product|commercial|advert|\bad\b|launch|brand film", "product"), (r"sports?|match|game day|tournament", "sports"),
    (r"concert|gig|live music|band", "concert"), (r"festival|fest\b", "festival"), (r"documentary|docu", "documentary"),
    (r"music video", "music"), (r"trailer|teaser", "trailer"), (r"birthday|bday", "birthday"),
    (r"corporate|company|business|conference", "corporate"),
    (r"college|university|campus|school|event|ceremony|highlight|recap|celebration|party", "event"),
    (r"portfolio|showreel|reel of my work", "portfolio"), (r"emotional|montage|tribute|memorial", "emotional"),
    (r"short film|story|narrative", "cinematic"),
]

COLOR = [
    (r"teal[\s\-]*(and|&|/)?[\s\-]*orange|blockbuster", "teal_orange"), (r"golden hour|sunset look|golden", "golden_hour"),
    (r"black\s*(and|&)\s*white|b\s*&\s*w|monochrome|grayscale|greyscale", "black_and_white"),
    (r"vintage|retro|old film|nostalgic", "vintage_film"), (r"night|neon|nightlife", "night_cinema"), (r"cyberpunk", "cyberpunk"),
    (r"moody|dark and|noir", "moody"), (r"pastel", "pastel"), (r"muted|desaturated", "muted"), (r"bleach", "bleach_bypass"),
    (r"high[\s\-]contrast|punchy", "high_contrast"), (r"clean commercial|bright and clean|crisp", "clean_commercial"),
    (r"soft wedding|airy|dreamy", "soft_wedding"), (r"film look|filmic|modern film|kodak|film stock", "modern_film"),
    (r"warm documentary", "warm_documentary"), (r"cool documentary", "cool_documentary"), (r"natural colou?r|no grade|ungraded", "natural"),
    (r"cinematic colou?r|cinematic grad", "cinematic_neutral"),
]

STYLE_WORDS = {
    "cinematic": ["cinematic", "film", "filmic", "movie"], "energetic": ["energetic", "energy", "hype", "dynamic", "exciting", "upbeat", "high-energy", "high energy", "pumped"],
    "emotional": ["emotional", "heartfelt", "touching", "sentimental", "moving"], "elegant": ["elegant", "classy", "premium", "luxury", "sophisticated"],
    "minimal": ["minimal", "clean", "simple"], "playful": ["playful", "fun", "quirky"], "dramatic": ["dramatic", "epic", "intense"],
    "documentary": ["documentary"], "professional": ["professional", "polished"], "calm": ["calm", "relaxing", "peaceful", "chill"],
}


def _num(s: str) -> float | None:
    s = s.strip().lower()
    if s in WORDNUM:
        return float(WORDNUM[s])
    try:
        return float(s)
    except ValueError:
        return None


def parse_duration(p: str) -> float | None:
    m = re.search(r"\b(\d{1,2}):(\d{2})\b(?!\s*(am|pm))", p)
    if m and not re.search(r"\d+:\d+\s*(aspect|ratio)", p):
        mm, ss = int(m.group(1)), int(m.group(2))
        if mm < 60 and not re.search(r"\b(16|9|4|1|21):(9|16|5|1)\b", m.group(0)):
            return float(mm * 60 + ss)
    m = re.search(r"(\d+(?:\.\d+)?|[a-z\-]+)[\s\-]*(minute|min)s?\b", p)
    if m and (v := _num(m.group(1))):
        sec = re.search(r"(\d+(?:\.\d+)?)[\s\-]*(minute|min)s?\s*(and\s*)?(\d+)[\s\-]*(second|sec|s)\b", p)
        return v * 60 + (float(sec.group(4)) if sec else 0)
    m = re.search(r"(\d+(?:\.\d+)?|[a-z\-]+)[\s\-]*(second|sec|s)\b(?![\s\-]*(intro|hook|section))", p)
    if m and (v := _num(m.group(1))) and v >= 3:
        return v
    return None


def parse_prompt(prompt: str) -> StyleIntent:
    p = " " + prompt.lower().replace("’", "'") + " "
    notes: list[str] = []
    it: dict = {"styles": [], "mood": [], "effects": [], "avoid": [], "prefer_tags": [], "reference_aspects": [], "music_indices": []}

    # intro / hook lengths (parsed before total duration so "3 seconds intro" isn't the duration)
    numw = r"(\d+(?:\.\d+)?|one|two|three|four|five|six|seven|eight|nine|ten|fifteen|twenty|thirty)"
    if m := re.search(rf"(intro|opening|hook)[^.]{{0,40}}?\b{numw}[\s\-]*(seconds?|secs?|s)\b", p):
        if (v := _num(m.group(2))) is not None:
            it["intro_seconds" if m.group(1) in ("intro", "opening") else "hook_seconds"] = v
            notes.append(f"{m.group(1)} length {v}s")
    if m := re.search(r"first\s+(\d+|[a-z]+)\s+seconds?", p):
        if (v := _num(m.group(1))) is not None:
            it["hook_seconds"] = v
    dur_text = re.sub(rf"(intro|opening|hook|first)[^.]{{0,40}}?\b{numw}[\s\-]*(seconds?|secs?|s)\b", " ", p)
    if (d := parse_duration(dur_text)) is not None:
        it["duration"] = max(3.0, min(1800.0, d))
        notes.append(f"duration {d:g}s")

    for rx, plat, ar in PLATFORMS:
        if re.search(rx, p):
            it["platform"], it["aspect_ratio"] = plat, ar
            notes.append(f"platform {plat} → {ar}")
            break
    for rx, story in STORY:
        if re.search(rx, p):
            it["story_type"] = story
            break
    for rx, preset in COLOR:
        if re.search(rx, p):
            it["color_preset"] = preset
            break
    ca: dict[str, float] = {}
    if re.search(r"warm(er)?\b(?! documentary)", p) and "golden" not in p:
        ca["temperature"] = 0.18
    if re.search(r"cool(er)?\b(?! documentary)|cold(er)?\b", p):
        ca["temperature"] = -0.18
    if re.search(r"more saturat|vibrant|colou?rful|vivid", p):
        ca["saturation"] = 1.15
    if re.search(r"less saturat|desaturat", p):
        ca["saturation"] = 0.8
    if re.search(r"brighter", p):
        ca["exposure"] = 0.15
    if re.search(r"darker", p):
        ca["exposure"] = -0.15
    if re.search(r"more contrast|contrasty", p):
        ca["contrast"] = 1.12
    if ca:
        it["color_adjust"] = ca

    for style, words in STYLE_WORDS.items():
        if any(re.search(rf"\b{re.escape(w)}\b", p) for w in words):
            it["styles"].append(style)
    if re.search(r"very fast|rapid|super fast|quick cuts|fast[\s\-]paced|hype", p):
        it["pacing"] = "very_fast" if re.search(r"very fast|rapid|super fast", p) else "fast"
    elif re.search(r"\bfast\b|energetic|upbeat|punchy", p):
        it["pacing"] = "fast"
    elif re.search(r"slow(er)?[\s\-]paced|slow pacing|\bcalm\b|relaxed|emotional (video|film|montage|edit|tribute)|gentle pac", p):
        it["pacing"] = "slow"
    elif re.search(r"medium pac|moderate", p):
        it["pacing"] = "medium"
    if it.get("pacing") is None and re.search(r"build(s|ing)? (energy|up)|build energy|highlight", p):
        it["pacing"] = "medium"
    if re.search(r"build(s|ing)? (energy|up)|build energy|toward(s)? the (climax|middle|end)|crescendo|climax", p):
        it["energy_curve"] = "build_to_climax"
    if re.search(r"(cut|edit|sync|synchroni[sz]e)[a-z ]{0,30}(to|with) the (\w+ )?(beat|music|song|rhythm|track)|beat[\s\-]sync|on the beat|beat cuts", p):
        it["beat_sync"] = True
    if re.search(r"slow[\s\-]?mo(tion)?|slowmo", p) and not re.search(r"no slow", p):
        it["slow_motion"] = True
    if re.search(r"speed[\s\-]?ramp", p):
        it["speed_ramps"] = True
    if re.search(r"no transitions|only cuts|hard cuts|straight cuts|just cuts", p):
        it["transition_style"] = "none"
    elif re.search(r"glitch", p):
        it["transition_style"] = "glitch"
    elif re.search(r"(subtle|minimal|clean|tasteful|elegant|gentle)[a-z ]{0,25}transitions?|transitions?[a-z ]{0,10}(subtle|minimal)", p):
        it["transition_style"] = "subtle"
    elif re.search(r"(energetic|dynamic|flashy|creative|bold) transitions?", p):
        it["transition_style"] = "energetic"
    for eff, rx in {"film_grain": r"grain", "light_leak": r"light leak", "vignette": r"vignette", "letterbox": r"letterbox|cinema bars|black bars|cinemascope",
                    "glitch": r"glitch effect|glitchy", "vhs": r"\bvhs\b", "soft_glow": r"glow|dreamy", "chromatic_aberration": r"chromatic|rgb split",
                    "bloom": r"bloom", "black_white": r"black and white|b&w|monochrome"}.items():
        if re.search(rx, p):
            it["effects"].append(eff)
    if re.search(r"handheld|shaky cam", p):
        it["camera_motion"] = "dynamic"
    elif re.search(r"(subtle|tasteful|gentle) (camera )?motion|ken burns|push[\s\-]ins?|slow zoom", p):
        it["camera_motion"] = "subtle"
    elif re.search(r"no (camera )?motion|static", p):
        it["camera_motion"] = "none"
    if re.search(r"stabili[sz]e|smooth (out )?shaky", p):
        it["stabilize"] = True
    m = re.search(r"[\"“]([^\"”]{1,80})[\"”]", prompt)
    if m:
        it["title"] = m.group(1).strip()
    m = re.search(r"(end|finish|close)[a-z ]{0,30}with (the )?([\"“][^\"”]+[\"”])", prompt, re.I)
    if m:
        it["end_title"] = m.group(3).strip("\"“” ")
    if re.search(r"(elegant|premium|classy)( \w+)? (typography|text|titles?)", p):
        it["text_style"] = "premium_title"
    elif re.search(r"(bold|big|impact) (text|titles?|typography)", p):
        it["text_style"] = "bold_impact"
    elif re.search(r"serif|script|wedding title", p):
        it["text_style"] = "elegant_serif"
    elif re.search(r"minimal (text|typography|titles?)", p):
        it["text_style"] = "chapter_title"
    elif re.search(r"white typography|white text", p):
        it["text_style"] = "premium_title"
    if re.search(r"\bno (text|titles|typography)\b", p):
        it["text_style"] = "none"
    if re.search(r"subtitles?|captions?|transcri", p) and not re.search(r"no (subtitles?|captions?)", p):
        it["captions"] = True
        for cs in ("karaoke", "word highlight", "bounce", "pop", "kinetic", "minimal documentary", "cinematic subtitle"):
            if cs in p:
                it["caption_style"] = cs.replace(" ", "_")
    # music
    if re.search(r"(all|every|each)( of the| the)? (\w+ )?(songs|tracks|music)|all (two|three|four|five|\d) (songs|tracks)", p):
        it["music_strategy"] = "all"
    for m in re.finditer(r"(song|track)\s*#?\s*(\d+|one|two|three|four|five|first|second|third|last)|(first|second|third|fourth|fifth|last) (song|track)", p):
        tok = m.group(2) or m.group(3)
        v = WORDNUM.get(tok, None) if not tok.isdigit() else int(tok)
        if v is not None:
            it["music_indices"].append(int(v))
    if it["music_indices"] and not it.get("music_strategy"):
        it["music_strategy"] = "single" if len(it["music_indices"]) == 1 else "all"
    if re.search(r"duck|lower the music (when|under)|music (under|below) (speech|dialogue|voice)|keep (the )?dialogue (clear|understandable|audible)", p):
        it["duck_music"] = True
    if re.search(r"dialogue|speech|interview|talking|voice", p) and not re.search(r"no dialogue|remove (the )?dialogue", p):
        it["keep_dialogue"] = True
    if re.search(r"sound effects|sfx|whoosh|impacts?\b|risers?", p):
        it["sfx"] = True
    if re.search(r"no (sound effects|sfx)", p):
        it["sfx"] = False
    # ending
    if re.search(r"logo", p) and re.search(r"(end|finish|clos|outro)", p):
        it["ending"] = "logo_title" if re.search(r"title|name", p) else "logo"
    elif re.search(r"(end|finish|close)[a-z ]{0,40}(title|name|card)", p):
        it["ending"] = "title"
    elif re.search(r"fade[\s\-]?out|fade to black", p):
        it["ending"] = "fade"
    if re.search(r"(branded|brand) ending|use my brand|brand kit|our brand|my brand", p):
        it["use_brand"] = True
        it["ending"] = it.get("ending") or "logo_title"
    # reference
    if re.search(r"reference|like this (video|one)|similar to|match the style", p):
        it["use_reference"] = True
        for asp, rx in {"pacing": r"pac(e|ing)|rhythm|cut", "color": r"colou?r|grade|mood|look", "typography": r"typograph|text|title|font",
                        "transitions": r"transition", "motion": r"camera|motion|movement", "music": r"music|audio"}.items():
            if re.search(rx, p):
                it["reference_aspects"].append(asp)
    # quality / exclusions / preferences
    if re.search(r"avoid blur|no blur|remove (poor|bad|blurry)|poor[\s\-]quality|best clips|best shots", p):
        it["avoid"] += ["blurry", "shaky", "underexposed", "overexposed", "black", "frozen", "duplicate"]
    if re.search(r"crowd", p):
        it["prefer_tags"].append("crowd")
    if re.search(r"faces|people|reactions?", p):
        it["prefer_tags"].append("faces")
    if re.search(r"close[\s\-]?ups?", p):
        it["prefer_tags"].append("closeup")
    if re.search(r"wide shots?|establishing", p):
        it["prefer_tags"].append("wide")
    if re.search(r"strong hook|engaging (start|opening|first)|grab attention|hook", p):
        it["hook_seconds"] = it.get("hook_seconds") or 3.0
    for mode in ("emergency", "quality", "fast"):
        if re.search(rf"\b{mode} mode\b", p):
            it["mode"] = mode
    if re.search(r"as (fast|quickly) as possible|asap|urgent", p):
        it["mode"] = "emergency"
    if not it["styles"] and it.get("story_type") in ("event", "festival", "concert", "sports"):
        it["styles"].append("energetic" if it.get("pacing") in ("fast", "very_fast") else "cinematic")
    it["notes"] = notes
    it = {k: v for k, v in it.items() if v not in (None, [], {})}
    return StyleIntent(**it)
