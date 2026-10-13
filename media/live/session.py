#!/usr/bin/env python3
import glob
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "tests"))

from mock_api import MockAnthropic


KEY = "sk-ant-api03-recording-only-not-a-real-key-0000000000"


SCRIPT = [
    {
        "say": "I'll start the backup and the build in the background, then run the tests while they go.",
        "command": "rsync -a --info=progress2 --bwlimit=24m datasets/ backup/datasets/",
        "description": "Back up the datasets",
        "run_in_background": True,
    },
    {
        "command": "make -j8",
        "description": "Build the project",
        "run_in_background": True,
    },
    {
        "command": "pytest tests/",
        "description": "Run the test suite",
    },
]


FINAL = [
    "All 60 tests pass. The backup and the build are still going; their bars stay in the statusline until they finish.",
    "The build finished cleanly. The backup is nearly done.",
    "The backup finished: 600 MB copied.",
]


def project(base):
    root = os.path.join(base, "atlas")
    os.makedirs(os.path.join(root, "datasets"))
    os.makedirs(os.path.join(root, "backup"))
    for name in ("tiles-z12.bin", "tiles-z13.bin", "tiles-z14.bin", "roads.bin", "labels.bin"):
        with open(os.path.join(root, "datasets", name), "wb") as f:
            f.truncate(120 * 1024 * 1024)
    shutil.copy(os.path.join(HERE, "Makefile"), root)
    shutil.copy(os.path.join(HERE, "build.py"), root)
    os.makedirs(os.path.join(root, "tests"))
    for area in ("routing", "geocode", "tiles", "labels", "roads", "search", "elevation", "export",
                              "import", "styles", "cache", "auth", "billing", "sync", "render", "metrics",
                              "projection", "bounds", "clusters", "places"):
        with open(os.path.join(root, "tests", f"test_{area}.py"), "w") as f:
            f.write("import time\n\n")
            for case in ("parses", "round_trips", "rejects_bad_input"):
                f.write(f"def test_{area}_{case}():\n    time.sleep(0.27)\n\n")
    return root


def config(base, root):
    home = os.path.join(base, "config")
    os.makedirs(home)
    hud = glob.glob(os.path.expanduser("~/.claude/plugins/cache/*/claude-hud"))
    if hud:
        os.makedirs(os.path.join(home, "plugins", "cache", "claude-hud"))
        os.symlink(hud[0], os.path.join(home, "plugins", "cache", "claude-hud", "claude-hud"))
    statusline = os.path.join(ROOT, "scripts", "statusline.py")
    with open(os.path.join(home, "settings.json"), "w") as f:
        json.dump({
            "statusLine": {"type": "command", "command": f"python3 -S {statusline} --wrap claude-hud", "refreshInterval": 1},
            "permissions": {"allow": ["Bash"], "defaultMode": "default"},
            "spinnerTipsEnabled": False,
        }, f)
    with open(os.path.join(home, ".claude.json"), "w") as f:
        json.dump({
            "hasCompletedOnboarding": True,
            "theme": "dark",
            "customApiKeyResponses": {"approved": [KEY[-20:]], "rejected": []},
            "projects": {root: {"hasTrustDialogAccepted": True, "hasCompletedProjectOnboarding": True}},
        }, f)
    return home


def main():
    base = tempfile.mkdtemp(prefix="demo-")
    try:
        root = project(base)
        home = config(base, root)
        with MockAnthropic(SCRIPT, final=FINAL) as mock:
            env = {k: v for k, v in os.environ.items() if not k.startswith(("CLAUDE", "ANTHROPIC"))}
            env.update({
                "ANTHROPIC_BASE_URL": mock.url,
                "ANTHROPIC_API_KEY": KEY,
                "CLAUDE_CONFIG_DIR": home,
                "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
                "DISABLE_AUTOUPDATER": "1",
                "SHELL": shutil.which("bash") or "/bin/bash",
                "XDG_STATE_HOME": os.path.join(base, "state"),
                "XDG_RUNTIME_DIR": os.path.join(base, "run"),
            })
            subprocess.run(["claude", "--model", "claude-sonnet-5", *sys.argv[1:]], env=env, cwd=root)
    finally:
        shutil.rmtree(base, ignore_errors=True)


if __name__ == "__main__":
    main()
