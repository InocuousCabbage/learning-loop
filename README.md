# Correction Loop

A system that catches every correction — every time a human says "no, do it this
way," states a preference, or repeats themselves to get the output they wanted —
and turns it into a **tracked, applied, and proven fix** to the skill that should
have handled it in the first place. A correction not written down is one you make
again next time; this closes that loop.

It has two halves, backed by two SQL tables.

```
                 CAPTURE                          APPLY
   conversation ─────────▶  Issues (tracker DB) ─────────▶  rewritten skill
   (skillhub-log)                                (learning-loop APPLY)
      reads a transcript,      one deduped,          rewrites the SKILL.md,
      routes each correction   routed row per        proves the fix handles
      to the right skill,      real correction       the issue, closes it
      dedupes, files an issue                        ON PROOF — never on save
```

- **CAPTURE** (`skillhub-log`) reads a finished conversation, finds every
  correction, routes each to the one skill that should have handled it, dedupes
  against that skill's already-open issues, and files a new Issue row for the rest.
- **APPLY** (`learning-loop`, APPLY mode) reads a skill's open issues, rewrites
  that skill's `SKILL.md` surgically to handle each one, shows the before/after,
  and — on approval — closes each issue **only once the fix is shown to work**.
  `learning-loop` also has an AUDIT mode that scores a run against a transcript and
  proves a fix moved the score on the next run; APPLY is the half wired to the
  tracker DB.

The two skills are kept deliberately separate: reading a chat for corrections is
different work from rewriting a skill and proving the rewrite helped. An issue is
filed by whoever read the conversation and closed by whoever can prove the fix.

---

## The two tables

The tracker DB is two tables — **Skills** and **Issues** — reached through one
helper, `tracker.py`, shared by both skills so the schema knowledge lives in one
place and cannot drift.

### `skills` — one row per skill, the routing targets and the backlog counters

| column         | type            | role |
|----------------|-----------------|------|
| `skill_name`   | text, PK        | unique per skill; the routing key CAPTURE matches corrections to |
| `what_it_does` | text, nullable  | one-line description of the skill, used when routing |
| `stage`        | varchar, CHECK IN (`planned`,`live`) | lifecycle state of the skill |
| `open_issues`  | integer, NOT NULL, default 0 | denormalized count of that skill's open issues; drives surfacing |
| `last_updated` | date            | last time the row's counters were recounted |

### `issues` — one row per real correction

| column           | type            | role |
|------------------|-----------------|------|
| `id`             | big autoincrement int, PK | issue id; used to close a single issue |
| `skill_name`     | text, NOT NULL → `skills.skill_name` | which skill this correction belongs to |
| `title`          | text, NOT NULL  | the change, written as an instruction |
| `what_to_change` | text, nullable  | the standalone detail: the trigger, the user's wording, the concrete behaviour to change |
| `status`         | varchar, CHECK IN (`open`,`closed`), default `open` | open until the fix is proven |
| `date_filed`     | date, default today | when the correction was captured |

`open_issues` on the Skills row is a cached count of that skill's `status='open'`
rows; `tracker.py recount` recomputes it. Surfacing (below) reads that count to
decide which skills have a big enough backlog to be worth a rewrite pass.

---

## Standing up the database

Three runnable DDL files live in `ddl/`. Pick the one for your platform.

| file                    | platform            | identity column                       | date default                    |
|-------------------------|---------------------|---------------------------------------|---------------------------------|
| `ddl/postgres.sql`      | Postgres / Supabase | `BIGINT GENERATED ALWAYS AS IDENTITY` | `DEFAULT CURRENT_DATE`          |
| `ddl/sqlserver.sql`     | Azure SQL / SQL Server (T-SQL) | `BIGINT IDENTITY(1,1)`     | `DEFAULT CAST(GETDATE() AS DATE)` |
| `ddl/portable-ansi.sql` | reference baseline (ANSI types) | documents both seams, runs neither by default | — |

