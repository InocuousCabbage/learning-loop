---
name: learning-loop
description: A measured After Action Review that closes the loop on a skill and then PROVES the fix worked. Two modes. AUDIT mode reads an agent's JSONL transcript as ground truth, scores how well the skill was followed across 5 dimensions out of 50, runs the US Army's 4-question AAR anchored to that evidence, writes a lesson plus a fix plan to a forward-loaded LESSONS.md, records the score, and on the next run re-audits to show whether the fix moved the number. APPLY mode works a skill's open Issues from the Skill Tracker: it rewrites that skill's SKILL.md to handle each issue, shows the before/after, and on approval closes each issue only once the fix is shown to work - never just because the file was saved. Use this whenever a skill-driven run just finished, whenever someone asks to review, improve, audit, or rewrite a skill, work a skill's issues, fix the skill that needs it most, run an AAR, check whether a past fix actually helped, or close the loop on a session - even if they only say "what did we learn", "did that change work", or "fix skill X's issues".
triggers: ["run a learning loop", "after action review", "run an aar", "review this session", "what did we learn", "audit this skill", "improve this skill", "did the skill work", "close the loop", "did the fix work", "did that change help", "analyze transcript", "skill audit", "measure the fix", "rewrite this skill", "work the issues", "fix the skill that needs it most", "apply the issues", "rewrite the skill that needs it most"]
effort: medium
---

# learning-loop

A disciplined reflect-and-write step that does the one thing a plain reflection cannot: it measures. Two systems inspired it, and it takes the load-bearing half of each.

