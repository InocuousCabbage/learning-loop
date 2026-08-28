---
name: skillhub-log
description: Capture every correction from a conversation and file it against the skill that should have handled it. When the user says we're done, "log this chat", "log this", "capture my corrections", or asks to record what they had to correct, read back over the whole conversation, find every place the user corrected you, stated a preference, or repeated themselves to get the output they wanted, route each to the right skill in the Skill Tracker, dedupe against that skill's open issues, and file a new Issue row for the rest. Use this at the end of any working session that had corrections, even if the user only says "we're done" or "log it" - a correction not written down is one you will make again next time.
triggers: ["log this chat", "log this", "we're done", "log this conversation", "capture my corrections", "file issues from this chat", "record what i corrected", "skillhub log", "log our chat"]
effort: medium
---

# skillhub-log

The capture half of the skill-improvement loop. It reads a finished conversation, finds every correction the user made, and turns each into a routed, deduped Issue row in the Skill Tracker - so the next session starts from what was learned instead of repeating the mistake.

This skill only CAPTURES. Fixing a skill from its issues is `learning-loop` (apply + prove). Keeping them apart is deliberate: reading a chat for corrections is different work from rewriting a skill and proving the rewrite helped, and an issue should be filed by whoever read the conversation and closed by whoever can prove the fix.

---

## The Skill Tracker

Two Supabase tables, reached through one helper (shared with learning-loop):

```bash
TRACKER=~/.claude/skills/learning-loop/scripts/tracker.py
python3 "$TRACKER" ping                       # verify the connection first
python3 "$TRACKER" skills                      # every skill_name + open_issues + stage
python3 "$TRACKER" issues <skill>              # that skill's OPEN issues (JSON)
python3 "$TRACKER" file-issue <skill> --title "..." --what "..."
python3 "$TRACKER" recount <skill>             # open_issues = count(open); last_updated = today
```

The connection (`SUPABASE_DB_URL`) is read from `secrets.env` automatically. If `ping` fails, the tracker is not configured - stop and say so rather than guessing.

---

## What counts as a correction

Read back over the whole conversation. Anchor to what was actually said, not to your memory of how it went - if a transcript is available, that is the record. Keep only what would change how you behave NEXT time. For each candidate, ask: would a different agent, six months from now, behave differently because this was written down?

**Capture these:**
- The user corrected an output ("no, do it this way").
- The user stated a preference ("always ask for the deadline first").
- The user repeated themselves to get what they wanted - a repetition is a correction the first ask did not land.
- A default of yours that the user had to override.

**Skip these (one-off, not behavioural):**
- Facts specific to this one job (a filename, a date, a person's name for this task).
- Something you got right the first time.
- Praise with no change attached.

A conversation with zero real corrections is a valid result. Do not manufacture issues to look productive - filing noise buries the real ones.

---

## The workflow

Run these steps in order. Show your reasoning as you go; the user will want to see what you routed where and what you skipped.

### 1. Pull the skill list

```bash
python3 "$TRACKER" skills > /tmp/skills.txt   # skill_name is the routing key
```

### 2. Extract the corrections

List every correction you found, in the user's own words where possible. This list is the input to routing - get it right before filing anything.

### 3. Route each correction to a skill

For each correction, pick the ONE skill from the Skills table whose `skill_name` should have handled it. Match on what the skill does, not on keywords.

**If no skill covers it:** file nothing for that correction. Tell the user what new skill you would create (name + one-line purpose) and let them decide. Do not invent a skill row.

### 4. Dedupe against open issues

Before filing against a skill, read its open issues:

```bash
python3 "$TRACKER" issues <skill_name>
```

If an open issue already asks for the same change, say so and file nothing for that correction. Two rows asking for the same fix is exactly the pile that makes the tracker useless.

### 5. File the remaining issues

One row per remaining correction:

```bash
python3 "$TRACKER" file-issue <skill_name> \
  --title "<the change as an instruction, e.g. 'Ask for the deadline before drafting'>" \
  --what  "<what the user asked for, their correction in their own words, and exactly what to do differently - written so someone who was not in this chat could make the change without asking anything>"
```

`status` is set to open and `date_filed` to today automatically. Write `what_to_change` to stand alone: the trigger, the user's wording, and the concrete behaviour. If a reader would have to ask "what did they actually want?", it is not specific enough yet.

### 6. Recount each skill you filed against

```bash
python3 "$TRACKER" recount <skill_name>   # open_issues on the Skills row = its open issues; last_updated = today
```

### 7. Report

Finish with:
- one line per Issue row you filed (skill + title),
- one line per correction you skipped and why (one-off / already-open-issue / no-skill-covers-it, with the proposed new skill named).

---

## Rules

- One Issue row per real correction. Never two rows for the same change - dedupe in step 4.
- `what_to_change` must stand alone. Someone who was not in the chat has to be able to act on it.
- Route on what a skill does, not on a keyword in its name.
- No skill covers it -> propose a new one and file nothing. Never invent a skill row to have somewhere to put it.
- A zero-correction conversation is a real, valid result. Do not pad.
- This skill files issues; it does not fix skills. Handing an issue to a fix is `learning-loop`.
