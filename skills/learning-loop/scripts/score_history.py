#!/usr/bin/env python3
"""learning-loop score tracker -- the measured half of the loop.

skill-optimizer scores a run; aar-loop writes a fix and hopes. This ties the
two together: it records each audit's 5-dimension score, and when the NEXT
audit of the same skill is recorded, it judges whether the fix applied after
the previous run actually moved the total. A fix that did not move the score
is surfaced as a bad fix instead of sitting in LESSONS.md wearing the look of
learning. That verdict is the one thing neither source system produces alone.

history.json lives per skill:
  { "skill": "<name>",
    "runs": [
      { "date", "transcript",
        "scores": {trigger, step_coverage, reference_accuracy,
                   execution_quality, output_match},
        "total",
        "fix": { "applied": bool, "target": "...", "lesson": "..." } | null,
        "fix_verdict": { "prev_total", "delta", "moved", "against_index" } | null
      }, ... ] }

The fix on run N is judged when run N+1 lands, because a fix applied in
response to run N's audit can only show up in the run AFTER it.

Usage:
  # record a run (scores are the five 1-10 dimension scores)
  python3 score_history.py record --skill kb-ingest \
      --scores 9,7,8,6,8 --transcript /path/to.jsonl \
      --fix-applied --fix-target "kb-ingest/SKILL.md step 3" \
      --fix-lesson "assert row count, not exit code"

  python3 score_history.py trend   --skill kb-ingest    # deltas across runs
  python3 score_history.py verdict --skill kb-ingest    # did the last fix work?
  python3 score_history.py show    --skill kb-ingest    # dump the history

Stdlib only. Default file: ./history.json (override with --file).
"""
import argparse
import datetime
import json
import pathlib
import sys

DIMS = ["trigger", "step_coverage", "reference_accuracy",
        "execution_quality", "output_match"]


def load(path):
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"ERROR: could not read {path}: {e}", file=sys.stderr)
        sys.exit(2)


