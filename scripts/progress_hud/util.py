import json
import os


def state_dir(env, fallback):
    path = os.path.join(os.environ.get(env) or fallback, "progress-hud")
    os.makedirs(path, exist_ok=True)
    return path


def write_atomic(path, payload):
    tmp = f"{path}.{os.getpid()}"
    with open(tmp, "w") as f:
        f.write(payload)
    os.replace(tmp, path)


def read_json(path):
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}
