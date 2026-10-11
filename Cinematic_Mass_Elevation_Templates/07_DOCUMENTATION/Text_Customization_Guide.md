# Text Customization Guide

## In DaVinci Resolve

1. Select the title clip on the Edit page and open the **Inspector > Title** tab.
   - **Main Title** is a multi-line text box. Press Enter to make two-line titles.
   - **Main Title Font / Style**. The default fonts are bundled in `02_SHARED_ASSETS/Fonts` (OFL); install them first.
   - **Main Title Size**, **Letter Spacing**, **Line Spacing**, **Alignment** and **Color**.
   - **Subtitle** (and **Tagline** in templates that have one) have their own font, size, spacing and colour controls.
2. **Text Position X/Y**, **Text Scale** and **Text Rotation** are under *Controls*. They move the
   whole title animation, including its lights and rims, rather than only the glyphs.
3. Long titles: reduce *Main Title Size* or *Text Scale* until the title sits inside the 2.39 letterbox
   safe area. If you turn *Letterbox* to 0, keep the title inside the 90% title-safe area instead.

## In the reference renderer (no Resolve)

```bash
cd 06_AUTOMATION/Scripts
python render_title.py T03 --set MAIN_TITLE="AGNI" --set SUBTITLE="RISE OF THE FLAME" --out agni.mp4
python render_title.py T40 --set "MAIN_TITLE=FAILATHON\n2026" --set LINE_SPACING=0.95 --out two_lines.mp4
python render_title.py T01 --config my_params.json --res 3840x2160 --codec prores --out final.mov
```

- Every parameter is listed in each template's `configuration/default_params.json` and in
  `documentation/parameters.md`.
- `FONT_SIZE` = 0 auto-fits the title to `TITLE_WIDTH` (a fraction of frame width). Set a value such as
  `0.12` (cap height as a fraction of frame height) for a fixed size.
- `LETTER_SPACING` is in em; 0.05–0.12 is typical for mass titles.
- Upper-case is applied automatically for Latin titles in most templates (`UPPER = True`).

## Telugu and other Indic scripts

**Reference renderer** (works):
- It uses complex text shaping (HarfBuzz/raqm).
- Set `FONT_FAMILY=telugu` (Ramabhadra, a bold display face) or `telugu_sans` (Noto Sans Telugu Bold).
- If you pass Telugu text with a Latin font, the renderer switches to Ramabhadra automatically so the glyphs never break.
- Per-letter effects split Telugu by word, not by letter, so syllable clusters stay intact.

```bash
python render_title.py T07 --set MAIN_TITLE="ఫెయిలథాన్" --set SUBTITLE="హ్యాకథాన్ 2026" \
    --set FONT_FAMILY=telugu --set SUB_FONT_FAMILY=telugu_sans --out telugu_title.mp4
```

**Resolve** (untested):
- Type or paste Telugu into Main Title and pick a Telugu font such as Ramabhadra, Noto Sans Telugu or Mandali.
- Text+ shaping of Indic scripts depends on the Resolve version and OS text engine. It was **not tested** here.
- Check the conjuncts against the reference renderer's output. If they break, render that title with the
  reference renderer and drop the clip onto your timeline.

## Mixed English + Telugu

Put English in Main Title and Telugu in Subtitle, each with its own font.
