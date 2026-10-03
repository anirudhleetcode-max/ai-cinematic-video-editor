"""Hardware & toolchain detection. Encoders are *test-encoded*, not just listed: an ffmpeg build can
list h264_nvenc without a GPU being present."""
from __future__ import annotations

import functools
import os
import platform
import re
import shutil

import psutil

from .config import get_settings
from .proc import run

# Preference order per codec.
CANDIDATES = {
    "h264": ["h264_nvenc", "h264_qsv", "h264_amf", "h264_videotoolbox", "h264_vaapi", "libx264"],
    "hevc": ["hevc_nvenc", "hevc_qsv", "hevc_amf", "hevc_videotoolbox", "hevc_vaapi", "libx265"],
}


def _version(binary: str) -> str | None:
    if not shutil.which(binary):
        return None
    try:
        out = run([binary, "-version"], timeout=20).stdout.decode("utf-8", "replace")
        m = re.search(r"version (\S+)", out)
        return m.group(1) if m else out.splitlines()[0]
    except Exception:
        return None


def _encoder_works(enc: str) -> bool:
    s = get_settings()
    args = [s.ffmpeg, "-v", "error", "-f", "lavfi", "-i", "testsrc2=s=256x144:r=30:d=0.3"]
    if enc.endswith("_vaapi"):
        args += ["-vaapi_device", "/dev/dri/renderD128", "-vf", "format=nv12,hwupload"]
    args += ["-c:v", enc, "-f", "null", "-"]
    try:
        run(args, timeout=30)
        return True
    except Exception:
        return False


@functools.lru_cache(maxsize=1)
def available_encoders() -> dict[str, list[str]]:
    s = get_settings()
    try:
        listed = run([s.ffmpeg, "-hide_banner", "-encoders"], timeout=20).stdout.decode()
    except Exception:
        return {"h264": [], "hevc": []}
    res: dict[str, list[str]] = {}
    for codec, cands in CANDIDATES.items():
        res[codec] = [e for e in cands if re.search(rf"\s{e}\s", listed) and _encoder_works(e)]
    return res


def pick_encoder(codec: str = "h264", prefer_hw: bool = True) -> str:
    encs = available_encoders().get(codec, [])
    if not prefer_hw:
        sw = "libx264" if codec == "h264" else "libx265"
        if sw in encs:
            return sw
    if encs:
        return encs[0]
    return "libx264"


@functools.lru_cache(maxsize=1)
def available_filters() -> frozenset[str]:
    try:
        out = run([get_settings().ffmpeg, "-hide_banner", "-filters"], timeout=30).stdout.decode("utf-8", "replace")
    except Exception:  # noqa: BLE001
        return frozenset()
    names = set()
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 3 and len(parts[0]) == 3 and set(parts[0]) <= set("TSC."):
            names.add(parts[1])
    return frozenset(names)


def has_filter(name: str) -> bool:
    return name in available_filters()


def encoder_args(enc: str, quality: str = "high") -> list[str]:
    """Quality ladder per encoder family (quality: draft | standard | high), always tagged BT.709 limited range."""
    return [*_encoder_args(enc, quality), "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709", "-color_range", "tv"]


def _encoder_args(enc: str, quality: str) -> list[str]:
    from . import contract as C

    crf = C.FINAL_CRF[quality]
    if enc in ("libx264", "libx265"):
        preset = C.FINAL_PRESET[quality]
        return ["-c:v", enc, "-preset", preset, "-crf", str(crf), "-pix_fmt", "yuv420p"]
    if enc.endswith("_nvenc"):
        return ["-c:v", enc, "-preset", "p5", "-rc", "vbr", "-cq", str(crf + 2), "-b:v", "0", "-pix_fmt", "yuv420p"]
    if enc.endswith("_qsv"):
        return ["-c:v", enc, "-global_quality", str(crf + 2), "-pix_fmt", "nv12"]
    if enc.endswith("_videotoolbox"):
        return ["-c:v", enc, "-q:v", str(70 - crf), "-pix_fmt", "yuv420p"]
    if enc.endswith("_amf"):
        return ["-c:v", enc, "-quality", "quality", "-rc", "cqp", "-qp_i", str(crf), "-qp_p", str(crf)]
    return ["-c:v", "libx264", "-preset", "veryfast", "-crf", str(crf), "-pix_fmt", "yuv420p"]


