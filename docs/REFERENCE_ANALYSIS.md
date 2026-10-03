# Reference analysis

`reference/analyze.py` turns a reference video into a **ReferenceStyleProfile**. Every field is labelled in the
profile's `provenance` block:

| Group | Fields | Provenance |
|---|---|---|
| Pacing | median / average shot length, p10 / p90, shot-length histogram, cuts per minute, pacing curve (cuts per 10 s), first / last shot length | **measured** (adaptive two-signal cut detector) |
| Colour | brightness, contrast, saturation, temperature, tint, clipped blacks / whites, dominant colours; **grade profile**: luma p5/p50/p95, saturation p50/p90, shadow / midtone / highlight casts, dominant hue | **measured** |
| Motion | camera translation and zoom (optical flow), motion intensity | **measured** |
| Fades | fade-in / fade-out seconds (luma ramps from / to black) | **measured** |
| Music & audio | BPM, energy, sections, beat alignment of cuts, RMS dynamics (p10 / p95, range) | **measured** |
| Transitions | frequency and types (cut / fade / dissolve) | **inferred** (from frame statistics, not edit metadata) |
| Text | presence per band, position, text events (start / end / band / relative coverage) | **inferred** (stroke-density heuristic, no OCR) |
| Speed | slow-motion estimate (repeated frames) | **inferred** |
| Not available | font identity, exact text, exact LUT / grading operations, speed-ramp curves, per-shot effects | **unavailable** |

## Checked against a reference of known construction
`scripts/real_acceptance.py --assemble` builds a reference montage from real footage with a known recipe:
* 30 shots of 1.2 s each, hard cuts only;
* a warm grade (`colorbalance` pushes red up and blue down in shadows and midtones);
* one title in the lower area from 1 to 5 s;
* real music.

| Property | Made with | Measured |
|---|---|---|
| median shot length | 1.2 s | **1.2 s** (before this pass: 2.4 s) |
| cuts per minute | 50 (29 cuts) | 38.3 — the 6 undetected cuts join consecutive takes from the same fixed camera, which are nearly identical frames |
| transitions | hard cuts | transition frequency 0.0 |
| grade | warm shadows and midtones | shadows +0.11, midtones +0.08 warmth, highlights −0.01 (neutral) |
| title | lower area, 1–5 s | text events at 1.0–2.5 s and 4.0–5.0 s (bottom band), plus one false event at 17–18.5 s |

## Reference Match Report (`qc/review.py::reference_match`)
After every final render that used a reference, the rendered edit is analysed with the **same analyser** and
compared metric by metric:
* pacing: shot-length ratio, cuts-per-minute ratio, shot-length histogram intersection;
* transition density;
* colour statistics and shadow/highlight warmth;
* text events per minute;
* music energy.

Each metric gets a similarity in [0, 1] (1 = equal value), plus an overall mean. The report states that this is
measured similarity, **not** a claim of stylistic replication. It also notes that the output's end card may have no
counterpart in the reference.