`portable-ansi.sql` is the reference: it fixes the column names, CHECK
constraints, and the foreign key, and its header comment names the two portability
seams (the identity column and the date default) and how each platform diverges.
The two platform files are the ones you actually run.

`tracker.py` itself talks to **Postgres** through the `psql` client, so if you are
using the tracker as shipped, stand up `ddl/postgres.sql`. The SQL Server DDL is
provided for portability of the schema, not for `tracker.py` as written.

### Steps

1. Create the tables:

   ```bash
   # Postgres / Supabase
   psql "$SUPABASE_DB_URL" -f ddl/postgres.sql
   ```

2. Provide the connection to the tools via the **`SUPABASE_DB_URL`** environment
   variable (the IPv4 session-pooler connection string). `tracker.py` reads it from
   the environment first, and falls back to a `SUPABASE_DB_URL=` line in an org
   `secrets.env` if the env var is unset.

   ```bash
   export SUPABASE_DB_URL='postgresql://user:pass@host:port/dbname'
   ```

   > **Secrets are never committed.** This repo contains no `secrets.env`, no
   > connection string, and no key. The `.gitignore` excludes `secrets.env`,
   > `.env`, and `*.key`. Supply the URL at runtime via the env var (or an
   > untracked local `secrets.env`).

3. Verify the connection:

   ```bash
   python3 skills/learning-loop/scripts/tracker.py ping
   # -> ok, N skills, M issues
   ```

---

## `tracker.py` — the shared DB helper

Stdlib-only Python; talks to Postgres through `psql` (no driver to install).
User-supplied text is inlined as a Postgres dollar-quoted literal built in Python
with a tag guaranteed absent from the value, so any title or note — quotes,
semicolons, a stray `DROP` — is treated as data, not SQL.

| command | what it does |
|---------|--------------|
| `tracker.py ping` | verify the connection; prints skill and issue counts |
| `tracker.py skills [--json] [--min N]` | every skill: `skill_name`, `open_issues`, `stage` (optionally only those with ≥ N open) |
| `tracker.py skill-exists <name>` | exit 0 if the skill row exists, 1 if not |
| `tracker.py highest-open` | the skill with the most open issues (what needs work most) |
| `tracker.py issues <skill> [--status open\|all]` | that skill's issues (default: open only) as JSON |
| `tracker.py file-issue <skill> --title T --what W [--date YYYY-MM-DD]` | file one new open issue |
| `tracker.py close-issue <id>` | set one issue to `closed`, by id |
| `tracker.py recount <skill>` | `open_issues = count(open)`, `last_updated = today` |

CAPTURE uses `skills`, `issues`, `file-issue`, `recount`. APPLY uses `highest-open`,
`issues`, `close-issue`, `recount`.

---

## How the skills wire together

- **`skills/skillhub-log/`** = **CAPTURE.** Triggered at the end of a working
  session ("log this chat," "we're done," "capture my corrections"). Pulls the
  skill list, extracts every correction, routes each to the one skill whose
  `skill_name` should have handled it, dedupes against that skill's open issues,
  files one Issue row per remaining correction, and recounts. Files nothing when a
  correction is a one-off, is already an open issue, or no skill covers it (in the
  last case it proposes a new skill and files nothing). A zero-correction
  conversation is a valid result — it does not manufacture issues.

- **`skills/learning-loop/`** = **AUDIT + APPLY.** APPLY mode empties a skill's
  Issues queue: pick one skill (`highest-open` or a named one), read its open
  issues, rewrite the `SKILL.md` surgically to handle each, show the before/after,
  and on GO save, prove each issue is handled by pointing at the exact
  before→after change, close only the proven-handled issues by id, and recount.
  **Close-on-proof, never close-on-save** is the rule that makes it a loop and not
  a blind rewriter. AUDIT mode is the transcript-scored half — it parses a session
  JSONL into a tool log (`parse_transcript.py`), scores the run across 5 dimensions
  (`/50`), writes a forward-loaded lesson (`append_lesson.py`), records the score
  (`score_history.py`), and on the next run proves whether the fix moved the number
  (MOVED / FLAT / REGRESSED).