PCI_VENDORS = {"0x10de": "NVIDIA", "0x1002": "AMD", "0x1022": "AMD", "0x8086": "Intel", "0x106b": "Apple"}


def _fixed_cmd(args: list[str], timeout: float = 10) -> str:
    """Run a FIXED system query (no user input ever reaches these arguments)."""
    import subprocess

    try:
        p = subprocess.run(args, capture_output=True, timeout=timeout, text=True)
        return p.stdout if p.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError):
        return ""


@functools.lru_cache(maxsize=1)
def detect_gpus() -> list[dict]:
    """Which GPUs exist (vendor + name + how it was detected). Presence of a GPU does NOT mean an encoder works:
    encoders are only used after a successful test encode (available_encoders)."""
    found: list[dict] = []
    system = platform.system()
    if shutil.which("nvidia-smi"):
        for line in _fixed_cmd(["nvidia-smi", "--query-gpu=name,driver_version", "--format=csv,noheader"]).splitlines():
            if line.strip():
                name, _, drv = line.partition(",")
                found.append({"vendor": "NVIDIA", "name": name.strip(), "driver": drv.strip(), "source": "nvidia-smi"})
    if system == "Linux":
        import glob

        for vf in sorted(glob.glob("/sys/class/drm/card[0-9]*/device/vendor")):
            try:
                vendor = open(vf).read().strip().lower()
                dev = open(vf.replace("vendor", "device")).read().strip().lower()
            except OSError:
                continue
            v = PCI_VENDORS.get(vendor)
            if v and not any(g["vendor"] == v and g["source"] == "nvidia-smi" for g in found):
                found.append({"vendor": v, "name": f"PCI {vendor}:{dev}", "source": "sysfs drm"})
    elif system == "Windows":
        out = _fixed_cmd(["powershell", "-NoProfile", "-Command", "Get-CimInstance Win32_VideoController | ForEach-Object { $_.Name }"], 20)
        for name in (x.strip() for x in out.splitlines()):
            if name:
                vendor = next((v for k, v in (("nvidia", "NVIDIA"), ("geforce", "NVIDIA"), ("quadro", "NVIDIA"), ("radeon", "AMD"), ("amd", "AMD"),
                                              ("intel", "Intel"), ("arc", "Intel")) if k in name.lower()), "unknown")
                if not any(g["name"] == name for g in found):
                    found.append({"vendor": vendor, "name": name, "source": "Win32_VideoController"})
    elif system == "Darwin":
        out = _fixed_cmd(["system_profiler", "SPDisplaysDataType"], 20)
        for line in out.splitlines():
            if "Chipset Model:" in line:
                name = line.split(":", 1)[1].strip()
                vendor = "Apple" if name.startswith("Apple") else next((v for k, v in (("NVIDIA", "NVIDIA"), ("AMD", "AMD"), ("Radeon", "AMD"),
                                                                                      ("Intel", "Intel")) if k in name), "unknown")
                found.append({"vendor": vendor, "name": name, "source": "system_profiler"})
    return found


def diagnostics() -> dict:
    s = get_settings()
    du = shutil.disk_usage(s.data_dir)
    vm = psutil.virtual_memory()
    gpus = detect_gpus()
    gpu = ", ".join(f"{g['vendor']} {g['name']}" for g in gpus) or None
    encs = available_encoders()
    hw_verified = [e for c in encs.values() for e in c if not e.startswith("lib")]
    return {
        "os": f"{platform.system()} {platform.release()}",
        "python": platform.python_version(),
        "ffmpeg": _version(s.ffmpeg),
        "ffprobe": _version(s.ffprobe),
        "ffmpeg_path": shutil.which(s.ffmpeg),
        "cpu_count": os.cpu_count(),
        "cpu_percent": psutil.cpu_percent(interval=0.1),
        "ram_total_gb": round(vm.total / 2**30, 2),
        "ram_available_gb": round(vm.available / 2**30, 2),
        "disk_free_gb": round(du.free / 2**30, 2),
        "gpu": gpu,
        "gpus": gpus,
        "platform_class": "CPU-only" if not gpus else "/".join(sorted({g["vendor"] for g in gpus})),
        "encoders": encs,
        "verified_hardware_encoders": hw_verified,
        "selected_encoder": pick_encoder("h264"),
        "hardware_encoding": pick_encoder("h264") != "libx264",
    }
