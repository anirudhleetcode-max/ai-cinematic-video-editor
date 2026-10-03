# Colour pipeline

```
SOURCE NORMALISATION → WHITE BALANCE / EXPOSURE / CONTRAST MATCH (technical, per shot) → SHOT MATCHING (neighbour smoothing)
→ CREATIVE GRADE (preset + overrides, or the reference's measured look) → FINISHING → FINAL OUTPUT TRANSFORM (BT.709)
```

## 1. Source normalisation (`render/colorspace.py`)
Each source is converted **once** into an RGB working space, using its own properties as measured by
`media/inspect.py`:

| Source property | Handling |
|---|---|
| matrix BT.709 / BT.601 (smpte170m, bt470bg) / BT.2020 | `scale=in_color_matrix=<source>` |
| unspecified matrix | BT.601 for heights ≤ 576, else BT.709 (the convention players use; recorded as *inferred*) |
| full range (`yuvj*`, `color_range=pc` — common on phones and webcams) | `in_range=pc` |
| HDR (PQ `smpte2084`, HLG `arib-std-b67`) | `zscale` → linear light → BT.709 primaries → Hable tone-map → BT.709 (requires FFmpeg with zimg; otherwise a matrix-only conversion, and the inspection warning stays visible) |
| non-square pixels | scaled to square-pixel display size |
| rotation | FFmpeg autorotate (display matrix) before any framing |
| interlaced | `bwdif` |

Every encode (mezzanines, transitions, end card, final, proxies) converts back **once** with
`scale=out_color_matrix=bt709:out_range=tv` and is tagged BT.709 / limited range.

**Why:** FFmpeg's implicit RGB↔YUV conversions use BT.601, while players decode untagged HD as BT.709. Before
this change every render shifted saturated colours by up to **25/255** (measured).
`tests/test_colorspace.py` renders known colour patches from BT.709, BT.601 SD and full-range sources through the
whole pipeline and requires every patch to come back within 6/255. All three pass.

## 2. Technical match (per shot, closed loop)
Analysis stores a 16×9 colour thumbnail per shot (averaged over three frames). The colorist runs the **real grading
model** (`registry/color.py::grade`) over that thumbnail and iterates exposure, temperature, tint, saturation and
contrast (`solve_technical`) until the predicted statistics move 75 % of the way to the target. The target is:
* the reference's measured look, when the prompt follows the reference's colour; otherwise
* the median of the selected shots (luma clamped to 0.38–0.52).

Older analyses without thumbnails fall back to the previous open-loop estimate.

## 3. Shot matching (neighbour smoothing)
Neighbouring shots in the same section must not jump. A jump means predicted luma differs by more than 0.05,
temperature by more than 0.025, or saturation by more than 0.06. Both shots of such a pair are re-solved toward
their mean (three passes). The decision log reports the largest predicted adjacent jumps before and after.

After rendering, `qc/review.py::segment_color_continuity` measures the **actual** per-segment luma, temperature and
saturation in the output and reports the largest adjacent jumps. The review checklist flags luma jumps above 0.12
or temperature jumps above 0.06.

## 4. Creative grade
A creative preset (21 built-in, plus parameter overrides or a validated user `.cube` LUT) is baked into a 33³ LUT.
When following a reference, the **ReferenceGradeProfile** is mapped instead of picking a generic look:

| Measured in the reference | Mapped to |
|---|---|
| shadow / highlight colour casts (mean RGB of pixels below 0.25 / above 0.7 luma) | split-toning hues and amount (shadow-weighted if highlights are neutral) |
| lifted blacks (luma p5 > 0.08) | `fade` |
| overall brightness, temperature, tint, saturation, contrast | the technical-match target (step 2) |
| closest named preset | reported only, as a description |

The base is the near-neutral `natural` preset, so the look comes from the measurements rather than a generic
"cinematic" filter.

## 5. Finishing
Vignette, grain, sharpen and halation. They scale with grade intensity: intensity 0 means no grade at all.
