import math
import time



SPINNER = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"


EIGHTHS = " ▏▎▍▌▋▊▉"


RESET = "\x1b[0m"


DIM = "\x1b[2m"


QUIET_AFTER = 30


def clock(seconds):
    s = int(max(seconds, 0))
    if s < 60:
        return f"{s}s"
    if s < 3600:
        return f"{s // 60}m{s % 60:02d}s"
    return f"{s // 3600}h{s % 3600 // 60:02d}m"


def clip(text, width):
    if width <= 0:
        return ""
    return text if len(text) <= width else text[:width - 1] + "…"


def jround(x):
    return math.floor(x + 0.5)


def clamp01(x):
    return min(max(x, 0.0), 1.0)


def spin(now):
    return SPINNER[int(now) % len(SPINNER)]


def mss(seconds):
    s = int(max(seconds, 0))
    h, m, x = s // 3600, s % 3600 // 60, s % 60
    return f"{h}:{m:02d}:{x:02d}" if h else f"{m}:{x:02d}"


def hhmm(epoch):
    return time.strftime("%H:%M", time.localtime(epoch))


def pad(text, width):
    return text + " " * max(0, width - len(text))


def lpad(text, width):
    return " " * max(0, width - len(text)) + text


def bounce_pos(width, now, size):
    span = max(width - size, 1)
    step = int(now * 2) % (2 * span)
    return step if step < span else 2 * span - step


def sgr(style):
    codes = []
    for token in style.split():
        if token == "b":
            codes.append("1")
        elif token == "dim":
            codes.append("2")
        elif token[:2] in ("F#", "B#"):
            r, g, b = (int(token[i:i + 2], 16) for i in (2, 4, 6))
            codes.append(f"{38 if token[0] == 'F' else 48};2;{r};{g};{b}")
        elif token[0] == "c":
            n = int(token[1:])
            codes.append(str(30 + n if n < 8 else 82 + n))
    return ";".join(codes)


def paint(spans, cols, keep_empty=False):
    out, left = [], cols
    for text, style in spans:
        if left is not None:
            if left <= 0:
                break
            text = text[:left]
            left -= len(text)
        if not text and not keep_empty:
            continue
        code = sgr(style)
        out.append(f"\x1b[{code}m{text}{RESET}" if code else text)
    return "".join(out)


def span_width(spans):
    return sum(len(text) for text, _ in spans)


def merge(cells):
    out = []
    for ch, style in cells:
        if out and out[-1][1] == style:
            out[-1] = (out[-1][0] + ch, style)
        else:
            out.append((ch, style))
    return out


def with_note(row, t, cols, quiet_style="c3", quiet_text=None, gap="  "):
    used = span_width(row)
    if t["quiet"] >= QUIET_AFTER:
        text = quiet_text(t) if quiet_text else f"quiet {clock(t['quiet'])}"
        return row + [(gap, ""), (text, quiet_style)] if used + len(gap) + len(text) <= cols else row
    text = clip(t.get("last") or "", cols - used - len(gap))
    return row + [(gap, ""), (text, "dim")] if text and used + len(gap) + len(text) <= cols else row


def split_eighths(fraction, width):
    cells = clamp01(fraction) * width
    full = int(cells)
    return full, int((cells - full) * 8) if full < width else 0


def between(low, high, per=None, scale=None):
    return lambda cols: max(low, min(high, cols // per if per else int(cols * scale)))
