#!/usr/bin/env python3
"""Skill Tracker helper - read/write the Supabase Skills and Issues tables.

Shared by skillhub-log (capture) and learning-loop (apply+prove). Both skills
touch the same two tables, so the DB access lives in one place to keep the
schema knowledge from drifting between them.

Connection: reads SUPABASE_DB_URL from the environment, else from the org
secrets file (resolved via CTX_FRAMEWORK_ROOT/CTX_ORG, with a fallback path).
The URL is the IPv4 session-pooler string; direct connections are IPv6-only.

Talks to Postgres through the psql client (always present where the tracker
lives) rather than a driver, so there is nothing to install. User-supplied
text is inlined as a POSTGRES DOLLAR-QUOTED literal ($tag$...$tag$) built in
Python with a tag guaranteed absent from the value - injection-safe for any
content (a title with quotes, semicolons, or a DROP is data, not SQL). psql's
own :'var' interpolation is NOT used: it does not fire through -c on psql 17.

Commands:
  tracker.py skills [--json]                     every skill: name, open_issues, stage
  tracker.py skill-exists <name>                 exit 0 if the skill row exists, 1 if not
  tracker.py highest-open                         the skill with the most open issues
  tracker.py issues <skill> [--status open|all]  that skill's issues (default: open only)
  tracker.py file-issue <skill> --title T --what W [--date YYYY-MM-DD]
  tracker.py close-issue <id>                     set one issue to closed
  tracker.py recount <skill>                      open_issues = count(open); last_updated = today
  tracker.py ping                                 verify the connection

Stdlib only.
"""
import argparse
import json
import os
import subprocess
import sys


def db_url():
    url = os.environ.get("SUPABASE_DB_URL")
    if url:
        return url
    root = os.environ.get("CTX_FRAMEWORK_ROOT", "/Users/chiveschamoy/cortextos-personal")
    org = os.environ.get("CTX_ORG", "personal")
    for path in (os.path.join(root, "orgs", org, "secrets.env"),
                 "/Users/chiveschamoy/cortextos-personal/orgs/personal/secrets.env"):
        try:
            for line in open(path, encoding="utf-8"):
                if line.startswith("SUPABASE_DB_URL="):
                    return line.split("=", 1)[1].strip()
        except FileNotFoundError:
            continue
    print("ERROR: SUPABASE_DB_URL not in env or secrets.env. The Skill Tracker "
          "connection is not configured.", file=sys.stderr)
    sys.exit(2)


def lit(value):
    """A Postgres dollar-quoted literal, with a tag guaranteed absent from the value."""
    v = str(value)
    tag = "tkr"
    n = 0
    while f"${tag}$" in v:
        n += 1
        tag = f"tkr{n}"
    return f"${tag}${v}${tag}$"


def psql(sql):
    r = subprocess.run(["psql", db_url(), "-tAq", "-v", "ON_ERROR_STOP=1", "-c", sql],
                       capture_output=True, text=True)
    if r.returncode != 0:
        print(f"ERROR: psql failed: {r.stderr.strip()}", file=sys.stderr)
        sys.exit(3)
    return r.stdout.strip()


def cmd_ping(a):
    print(psql("select 'ok, '||count(*)||' skills, '||"
               "(select count(*) from public.issues)||' issues' from public.skills;"))


def cmd_skills(a):
    rows = json.loads(psql(
        "select coalesce(json_agg(row_to_json(t)),'[]') from "
        f"(select skill_name, open_issues, stage from public.skills "
        f"where open_issues >= {int(a.min)} "
        "order by open_issues desc, skill_name) t;"))
    if a.json:
        print(json.dumps(rows, indent=2))
    else:
        for r in rows:
            print(f"{r['skill_name']}\t{r['open_issues']}\t{r['stage']}")


def cmd_skill_exists(a):
    out = psql(f"select 1 from public.skills where skill_name={lit(a.skill)};")
    if out.strip() == "1":
        print("exists"); sys.exit(0)
    print("absent"); sys.exit(1)


def cmd_highest_open(a):
    rows = json.loads(psql(
        "select coalesce(json_agg(row_to_json(t)),'[]') from "
        "(select skill_name, open_issues from public.skills where open_issues > 0 "
        "order by open_issues desc, skill_name limit 1) t;"))
    if not rows:
        print("no skill has any open issues"); sys.exit(1)
    print(f"{rows[0]['skill_name']}\t{rows[0]['open_issues']}")


def cmd_issues(a):
    where = f"skill_name={lit(a.skill)}"
    if a.status != "all":
        where += f" and status={lit(a.status)}"
    rows = json.loads(psql(
        "select coalesce(json_agg(row_to_json(t)),'[]') from "
        "(select id, title, coalesce(what_to_change,'') as what_to_change, status, "
        f"date_filed from public.issues where {where} order by date_filed, id) t;"))
    print(json.dumps(rows, indent=2))


def cmd_file_issue(a):
    date_expr = "current_date" if not a.date else f"{lit(a.date)}::date"
    out = psql(
        "insert into public.issues (skill_name, title, what_to_change, status, date_filed) "
        f"values ({lit(a.skill)}, {lit(a.title)}, {lit(a.what)}, 'open', {date_expr}) "
        "returning id;")
    print(f"filed issue id={out.strip()} against {a.skill}")


def cmd_close_issue(a):
    out = psql(f"update public.issues set status='closed' where id={lit(a.id)}::bigint returning id;")
    if out.strip():
        print(f"closed issue id={out.strip()}")
    else:
        print(f"no issue with id={a.id}", file=sys.stderr); sys.exit(1)


def cmd_recount(a):
    out = psql(
        "update public.skills set open_issues=(select count(*) from public.issues "
        f"where skill_name={lit(a.skill)} and status='open'), last_updated=current_date "
        f"where skill_name={lit(a.skill)} returning open_issues;")
    if out.strip() == "":
        print(f"no skill named {a.skill}", file=sys.stderr); sys.exit(1)
    print(f"{a.skill} open_issues={out.strip()}, last_updated=today")


def main():
    ap = argparse.ArgumentParser(description="Read/write the Supabase Skill Tracker (Skills + Issues).")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("ping").set_defaults(func=cmd_ping)
    s = sub.add_parser("skills"); s.add_argument("--json", action="store_true")
    s.add_argument("--min", type=int, default=0, help="only skills with open_issues >= N (surfacing)")
    s.set_defaults(func=cmd_skills)
    s = sub.add_parser("skill-exists"); s.add_argument("skill"); s.set_defaults(func=cmd_skill_exists)
    sub.add_parser("highest-open").set_defaults(func=cmd_highest_open)
    s = sub.add_parser("issues"); s.add_argument("skill"); s.add_argument("--status", default="open"); s.set_defaults(func=cmd_issues)
    s = sub.add_parser("file-issue"); s.add_argument("skill")
    s.add_argument("--title", required=True); s.add_argument("--what", required=True)
    s.add_argument("--date", default=""); s.set_defaults(func=cmd_file_issue)
    s = sub.add_parser("close-issue"); s.add_argument("id"); s.set_defaults(func=cmd_close_issue)
    s = sub.add_parser("recount"); s.add_argument("skill"); s.set_defaults(func=cmd_recount)
    a = ap.parse_args()
    a.func(a)


if __name__ == "__main__":
    main()
