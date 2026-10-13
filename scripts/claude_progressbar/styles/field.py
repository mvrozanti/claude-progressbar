import math
import os
import re

from ..draw import QUIET_AFTER, clamp01, clip, clock, jround, lpad, merge, pad, paint
from .braille import DOT


HEX = re.compile(r"#[0-9a-fA-F]{6}")


def rgb(code):
    return [int(code[i:i + 2], 16) for i in (1, 3, 5)]


def mix(a, b, t):
    return [x + (y - x) * t for x, y in zip(a, b)]


def q8(m):
    return jround(min(max(m, 0), 1) * 8) / 8


def wave(ms, period, offset=0.0):
    return 0.5 + 0.5 * math.sin((ms / period + offset) * math.pi * 2)


def q17(c):
    return [max(0, min(255, jround(v / 17) * 17)) for v in c]


def hexof(c):
    return "#" + "".join(f"{v:02x}" for v in q17(c))


def luminance(c):
    lin = [v / 255 / 12.92 if v / 255 <= 0.03928 else ((v / 255 + 0.055) / 1.055) ** 2.4 for v in q17(c)]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def ink_on(c):
    white = [255, 255, 255]
    ratio = (max(luminance(white), luminance(c)) + 0.05) / (min(luminance(white), luminance(c)) + 0.05)
    return white if ratio >= 4.5 else [14, 20, 22]


def hash3(x, y, seed):
    h = (x * 374761393 + y * 668265263 + seed * 982451653) & 0xFFFFFFFF
    h = ((h ^ (h >> 13)) * 1274126177) & 0xFFFFFFFF
    h ^= h >> 16
    return h / 4294967296


DEFAULT_PALETTE = {"run": rgb("#8b7cf6"), "done": rgb("#9bd8a8"), "over": rgb("#e6c46a"), "back": rgb("#000000")}


def load_palette(path):
    palette = dict(DEFAULT_PALETTE)
    if not path:
        return palette
    try:
        with open(os.path.expanduser(path), encoding="utf-8", errors="replace") as f:
            for line in f:
                parts = line.split()
                if len(parts) >= 2 and HEX.fullmatch(parts[1]):
                    if parts[0] == "color12":
                        palette["run"] = rgb(parts[1])
                    elif parts[0] == "background":
                        palette["back"] = rgb(parts[1])
    except OSError:
        pass
    return palette


def dot_field(width, spec, ms, back):
    track = mix(back, [128, 128, 128], 0.18)
    acc, done = spec["acc"], spec.get("done", False)
    light, grey = mix(acc, [255, 255, 255], 0.35), [120, 118, 128]
    fill = mix(track, acc, 0.3 if done else 0.17)
    lo, fx = spec.get("from", 0), spec["to"]
    span = max(1, fx - lo)
    cells = [[" ", None, fill if lo <= x + 0.5 < fx else track] for x in range(width)]
    twinkle = (3200, 3800, 4400, 3500) if done else (2200, 2800, 1900, 3300)
    delay, depth = (0, 700, 1300, 400), 0.2 if done else 0.55
    for col in range(max(0, math.floor(lo)), min(width, math.ceil(fx))):
        u = min(1, max(0, (col + 0.5 - lo) / span))
        dense = 0.8 if done else (0.22 + 0.78 * u ** 1.5) * (0.6 if spec.get("sparse") else 1)
        bits = 0
        for r in range(4):
            for c in range(2):
                sx = col * 2 + c
                if sx / 2 >= fx or sx / 2 < lo or hash3(sx, r, 1) > dense * 0.6:
                    continue
                bits |= DOT[c][r]
        if not bits:
            continue
        group = math.floor(hash3(col, 0, 2) * 4)
        blink = 1 - depth * wave(ms + delay[group], twinkle[group], 0.25)
        bucket = 1 if done else q8(min(1, u ** 0.9 * 1.1))
        cells[col] = [chr(0x2800 + bits), mix(fill, mix(grey, light, bucket), q8((0.35 + 0.65 * dense) * blink)), fill]
    if spec.get("marks"):
        for m in (0.25, 0.5, 0.75):
            x = jround(m * width)
            if 0 < x < width - 1:
                cells[x] = ["│", mix(light, [255, 255, 255], 0.5) if x < fx - 0.5 else mix(track, [255, 255, 255], 0.3), cells[x][2]]
    if spec.get("pill"):
        text, color = spec["pill"]
        kw = len(text) + 2
        kx = jround(max(0, min(width - kw, fx - kw / 2)))
        ink = ink_on(color)
        for x in range(kx, min(width, kx + kw)):
            cells[x] = [" ", None, color]
        for i, ch in enumerate(text):
            if kx + 1 + i < width:
                cells[kx + 1 + i] = [ch, ink, color]
    return merge([(ch, ("F" + hexof(fg) + " " if fg else "") + "B" + hexof(bg)) for ch, fg, bg in cells])


