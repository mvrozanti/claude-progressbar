#!/usr/bin/env python3
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.join(HERE, "..", "scripts")
sys.path.insert(0, SCRIPTS)

from claude_progressbar import procs, system
from claude_progressbar.parse import ANSI


WINDOWS_TASK = "C:\\Users\\u\\AppData\\Local\\Temp\\claude\\C--proj\\sess\\tasks\\b1.output"
MAC_TASK = "/private/tmp/claude-501/-Users-u-proj/sess/tasks/b2.output"
GIT_BASH_WRAPPER = (
    "source /c/Users/u/.claude/shell-snapshots/snapshot-bash-1-x.sh 2>/dev/null || true"
    " && eval 'cd /c/proj && npm test' < /dev/null && pwd -P >| /tmp/claude-9f1e-cwd"
)


class FakeSystem:
    def __init__(self, table):
        self.table = table

    def entry(self, pid):
        if pid not in self.table:
            raise OSError(3, "no such process")
        return self.table[pid]

    def info(self, pid):
        p = self.entry(pid)
        return p["name"], p["ppid"], p["start"]

    def argv(self, pid):
        return self.entry(pid)["argv"]

    def stdout(self, pid):
        out = self.entry(pid).get("out")
        if out is None:
            raise OSError(9, "not a file")
        return out

    def children(self, pid):
        return [k for k, p in self.table.items() if p["ppid"] == pid]

    def everyone(self):
        return list(self.table)


def proc(name, ppid, start, argv, out=None):
    return {"name": name, "ppid": ppid, "start": start, "argv": argv, "out": out}


