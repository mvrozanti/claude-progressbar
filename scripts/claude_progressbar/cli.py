import hashlib
import json
import os
import sys
import time

from .util import state_dir
from .parse import family, output_lines
from .procs import file_mtime, running_tasks
from .history import estimate, load_history, track
from .model import enrich, visible_tasks
from .styles.field import load_palette
from .styles import DEFAULT_STYLE, STYLES, rows
from .hud import columns, hud_command, hud_output


DEFAULT_ROWS = 3


def progress_rows(session, state_path, history_path, cols, max_rows, style=DEFAULT_STYLE, palette=None):
    now = time.time()
    tasks = running_tasks(session)
    spec = STYLES[style]
    finished = track(state_path, history_path, tasks, now, sizes=spec.samples_sizes)
    visible = visible_tasks(tasks, now)
    if spec.lingers:
        lingering = [{"key": d["key"], "family": family(d["key"]), "start": d["start"], "duration": d["duration"], "done": True} for d in finished]
        visible = sorted(visible + lingering, key=lambda t: t["start"])
    if not visible:
        return []
    exact, families = load_history(history_path)
    shown = [
        t if t.get("done") else enrich(t, output_lines(t["out"]), file_mtime(t["out"], t["start"]), exact, families)
        for t in visible[:max_rows]
    ]
    hidden = [{**t, "estimate": estimate(t, exact, families)} for t in visible[max_rows:]]
    return rows(shown, now, cols, hidden, style, palette)


USAGE = (
    "usage: statusline.py [--wrap CMD] [--max-rows N] [--style NAME] [--palette KITTY_COLORS]\n"
    f"  N >= 1, default {DEFAULT_ROWS}; NAME is one of {', '.join(STYLES)}, default {DEFAULT_STYLE}"
)


def options(argv):
    wrap, max_rows, style, palette = None, DEFAULT_ROWS, DEFAULT_STYLE, None
    pairs = []
    for arg in argv:
        if pairs and pairs[-1][1] is None:
            pairs[-1][1] = arg
        elif "=" in arg:
            pairs.append(arg.split("=", 1))
        else:
            pairs.append([arg, None])
    for flag, value in pairs:
        if flag == "--wrap":
            wrap = value or ""
        elif flag == "--max-rows" and value and value.isdigit() and int(value) > 0:
            max_rows = int(value)
        elif flag == "--style" and value in STYLES:
            style = value
        elif flag == "--palette" and value:
            palette = value
        else:
            sys.exit(USAGE)
    return wrap, max_rows, style, palette


def main():
    wrap, max_rows, style, palette_path = options(sys.argv[1:])
    palette = load_palette(palette_path) if STYLES[style].uses_palette else None
    raw = sys.stdin.read()
    try:
        data = json.loads(raw) if raw.strip() else {}
    except ValueError:
        data = {}
    session = str(data.get("session_id") or "default")
    slug = hashlib.sha1(session.encode()).hexdigest()[:16]
    runtime = state_dir("XDG_RUNTIME_DIR", f"/tmp/claude-progressbar-{os.getuid()}")
    cols = columns()
    lines = []
    command = hud_command(wrap)
    if command:
        hud = hud_output(command, raw, data, cols, os.path.join(runtime, f"hud-{slug}.json"))
        if hud:
            lines.append(hud)
    try:
        history = os.path.join(state_dir("XDG_STATE_HOME", os.path.expanduser("~/.local/state")), "history.jsonl")
        lines.extend(progress_rows(session, os.path.join(runtime, f"state-{slug}.json"), history, cols, max_rows, style, palette))
    except Exception:
        import traceback
        traceback.print_exc()
    sys.stdout.write("\n".join(lines))
