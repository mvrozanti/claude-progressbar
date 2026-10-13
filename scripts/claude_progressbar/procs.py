import os
import re
import shlex

from . import system
from .parse import family, normalize


TASK_OUTPUT = re.compile(r"[\\/]tasks[\\/][^\\/]+\.output$")


SCRIPT_FLAG = re.compile(r"-[a-z]{0,2}c[a-z]{0,2}|-command", re.IGNORECASE)


ANCESTRY = 8


SYSTEM = system.load()


def program(path):
    name = re.split(r"[\\/]", path)[-1].lower()
    return name[:-4] if name.endswith(".exe") else name


def is_claude(backend, pid, name):
    if program(name) == "claude":
        return True
    try:
        argv = backend.argv(pid)
    except OSError:
        return False
    return any(program(a) in ("claude", "cli.js") for a in argv[:2])


def claude_ancestor(backend, pid):
    for _ in range(ANCESTRY):
        if pid <= 1:
            return None
        try:
            name, ppid, _ = backend.info(pid)
        except OSError:
            return None
        if is_claude(backend, pid, name):
            return pid
        pid = ppid
    return None


def shell_script(argv):
    flagged = False
    for arg in argv[1:]:
        if not arg.startswith("--") and SCRIPT_FLAG.fullmatch(arg):
            flagged = True
        elif flagged and not arg.startswith("-"):
            return arg
    return None


def extract_command(argv):
    script = shell_script(argv)
    if script is None:
        return " ".join(argv)
    try:
        tokens = shlex.split(script)
    except ValueError:
        tokens = []
    if "eval" in tokens:
        i = tokens.index("eval")
        if i + 1 < len(tokens):
            return tokens[i + 1]
    return script


def in_session(path, session):
    return re.search(rf"[\\/]{re.escape(session)}[\\/]", path) is not None


def running_tasks(session, backend=SYSTEM, start=None):
    if backend is None:
        return []
    owner = claude_ancestor(backend, os.getppid() if start is None else start)
    pids = backend.everyone() if owner is None else backend.children(owner)
    found = {}
    for pid in pids:
        try:
            path = backend.stdout(pid)
        except OSError:
            continue
        if not TASK_OUTPUT.search(path):
            continue
        try:
            _, ppid, began = backend.info(pid)
            argv = backend.argv(pid)
        except OSError:
            continue
        mine = ppid == owner if owner is not None else in_session(path, session)
        if not mine:
            continue
        if path in found and found[path]["start"] <= began:
            continue
        key = normalize(extract_command(argv))
        found[path] = {"pid": str(pid), "out": path, "start": began, "key": key, "family": family(key)}
    return list(found.values())


def file_size(path):
    try:
        return os.stat(path).st_size
    except OSError:
        return 0


def file_mtime(path, fallback):
    try:
        return os.stat(path).st_mtime
    except OSError:
        return fallback
