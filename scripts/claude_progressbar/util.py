import json
import os


def state_dir(env, fallback):
    path = os.path.join(os.environ.get(env) or fallback, "claude-progressbar")
    os.makedirs(path, exist_ok=True)
    return path


def write_atomic(path, payload):
    tmp = f"{path}.{os.getpid()}"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(payload)
    try:
        os.replace(tmp, path)
    except PermissionError:
        os.remove(tmp)


def read_json(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}
