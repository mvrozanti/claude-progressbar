#!/usr/bin/env python3
import argparse
import math
import os
import sys
import time

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from claude_progressbar.draw import paint
from claude_progressbar.parse import family
from claude_progressbar.styles import DEFAULT_STYLE, STYLES, rows

TOUR = [
    ("rise", "braille cells that fill bottom-up over a dotted floor (the default)"),
    ("field", "a twinkling dot field with a pill riding the head"),
    ("dots", "every dot of the grid visible, dim until lit"),
    ("rail", "a solid fill riding a dotted rail"),
    ("graph", "how much the command printed, over its run"),
    ("digits", "the number first, then a thin line"),
    ("ruler", "eighth-blocks with quarter ticks"),
    ("segments", "twenty squares you can count"),
    ("countdown", "time left and the clock time it ends"),
    ("history", "this run against its past durations"),
    ("today", "the original eighth-block bar"),
]

SCENARIO = [
    {"key": "nixos-rebuild switch --flake .#desktop", "offset": 34, "kind": "estimate", "estimate": 71.0, "samples": [64.0, 71.0, 88.0], "length": 74.0},
    {"key": "rsync -a --info=progress2 ~/Music/ /mnt/backup/", "offset": 21, "kind": "percent", "length": 58.0},
    {"key": "cargo build --release", "offset": 9, "kind": "ratio", "total": 312, "length": 44.0},
    {"key": "./scripts/smoke.sh", "offset": 52, "kind": "estimate", "estimate": 46.0, "samples": [42.0, 46.0, 51.0], "length": 63.0},
    {"key": "fd -H -g '*.kra' /", "offset": 37, "kind": "silent", "length": 90.0},
]

NIX_LINES = [
    "evaluating derivation 'path:/etc/nixos#nixosConfigurations.desktop'",
    "building '/nix/store/s4k79nirdm68337hghwd3932zrqiz8n3-system-path.drv'...",
    "building '/nix/store/j2230ns5mjzl2p0s4zab4n23a6dlznz2-system-units.drv'...",
    "building '/nix/store/0lkcp26ba4zsyrj1azq1kd2q9szy5kb7-etc.drv'...",
    "activating the configuration...",
]
SMOKE_LINES = ["==> preflight", "==> render e3", "==> render e6", "==> mixing", "==> writing report"]
CRATES = ["proc-macro2", "syn", "serde_derive", "tokio", "hyper", "serde_json", "ratatui", "crossterm", "clap_derive", "reqwest"]


def noise(x):
    s = math.sin(x * 12.9898) * 43758.5453
    return s - math.floor(s)


def task_at(spec, clock_now, sim):
    elapsed = (sim + spec["offset"]) % spec["length"]
    start = clock_now - elapsed
    task = {"key": spec["key"], "family": family(spec["key"]), "start": start, "mtime": clock_now - 1, "progress": None,
            "src": None, "ratio": None, "estimate": spec.get("estimate"), "samples": spec.get("samples", []), "last": ""}
    fraction = min(1.0, elapsed / spec["length"])
    if spec["kind"] == "percent":
        pct = int(fraction * 100)
        left = max(0, spec["length"] - elapsed)
        task.update(progress=pct / 100, src=f"{pct}%", last=f"{int(fraction * 1084337152):>15,} {pct:>3}%   {22 + 4 * math.sin(elapsed / 7):.2f}MB/s    0:{int(left // 60):02d}:{int(left % 60):02d}")
    elif spec["kind"] == "ratio":
        done = min(spec["total"], int(spec["total"] * fraction ** 1.15))
        bar = int(done / spec["total"] * 27)
        crates = f"{CRATES[int(elapsed / 4) % len(CRATES)]}, {CRATES[(int(elapsed / 4) + 5) % len(CRATES)]}"
        task.update(progress=done / spec["total"], src=f"{done}/{spec['total']}", ratio=(done, spec["total"]),
                    last=f"    Building [{'=' * max(0, bar - 1)}{'>' if bar else ''}{' ' * (27 - bar)}] {done}/{spec['total']}: {crates}")
    elif spec["kind"] == "estimate":
        lines = NIX_LINES if spec["key"].startswith("nixos") else SMOKE_LINES
        task["last"] = lines[min(len(lines) - 1, int(fraction * len(lines)))]
    else:
        task["mtime"] = start
    task["sizes"] = [[start + s, sum(int(400 * noise(i) ** 2) for i in range(int(s)))] for s in range(0, int(elapsed) + 1, 2)]
    return task


def frame(style, sim, cols, max_rows, caption):
    clock_now = time.time()
    tasks = sorted((task_at(spec, clock_now, sim) for spec in SCENARIO), key=lambda t: t["start"])
    shown, hidden = tasks[:max_rows], [{**t, "estimate": t.get("estimate")} for t in tasks[max_rows:]]
    lines = []
    if caption:
        name, text = caption
        lines += [paint([("  --style ", "dim"), (name, "b c12"), ("   " + text, "dim")], cols + 2), ""]
    lines += ["  " + row for row in rows(shown, clock_now, cols, hidden, style)]
    return lines


def card(lines, cols):
    return [""] + [" " * max(0, (cols - len(text)) // 2) + paint([(text, style)], cols) for text, style in lines]


def play(frames_for, seconds, fps):
    end = time.time() + seconds
    while time.time() < end:
        out = frames_for(time.time())
        sys.stdout.write("\x1b[H" + "\x1b[K\n".join(out) + "\x1b[K\x1b[J")
        sys.stdout.flush()
        time.sleep(1 / fps)


def main():
    parser = argparse.ArgumentParser(description="Replay claude-progressbar on a simulated set of running commands.")
    parser.add_argument("--style", default=DEFAULT_STYLE, choices=list(STYLES))
    parser.add_argument("--tour", action="store_true", help="show every style in turn, with title and end cards")
    parser.add_argument("--cols", type=int, default=116)
    parser.add_argument("--rows", type=int, default=5)
    parser.add_argument("--seconds", type=float, default=20.0)
    parser.add_argument("--speed", type=float, default=3.0)
    parser.add_argument("--fps", type=float, default=12.0)
    args = parser.parse_args()
    began = time.time()
    sim = lambda now: (now - began) * args.speed
    sys.stdout.write("\x1b[?25l\x1b[2J")
    try:
        if not args.tour:
            play(lambda now: frame(args.style, sim(now), args.cols, args.rows, None), args.seconds, args.fps)
            return
        title = [("claude-progressbar", "b c12"), ("", ""), ("progress bars for the commands Claude Code runs", ""), ("", ""), ("parsed from their output · estimated from past runs · animated when unknown", "dim")]
        play(lambda now: card(title, args.cols), 3.0, args.fps)
        for name, text in TOUR:
            play(lambda now, name=name, text=text: frame(name, sim(now), args.cols, args.rows, (name, text)), 2.6, args.fps)
        ending = [("claude-progressbar", "b c12"), ("", ""), ("a Claude Code plugin · Linux · Python 3.9+", "dim"), ("", ""), ("github.com/mvrozanti/claude-progressbar", "b")]
        play(lambda now: card(ending, args.cols), 3.5, args.fps)
    finally:
        sys.stdout.write("\x1b[?25h\n")


if __name__ == "__main__":
    main()