`skillhub-log` fills the Issues queue; `learning-loop` APPLY empties it and proves
each fix.

### Scripts in `skills/learning-loop/scripts/`

| script | role |
|--------|------|
| `tracker.py` | the shared Skills/Issues DB helper (above) |
| `parse_transcript.py` | turns a Claude Code JSONL session into an ordered tool log — the ground truth an AUDIT reads instead of memory; `--self-check` guards the flat-parse false zero |
| `append_lesson.py` | appends a dated, measurement-anchored lesson to a forward-loaded `LESSONS.md` |
| `score_history.py` | records each audit's 5-dimension score and judges whether the previous run's fix moved the total |

---

## How the orchestration runs it

The loop runs itself nightly and surfaces its backlog every morning; the rewrite
step is always gated on a human GO.

- **Nightly `skill-capture` cron** (daemon-managed; runs every night): runs
  `skillhub-log` CAPTURE over the day's conversations, routing each correction to a
  skill and filing deduped Issue rows. This is what keeps the Issues queue current
  without anyone having to remember to "log this chat." (The cron's daemon config
  lives outside this repo — it is scheduled by the cortextOS daemon, not by a file
  here — so it is described here as prose rather than shipped.)

- **`orchestration/skill-tracker-surface.sh`** — the SURFACE half of the loop, and
  read-only. Given a threshold (default 3), it pings the tracker and lists the
  skills at/over that many open issues — the candidates for a `learning-loop` APPLY
  pass. It never rewrites anything; it only names candidates for a human GO. Exit
  codes: `0` with a list (or "nothing to work"), `2` if the connection is not
  configured (which must be reported as a gap, not read as "clear").

  ```bash
  bash orchestration/skill-tracker-surface.sh 3   # skills with >= 3 open issues
  ```

- **Morning review, Phase 0F ("Skill Tracker surfacing")** — the orchestrator's
  daily morning-review skill runs `skill-tracker-surface.sh 3` as one phase. If
  nothing surfaces, it notes "Skill Tracker clear" and moves on. If skills surface,
  it folds a one-line "Skills needing a rewrite pass" item into the morning
  briefing — naming each skill and its open-issue count — and offers to run
  `learning-loop` APPLY on the top one. The rewrite is never automatic: surfacing
  is read-only and the rewrite waits for the human to pick a skill and say go. The
  threshold is 3 by design — one or two corrections on a skill is noise, three is a
  pattern worth a focused rewrite. (This morning-review skill is
  orchestrator-specific and is not copied into this repo; it is described here.)

So the full cycle: corrections get captured nightly into Issues → the morning
surface names the skills whose backlog crossed the threshold → a human approves a
`learning-loop` APPLY pass → the skill is rewritten, each fix is proven, and the
issues are closed on that proof.

---

## Repository layout

```
.
├── README.md
├── .gitignore                       # excludes secrets.env, .env, *.key
├── ddl/
│   ├── postgres.sql                 # Postgres / Supabase (runnable)
│   ├── sqlserver.sql                # Azure SQL / SQL Server (runnable)
│   └── portable-ansi.sql            # ANSI reference; documents the two seams
├── skills/
│   ├── learning-loop/
│   │   ├── SKILL.md                 # AUDIT + APPLY
│   │   └── scripts/
│   │       ├── tracker.py           # shared Skills/Issues DB helper
│   │       ├── parse_transcript.py
│   │       ├── append_lesson.py
│   │       └── score_history.py
│   └── skillhub-log/
│       └── SKILL.md                 # CAPTURE
└── orchestration/
    └── skill-tracker-surface.sh     # read-only backlog surfacing
```

---

## Requirements

- **Python 3.8+**, standard library only — nothing to install.
- **`psql`** on `PATH` for `tracker.py` (it shells out to the Postgres client).
- A Postgres/Supabase database reachable via `SUPABASE_DB_URL` (see above).
