import json
import os

from .util import read_json, write_atomic
from .procs import file_size


LINGER = 5


SIZE_SAMPLES = 240


MIN_RECORDED = 3.0


HISTORY_SAMPLES = 7


FAMILY_SPREAD = 3


HISTORY_MAX_BYTES = 512 * 1024


HISTORY_KEEP = 2000


def load_history(path):
    exact, families = {}, {}
    try:
        with open(path) as f:
            for line in f:
                try:
                    entry = json.loads(line)
                    key, group, duration = entry["k"], entry["f"], float(entry["d"])
                except (ValueError, KeyError, TypeError):
                    continue
                exact.setdefault(key, []).append(duration)
                families.setdefault(group, []).append(duration)
    except OSError:
        pass
    return exact, families


def median(samples):
    ordered = sorted(samples)
    mid = len(ordered) // 2
    return ordered[mid] if len(ordered) % 2 else (ordered[mid - 1] + ordered[mid]) / 2


def estimate_samples(task, exact, families):
    own = exact.get(task["key"])
    if own:
        recent = own[-HISTORY_SAMPLES:]
        return median(recent), recent
    kin = families.get(task["family"], [])[-HISTORY_SAMPLES:]
    if len(kin) >= 2 and max(kin) <= FAMILY_SPREAD * min(kin):
        return median(kin), kin
    return None, []


def estimate(task, exact, families):
    return estimate_samples(task, exact, families)[0]


def append_history(path, entries):
    with open(path, "a") as f:
        f.write("".join(json.dumps(e) + "\n" for e in entries))
    if os.path.getsize(path) > HISTORY_MAX_BYTES:
        with open(path) as f:
            kept = f.readlines()[-HISTORY_KEEP:]
        write_atomic(path, "".join(kept))


def track(state_path, history_path, tasks, now, sizes=False):
    previous = read_json(state_path)
    if not isinstance(previous, dict):
        previous = {}
    seen_tasks = previous.get("tasks") if isinstance(previous.get("tasks"), dict) else {}
    alive = {t["pid"]: t for t in tasks}
    finished = []
    done = [d for d in previous.get("done", []) if isinstance(d, dict) and now - d.get("at", 0) < LINGER]
    for pid, seen in seen_tasks.items():
        current = alive.get(pid)
        if current and abs(current["start"] - seen["s"]) < 1:
            continue
        end = seen["l"]
        try:
            end = max(end, os.stat(seen["o"]).st_mtime)
        except OSError:
            pass
        duration = min(end, now) - seen["s"]
        if duration >= MIN_RECORDED:
            finished.append({"k": seen["k"], "f": seen["f"], "d": round(duration, 1), "t": int(now)})
            done.append({"key": seen["k"], "start": seen["s"], "duration": round(duration, 1), "at": now})
    if finished:
        append_history(history_path, finished)
    entries = {}
    for t in tasks:
        entry = {"s": t["start"], "l": now, "o": t["out"], "k": t["key"], "f": t["family"]}
        if sizes:
            old = seen_tasks.get(t["pid"]) or {}
            trail = old.get("z", []) if abs(old.get("s", 0) - t["start"]) < 1 else []
            entry["z"] = (trail + [[now, file_size(t["out"])]])[-SIZE_SAMPLES:]
            t["sizes"] = entry["z"]
        entries[t["pid"]] = entry
    if entries or seen_tasks or done or previous.get("done"):
        write_atomic(state_path, json.dumps({"tasks": entries, "done": done}))
    return done
