-- Skill Tracker schema — ANSI-SQL reference baseline
-- =================================================================
-- This is the REFERENCE definition of the two tables the correction-loop
-- system uses (Skills + Issues). It is written in the most standard SQL
-- types (VARCHAR, INTEGER, DATE) so the column names, constraints, and
-- relationships are unambiguous. The two platform files
-- (postgres.sql, sqlserver.sql) are the RUNNABLE ones; this file documents
-- the two portability seams where the standard leaves the choice to the
-- platform.
--
-- PORTABILITY SEAM 1 — the identity (auto-increment) column, issues.id
--   ANSI SQL:2003 spec is `GENERATED ALWAYS AS IDENTITY`, but support is
--   uneven, so this reference leaves the type as a plain INTEGER/BIGINT and
--   documents the per-platform form instead:
--     Postgres / Supabase : BIGINT GENERATED ALWAYS AS IDENTITY  (or BIGSERIAL)
--     SQL Server / Azure SQL: BIGINT IDENTITY(1,1)
--
-- PORTABILITY SEAM 2 — the "today" default on a DATE column
--   There is no single portable spelling of "current date as a default":
--     Postgres / Supabase : DEFAULT CURRENT_DATE
--     SQL Server / Azure SQL: DEFAULT CAST(GETDATE() AS DATE)
--   ANSI names CURRENT_DATE; SQL Server accepts it in expressions but the
--   idiomatic default is the GETDATE() cast shown above.
--
-- Everything else — column names, NOT NULL, the CHECK constraints, the
-- foreign key — is identical across all three files.
-- =================================================================

CREATE TABLE skills (
    skill_name    VARCHAR(255) NOT NULL,
    what_it_does  VARCHAR(4000),
    stage         VARCHAR(16),
    open_issues   INTEGER      NOT NULL DEFAULT 0,
    last_updated  DATE,
    CONSTRAINT pk_skills PRIMARY KEY (skill_name),
    CONSTRAINT ck_skills_stage CHECK (stage IN ('planned', 'live'))
);

CREATE TABLE issues (
    id             INTEGER      NOT NULL,   -- identity column; see SEAM 1 above
    skill_name     VARCHAR(255) NOT NULL,
    title          VARCHAR(4000) NOT NULL,
    what_to_change VARCHAR(4000),
    status         VARCHAR(16)  DEFAULT 'open',
    date_filed     DATE         DEFAULT CURRENT_DATE,   -- see SEAM 2 above
    CONSTRAINT pk_issues PRIMARY KEY (id),
    CONSTRAINT ck_issues_status CHECK (status IN ('open', 'closed')),
    CONSTRAINT fk_issues_skill FOREIGN KEY (skill_name) REFERENCES skills (skill_name)
);
