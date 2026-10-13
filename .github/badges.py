#!/usr/bin/env python3
import datetime
import glob
import json
import os
import sys


WINDOWS_LOGO = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="white">'
    '<path d="M0 3.4 9.8 2v9.5H0zM11 1.8 24 0v11.5H11zM0 12.5h9.8V22L0 20.6zM11 12.5h13V24l-13-1.8z"/></svg>'
)


PLATFORMS = {
    "ubuntu-latest": {"file": "linux.json", "label": "Linux", "namedLogo": "linux"},
    "macos-latest": {"file": "macos.json", "label": "macOS", "namedLogo": "apple"},
    "windows-latest": {"file": "windows.json", "label": "Windows", "logoSvg": WINDOWS_LOGO},
}


CACHE_SECONDS = 600


def version_key(version):
    return tuple(int(part) if part.isdigit() else 0 for part in version.split("."))


def load(folder):
    results = []
    for path in sorted(glob.glob(os.path.join(folder, "*.json"))):
        with open(path, encoding="utf-8") as f:
            results.append(json.load(f))
    return results


def badge(label, message, ok, **logo):
    return {
        "schemaVersion": 1,
        "label": label,
        "message": message,
        "color": "brightgreen" if ok else "red",
        "cacheSeconds": CACHE_SECONDS,
        **({"logoColor": "white"} if "namedLogo" in logo else {}),
        **logo,
    }


def platform(results, runner):
    spec = PLATFORMS[runner]
    mine = [r for r in results if r["os"] == runner]
    units = sorted((r for r in mine if r["job"] == "unittest"), key=lambda r: version_key(r["python"]))
    live = [r for r in mine if r["job"] == "claude-code"]
    failed = [f"Python {r['python']}" for r in units if not r["ok"]] + ["Claude Code" for r in live if not r["ok"]]
    logo = {k: v for k, v in spec.items() if k in ("namedLogo", "logoSvg")}
    if not units:
        return badge(spec["label"], "not run", False, **logo)
    if failed:
        return badge(spec["label"], "failing: " + ", ".join(failed), False, **logo)
    return badge(spec["label"], f"Python {units[0]['python']} – {units[-1]['python']}", True, **logo)


def claude_code(results, today):
    live = [r for r in results if r["job"] == "claude-code"]
    versions = sorted({r["claude"] for r in live if r.get("claude")}, key=version_key)
    shown = " / ".join(versions) or "unknown"
    failing = [PLATFORMS[r["os"]]["label"] for r in live if not r["ok"]]
    if not live:
        return badge("Claude Code", "not run", False, namedLogo="claude")
    if failing:
        return badge("Claude Code", f"{shown} failing on " + ", ".join(failing), False, namedLogo="claude")
    return badge("Claude Code", f"{shown} · tested {today}", True, namedLogo="claude")


def main():
    source, target = sys.argv[1:3]
    results = load(source)
    today = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
    os.makedirs(target, exist_ok=True)
    badges = {spec["file"]: platform(results, runner) for runner, spec in PLATFORMS.items()}
    badges["claude-code.json"] = claude_code(results, today)
    for name, content in badges.items():
        with open(os.path.join(target, name), "w", encoding="utf-8") as f:
            json.dump(content, f, indent=2)
            f.write("\n")
        print(f"{name}: {content['label']} | {content['message']}")


if __name__ == "__main__":
    main()
