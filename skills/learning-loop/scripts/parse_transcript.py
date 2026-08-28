#!/usr/bin/env python3
"""learning-loop transcript parser.

Turns a Claude Code JSONL session file into a compact, ordered log of what the
agent ACTUALLY did -- the ground truth the audit reads instead of the agent's
own self-report. This is the half aar-loop lacks: an After Action Review run
against evidence rather than memory cannot flatter itself, because the record
of what happened is not written by the party being reviewed.

Claude Code JSONL is NOT flat. Tool calls live in message.content blocks on
'assistant' entries; tool results live in message.content blocks on 'user'
entries. Parsing it as a flat message list silently finds zero tool calls,
which reads as "the agent did nothing" -- a false zero. See --self-check.

Usage:
    python3 parse_transcript.py <transcript.jsonl>                # human summary
    python3 parse_transcript.py <transcript.jsonl> --json         # machine log
    python3 parse_transcript.py <transcript.jsonl> --json --cap 400
    python3 parse_transcript.py --latest                          # newest session, this cwd's project

Stdlib only. No install.
"""
import argparse
import glob
import json
import os
import sys


def _summ(v, cap):
    """Compact a value to a single short string, so the log stays readable."""
    if isinstance(v, (dict, list)):
        try:
            s = json.dumps(v, ensure_ascii=False)
        except Exception:
            s = str(v)
    else:
        s = str(v)
    s = " ".join(s.split())
    return s if len(s) <= cap else s[: cap - 1] + "…"


def latest_transcript():
    """Best-effort: the newest .jsonl under the project dir for this cwd.

    Claude Code names project dirs after the working directory with slashes
    turned to dashes. We match on the cwd's basename to avoid guessing the
    full slug, then fall back to the newest jsonl anywhere under projects/.
    """
    root = os.path.expanduser("~/.claude/projects")
    cwd_slug = os.getcwd().replace("/", "-")
    candidates = []
    for d in glob.glob(os.path.join(root, "*")):
        base = os.path.basename(d)
        if base and base in cwd_slug:
            candidates += glob.glob(os.path.join(d, "*.jsonl"))
    if not candidates:
        candidates = glob.glob(os.path.join(root, "*", "*.jsonl"))
    if not candidates:
        return None
    return max(candidates, key=os.path.getmtime)


def parse(path, cap):
    """Return (events, stats). events is an ordered list of dicts."""
    events = []
    stats = {"lines": 0, "assistant": 0, "user": 0, "tool_use": 0,
             "tool_result": 0, "errors": 0, "text_blocks": 0}
    pending = {}  # tool_use_id -> event index awaiting its result

    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            stats["lines"] += 1
            try:
                entry = json.loads(line)
            except Exception:
                continue
            etype = entry.get("type")
            msg = entry.get("message", {}) or {}
            content = msg.get("content", [])
            if isinstance(content, str):
                content = [{"type": "text", "text": content}]
            if not isinstance(content, list):
                continue

            if etype == "assistant":
                stats["assistant"] += 1
                for block in content:
                    if not isinstance(block, dict):
                        continue
                    if block.get("type") == "tool_use":
                        stats["tool_use"] += 1
                        ev = {
                            "i": len(events),
                            "kind": "tool_use",
                            "tool": block.get("name", "?"),
                            "input": _summ(block.get("input", {}), cap),
                            "result": None,
                            "error": False,
                        }
                        tuid = block.get("id")
                        if tuid:
                            pending[tuid] = ev["i"]
                        events.append(ev)
                    elif block.get("type") == "text":
                        stats["text_blocks"] += 1

            elif etype == "user":
                stats["user"] += 1
                for block in content:
                    if not isinstance(block, dict):
                        continue
                    if block.get("type") == "tool_result":
                        stats["tool_result"] += 1
                        rc = block.get("content", "")
                        if isinstance(rc, list):
                            rc = " ".join(
                                b.get("text", "") for b in rc
                                if isinstance(b, dict))
                        is_err = bool(block.get("is_error"))
                        if is_err:
                            stats["errors"] += 1
                        tuid = block.get("tool_use_id")
                        if tuid in pending:
                            ev = events[pending.pop(tuid)]
                            ev["result"] = _summ(rc, cap)
                            ev["error"] = is_err
    return events, stats


def main():
    ap = argparse.ArgumentParser(description="Parse a Claude Code JSONL transcript into an ordered tool log.")
    ap.add_argument("transcript", nargs="?", help="Path to the .jsonl session file")
    ap.add_argument("--latest", action="store_true", help="Use the newest session for this cwd's project")
    ap.add_argument("--json", action="store_true", help="Emit the machine-readable event log as JSON")
    ap.add_argument("--cap", type=int, default=300, help="Max chars per input/result summary (default 300)")
    ap.add_argument("--self-check", action="store_true",
                    help="Fail loudly if zero tool calls were found -- the classic flat-parse false zero")
    args = ap.parse_args()

    path = args.transcript
    if args.latest or not path:
        path = latest_transcript()
        if not path:
            print("ERROR: no transcript found. Pass a path explicitly.", file=sys.stderr)
            sys.exit(2)

    if not os.path.exists(path):
        print(f"ERROR: transcript not found: {path}", file=sys.stderr)
        sys.exit(2)

    events, stats = parse(path, args.cap)

    if args.self_check and stats["tool_use"] == 0 and stats["lines"] > 0:
        print("SELF-CHECK FAILED: parsed lines but found zero tool_use blocks. "
              "Either the session truly used no tools, or the JSONL structure is "
              "not what this parser expects (tool calls nest in message.content). "
              "Do NOT report 'the agent did nothing' from this -- verify the file.",
              file=sys.stderr)
        sys.exit(3)

    if args.json:
        print(json.dumps({"transcript": path, "stats": stats, "events": events},
                         ensure_ascii=False, indent=2))
        return

    print(f"transcript: {path}")
    print(f"lines={stats['lines']} tool_calls={stats['tool_use']} "
          f"results={stats['tool_result']} errors={stats['errors']} "
          f"text_blocks={stats['text_blocks']}")
    print("-" * 60)
    for ev in events:
        flag = " [ERROR]" if ev["error"] else ""
        print(f"[{ev['i']:>3}] {ev['tool']}{flag}")
        print(f"      in : {ev['input']}")
        if ev["result"] is not None:
            print(f"      out: {ev['result']}")


if __name__ == "__main__":
    main()
