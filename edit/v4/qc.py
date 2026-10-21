"""Automated QC for an encoded delivery file. Every number reported comes from a
command run here; nothing is assumed.

usage: qc.py delivery.mp4 [master.mp4] [out.json]
"""
import json
import re
import subprocess
import sys

import numpy as np

EXPECT = dict(width=1920, height=1080, fps="30/1", frames=3396, duration=113.2)


def ff(args):
    return subprocess.run(args, capture_output=True, text=True)


def main():
    path = sys.argv[1]
    master = sys.argv[2] if len(sys.argv) > 2 else None
    out = sys.argv[3] if len(sys.argv) > 3 else None
    r = {"file": path}
    p = json.loads(ff(["ffprobe", "-v", "error", "-show_entries",
                       "format=duration,size,bit_rate:stream=codec_type,codec_name,profile,width,height,r_frame_rate,"
                       "pix_fmt,sample_rate,channels,duration,start_time", "-of", "json", path]).stdout)
    v = next(s for s in p["streams"] if s["codec_type"] == "video")
    a = [s for s in p["streams"] if s["codec_type"] == "audio"]
    r["size_bytes"] = int(p["format"]["size"])
    r["bitrate_bps"] = int(p["format"]["bit_rate"])
    r["duration_s"] = float(p["format"]["duration"])
    r["video"] = {k: v.get(k) for k in ("codec_name", "profile", "width", "height", "r_frame_rate", "pix_fmt", "duration")}
    r["audio"] = [{k: s.get(k) for k in ("codec_name", "sample_rate", "channels", "duration", "start_time")} for s in a]
    cnt = ff(["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v", "-show_entries",
              "stream=nb_read_frames", "-of", "csv=p=0", path]).stdout.strip()
    r["decoded_frames"] = int(cnt)
    det = ff(["ffmpeg", "-hide_banner", "-i", path, "-vf", "blackdetect=d=0.1:pix_th=0.06,freezedetect=n=0.002:d=1.0",
              "-af", "volumedetect,silencedetect=n=-50dB:d=1.5", "-f", "null", "-"]).stderr
    r["black_segments"] = [(float(a), float(b)) for a, b in re.findall(r"black_start:([\d.]+) black_end:([\d.]+)", det)]
    r["freeze_segments"] = re.findall(r"freeze_start: ([\d.]+)", det)
    r["silence_segments"] = [(float(a),) for a in re.findall(r"silence_start: ([\d.]+)", det)]
    m = re.search(r"mean_volume: ([-\d.]+) dB", det)
    x = re.search(r"max_volume: ([-\d.]+) dB", det)
    r["mean_volume_db"] = float(m.group(1)) if m else None
    r["max_volume_db"] = float(x.group(1)) if x else None
    if master:
        s = ff(["ffmpeg", "-hide_banner", "-i", master, "-i", path, "-lavfi", "[0:v][1:v]ssim", "-f", "null", "-"]).stderr
        mm = re.search(r"All:([\d.]+) \(([\d.]+)\)", s)
        r["ssim_vs_master"] = float(mm.group(1)) if mm else None
        r["ssim_db_vs_master"] = float(mm.group(2)) if mm else None
    # luminance continuity: flag frame-to-frame brightness jumps
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-vf", "scale=64:36", "-f", "rawvideo", "-pix_fmt",
                          "gray", "-"], capture_output=True).stdout
    y = np.frombuffer(raw, np.uint8).reshape(-1, 36, 64).astype(np.float32)
    lum = y.mean((1, 2))
    d = np.abs(np.diff(lum))
    r["max_luma_jump"] = float(d.max())
    r["luma_jumps_over_12"] = [round(float(i + 1) / 30, 2) for i in np.nonzero(d > 12)[0]]
    checks = {
        "resolution": v["width"] == EXPECT["width"] and v["height"] == EXPECT["height"],
        "frame_rate": v["r_frame_rate"] == EXPECT["fps"],
        "all_frames_decode": r["decoded_frames"] == EXPECT["frames"],
        "duration": abs(r["duration_s"] - EXPECT["duration"]) < 0.05,
        "audio_present": bool(a) and a[0]["channels"] == 2,
        "audio_full_length": bool(a) and abs(float(a[0]["duration"]) - EXPECT["duration"]) < 0.1,
        "no_freezes": not r["freeze_segments"],
        "black_only_at_fades": all(b0 < 0.5 or b1 > EXPECT["duration"] - 1.2 for b0, b1 in r["black_segments"]),
    }
    r["checks"] = checks
    r["all_passed"] = all(checks.values())
    txt = json.dumps(r, indent=2)
    print(txt)
    if out:
        with open(out, "w") as fh:
            fh.write(txt)


if __name__ == "__main__":
    main()