def field_spec(t, width, ms, palette):
    track = mix(palette["back"], [128, 128, 128], 0.18)
    roomy, mode = width >= 46, t["mode"]
    if mode == "done":
        return {"to": width, "acc": palette["done"], "done": True, "marks": True, "pill": ("✓ " + clock(t["elapsed"]), palette["done"]), "right": "100%", "style": "F" + hexof(palette["done"])}
    if mode == "over":
        pill = "+" + clock(t["elapsed"] - t["est"]) + (" past ~" + clock(t["est"]) if roomy else "")
        return {"to": width, "acc": palette["over"], "marks": True, "pill": (pill, palette["over"]), "right": f"+{jround((t['elapsed'] / t['est'] - 1) * 100)}%", "style": "b F" + hexof(palette["over"])}
    if mode == "unknown":
        span = width * 0.32
        head = span + (width - span) * (0.5 - 0.5 * math.cos(ms / 2400 * math.pi))
        return {"from": head - span, "to": head, "acc": palette["run"], "pill": (clock(t["elapsed"]), mix(palette["run"], track, 0.35)), "right": "—", "style": "dim"}
    to = clamp01(t["fraction"]) * width
    if mode == "estimate":
        pill = f"{clock(t['elapsed'])} / ~{clock(t['est'])}" if roomy else "~" + clock(t["est"] - t["elapsed"])
        return {"to": to, "acc": palette["run"], "sparse": True, "marks": True, "pill": (pill, mix(palette["run"], track, 0.45)), "right": "?" if t.get("stale") else f"~{jround(t['fraction'] * 100)}%", "style": "dim" if t.get("stale") else ""}
    src = t.get("src") or ""
    pill = f"{t['ratio'][0]}/{t['ratio'][1]}" if t.get("ratio") else clock(t["elapsed"])
    return {"to": to, "acc": palette["run"], "marks": True, "pill": (pill, palette["run"]), "right": src if src.endswith("%") else f"{t['fraction'] * 100:.1f}%", "style": "b"}


def field_rows(t, now, cols, style, palette):
    ms = math.floor(now) * 1000
    lw = style.label(cols)
    width = style.gauge(cols)
    spec, mode = field_spec(t, width, ms, palette), t["mode"]
    dot = palette["done"] if mode == "done" else palette["over"] if mode == "over" else mix(palette["run"], [255, 255, 255], 0.3 * wave(ms, 1100))
    bar = [("✓ " if mode == "done" else "● ", "F" + hexof(dot)), (pad(clip(t["key"], lw), lw) + "  ", "")]
    bar += dot_field(width, spec, ms, palette["back"]) + [(" " + lpad(spec["right"], 6), spec["style"])]
    indent = " " * (lw + 4)
    if mode != "done" and t["quiet"] >= QUIET_AFTER:
        strip = [(indent + "⎿ ", ""), ("quiet " + clock(t["quiet"]), "F" + hexof(palette["over"]))]
    else:
        strip = [(indent + "⎿ ", "dim"), (clip("finished" if mode == "done" else (t.get("last") or ""), width), "dim")]
    return [paint(bar, cols), paint(strip, cols)]
