-- Skill Tracker schema — Azure SQL / SQL Server (T-SQL, runnable as-is)
-- =================================================================
-- Run against Azure SQL Database or SQL Server 2016+:
--   sqlcmd -S <server> -d <db> -U <user> -P <pass> -i ddl/sqlserver.sql
-- or paste into the Azure SQL query editor.
--
-- Column names, CHECK constraints, and the foreign key match the other two
-- DDL files exactly. The two portability seams are handled the T-SQL way:
-- BIGINT IDENTITY(1,1) for the id, and DEFAULT CAST(GETDATE() AS DATE) for
-- the filed-today date.
-- =================================================================

CREATE TABLE dbo.skills (
    skill_name    NVARCHAR(255) NOT NULL,
    what_it_does  NVARCHAR(MAX) NULL,
    stage         NVARCHAR(16)  NULL,
    open_issues   INT           NOT NULL CONSTRAINT df_skills_open_issues DEFAULT 0,
    last_updated  DATE          NULL,
    CONSTRAINT pk_skills PRIMARY KEY (skill_name),
    CONSTRAINT ck_skills_stage CHECK (stage IN ('planned', 'live'))
);

CREATE TABLE dbo.issues (
    id             BIGINT        IDENTITY(1,1) NOT NULL,
    skill_name     NVARCHAR(255) NOT NULL,
    title          NVARCHAR(MAX) NOT NULL,
    what_to_change NVARCHAR(MAX) NULL,
    status         NVARCHAR(16)  NOT NULL CONSTRAINT df_issues_status DEFAULT 'open',
    date_filed     DATE          NOT NULL CONSTRAINT df_issues_date_filed DEFAULT CAST(GETDATE() AS DATE),
    CONSTRAINT pk_issues PRIMARY KEY (id),
    CONSTRAINT ck_issues_status CHECK (status IN ('open', 'closed')),
    CONSTRAINT fk_issues_skill FOREIGN KEY (skill_name) REFERENCES dbo.skills (skill_name)
);

-- Speeds up the tracker's hottest read: a skill's open issues.
CREATE INDEX idx_issues_skill_status
    ON dbo.issues (skill_name, status);
