import glob
import hashlib
import json
import os
import re
import shutil
import time

from .util import read_json, write_atomic


HUD_MAX_AGE = 15


HUD_TIMEOUT = 3


def columns():
    try:
        fd = os.open("/dev/tty", os.O_RDONLY)
        try:
            cols = os.get_terminal_size(fd).columns
        finally:
            os.close(fd)
    except OSError:
        cols = int(os.environ.get("COLUMNS") or 124)
    return max(cols - 4, 20)


def version_key(path):
    return [int(p) if p.isdigit() else p for p in re.findall(r"\d+|\D+", path)]


def hud_command(wrap):
    if wrap != "claude-hud":
        return wrap or None
    base = os.environ.get("CLAUDE_CONFIG_DIR") or os.path.expanduser("~/.claude")
    entries = sorted(glob.glob(os.path.join(base, "plugins/cache/*/claude-hud/*/dist/index.js")), key=version_key)
    node = shutil.which("node")
    return [node, entries[-1]] if entries and node else None


def shell_argv(command):
    if isinstance(command, str) and os.name == "nt":
        sh = shutil.which("sh") or shutil.which("bash")
        if sh:
            return [sh, "-c", command]
    return command


def hud_output(command, raw, data, cols, cache_path):
    try:
        st = os.stat(data.get("transcript_path") or "")
        stamp = f"{st.st_mtime_ns}:{st.st_size}"
    except OSError:
        stamp = ""
    stable = json.dumps({k: v for k, v in data.items() if k != "cost"}, sort_keys=True)
    key = hashlib.sha1(f"{stable}|{stamp}|{cols}|{command}".encode()).hexdigest()
    cached = read_json(cache_path)
    if cached.get("key") == key and time.time() - cached.get("t", 0) < HUD_MAX_AGE:
        return cached.get("out", "")
    import subprocess
    try:
        argv = shell_argv(command)
        result = subprocess.run(
            argv,
            shell=isinstance(argv, str),
            input=raw,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=HUD_TIMEOUT,
            env={**os.environ, "COLUMNS": str(cols)},
        )
        out = result.stdout.rstrip("\n")
    except (OSError, subprocess.TimeoutExpired):
        return cached.get("out", "")
    write_atomic(cache_path, json.dumps({"key": key, "t": time.time(), "out": out}))
    return out
