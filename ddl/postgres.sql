-- Skill Tracker schema — Postgres / Supabase (runnable as-is)
-- =================================================================
-- Run against a Postgres 12+ database (Supabase included):
--   psql "$SUPABASE_DB_URL" -f ddl/postgres.sql
--
-- tracker.py addresses these tables as public.skills and public.issues,
-- which is the default schema created here.
-- =================================================================

CREATE TABLE IF NOT EXISTS public.skills (
    skill_name    TEXT        PRIMARY KEY,
    what_it_does  TEXT,
    stage         VARCHAR(16) CHECK (stage IN ('planned', 'live')),
    open_issues   INTEGER     NOT NULL DEFAULT 0,
    last_updated  DATE
);

CREATE TABLE IF NOT EXISTS public.issues (
    id             BIGINT      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    skill_name     TEXT        NOT NULL REFERENCES public.skills (skill_name),
    title          TEXT        NOT NULL,
    what_to_change TEXT,
    status         VARCHAR(16) NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'closed')),
    date_filed     DATE        NOT NULL DEFAULT CURRENT_DATE
);

-- Speeds up the tracker's hottest read: a skill's open issues.
CREATE INDEX IF NOT EXISTS idx_issues_skill_status
    ON public.issues (skill_name, status);
