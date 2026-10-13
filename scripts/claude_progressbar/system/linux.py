import os


TICKS = os.sysconf("SC_CLK_TCK")


_boot = []


def stat(pid):
    with open(f"/proc/{pid}/stat") as f:
        data = f.read()
    close = data.rindex(")")
    rest = data[close + 2:].split()
    return data[data.index("(") + 1:close], int(rest[1]), int(rest[19])


def boot_time():
    if not _boot:
        found = 0
        with open("/proc/stat") as f:
            for line in f:
                if line.startswith("btime "):
                    found = int(line.split()[1])
                    break
        _boot.append(found)
    return _boot[0]


def info(pid):
    name, ppid, start = stat(pid)
    return name, ppid, boot_time() + start / TICKS


def argv(pid):
    with open(f"/proc/{pid}/cmdline", "rb") as f:
        return [a.decode("utf-8", "replace") for a in f.read().split(b"\0") if a]


def stdout(pid):
    return os.readlink(f"/proc/{pid}/fd/1").removesuffix(" (deleted)")


def children(pid):
    pids = []
    try:
        tasks = os.listdir(f"/proc/{pid}/task")
    except OSError:
        return pids
    for tid in tasks:
        try:
            with open(f"/proc/{pid}/task/{tid}/children") as f:
                pids.extend(int(p) for p in f.read().split())
        except OSError:
            continue
    return pids


def everyone():
    return [int(name) for name in os.listdir("/proc") if name.isdigit()]
