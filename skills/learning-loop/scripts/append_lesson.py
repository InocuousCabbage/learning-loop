#!/usr/bin/env python3
"""learning-loop lesson writer (extends aar-loop's append_lesson.py).

Appends one structured, dated lesson to a forward-loaded LESSONS.md, in the
4-question After Action Review shape (expected / actual / why / lesson), so the
next session can read past lessons before repeating a mistake. Also lists what
is already recorded so the same lesson is not written twice.

What this adds over the original aar-loop writer: two fields that link the
qualitative lesson to the quantitative loop, so a later read of LESSONS.md shows
not just what was learned but whether the fix was made and whether it worked.

    --fix        where the durable fix landed (exact file + what changed), or
                 "none" for a context-only lesson that changes no file.
    --skill/--score  the audit this lesson came from and its /50 total, so the
                 lesson is anchored to a measurement, not a memory.

Usage:
    python3 append_lesson.py \
        --lesson "Batch size >100 fails with a silent timeout; cap writes at 100 and check the row count returned." \
        --expected "Bulk upload of 500 rows completes in one call." \
        --actual   "Call returned 200 OK but only 100 rows landed; the rest dropped silently." \
        --why      "The API caps batch writes at 100 and does not error on a partial write." \
        --fix      "deploy/SKILL.md step 6: assert returned row count == requested." \
        --skill kb-ingest --score 34 \
        --tags "api,timeouts,fix-applied"

    python3 append_lesson.py --list                 # all lessons
    python3 append_lesson.py --list --tag api        # filter by tag

Stdlib only. No install. Default file: ./LESSONS.md (override with --file).
"""
import argparse
import datetime
import pathlib
import re

DEFAULT_FILE = "LESSONS.md"

HEADER = (
    "# Lessons\n\n"
    "Written by /learning-loop after each measured After Action Review. Read "
    "this file before starting a new task in this project. Every entry is "
    "concrete and checkable, never vague, and records whether a durable fix "
    "was made and -- once re-audited -- whether it moved the skill's score.\n"
)


def load_existing(path):
    if not path.exists():
        return HEADER
    text = path.read_text(encoding="utf-8")
    return text if text.strip() else HEADER


def format_entry(args):
    date = datetime.date.today().isoformat()
    lines = [f"## {date} -- {args.lesson}\n"]
    if args.expected:
        lines.append(f"- Expected: {args.expected}\n")
    if args.actual:
        lines.append(f"- Actual: {args.actual}\n")
    if args.why:
        lines.append(f"- Why: {args.why}\n")
    if args.fix:
        lines.append(f"- Fix: {args.fix}\n")
    if args.skill or args.score is not None:
        anchor = args.skill or "?"
        if args.score is not None:
            anchor += f" scored {args.score}/50 at time of lesson"
        lines.append(f"- From audit: {anchor}\n")
    if args.tags:
        lines.append(f"- tags: {args.tags.strip()}\n")
    return "".join(lines)


def cmd_add(args):
    path = pathlib.Path(args.file)
    existing = load_existing(path)
    entry = format_entry(args)
    path.write_text(existing.rstrip("\n") + "\n\n" + entry, encoding="utf-8")
    print(f"Wrote lesson to {path}:")
    print(entry.strip())


def cmd_list(args):
    path = pathlib.Path(args.file)
    if not path.exists():
        print(f"No lessons file at {path} yet.")
        return
    text = path.read_text(encoding="utf-8")
    entries = re.split(r"\n(?=## )", text)
    shown = 0
    for e in entries:
        e = e.strip()
        if not e.startswith("## "):
            continue
        if args.tag:
            tag_match = re.search(r"tags:\s*(.+)", e, re.IGNORECASE)
            tags = tag_match.group(1).lower() if tag_match else ""
            if args.tag.lower() not in tags:
                continue
        print(e)
        print()
        shown += 1
    if shown == 0:
        print("No matching lessons.")


def main():
    parser = argparse.ArgumentParser(
        description="Append or list dated, measurement-anchored AAR lessons in a LESSONS.md file.")
    parser.add_argument("--file", default=DEFAULT_FILE,
                        help="Path to the lessons file (default: ./LESSONS.md)")
    parser.add_argument("--lesson",
                        help="The concrete, checkable lesson (AAR question 4: what to do differently)")
    parser.add_argument("--expected", help="AAR question 1: what was supposed to happen")
    parser.add_argument("--actual", help="AAR question 2: what actually happened (from the transcript)")
    parser.add_argument("--why", help="AAR question 3: the mechanism -- why there was a difference")
    parser.add_argument("--fix", help="Where the durable fix landed (exact file + change), or 'none'")
    parser.add_argument("--skill", help="The skill this lesson's audit was about")
    parser.add_argument("--score", type=int, help="The audit /50 total at the time of the lesson")
    parser.add_argument("--tags", help="Comma-separated tags for later filtering")
    parser.add_argument("--list", action="store_true", help="List existing lessons instead of adding one")
    parser.add_argument("--tag", help="With --list, filter to lessons matching this tag")
    args = parser.parse_args()

    if args.list:
        cmd_list(args)
        return
    if not args.lesson:
        parser.error("--lesson is required unless using --list")
    cmd_add(args)


if __name__ == "__main__":
    main()
