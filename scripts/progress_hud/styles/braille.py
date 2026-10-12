import math

from ..draw import bounce_pos, clamp01, clip, clock, jround, lpad, merge, pad, paint, spin, with_note


DOT = ((0x01, 0x02, 0x04, 0x40), (0x08, 0x10, 0x20, 0x80))


def braille(pred):
    bits = 0
    for c in (0, 1):
        for r in range(4):
            if pred(c, r):
                bits |= DOT[c][r]
    return chr(0x2800 + bits)


FULL = braille(lambda c, r: True)


def rise_order(c, r):
    return c * 4 + (3 - r)


def dot_number(t):
    if t["mode"] == "parsed":
        src = t.get("src") or ""
        return (src if src.endswith("%") else f"{t['fraction'] * 100:.1f}%"), "b"
    if t["mode"] == "estimate":
        return f"~{jround(t['fraction'] * 100)}%", ""
    if t["mode"] == "over":
        return f"+{jround((t['elapsed'] / t['est'] - 1) * 100)}%", "b c11"
    return "—", "dim"


def dot_row(t, now, cols, style, gauge):
    lw = style.label(cols)
    num, style = dot_number(t)
    timing = clock(t["elapsed"])
    if t["mode"] in ("estimate", "over"):
        timing += "/~" + clock(t["est"])
    if t["mode"] == "parsed" and t.get("ratio"):
        timing = f"{t['ratio'][0]}/{t['ratio'][1]} · " + timing
    row = [(spin(now), "b c11" if t["mode"] == "over" else "c12"), (" " + pad(clip(t["key"], lw), lw) + " ", "")]
    row += gauge + [(" ", ""), (lpad(num, 6), style), ("  " + timing, "")]
    return [paint(with_note(row, t, cols, quiet_style="b c11"), cols)]


def rise_gauge(t, now, w):
    if t["mode"] == "unknown":
        cells = []
        for i in range(w):
            h = max(1, jround(2 + 2 * math.sin((i - now * 4) / 2)))
            cells.append((braille(lambda c, r, h=h: r >= 4 - h), "b c12" if h >= 4 else "c12"))
        return merge(cells)
    if t["mode"] == "over":
        return [(FULL * w, "b c11")]
    est = t["mode"] == "estimate"
    per = 4 if est else 8
    steps = int(clamp01(t["fraction"]) * w * per)
    order = (lambda c, r: c * 2 + (3 - r) if r >= 2 else 99) if est else rise_order
    floor = braille(lambda c, r: r == 3)
    cells = []
    for i in range(w):
        local = min(per, max(0, steps - i * per))
        if local:
            cells.append((braille(lambda c, r, local=local: order(c, r) < local), "c12" if est else "b c12"))
        else:
            cells.append((floor, "c8"))
    return merge(cells)


def matrix_gauge(t, now, w):
    quarter = {jround(q * w) - 1 for q in (0.25, 0.5, 0.75)}
    cells = [(FULL, "dim" if i in quarter else "c8") for i in range(w)]
    if t["mode"] == "unknown":
        head = int(now * 3) % (w + 4) - 1
        trail = (FULL, braille(lambda c, r: r >= 1), braille(lambda c, r: r >= 2), braille(lambda c, r: r >= 3))
        for k, ch in enumerate(trail):
            if 0 <= head - k < w:
                cells[head - k] = (ch, "c12" if k else "b c12")
        return merge(cells)
    if t["mode"] == "over":
        return [(FULL * w, "b c11")]
    est = t["mode"] == "estimate"
    steps = int(clamp01(t["fraction"]) * w * 8)
    for i in range(w):
        local = min(8, max(0, steps - i * 8))
        if not local:
            break
        lit = braille(lambda c, r, local=local: rise_order(c, r) < local and (not est or (c + r) % 2 == 0))
        cells[i] = (lit, "c12" if est else "b c12")
    return merge(cells)


def rail_gauge(t, now, w):
    cells = [(braille(lambda c, r: r == 2), "c8") for _ in range(w)]
    if t["mode"] == "unknown":
        cells[bounce_pos(w, now, 1)] = (FULL, "b c12")
        return merge(cells)
    if t["mode"] == "over":
        return [(FULL * w, "b c11")]
    est = t["mode"] == "estimate"
    style = "c12" if est else "b c12"
    full, half = divmod(int(clamp01(t["fraction"]) * w * 2), 2)
    for i in range(full):
        cells[i] = (braille(lambda c, r: not est or r in (1, 2)), style)
    if half and full < w:
        cells[full] = (braille(lambda c, r: c == 0 and (not est or r in (1, 2))), style)
    return merge(cells)


def size_curve(t):
    trail = t.get("sizes") or []
    if len(trail) < 2:
        return None

    def at(x):
        if x <= trail[0][0]:
            return trail[0][1]
        for (t0, s0), (t1, s1) in zip(trail, trail[1:]):
            if x <= t1:
                return s0 + (s1 - s0) * (x - t0) / max(t1 - t0, 1e-6)
        return trail[-1][1]
    return at


def graph_gauge(t, now, w):
    mode = t["mode"]
    if mode == "parsed":
        span = t["elapsed"] / max(t["fraction"], 0.02)
    elif mode in ("estimate", "over"):
        span = max(t["est"], t["elapsed"])
    else:
        span = max(t["elapsed"] * 1.25, 30)
    n, curve, rates = w * 2, size_curve(t), []
    for j in range(n):
        t0, t1 = j / n * span, (j + 1) / n * span
        if t0 >= t["elapsed"]:
            rates.append(None)
            continue
        top = min(t1, t["elapsed"])
        rates.append(0.0 if curve is None else max(0.0, (curve(t["start"] + top) - curve(t["start"] + t0)) / max(top - t0, 1e-6)))
    peak = max([r for r in rates if r is not None] or [0]) or 1
    heights = [-1 if r is None else 1 + jround(min(1, r / peak) * 3) for r in rates]
    cells = []
    for i in range(w):
        hs = heights[i * 2:i * 2 + 2]
        if all(h < 0 for h in hs):
            style = "c8"
        elif mode == "over" and i * 2 / n * span >= t["est"]:
            style = "b c11"
        else:
            style = "b c12" if mode == "parsed" else "c12"
        cells.append((braille(lambda c, r, hs=hs: r == 3 if hs[c] < 0 else r >= 4 - hs[c]), style))
    return merge(cells)
