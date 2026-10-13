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
from test_platform import documented_command, git_bash


LIVE = os.environ.get("CLAUDE_PROGRESSBAR_LIVE") == "1"


INHERITED = ("CLAUDECODE", "CLAUDE_CODE_ENTRYPOINT", "CLAUDE_CODE_SSE_PORT", "ANTHROPIC_AUTH_TOKEN", "CLAUDE_CODE_OAUTH_TOKEN")


def posix(path):
    return os.path.abspath(path).replace("\\", "/")


def isolated(home, **extra):
    env = {k: v for k, v in os.environ.items() if k not in INHERITED}
    env.update({
        "CLAUDE_CONFIG_DIR": home,
        "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
        "DISABLE_AUTOUPDATER": "1",
        "XDG_STATE_HOME": home,
        "XDG_RUNTIME_DIR": home,
        **extra,
    })
    return env


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
            env = isolated(home, ANTHROPIC_BASE_URL=mock.url, ANTHROPIC_API_KEY="sk-ant-mock")
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

    def test_the_documented_command_runs_the_plugin_claude_installed(self):
        claude = os.environ.get("CLAUDE_BIN") or shutil.which("claude") or self.fail("claude is not on PATH")
        repo = os.path.abspath(os.path.join(HERE, ".."))
        with tempfile.TemporaryDirectory() as home:
            env = isolated(home)
            for args in (["plugin", "marketplace", "add", repo], ["plugin", "install", "progressbar@claude-progressbar"]):
                step = subprocess.run([claude, *args], env=env, stdin=subprocess.DEVNULL, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
                self.assertEqual(step.returncode, 0, f"{args}: {step.stdout}{step.stderr}")
            installed = os.listdir(os.path.join(home, "plugins", "cache", "claude-progressbar", "progressbar"))
            self.assertEqual(len(installed), 1, installed)
            self.assertTrue(os.path.isfile(os.path.join(home, "plugins", "cache", "claude-progressbar", "progressbar", installed[0], "scripts", "statusline.py")))
            env["CLAUDE_CONFIG_DIR"] = posix(home)
            shell = [git_bash() or self.fail("Git Bash not found"), "-c"] if os.name == "nt" else ["sh", "-c"]
            run = subprocess.run([*shell, documented_command()], env=env, input='{"session_id":"installed"}', capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(run.stderr, "")


if __name__ == "__main__":
    unittest.main()
