from collections import namedtuple

from ..draw import DIM, RESET, between, hhmm, paint
from ..model import facts
from .blocks import history_rows, render, ruler_rows
from .braille import dot_row, graph_gauge, matrix_gauge, rail_gauge, rise_gauge
from .numeric import countdown_rows, digits_rows, segments_rows
from .field import DEFAULT_PALETTE, field_rows


DEFAULT_STYLE = "rise"


def plain_overflow(hidden, now, cols):
    return [f"{DIM}  +{len(hidden)} more running{RESET}"]


def names_overflow(hidden, now, cols):
    return [paint([(f"  +{len(hidden)} more · " + ", ".join(h["key"] for h in hidden), "dim")], cols)]


def countdown_overflow(hidden, now, cols):
    ends = sorted(h["start"] + h["estimate"] for h in hidden if h.get("estimate") and now - h["start"] <= h["estimate"])
    tail = f" · next ends ~{hhmm(ends[0])}" if ends else " · " + ", ".join(h["key"] for h in hidden)
    return [paint([(f"  +{len(hidden)} more" + tail, "dim")], cols)]


Style = namedtuple("Style", "draw overflow label gauge samples_sizes lingers uses_palette")
DOT_LABEL = between(12, 40, per=4)
FIELD_LABEL = between(12, 34, scale=0.22)


def braille_style(gauge):
    return Style(
        lambda t, now, cols, style, palette: dot_row(t, now, cols, style, gauge(t, now, style.gauge(cols))),
        names_overflow, DOT_LABEL, between(8, 30, per=5), gauge is graph_gauge, False, False,
    )


STYLES = {
    "rise": braille_style(rise_gauge),
    "dots": braille_style(matrix_gauge),
    "rail": braille_style(rail_gauge),
    "graph": braille_style(graph_gauge),
    "field": Style(field_rows, names_overflow, FIELD_LABEL, lambda cols: max(14, cols - FIELD_LABEL(cols) - 11), False, True, True),
    "today": Style(render, plain_overflow, between(12, 48, per=4), between(6, 24, per=5), False, False, False),
    "ruler": Style(ruler_rows, plain_overflow, between(12, 40, per=4), between(10, 32, per=5), False, False, False),
    "digits": Style(digits_rows, names_overflow, between(12, 44, per=4), between(12, 40, per=4), False, False, False),
    "segments": Style(segments_rows, names_overflow, between(12, 40, per=4), lambda cols: 20 if cols >= 90 else 10, False, False, False),
    "countdown": Style(countdown_rows, countdown_overflow, between(12, 36, per=4), between(10, 24, per=6), False, False, False),
    "history": Style(history_rows, names_overflow, between(12, 36, per=4), between(16, 36, per=4), False, False, False),
}


def rows(tasks, now, cols, hidden, style, palette=None):
    spec = STYLES[style]
    out = [line for t in tasks for line in spec.draw(facts(t, now), now, cols, spec, palette or DEFAULT_PALETTE)]
    if hidden:
        out.extend(spec.overflow(hidden, now, cols))
    return out