class Discovery(unittest.TestCase):
    def test_windows_shaped_tree(self):
        fake = FakeSystem({
            100: proc("claude.exe", 4, 10.0, ["C:\\Users\\u\\.local\\bin\\claude.exe"]),
            200: proc("bash.exe", 100, 50.0, ["C:\\Program Files\\Git\\bin\\bash.exe", "-c", GIT_BASH_WRAPPER], WINDOWS_TASK),
            300: proc("bash.exe", 100, 60.0, ["C:\\Program Files\\Git\\bin\\bash.exe", "-c", "python statusline.py"]),
            400: proc("python.exe", 300, 61.0, ["python", "statusline.py"]),
        })
        tasks = procs.running_tasks("sess", backend=fake, start=300)
        self.assertEqual(tasks, [{"pid": "200", "out": WINDOWS_TASK, "start": 50.0, "key": "npm test", "family": "npm test"}])

    def test_macos_native_binary_is_named_by_its_version(self):
        fake = FakeSystem({
            1: proc("launchd", 0, 0.0, ["/sbin/launchd"]),
            500: proc("2.1.283", 1, 10.0, ["claude"]),
            600: proc("zsh", 500, 20.0, ["/bin/zsh", "-c", "eval 'make -j8'"], MAC_TASK),
            700: proc("sh", 500, 30.0, ["sh", "-c", "exec python3 statusline.py"]),
        })
        tasks = procs.running_tasks("sess", backend=fake, start=700)
        self.assertEqual([(t["pid"], t["key"]) for t in tasks], [("600", "make -j8")])

    def test_node_install_is_found_by_its_script(self):
        fake = FakeSystem({
            500: proc("node", 1, 10.0, ["node", "/usr/lib/node_modules/@anthropic-ai/claude-code/cli.js"]),
            600: proc("bash", 500, 20.0, ["bash", "-c", "eval 'cargo build'"], MAC_TASK),
        })
        self.assertEqual(procs.claude_ancestor(fake, 600), 500)
        self.assertEqual([t["key"] for t in procs.running_tasks("sess", backend=fake, start=600)], ["cargo build"])

    def test_without_a_claude_ancestor_the_session_decides(self):
        fake = FakeSystem({
            600: proc("bash", 1, 20.0, ["bash", "-c", "eval 'sleep 9'"], MAC_TASK),
            601: proc("bash", 1, 20.0, ["bash", "-c", "eval 'sleep 8'"], MAC_TASK.replace("/sess/", "/other/")),
            602: proc("bash", 1, 20.0, ["bash", "-c", "eval 'sleep 7'"], WINDOWS_TASK),
        })
        tasks = procs.running_tasks("sess", backend=fake, start=999)
        self.assertEqual(sorted(t["key"] for t in tasks), ["sleep 7", "sleep 9"])

    def test_a_vanished_process_is_skipped(self):
        fake = FakeSystem({
            500: proc("claude", 1, 10.0, ["claude"]),
            600: proc("bash", 500, 20.0, ["bash", "-c", "eval 'x'"], MAC_TASK),
        })
        fake.children = lambda pid: [600, 601]
        self.assertEqual([t["pid"] for t in procs.running_tasks("sess", backend=fake, start=600)], ["600"])

    def test_shell_scripts_are_read_from_every_shell_shape(self):
        cases = [
            (["bash", "-c", "eval 'make'"], "make"),
            (["bash", "-l", "-c", "eval 'make'"], "make"),
            (["bash", "-c", "-l", "eval 'make'"], "make"),
            (["bash", "-lc", "eval 'make'"], "make"),
            (["pwsh", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", "npm run build"], "npm run build"),
            (["powershell.exe", "-c", "npm ci"], "npm ci"),
            (["sleep", "5"], "sleep 5"),
            (["node", "--inspect", "server.js"], "node --inspect server.js"),
        ]
        for argv, expected in cases:
            self.assertEqual(procs.extract_command(argv), expected, argv)

    def test_program_names_ignore_paths_case_and_exe(self):
        self.assertEqual(procs.program("C:\\Users\\u\\.local\\bin\\Claude.EXE"), "claude")
        self.assertEqual(procs.program("/usr/local/bin/claude"), "claude")
        self.assertEqual(procs.program("cli.js"), "cli.js")


FAKE_CLAUDE = """
import json, os, subprocess, sys, time
python, tasks, statusline, result = sys.argv[1:5]
out = open(os.path.join(tasks, "probe.output"), "w")
worker = subprocess.Popen([python, "-c", "import time; print('3/10', flush=True); time.sleep(60)"], stdout=out, stderr=out)
try:
    time.sleep(2.5)
    shown = subprocess.run([python, "-S", statusline, "--style", "digits"], input=json.dumps({"session_id": "s"}), capture_output=True, text=True, encoding="utf-8", timeout=60)
    with open(result, "w", encoding="utf-8") as f:
        json.dump({"out": shown.stdout, "err": shown.stderr, "code": shown.returncode}, f)
finally:
    worker.kill()
"""


@unittest.skipIf(system.load() is None, "no process backend for this platform")
class Backend(unittest.TestCase):
    def test_reads_a_live_child(self):
        backend = system.load()
        with tempfile.TemporaryDirectory() as d:
            tasks = os.path.join(d, "tasks")
            os.mkdir(tasks)
            target = os.path.join(tasks, "x.output")
            with open(target, "w") as out:
                child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"], stdout=out)
            try:
                deadline = time.time() + 10
                while child.pid not in backend.children(os.getpid()) and time.time() < deadline:
                    time.sleep(0.1)
                self.assertIn(child.pid, backend.children(os.getpid()))
                self.assertIn(child.pid, backend.everyone())
                name, ppid, start = backend.info(child.pid)
                self.assertEqual(ppid, os.getpid())
                self.assertLess(abs(start - time.time()), 60)
                self.assertIn("python", procs.program(name))
                argv = backend.argv(child.pid)
                self.assertEqual(argv[1:], ["-c", "import time; time.sleep(30)"])
                self.assertEqual(os.path.normcase(os.path.realpath(backend.stdout(child.pid))), os.path.normcase(os.path.realpath(target)))
                self.assertTrue(procs.TASK_OUTPUT.search(backend.stdout(child.pid)))
            finally:
                child.kill()
                child.wait()

    def test_a_missing_process_raises(self):
        backend = system.load()
        child = subprocess.Popen([sys.executable, "-c", "pass"])
        child.wait()
        for call in (backend.argv, backend.stdout):
            with self.assertRaises(OSError):
                call(child.pid)

    def test_statusline_finds_a_task_under_a_process_called_claude(self):
        with tempfile.TemporaryDirectory() as d:
            tasks = os.path.join(d, "s", "tasks")
            os.makedirs(tasks)
            result = os.path.join(d, "result.json")
            env = {**os.environ, "XDG_STATE_HOME": d, "XDG_RUNTIME_DIR": d, "XDG_CACHE_HOME": d}
            subprocess.run(
                ["claude", "-c", FAKE_CLAUDE, sys.executable, tasks, os.path.join(SCRIPTS, "statusline.py"), result],
                executable=sys.executable, env=env, timeout=90, check=True,
            )
            with open(result, encoding="utf-8") as f:
                shown = json.load(f)
        self.assertEqual(shown["code"], 0, shown["err"])
        bars = ANSI.sub("", shown["out"])
        self.assertIn("3/10", bars, shown)
        self.assertIn("30.0%", bars, shown)
        self.assertIn("import time", bars, shown)


def git_bash():
    candidates = [os.environ.get("CLAUDE_CODE_GIT_BASH_PATH")]
    git = shutil.which("git")
    if git:
        root = os.path.dirname(os.path.dirname(os.path.realpath(git)))
        candidates.append(os.path.join(root, "bin", "bash.exe"))
    candidates.append("C:\\Program Files\\Git\\bin\\bash.exe")
    return next((c for c in candidates if c and os.path.exists(c)), None)


def documented_command():
    with open(os.path.join(HERE, "..", "README.md"), encoding="utf-8") as f:
        readme = f.read()
    found = re.search(r"```json\n(\"statusLine\": \{.*?\n\})\n```", readme, re.S)
    if found is None:
        raise AssertionError("README has no statusLine block")
    command = json.loads("{" + found.group(1) + "}")["statusLine"]["command"]
    if os.name == "nt":
        command = command.replace("exec python3 ", "exec python ")
    return command


STUB = 'import sys\nprint("{version}", *sys.argv[1:])\n'


class InstallCommand(unittest.TestCase):
    def test_the_readme_command_runs_the_newest_installed_version(self):
        command = documented_command()
        with tempfile.TemporaryDirectory() as d:
            for version in ("2.9.0", "2.10.0", "10.0.0-rc1", "9.1.0"):
                scripts = os.path.join(d, "plugins", "cache", "claude-progressbar", "claude-progressbar", version, "scripts")
                os.makedirs(scripts)
                with open(os.path.join(scripts, "statusline.py"), "w") as f:
                    f.write(STUB.format(version=version))
            env = {**os.environ, "CLAUDE_CONFIG_DIR": d.replace("\\", "/")}
            if os.name == "nt":
                bash = git_bash()
                if bash is None:
                    self.skipTest("Git Bash not found")
                run = subprocess.run([bash, "-c", command], env=env, capture_output=True, text=True, timeout=60)
            else:
                run = subprocess.run(command, shell=True, env=env, capture_output=True, text=True, timeout=60)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(run.stdout.split(), ["10.0.0-rc1", "--wrap", "claude-hud"])


if __name__ == "__main__":
    unittest.main()
