# Fonts

All bundled fonts are licensed under the **SIL Open Font License 1.1** (licence text next to each font,
`OFL.txt`). OFL permits use in videos/titles and redistribution of the font files with the licence; it
forbids selling the fonts by themselves. They were downloaded from the Google Fonts distribution.

**Install them before opening the templates** (Fusion looks fonts up by family/style name):
`05_RESOLVE_IMPORT/install_titles.ps1 -InstallFonts` (per-user install on Windows/macOS/Linux), or
double-click each `.ttf` > Install. If a font is missing, Fusion substitutes a default; just pick any
installed font in the Inspector (Main Title Font).

| Key | Fusion family / style | File | Notes |
|---|---|---|---|
| `anton` | Anton / Regular | anton/Anton-Regular.ttf |  |
| `bebas` | Bebas Neue / Regular | bebasneue/BebasNeue-Regular.ttf |  |
| `blackops` | Black Ops One / Regular | blackopsone/BlackOpsOne-Regular.ttf |  |
| `russo` | Russo One / Regular | russoone/RussoOne-Regular.ttf |  |
| `cinzel_deco` | Cinzel Decorative / Black | cinzeldecorative/CinzelDecorative-Black.ttf |  |
| `cinzel` | Cinzel / Black | cinzel/Cinzel[wght].ttf |  |
| `cinzel_bold` | Cinzel / Bold | cinzel/Cinzel[wght].ttf |  |
| `audiowide` | Audiowide / Regular | audiowide/Audiowide-Regular.ttf |  |
| `staatliches` | Staatliches / Regular | staatliches/Staatliches-Regular.ttf |  |
| `marcellus` | Marcellus SC / Regular | marcellussc/MarcellusSC-Regular.ttf |  |
| `orbitron` | Orbitron / Black | orbitron/Orbitron[wght].ttf |  |
| `orbitron_med` | Orbitron / Medium | orbitron/Orbitron[wght].ttf |  |
| `teko` | Teko / SemiBold | teko/Teko[wght].ttf |  |
| `teko_light` | Teko / Light | teko/Teko[wght].ttf |  |
| `telugu` | Ramabhadra / Regular | ramabhadra/Ramabhadra-Regular.ttf | Telugu display (bold, rounded). Complex-script shaping verified in the reference renderer (raqm). |
| `telugu_sans` | Noto Sans Telugu / Bold | notosanstelugu/NotoSansTelugu[wdth,wght].ttf | Telugu text face (variable; Bold instance). |
| `inter_black` | Inter / Black | (system) | Uses system Inter if present, else falls back to Anton. |

## Telugu / Indic text

* The reference renderer shapes Telugu correctly (HarfBuzz via libraqm): conjuncts and vowel signs were
  checked visually with `ఫెయిలథాన్` / `హ్యాకథాన్`. Use `--set FONT_FAMILY=telugu`.
* Per-letter animations treat Telugu text per word (clusters must not be split).
* In DaVinci Resolve, Text+ shapes Indic scripts through the OS text stack; it has **not been tested
  here**. Choose a Telugu font (Ramabhadra, Noto Sans Telugu, Mandali) in the Inspector.
* `Mandali-Regular.ttf` is an additional Telugu text face (not used by default).
