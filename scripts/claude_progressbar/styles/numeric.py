import math

from ..draw import estimate_tone, clamp01, clip, clock, hhmm, jround, lpad, merge, mss, pad, paint, spin, with_note
from .braille import dot_number


def digits_rows(t, now, cols, style, palette):
    w, lw, mode = style.gauge(cols), style.label(cols), t["mode"]
    num, style = dot_number(t)
    style = "" if mode == "estimate" else style
    if mode in ("parsed", "estimate"):
        full, half = divmod(int(clamp01(t["fraction"]) * w * 2), 2)
        ch = "╍" if mode == "estimate" else "━"
        bar = [(ch * full + ("╸" if half else ""), estimate_tone(t) if mode == "estimate" else "b c12"), ("━" * (w - full - half), "c8")]
    elif mode == "over":
        bar = [("━" * w, "b c11")]
    else:
        center = (now * 6) % (w + 10) - 5
        bar = merge([("━", "b c12" if abs(i - center) < 1.5 else "c12" if abs(i - center) < 4 else "c8") for i in range(w)])
    timing = mss(t["elapsed"])
    if mode in ("estimate", "over"):
        timing = f"{mss(t['elapsed'])} / ~{mss(t['est'])}"
    if mode == "parsed" and t.get("ratio"):
        timing = f"{t['ratio'][0]}/{t['ratio'][1]}  " + timing
    row = [(spin(now), "b c11" if mode == "over" else "c12"), (" ", ""), (lpad(num, 6), style), ("  ", "")]
    row += bar + [("  " + pad(clip(t["key"], lw), lw) + "  ", ""), (timing, "")]
    return [paint(with_note(row, t, cols, quiet_style="b c11", quiet_text=lambda x: "quiet " + mss(x["quiet"])), cols)]


def segments_rows(t, now, cols, style, palette):
    lw, n, mode = style.label(cols), style.gauge(cols), t["mode"]
    lit = -1 if t["fraction"] is None else int(clamp01(t["fraction"]) * n)
    march = int(now * 2) % n
    cells = []
    for i in range(n):
        if i and i % 5 == 0:
            cells.append((" ", ""))
        if mode == "unknown":
            cells.append(("■", "b c12") if i == march else ("□", "c8"))
        elif mode == "over":
            cells.append(("■", "b c11"))
        elif i < lit:
            cells.append(("▪", estimate_tone(t)) if mode == "estimate" else ("■", "b c12"))
        else:
            cells.append(("□", "c8"))
    if mode == "over":
        spill = min(5, math.ceil((t["elapsed"] / t["est"] - 1) * n))
        if spill > 0:
            cells += [(" ", ""), ("▸" * spill, "b c11")]
    pct, timing = "", clock(t["elapsed"])
    if mode == "parsed":
        pct = f"{jround(t['fraction'] * 100)}%"
    elif mode == "estimate":
        pct, timing = "?" if t.get("stale") else f"~{jround(t['fraction'] * 100)}%", timing + "/~" + clock(t["est"])
    elif mode == "over":
        pct, timing = f"+{jround((t['elapsed'] / t['est'] - 1) * 100)}%", timing + "/~" + clock(t["est"])
    row = [(spin(now), "b c11" if mode == "over" else "c12"), (" " + pad(clip(t["key"], lw), lw) + " ", "")]
    row += merge(cells) + [(" " + lpad(pct, 5), "b" if mode == "parsed" else "b c11" if mode == "over" else ""), (" " + timing, "")]
    return [paint(with_note(row, t, cols, quiet_style="b c11"), cols)]


def countdown_rows(t, now, cols, style, palette):
    lw, w, mode = style.label(cols), style.gauge(cols), t["mode"]
    remain = None
    if mode == "estimate" and not t.get("stale"):
        remain = t["est"] - t["elapsed"]
    elif mode == "parsed" and t["fraction"] >= 0.03 and t["elapsed"] >= 5:
        remain = t["elapsed"] * (1 - t["fraction"]) / t["fraction"]
    hero_style = "b"
    if remain is not None:
        hero = ("≈" if mode == "parsed" else "~") + f"{clock(remain)} left · ends {hhmm(now + remain)}"
    elif mode == "parsed":
        hero = "measuring rate…"
    elif t.get("stale"):
        hero, hero_style = f"no output for {clock(t['quiet'])} · usually {clock(t['est'])}", ""
    elif mode == "over":
        hero, hero_style = f"overdue {clock(t['elapsed'] - t['est'])} · usually {clock(t['est'])}", "b c11"
    else:
        hero, hero_style = f"running {clock(t['elapsed'])} · no estimate yet", ""
    if mode == "unknown":
        bar = [("┄" * w, "c8")]
    elif mode == "over":
        bar = [("─" * w, "c11")]
    else:
        keep = jround((1 - clamp01(t["fraction"])) * w)
        bar = [("─" * (w - keep), "c8"), ("━" * keep, "b c12")]
    pct = f"{jround(t['fraction'] * 100)}%" if mode == "parsed" else ("?" if t.get("stale") else f"~{jround(t['fraction'] * 100)}%") if mode == "estimate" else ""
    row = [(spin(now), "b c11" if "c11" in hero_style else "c12"), (" " + pad(clip(t["key"], lw), lw) + "  ", ""), (pad(hero, 32), hero_style), (" ", "")]
    row += bar + [(" " + lpad(pct, 4), "dim")]
    return [paint(with_note(row, t, cols, quiet_style="b c11"), cols)]
