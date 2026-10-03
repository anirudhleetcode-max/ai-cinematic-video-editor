"""Colour-space discipline for the whole render pipeline.

Rule: every source is converted ONCE into the RGB working space using *its own* matrix / range (or tone-mapped if
HDR), all grading and effects happen in RGB, and every encode converts back ONCE with BT.709 limited range and is
tagged BT.709. Without this, FFmpeg's implicit conversions use BT.601 for RGB↔YUV while players assume BT.709 for
HD, which shifts saturated colours by up to ~25/255 (measured; see tests/test_colorspace.py).
"""
from __future__ import annotations

TAGS = ["-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709", "-color_range", "tv"]
TO_YUV420 = "scale=out_color_matrix=bt709:out_range=tv,format=yuv420p"
MEZZ_TO_RGB = "scale=in_color_matrix=bt709:in_range=tv,format=gbrp"
MEZZ_TO_RGB24 = "scale=in_color_matrix=bt709:in_range=tv,format=rgb24"

_MATRIX = {"bt709": "bt709", "smpte170m": "bt601", "bt470bg": "bt601", "bt601": "bt601", "fcc": "fcc", "smpte240m": "smpte240m",
           "bt2020nc": "bt2020", "bt2020c": "bt2020", "bt2020": "bt2020"}


def source_matrix(meta: dict) -> tuple[str, str, bool]:
    """(swscale matrix name, range 'tv'|'pc', inferred?) for a source asset's meta (from editor.media.inspect)."""
    ins = meta.get("inspection") or {}
    cs = ins.get("color_space") or meta.get("color_space") or "unknown"
    m = _MATRIX.get(cs)
    inferred = m is None
    if m is None:  # unspecified: the convention players use — SD heights are BT.601, everything else BT.709
        m = "bt601" if (meta.get("height") or 1080) <= 576 else "bt709"
    rng = "pc" if (ins.get("color_range") == "full" or meta.get("color_range") == "pc" or str(meta.get("pix_fmt", "")).startswith("yuvj")) else "tv"
    return m, rng, inferred


def source_to_rgb(meta: dict, w: int, h: int, image: bool = False) -> str:
    """Filter chain: decoded source frames → square-pixel w×h planar RGB (gbrp) in the BT.709 working space."""
    if image:
        return f"scale={w}:{h}:flags=lanczos,format=gbrp"
    ins = meta.get("inspection") or {}
    from ..hw import has_filter

    if (ins.get("hdr") or meta.get("hdr")) and has_filter("zscale") and has_filter("tonemap"):
        # HDR (PQ/HLG, BT.2020) → linear light → BT.709 primaries → Hable tone-map → BT.709 transfer
        # resize first (inside the linearising zscale) so tone-mapping runs at output size, not source 4K
        return (f"zscale=w={w}:h={h}:f=spline36:t=linear:npl=203,format=gbrpf32le,zscale=p=bt709,tonemap=tonemap=hable:desat=0,"
                f"zscale=t=bt709:m=bt709:r=tv,format=gbrp")
    # (HDR without zimg/zscale in this FFmpeg build falls through to a plain BT.2020 matrix conversion — no tone-mapping;
    #  inspection reports the HDR warning so the limitation is visible)
    m, rng, _ = source_matrix(meta)
    return f"scale={w}:{h}:flags=lanczos:in_color_matrix={m}:in_range={rng},format=gbrp"
