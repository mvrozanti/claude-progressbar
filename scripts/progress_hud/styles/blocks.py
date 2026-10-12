from ..history import median
from ..draw import EIGHTHS, QUIET_AFTER, bounce_pos, clamp01, clip, clock, jround, lpad, merge, pad, paint, span_width, spin, split_eighths, with_note


TONE = {"parsed": "c2", "estimate": "c6", "over": "c3", "unknown": "c5"}


def today_gauge(fraction, width, now, tone):
    if fraction is None:
        size = min(3, width)
        pos = bounce_pos(width, now, size)
        return [("░" * pos, "dim"), ("█" * size, tone), ("░" * (width - pos - size), "dim")]
    full, partial = split_eighths(fraction, width)
    used = full + (1 if partial else 0)
    return [("█" * full + (EIGHTHS[partial] if partial else ""), tone), ("░" * (width - used), "dim")]


def render(task, now, cols, style, palette=None):
    elapsed = now - task["start"]
    expected = task["estimate"]
    if task["progress"] is not None:
        mode, fraction, percent, timing = "parsed", task["progress"], f"{task['progress'] * 100:3.0f}%", clock(elapsed)
    elif expected and elapsed <= expected:
        fraction = elapsed / expected
        mode, percent, timing = "estimate", f"~{fraction * 100:.0f}%", f"{clock(elapsed)}/~{clock(expected)}"
    elif expected:
        mode, fraction, percent, timing = "over", 1.0, "", f"{clock(elapsed)} +{clock(elapsed - expected)}"
    else:
        mode, fraction, percent, timing = "unknown", None, "", clock(elapsed)
    tone = TONE[mode]
    stats = " ".join(s for s in (percent, timing) if s)
    row = [(spin(now), tone), (" " + clip(task["key"], style.label(cols)) + " ", "")]
    row += today_gauge(fraction, style.gauge(cols), now, tone) + [(" " + stats, "")]
    used = span_width(row)
    quiet = now - task["mtime"]
    if quiet >= QUIET_AFTER:
        note, note_style = f"quiet {clock(quiet)}", "c3"
    else:
        note, note_style = clip(task["last"], cols - used - 2), "dim"
    if note and used + 2 + len(note) <= cols:
        row += [("  ", ""), (note, note_style)]
    return [paint(row, None, keep_empty=True)]


def ruler_rows(t, now, cols, style, palette):
    lw, w, mode = style.label(cols), style.gauge(cols), t["mode"]
    ticks = {jround(q * w) - 1 for q in (0.25, 0.5, 0.75)}
    cells = [("┆" if i in ticks else "·", "dim") for i in range(w)]
    fill = {"parsed": "b c12", "estimate": "c12", "over": "b c11", "unknown": "b c12"}[mode]
    cap = ("▏", "dim")
    if t["fraction"] is None:
        p = bounce_pos(w, now, 3)
        for i in range(p, min(p + 3, w)):
            cells[i] = ("▒", fill)
    else:
        full, part = split_eighths(t["fraction"], w)
        for i in range(full):
            cells[i] = ("▓" if mode == "estimate" else "█", fill)
        if part:
            cells[full] = (EIGHTHS[part], fill)
        if mode == "over":
            cap = ("▶", "b c11")
    pct, timing = "", clock(t["elapsed"])
    if mode == "parsed":
        pct = f"{t['fraction'] * 100:.1f}%"
    elif mode == "estimate":
        pct, timing = f"~{jround(t['fraction'] * 100)}%", f"{clock(t['elapsed'])} of ~{clock(t['est'])}"
    elif mode == "over":
        pct, timing = f"+{jround((t['elapsed'] / t['est'] - 1) * 100)}%", f"{clock(t['elapsed'])} (~{clock(t['est'])})"
    row = [(spin(now), "b c11" if mode == "over" else "c12"), (" " + pad(clip(t["key"], lw), lw) + " ", ""), ("▕", "dim")]
    row += merge(cells) + [cap, (" ", ""), (lpad(pct, 6), "b c11" if mode == "over" else ("b" if mode == "parsed" else "")), (" " + timing, "")]
    return [paint(with_note(row, t, cols, quiet_style="b c11"), cols)]


def history_rows(t, now, cols, style, palette):
    lw, w, mode = style.label(cols), style.gauge(cols), t["mode"]
    xs = t.get("samples") or []
    med = median(xs) if xs else None
    lo, hi = (min(xs), max(xs)) if xs else (None, None)
    if mode == "parsed":
        cells = [("─", "c8") for _ in range(w)]
        full, part = split_eighths(t["fraction"], w)
        for i in range(full):
            cells[i] = ("█", "b c12")
        if part:
            cells[full] = (EIGHTHS[part], "b c12")
        pace = min(1, t["elapsed"] / med) if med else None
        if pace is not None:
            cells[min(w - 1, jround(pace * w))] = ("┃", "b c11")
        src = t.get("src") or ""
        summary = (src if src.endswith("%") else f"{t['fraction'] * 100:.1f}%")
        summary += f" · usual pace {jround(pace * 100)}% " + ("▲ ahead" if t["fraction"] >= pace else "▼ behind") if pace is not None else " · first run, no pace yet"
    else:
        span = max(hi or 0, t["elapsed"], 30 if mode == "unknown" else 0) * (1.25 if mode == "unknown" else 1.15)
        cells = []
        for i in range(w):
            ti = (i + 0.5) / w * span
            inside = bool(xs) and lo <= ti <= hi
            cells.append(("─", "c8") if inside else ("·", "dim"))
        fill = "b c11" if mode == "over" else "b c12"
        full, part = split_eighths(t["elapsed"] / span, w)
        for i in range(full):
            cells[i] = ("█", fill)
        if part:
            cells[full] = (EIGHTHS[part], fill)
        if med:
            cells[min(w - 1, int(med / span * w))] = ("┃", "b c11")
        if mode == "estimate":
            summary = f"{clock(t['elapsed'])} · usual {clock(med)} ({clock(lo)}–{clock(hi)}, {len(xs)} run{'s' if len(xs) > 1 else ''})"
        elif mode == "over":
            summary = f"{clock(t['elapsed'])} · {clock(t['elapsed'] - med)} past usual" + (" · longest yet" if t["elapsed"] > hi else "") if med else f"{clock(t['elapsed'])} · over"
        else:
            summary = f"{clock(t['elapsed'])} · first run, recording"
    row = [(spin(now), "b c11" if mode == "over" else "c12"), (" " + pad(clip(t["key"], lw), lw) + " ", ""), ("▕", "dim")]
    row += merge(cells) + [("▏", "dim"), (" " + summary, "c11" if mode == "over" else "")]
    return [paint(with_note(row, t, cols, quiet_style="b c11"), cols)]