def save(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _now():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _fmt_verdict(v):
    if v is None:
        return ""
    if v["moved"]:
        return f"MOVED +{v['delta']} (was {v['prev_total']}/50) -- the fix helped."
    if v["delta"] == 0:
        return f"FLAT 0 (still {v['prev_total']}/50) -- the fix did not move the score. Re-examine it."
    return f"REGRESSED {v['delta']} (was {v['prev_total']}/50) -- the fix made it worse. Revert or rethink."


def cmd_record(args):
    path = pathlib.Path(args.file)
    parts = [p.strip() for p in args.scores.split(",")]
    if len(parts) != 5:
        print("ERROR: --scores needs exactly 5 comma-separated values "
              "(trigger,step_coverage,reference_accuracy,execution_quality,output_match).",
              file=sys.stderr)
        sys.exit(2)
    try:
        vals = [int(p) for p in parts]
    except ValueError:
        print("ERROR: scores must be integers 1-10.", file=sys.stderr)
        sys.exit(2)
    if not all(1 <= v <= 10 for v in vals):
        print("ERROR: each score must be between 1 and 10.", file=sys.stderr)
        sys.exit(2)

    data = load(path) or {"skill": args.skill, "runs": []}
    if data.get("skill") and args.skill and data["skill"] != args.skill:
        print(f"ERROR: {path} is history for skill '{data['skill']}', not '{args.skill}'. "
              f"Use a per-skill history file.", file=sys.stderr)
        sys.exit(2)

    run = {
        "date": _now(),
        "transcript": args.transcript or "",
        "scores": dict(zip(DIMS, vals)),
        "total": sum(vals),
        "fix": None,
        "fix_verdict": None,
    }
    if args.fix_applied or args.fix_target or args.fix_lesson:
        run["fix"] = {
            "applied": bool(args.fix_applied),
            "target": args.fix_target or "",
            "lesson": args.fix_lesson or "",
        }

    # Judge the most recent prior APPLIED, UNJUDGED fix against this new total.
    verdict_line = ""
    for i in range(len(data["runs"]) - 1, -1, -1):
        prev = data["runs"][i]
        pfix = prev.get("fix")
        if pfix and pfix.get("applied") and prev.get("fix_verdict") is None:
            delta = run["total"] - prev["total"]
            verdict = {
                "prev_total": prev["total"],
                "delta": delta,
                "moved": delta > 0,
                "against_index": len(data["runs"]),  # index this new run will take
            }
            prev["fix_verdict"] = verdict
            verdict_line = _fmt_verdict(verdict)
            break

    data["runs"].append(run)
    save(path, data)

    print(f"Recorded {args.skill}: {run['total']}/50 "
          f"({', '.join(f'{d}={v}' for d, v in run['scores'].items())})")
    if len(data["runs"]) >= 2:
        prev_total = data["runs"][-2]["total"]
        d = run["total"] - prev_total
        print(f"  trend: {prev_total}/50 -> {run['total']}/50 ({'+' if d >= 0 else ''}{d})")
    if verdict_line:
        print(f"  fix verdict (previous run's fix, judged now): {verdict_line}")


def cmd_trend(args):
    data = load(pathlib.Path(args.file))
    if not data or not data["runs"]:
        print("No runs recorded yet.")
        return
    runs = data["runs"]
    print(f"skill: {data.get('skill','?')}   runs: {len(runs)}")
    print("-" * 60)
    prev = None
    for idx, r in enumerate(runs):
        d = "" if prev is None else f"  ({'+' if r['total']-prev >= 0 else ''}{r['total']-prev})"
        print(f"[{idx}] {r['date'][:19]}  total {r['total']}/50{d}")
        if prev is not None:
            for dim in DIMS:
                pd = runs[idx - 1]["scores"][dim]
                cd = r["scores"][dim]
                if cd != pd:
                    print(f"       {dim}: {pd}->{cd} ({'+' if cd-pd>=0 else ''}{cd-pd})")
        if r.get("fix"):
            state = "applied" if r["fix"]["applied"] else "proposed-not-applied"
            print(f"       fix [{state}]: {r['fix'].get('target','')}")
            if r.get("fix_verdict"):
                print(f"       -> {_fmt_verdict(r['fix_verdict'])}")
            else:
                print("       -> not yet judged (needs the next audit of this skill)")
        prev = r["total"]


def cmd_verdict(args):
    data = load(pathlib.Path(args.file))
    if not data or not data["runs"]:
        print("No runs recorded yet.")
        return
    judged = [r for r in data["runs"] if r.get("fix_verdict")]
    if not judged:
        pending = [r for r in data["runs"]
                   if r.get("fix") and r["fix"].get("applied") and not r.get("fix_verdict")]
        if pending:
            print("A fix is applied but not yet judged -- run one more audit of this "
                  "skill, then `record` it, and the fix gets its verdict.")
        else:
            print("No applied fixes to judge yet.")
        return
    last = judged[-1]
    print(f"Most recent judged fix on '{data.get('skill','?')}':")
    print(f"  target : {last['fix'].get('target','')}")
    print(f"  lesson : {last['fix'].get('lesson','')}")
    print(f"  verdict: {_fmt_verdict(last['fix_verdict'])}")


def cmd_show(args):
    data = load(pathlib.Path(args.file))
    if not data:
        print("No history yet.")
        return
    print(json.dumps(data, ensure_ascii=False, indent=2))


def main():
    ap = argparse.ArgumentParser(description="Track skill-audit scores and judge whether applied fixes moved them.")
    ap.add_argument("--file", default="history.json", help="Path to history.json (default: ./history.json)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("record", help="Record a run's 5 dimension scores")
    r.add_argument("--skill", required=True)
    r.add_argument("--scores", required=True,
                   help="5 comma-separated 1-10 scores: trigger,step_coverage,reference_accuracy,execution_quality,output_match")
    r.add_argument("--transcript", default="")
    r.add_argument("--fix-applied", action="store_true", help="A durable fix was applied after this run")
    r.add_argument("--fix-target", help="Where the fix landed (exact file + change)")
    r.add_argument("--fix-lesson", help="One-line summary of the lesson the fix encodes")
    r.set_defaults(func=cmd_record)

    t = sub.add_parser("trend", help="Show score deltas across runs")
    t.set_defaults(func=cmd_trend)

    v = sub.add_parser("verdict", help="Did the last applied fix move the score?")
    v.set_defaults(func=cmd_verdict)

    s = sub.add_parser("show", help="Dump history.json")
    s.set_defaults(func=cmd_show)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
