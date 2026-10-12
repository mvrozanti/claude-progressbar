from .parse import parse_match
from .history import estimate_samples


MIN_ELAPSED = 1.5


def enrich(task, lines, mtime, exact, families):
    match = parse_match(lines)
    expected, samples = estimate_samples(task, exact, families)
    return {
        **task,
        "mtime": max(mtime, task["start"]),
        "last": lines[-1] if lines else "",
        "progress": match[0] if match else None,
        "src": match[1] if match else None,
        "ratio": match[2] if match else None,
        "estimate": expected,
        "samples": samples,
    }


def facts(task, now):
    elapsed = task["duration"] if task.get("done") else now - task["start"]
    expected = task.get("estimate")
    if task.get("done"):
        mode, fraction = "done", 1.0
    elif task.get("progress") is not None:
        mode, fraction = "parsed", task["progress"]
    elif expected and elapsed <= expected:
        mode, fraction = "estimate", elapsed / expected
    elif expected:
        mode, fraction = "over", 1.0
    else:
        mode, fraction = "unknown", None
    quiet = now - task.get("mtime", task["start"])
    return {**task, "elapsed": elapsed, "mode": mode, "fraction": fraction, "est": expected, "quiet": quiet}


def visible_tasks(tasks, now):
    return sorted((t for t in tasks if now - t["start"] >= MIN_ELAPSED), key=lambda t: t["start"])
