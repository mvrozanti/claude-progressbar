#!/usr/bin/env python3
import hashlib
import json
import os
import sys
import time

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))

from claude_progressbar.styles import STYLES, rows


def digest(lines):
    return hashlib.sha256("\n".join(lines).encode()).hexdigest()[:20]


def cases(inputs):
    for style in STYLES:
        for task_name, task in inputs["tasks"].items():
            if task.get("done") and style != "field":
                continue
            for palette_name, palette in inputs["palettes"].items():
                if palette_name != "default" and style != "field":
                    continue
                for cols in inputs["cols"]:
                    for now in inputs["nows"]:
                        t = {**task, "ratio": tuple(task["ratio"]) if task.get("ratio") else task.get("ratio")}
                        yield f"{style}|{task_name}|{palette_name}|{cols}|{now}", lambda t=t, now=now, cols=cols, style=style, palette=palette: rows([t], now, cols, [], style, palette)
        for cols in inputs["cols"]:
            yield f"{style}|overflow|{cols}", lambda cols=cols, style=style: rows([], 1045.0, cols, inputs["hidden"], style)


def computed():
    with open(os.path.join(HERE, "golden_inputs.json")) as f:
        inputs = json.load(f)
    local = time.localtime
    time.localtime = time.gmtime
    try:
        return {key: digest(draw()) for key, draw in cases(inputs)}
    finally:
        time.localtime = local


if __name__ == "__main__":
    goldens = computed()
    with open(os.path.join(HERE, "goldens.json"), "w") as f:
        json.dump(goldens, f, indent=0, sort_keys=True)
    print(f"{len(goldens)} golden cases written")
