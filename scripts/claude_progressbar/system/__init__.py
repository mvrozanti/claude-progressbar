import sys


def load():
    try:
        if sys.platform.startswith("linux"):
            from . import linux as backend
        elif sys.platform == "darwin":
            from . import darwin as backend
        elif sys.platform == "win32":
            from . import windows as backend
        else:
            return None
    except (OSError, AttributeError):
        return None
    return backend