- From **skill-optimizer**: the transcript is ground truth, the score is quantified (5 dimensions, /50), and the score is tracked run over run.
- From **aar-loop** (the US Army's After Action Review, run as manual Reflexion): the 4 honest questions, a concrete checkable lesson, a fix plan that names an exact file and edit, and a forward-loaded LESSONS.md the next session reads before acting.

The combination is what neither has alone. aar-loop writes a fix and hopes; it has no measurement, so a lesson that did nothing looks identical to one that fixed everything. skill-optimizer measures but never carries the fix forward. This skill writes the fix, forward-loads it, and then **proves with a number whether it reduced the failure** -- and surfaces a fix that did not move the score as a bad fix, instead of letting it sit in LESSONS.md wearing the appearance of learning.

Run it after any skill-driven run. It is a habit, not an automatic improver: nothing here retrains a model. It proposes, and on approval writes, changes to the files an agent loads, and the fix takes effect starting next time, not mid-run.

---

## Two modes

- **AUDIT** (the default, below): start from a transcript. Score the run, run the AAR, propose a fix, record the score, and prove the fix moved it on the next run. Use when a skill-driven run just finished and you want to know what to change.
- **APPLY** (see "APPLY mode" near the end): start from the **Skill Tracker's open Issues** for a skill. Rewrite that skill's SKILL.md to handle each issue, show the before/after, and on approval close each issue **only once the fix is shown to work**. Use when corrections have already been captured (by `skillhub-log`) and you want to work a skill's backlog down.

The two share one spine and one rule. The spine: the transcript and the score are ground truth, not memory. The rule: **a fix is closed on proof, never on save.** AUDIT proves with a score delta on the next run; APPLY proves by pointing at the exact before→after change that handles the issue, and records it so the next AUDIT can confirm the score moved. `skillhub-log` fills the Issues queue; this skill empties it and proves each fix.

---

## Why anchor the reflection to the transcript

The 4-question AAR is normally answered from memory. That is exactly where a review flatters itself: an agent narrating its own session can miss a silent failure, or report a success the record would contradict. The failure mode has a name in this fleet -- perception-coloring: reading a fail as a pass because you expected a pass, leaving no trace to re-read because the misperception never reached the page.

So question 2 ("what actually happened") is read off `parse_transcript.py`, not recalled. The transcript is the external witness. This is the same discipline as "read the exit code, not the rendered text" -- trust the measurement, keep the narrative labeled and separate.

---

## Dependency check

```bash
python3 --version           # 3.8+ ; the scripts are stdlib-only
```

No other dependencies. jq is optional (the parser is Python).

---

## Inputs

1. **Transcript** -- the agent's JSONL session file (ground truth for what happened):
   ```bash
   python3 scripts/parse_transcript.py --latest          # newest session for this cwd's project
   # or pass a path: ~/.claude/projects/<project-dir>/<session>.jsonl
   ```
2. **Skill** -- the `SKILL.md` being evaluated (the standard it is judged against).
3. **Prior state (optional, and the point of the loop)** -- an existing `history.json` and `LESSONS.md` for this skill. If they exist, this run judges the last fix and continues the trend.

Output goes to `learning-loop/<skill-name>/` in the current working directory:
```
learning-loop/<skill-name>/
  YYYY-MM-DD-HH-analysis.md   scores + AAR + fix plan
  LESSONS.md                  forward-loaded, one dated lesson per entry
  history.json                every run's scores + fix verdicts (the trend)
```

---

## The loop -- five steps

### Step 1 -- Audit the transcript (measure)

Parse the session into an ordered tool log, then score it against the skill.

```bash
python3 scripts/parse_transcript.py <transcript.jsonl> --json --self-check > /tmp/log.json
```

`--self-check` fails loudly if it parsed lines but found zero tool calls -- the classic flat-parse false zero that reads as "the agent did nothing." Never report inactivity from a zero without clearing this.

Read the skill's required steps, tools, and expected outputs. Then score **5 dimensions, 1-10 each**, from what the log shows:

| Dimension | Question | 10 vs 1 |
|---|---|---|
| **trigger** | Was the right skill invoked for the right reason? | perfect match vs wrong skill |
| **step_coverage** | Were all steps followed, in order? | all in order vs most skipped |
| **reference_accuracy** | Right tools, flags, arguments, scripts? | all correct vs wrong tools |
| **execution_quality** | Clean run, errors handled? | clean vs unhandled failures |
| **output_match** | Did the final output match what the skill intended? | exact vs missing/wrong |

Score from evidence in the log (which tool, which flags, which errors), not from impression. The total is out of 50.

### Step 2 -- Run the 4-question AAR, anchored to the evidence

Answer all four, briefly and honestly. Draw 1 and 2 from the transcript, not from memory.

1. **What was supposed to happen?** The skill's plan and expected outcome, stated plainly.
2. **What actually happened?** From the tool log -- including partial completions, silent failures, and anything worked around. This is where the score's low dimension usually shows its cause.
3. **Why was there a difference?** The mechanism, not a mood. "The cron prompt is 3 steps and the skill is 4, so the agent follows the shorter one" is a why. "Should have been more careful" is not.
4. **Same or differently next time?** The concrete rule that would have closed the gap, or the pattern that worked and should be locked in.

If nothing went wrong, that is a valid AAR -- write down what worked so it is not lost. Most of the value on a bad day is catching a bug; most of the value on a good day is locking in a pattern that is not obvious yet.

### Step 3 -- Extract a concrete lesson and a fix plan

A lesson is worth keeping only if a different agent, six months from now, could read it and know exactly what to do, with no judgment call. "Cap batch writes at 100 and check the returned row count, not the status code" ships. "Write better code" does not. A lesson that names no tool, number, file, or condition is not a lesson yet -- push on it or drop it.

Then ask one question of each lesson: **will the next run make this same mistake unless something it loads is different?**

- **No** -> it is context. Skip to Step 4 and log it; do not force a file edit.
- **Yes** -> it needs a fix plan. Name the exact target and the exact edit, scoped to **any file the next run loads** -- not just the audited skill. A CLAUDE.md or AGENTS.md for a rule, a specific SKILL.md step, a checklist, a config file.

```
FIX PLAN
1. Target: <exact file>
   Edit: <the literal line or rule to add/change, not a description of the idea>
```

Present the fix plan and **wait for approval before editing**, unless the invocation already said "apply" or "fix it." Silence about a presented plan means "not yet," not yes. When approved, make the edits and confirm each one landed.

### Step 4 -- Write the lesson and record the score

Write the analysis (scores table, the 4 AAR answers, what worked, what failed, root cause, the fix plan and its status) to `learning-loop/<skill>/YYYY-MM-DD-HH-analysis.md`.

Log the lesson (check for duplicates first):

```bash
python3 scripts/append_lesson.py --file learning-loop/<skill>/LESSONS.md --list      # dedup check
python3 scripts/append_lesson.py --file learning-loop/<skill>/LESSONS.md \
  --lesson "<concrete, checkable>" \
  --expected "<AAR q1>" --actual "<AAR q2, from transcript>" --why "<AAR q3>" \
  --fix "<exact file + edit, or 'none' for context-only>" \
  --skill <skill> --score <total> \
  --tags "<area>,<fix-applied|context-only>"
```

Record the score, and note whether a durable fix was applied so the next run can judge it:

```bash
python3 scripts/score_history.py --file learning-loop/<skill>/history.json record \
  --skill <skill> --scores <t,s,r,e,o> --transcript <path> \
  [--fix-applied --fix-target "<file + edit>" --fix-lesson "<one line>"]
```

Recording a new run automatically judges the most recent prior applied-but-unjudged fix (see Step 5).

### Step 5 -- Prove the fix worked (the measured close)

This is the step that makes it a loop and not a diary. A fix applied after run N can only show up in run N+1. So when the next audit of this skill is recorded, `score_history.py` compares the new total against the total from the run whose fix was applied, and labels it:

- **MOVED +n** -- the fix helped. Lock it in.
- **FLAT 0** -- the fix did not move the score. The lesson looked like learning and was not. Re-examine it.
- **REGRESSED -n** -- the fix made it worse. Revert or rethink.

```bash
python3 scripts/score_history.py --file learning-loop/<skill>/history.json trend      # deltas across runs
python3 scripts/score_history.py --file learning-loop/<skill>/history.json verdict     # did the last fix work?
```

Report the verdict alongside the new score. A FLAT or REGRESSED verdict is not a failure of the loop -- it is the loop doing the one thing a plain reflection cannot: telling you the fix was wrong before you trust it for another month.

---

## Loading lessons next session

A lessons file nobody reads is a diary, not a loop. Close it: add one line to the project's CLAUDE.md or AGENTS.md -- "Read learning-loop/<skill>/LESSONS.md before working on <skill>." Any agent that reads project instructions at session start then picks up every past lesson for free, and the fix is present before the mistake can recur.

---

## APPLY mode -- work a skill's issues from the Skill Tracker

Use this when corrections have already been captured into the Skill Tracker (by `skillhub-log`) and you want to work a skill's backlog down. AUDIT mode starts from a transcript and asks "what should change?"; APPLY mode starts from the Issues that already say what should change, and does it -- with the same close-on-proof rule.

The tracker helper is shared with `skillhub-log`:

```bash
TRACKER=~/.claude/skills/learning-loop/scripts/tracker.py
python3 "$TRACKER" ping                         # verify the connection first
python3 "$TRACKER" highest-open                  # the skill that needs it most
python3 "$TRACKER" issues <skill>                # its OPEN issues (JSON: id, title, what_to_change)
python3 "$TRACKER" close-issue <id>              # close ONE issue, by id
python3 "$TRACKER" recount <skill>               # open_issues = count(open); last_updated = today
```

### Step A1 -- Pick the skill. One skill per run.

If the user names a skill, work that one. If they ask for the one that needs it most, use `highest-open`. Never batch several skills in one run -- a rewrite is a focused edit and a reviewer approves one skill's changes at a time.

### Step A2 -- Read its open issues.

```bash
python3 "$TRACKER" issues <skill>
```

These are the instructions. Do not go looking for other things to improve -- leave alone anything the issues did not ask about.

### Step A3 -- Rewrite the SKILL.md surgically.

Open the skill's `SKILL.md` and change it so each open issue is handled. The discipline is the point:

- **Change the sentence that caused the problem.** Do NOT append a list of exceptions at the bottom -- an exceptions list is how a skill rots, and the real fix is editing the line that misled.
- **Keep the author's wording.** Rewrite the specific rule, not the voice.
- **Only touch the name or description at the top** if an issue is about *when the skill fires* (its trigger). Otherwise leave the frontmatter alone.
- **Leave alone anything the issues did not ask about.** Scope is the open issues, nothing more.

### Step A4 -- Show the before/after. STOP.

For every part you changed, show the before and the after, and name which issue it handles. Then stop and wait for the user to reply GO. Silence is not GO. If an issue cannot be cleanly handled by a sentence change, say so now and plan to leave it open -- do not force it.

### Step A5 -- On GO: save, prove, and close on the proof.

1. **Save** the rewritten SKILL.md over the old one.
2. **Prove each issue is handled** -- this is the close-on-proof rule, and it is what makes this learning-loop and not a blind rewriter. For each issue, point at the exact before→after change and state how the new text produces the corrected behaviour the issue asked for. An issue you cannot map to a concrete change is **not handled** -- leave it open.
3. **Close only the issues you actually handled**, by id:
   ```bash
   python3 "$TRACKER" close-issue <id>     # once per proven-handled issue
   ```
4. **Recount** so the Skills row reflects reality:
   ```bash
   python3 "$TRACKER" recount <skill>      # open_issues -> its remaining open count; last_updated -> today
   ```
5. **Record the change for the deferred, quantified proof.** The before→after mapping is the immediate proof; the stronger proof is a score delta on the skill's next real run. Log it so an AUDIT can confirm it later:
   ```bash
   python3 scripts/score_history.py --file learning-loop/<skill>/history.json record \
     --skill <skill> --scores <current 5 dims from the latest audit, or the last recorded> \
     --fix-applied --fix-target "<skill>/SKILL.md: <the sentences changed>" \
     --fix-lesson "<the issue titles handled>"
   ```
   The next time this skill is AUDITed, `score_history.py` judges whether that rewrite moved the score -- MOVED, FLAT, or REGRESSED. A FLAT verdict means the rewrite closed the issue on paper but did not change behaviour, which is exactly the failure this mode exists to catch.

### Step A6 -- Report.

Finish with one line per issue you **closed** (id + title + the before→after that handles it), and one line per issue you **left open** and why. Never close an issue you only saved a file for.

---

## Rules

- **Question 2 comes from the transcript, not memory.** The whole point is a review that cannot flatter itself. Run `--self-check` before trusting a zero.
- **Every lesson names a specific tool, number, file, or condition.** No vague lessons.
- **Every fix plan names an exact target file and an exact edit.** No "improve the process."
- **Not every lesson gets a fix plan.** Context-only lessons go straight to LESSONS.md; forcing a file edit for each one buries the real fixes.
- **Never apply a fix plan without approval**, unless the user already said "apply" or "fix it."
- **Report the verdict honestly.** A fix that did not move the score gets said out loud, not quietly kept. State the measured total bare; keep any narrative about it labeled and after.
- **Run it even when the run went fine.** Locking in what worked is half the value; an AAR that only ever says "great" is not doing its job.

---

## What this is not

It is a reflect-measure-and-write habit, not automatic learning. It changes the files an agent loads, never the model. A proposed fix helps only once it is applied and actually loaded by a later run, and the verdict on whether it helped only exists after that later run is audited. Skip any of those and this becomes a growing file nobody reads or a pile of unproven fixes -- both worse than nothing, because they look like a system that is learning when it is not.
