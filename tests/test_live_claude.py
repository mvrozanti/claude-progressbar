#!/usr/bin/env python3
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.join(HERE, "..", "scripts")
sys.path.insert(0, SCRIPTS)
sys.path.insert(0, HERE)

from claude_progressbar.parse import ANSI
from mock_api import MockAnthropic


LIVE = os.environ.get("CLAUDE_PROGRESSBAR_LIVE") == "1"


INHERITED = ("CLAUDECODE", "CLAUDE_CODE_ENTRYPOINT", "CLAUDE_CODE_SSE_PORT", "ANTHROPIC_AUTH_TOKEN", "CLAUDE_CODE_OAUTH_TOKEN")


def posix(path):
    return os.path.abspath(path).replace("\\", "/")


@unittest.skipUnless(LIVE, "set CLAUDE_PROGRESSBAR_LIVE=1 to drive a real Claude Code through a mock API")
class LiveClaude(unittest.TestCase):
    def test_bars_follow_the_commands_claude_runs(self):
        claude = os.environ.get("CLAUDE_BIN") or shutil.which("claude") or self.fail("claude is not on PATH")
        background = "for i in $(seq 1 30); do echo step $i/30; sleep 1; done"
        probe = f"echo 3/10; sleep 2; echo '{{\"session_id\":\"live\"}}' | \"{posix(sys.executable)}\" -S \"{posix(os.path.join(SCRIPTS, 'statusline.py'))}\" --style digits --max-rows 5"
        script = [
            {"command": background, "description": "count in the background", "run_in_background": True},
            {"command": probe, "description": "draw the bars"},
        ]
        with MockAnthropic(script) as mock, tempfile.TemporaryDirectory() as home:
            env = {k: v for k, v in os.environ.items() if k not in INHERITED}
            env.update({
                "ANTHROPIC_BASE_URL": mock.url,
                "ANTHROPIC_API_KEY": "sk-ant-mock",
                "CLAUDE_CONFIG_DIR": home,
                "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
                "DISABLE_AUTOUPDATER": "1",
                "XDG_STATE_HOME": home,
                "XDG_RUNTIME_DIR": home,
            })
            run = subprocess.run(
                [claude, "-p", "go", "--permission-mode", "bypassPermissions", "--model", "claude-sonnet-5"],
                env=env, cwd=home, stdin=subprocess.DEVNULL, capture_output=True,
                text=True, encoding="utf-8", errors="replace", timeout=240,
            )
            results = list(mock.results)
        report = f"exit {run.returncode}\nstdout: {run.stdout[-2000:]}\nstderr: {run.stderr[-2000:]}\nresults: {results!r}"
        print(report, file=sys.stderr)
        self.assertEqual(len(results), 2, report)
        bars = ANSI.sub("", results[-1])
        self.assertIn("step ", bars, report)
        self.assertIn("for i in $(seq 1 30)", bars, report)
        self.assertIn("echo 3/10", bars, report)
        self.assertIn("30.0%", bars, report)
        self.assertNotIn("eval", bars, report)
        self.assertNotIn("snapshot", bars, report)


if __name__ == "__main__":
    unittest.main()
