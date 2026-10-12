import os
import re
import shlex

from .parse import family, normalize


TASK_OUTPUT = re.compile(r"/tasks/[^/]+\.output(?: \(deleted\))?$")


def proc_stat(pid):
    with open(f"/proc/{pid}/stat") as f:
        data = f.read()
    close = data.rindex(")")
    rest = data[close + 2:].split()
    return data[data.index("(") + 1:close], int(rest[1]), int(rest[19])


def proc_argv(pid):
    with open(f"/proc/{pid}/cmdline", "rb") as f:
        return [a.decode("utf-8", "replace") for a in f.read().split(b"\0") if a]


def boot_time():
    with open("/proc/stat") as f:
        for line in f:
            if line.startswith("btime "):
                return int(line.split()[1])
    return 0


def is_claude(pid, comm):
    if comm == "claude":
        return True
    try:
        argv = proc_argv(pid)
    except OSError:
        return False
    return any(os.path.basename(a) in ("claude", "cli.js") for a in argv[:2])


def claude_ancestor():
    pid = os.getppid()
    for _ in range(8):
        if pid <= 1:
            return None
        try:
            comm, ppid, _ = proc_stat(pid)
        except OSError:
            return None
        if is_claude(pid, comm):
            return pid
        pid = ppid
    return None


def extract_command(argv):
    if len(argv) >= 3 and argv[1] == "-c":
        try:
            tokens = shlex.split(argv[2])
        except ValueError:
            tokens = []
        if "eval" in tokens:
            i = tokens.index("eval")
            if i + 1 < len(tokens):
                return tokens[i + 1]
        return argv[2]
    return " ".join(argv)


def children_of(owner):
    pids = []
    for tid in os.listdir(f"/proc/{owner}/task"):
        try:
            with open(f"/proc/{owner}/task/{tid}/children") as f:
                pids.extend(f.read().split())
        except OSError:
            continue
    return pids


def all_processes():
    return [name for name in os.listdir("/proc") if name.isdigit()]


def running_tasks(session):
    if not os.path.isdir("/proc"):
        return []
    owner = claude_ancestor()
    pids = all_processes() if owner is None else children_of(owner)
    ticks = os.sysconf("SC_CLK_TCK")
    btime = boot_time()
    found = {}
    for name in pids:
        try:
            target = os.readlink(f"/proc/{name}/fd/1")
        except OSError:
            continue
        if not TASK_OUTPUT.search(target):
            continue
        try:
            _, ppid, start = proc_stat(name)
            argv = proc_argv(name)
        except OSError:
            continue
        mine = ppid == owner if owner is not None else f"/{session}/" in target
        if not mine:
            continue
        path = target.removesuffix(" (deleted)")
        began = btime + start / ticks
        if path in found and found[path]["start"] <= began:
            continue
        key = normalize(extract_command(argv))
        found[path] = {"pid": name, "out": path, "start": began, "key": key, "family": family(key)}
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
