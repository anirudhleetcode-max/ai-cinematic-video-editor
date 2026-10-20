"""Shared timeline, segmentation and palette for the doodle music edit."""
import os
import subprocess

import cv2
import numpy as np

FPS = 30
W, H = 1920, 1080
WORK = os.environ.get("EDIT_WORK", os.path.join(os.path.dirname(__file__), "..", "work"))
SOURCE = os.environ.get("EDIT_SOURCE", os.path.join(WORK, "source.mov"))
SLOWMO = os.path.join(WORK, "slowmo.mp4")

# Timeline (output frame numbers; output audio == source audio 1:1).
#   source frames 2393..2647 are a covered lens (dark/blurred hand) and
#   frames >= 3396 are a covered lens again, so they are never shown.
#   Output frames [SLOW_A, SLOW_B) show the hug scene (source 2648..3031,
#   384 frames) slowed to 639 frames with motion-compensated interpolation.
SLOW_A, SLOW_B = 2393, 3032
N_OUT = 3396
SCENE_CUTS = [0, SLOW_A, SLOW_B]

# Pastel palette (BGR)
PINK = (203, 182, 255)
LAVENDER = (250, 200, 215)
BABY_BLUE = (255, 216, 168)
MINT = (213, 245, 181)
YELLOW = (168, 241, 255)
PEACH = (164, 203, 255)
WHITE = (255, 255, 255)
CORAL = (140, 127, 255)
PURPLE = (255, 140, 190)
DARK_V = int(os.environ.get("EDIT_DARK_V", "58"))
PALETTE = [PINK, LAVENDER, BABY_BLUE, MINT, YELLOW, PEACH, WHITE]


def segments(a, b):
    """Split output range [a, b) into (file, start_frame, count) decode jobs."""
    out = []
    f = a
    while f < b:
        if f < SLOW_A:
            e = min(b, SLOW_A)
            out.append((SOURCE, f, e - f))
        elif f < SLOW_B:
            e = min(b, SLOW_B)
            out.append((SLOWMO, f - SLOW_A, e - f))
        else:
            e = b
            out.append((SOURCE, f, e - f))
        f = e
    return out


def read_frames(a, b, w=W, h=H):
    """Yield BGR frames of the output timeline for frames [a, b)."""
    for path, s, n in segments(a, b):
        vf = f"trim=start_frame={s}:end_frame={s + n},setpts=PTS-STARTPTS"
        if (w, h) != (W, H):
            vf += f",scale={w}:{h}:flags=area"
        p = subprocess.Popen(
            ["ffmpeg", "-v", "error", "-i", path, "-an", "-vf", vf,
             "-f", "rawvideo", "-pix_fmt", "bgr24", "-"],
            stdout=subprocess.PIPE, bufsize=w * h * 3 * 4)
        got = 0
        while got < n:
            buf = p.stdout.read(w * h * 3)
            if len(buf) < w * h * 3:
                break
            got += 1
            last_buf = buf
            yield np.frombuffer(buf, np.uint8).reshape(h, w, 3)
        p.stdout.close()
        p.wait()
        # minterpolate can end a few frames early: hold the last frame
        # (covered by the sparkle flash at the cut back to the singing).
        if path == SLOWMO and got and n - got <= 6:
            last = np.frombuffer(last_buf, np.uint8).reshape(h, w, 3)
            for _ in range(n - got):
                yield last
            got = n
        if got != n:
            raise RuntimeError(f"short read {path} start={s}: {got}/{n}")


def person_mask(small_bgr):
    """Person mask from a downscaled frame.

    The wall behind the singers is a flat, unsaturated grey, so anything
    saturated (skin, maroon tops) or dark (hair) is person.
    """
    sm = cv2.GaussianBlur(small_bgr, (5, 5), 0)
    hsv = cv2.cvtColor(sm, cv2.COLOR_BGR2HSV)
    m = ((hsv[..., 1] > 38) | (hsv[..., 2] < DARK_V)).astype(np.uint8) * 255
    k = max(3, small_bgr.shape[1] // 160) | 1
    m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE,
                         cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k * 3, k * 3)))
    n, lab, st, _ = cv2.connectedComponentsWithStats(m)
    keep = np.zeros_like(m)
    min_area = m.size * 0.02
    for i in range(1, n):
        if st[i, 4] > min_area:
            keep[lab == i] = 255
    pad = cv2.copyMakeBorder(keep, 1, 1, 1, 1, cv2.BORDER_CONSTANT, value=0)
    inv = 255 - pad
    cv2.floodFill(inv, None, (0, 0), 0)
    holes = inv[1:-1, 1:-1]
    # only fill small holes (white undershirt, eyes); big enclosed areas are
    # wall seen through an arm loop and must stay background
    n, lab, st, _ = cv2.connectedComponentsWithStats(holes)
    for i in range(1, n):
        if st[i, 4] > m.size * 0.012:
            holes[lab == i] = 0
    return keep | holes
