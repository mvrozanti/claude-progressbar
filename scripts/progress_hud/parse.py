import os
import re


ANSI = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]|\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)|\x1b[@-Z\\-_]")


CONTROL = re.compile(r"[\x00-\x1f\x7f-\x9f]")


PERCENT = re.compile(r"(?<![\w.])(\d{1,3}(?:\.\d+)?)\s?%")


FRACTION = re.compile(r"(?<![\w/.:-])(\d+)\s?/\s?(\d+)(?![\w/.-])|(?<![\w.])(\d+) of (\d+)(?![\w.])")


CD_PREFIX = re.compile(r"cd\s+\S+\s*(?:&&|;)\s*")


ASSIGNMENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*=\S*")


SUBCOMMAND = re.compile(r"[a-z][\w:./-]*")
CHAIN = re.compile(r"\s*(?:&&|\|\|)\s*")


DURATION = re.compile(r"\d+(?:\.\d+)?[smhd]?")


WRAPPERS = {"rtk", "sudo", "time", "nice", "nohup", "command", "exec", "env", "builtin", "stdbuf"}


CONNECTORS = {"&&", "||", ";"}


TAIL_BYTES = 8192


TAIL_LINES = 8


def normalize(command):
    original = " ".join(command.split())
    text = original
    while True:
        before = text
        if (m := CD_PREFIX.match(text)):
            text = text[m.end():]
        words = text.split(" ") if text else []
        if words and (ASSIGNMENT.fullmatch(words[0]) or words[0] in WRAPPERS or words[0] in CONNECTORS):
            words.pop(0)
        elif words and words[0] == "timeout" and len(words) > 1:
            words.pop(0)
            while words and (words[0].startswith("-") or DURATION.fullmatch(words[0])):
                words.pop(0)
        text = " ".join(words)
        if text == before:
            break
    return (text or original)[:200]


def family(key):
    words = normalize(CHAIN.split(key)[-1]).split(" ")
    head = os.path.basename(words[0])
    if len(words) > 1 and SUBCOMMAND.fullmatch(words[1]):
        return f"{head} {words[1]}"
    return head


def output_lines(path):
    try:
        with open(path, "rb") as f:
            f.seek(0, os.SEEK_END)
            f.seek(max(0, f.tell() - TAIL_BYTES))
            text = f.read().decode("utf-8", "replace")
    except OSError:
        return []
    clean = ANSI.sub("", text)
    return [CONTROL.sub("", s).strip() for s in re.split(r"[\r\n]+", clean) if s.strip()][-TAIL_LINES:]


def parse_match(lines):
    for line in reversed(lines):
        percents = [m for m in PERCENT.finditer(line) if float(m.group(1)) <= 100]
        if percents:
            m = percents[-1]
            return float(m.group(1)) / 100, m.group(0).replace(" ", ""), None
        ratios = []
        for m in FRACTION.finditer(line):
            done, total = (int(m.group(1)), int(m.group(2))) if m.group(1) else (int(m.group(3)), int(m.group(4)))
            if total >= 2 and done <= total:
                ratios.append((done / total, f"{done}/{total}", (done, total)))
        if ratios:
            return ratios[-1]
    return None


def parse_progress(lines):
    match = parse_match(lines)
    return match[0] if match else None
