\set ON_ERROR_STOP on
\if :{?schema_name}
\else
\set schema_name public
\endif

-- Read-only PostgreSQL schema audit for LexFlow Sprint 1A.5.
-- Usage:
--   psql "$DATABASE_URL" -v schema_name=public \
--     -f scripts/audit_production_schema.sql | tee schema-audit.txt

BEGIN;
SET TRANSACTION READ ONLY;

SELECT current_database() AS database_name,
       current_user AS database_user,
       current_schema() AS current_schema,
       version() AS server_version;

SELECT to_regclass(format('%I.alembic_version', :'schema_name')) IS NOT NULL AS has_alembic_version
\gset

\if :has_alembic_version
SELECT version_num AS alembic_version
FROM :"schema_name".alembic_version;
\else
SELECT 'NOT INSTALLED' AS alembic_version;
\endif

-- All application tables currently present.
SELECT table_name
FROM information_schema.tables
WHERE table_schema = :'schema_name'
  AND table_type = 'BASE TABLE'
ORDER BY table_name;

-- Tables required by the MVP 1 baseline. Any returned row is missing.
WITH expected(table_name) AS (
    VALUES
        ('cases'), ('work_units'), ('documents'), ('evidences'),
        ('ai_outputs'), ('decision_traces'), ('legal_memories'),
        ('case_facts'), ('case_issues'), ('workflow_events'),
        ('case_work_records'), ('case_todos'), ('case_follow_ups')
), actual AS (
    SELECT table_name
    FROM information_schema.tables
    WHERE table_schema = :'schema_name'
      AND table_type = 'BASE TABLE'
)
SELECT expected.table_name AS missing_mvp1_table
FROM expected
LEFT JOIN actual USING (table_name)
WHERE actual.table_name IS NULL
ORDER BY expected.table_name;

-- Column names, PostgreSQL types, nullability, and defaults.
SELECT table_name,
       ordinal_position,
       column_name,
       data_type,
       udt_name,
       is_nullable,
       column_default
FROM information_schema.columns
WHERE table_schema = :'schema_name'
  AND table_name IN (
      'cases', 'work_units', 'documents', 'evidences', 'ai_outputs',
      'decision_traces', 'legal_memories', 'case_facts', 'case_issues',
      'workflow_events', 'case_work_records', 'case_todos',
      'case_follow_ups', 'fact_sources', 'alembic_version'
  )
ORDER BY table_name, ordinal_position;

-- Stable per-table structural fingerprints. Compare these with the output
-- from a temporary database migrated to 0001_baseline.
SELECT table_name,
       md5(string_agg(
           concat_ws('|', ordinal_position, column_name, data_type, udt_name, is_nullable, coalesce(column_default, '')),
           E'\n' ORDER BY ordinal_position
       )) AS column_signature
FROM information_schema.columns
WHERE table_schema = :'schema_name'
  AND table_name IN (
      'cases', 'work_units', 'documents', 'evidences', 'ai_outputs',
      'decision_traces', 'legal_memories', 'case_facts', 'case_issues',
      'workflow_events', 'case_work_records', 'case_todos', 'case_follow_ups',
      'fact_sources'
  )
GROUP BY table_name
ORDER BY table_name;

-- Index definitions, including uniqueness and indexed columns.
SELECT schemaname,
       tablename,
       indexname,
       indexdef
FROM pg_indexes
WHERE schemaname = :'schema_name'
  AND tablename IN (
      'cases', 'work_units', 'documents', 'evidences', 'ai_outputs',
      'decision_traces', 'legal_memories', 'case_facts', 'case_issues',
      'workflow_events', 'case_work_records', 'case_todos',
      'case_follow_ups', 'fact_sources'
  )
ORDER BY tablename, indexname;

-- Foreign keys and delete behavior. confdeltype: a=no action, r=restrict,
-- c=cascade, n=set null, d=set default.
SELECT child.relname AS table_name,
       constraint_record.conname AS constraint_name,
       pg_get_constraintdef(constraint_record.oid, true) AS definition,
       constraint_record.confdeltype AS delete_action_code
FROM pg_constraint AS constraint_record
JOIN pg_class AS child ON child.oid = constraint_record.conrelid
JOIN pg_namespace AS namespace_record ON namespace_record.oid = child.relnamespace
WHERE constraint_record.contype = 'f'
  AND namespace_record.nspname = :'schema_name'
  AND child.relname IN (
      'work_units', 'documents', 'evidences', 'ai_outputs',
      'decision_traces', 'legal_memories', 'case_facts', 'case_issues',
      'workflow_events', 'case_work_records', 'case_todos',
      'case_follow_ups', 'fact_sources'
  )
ORDER BY child.relname, constraint_record.conname;

-- Sprint 1A.5 critical checks. A false value blocks production migration.
SELECT
    to_regclass(format('%I.cases', :'schema_name')) IS NOT NULL AS has_cases,
    to_regclass(format('%I.documents', :'schema_name')) IS NOT NULL AS has_documents,
    to_regclass(format('%I.case_facts', :'schema_name')) IS NOT NULL AS has_case_facts,
    to_regclass(format('%I.case_issues', :'schema_name')) IS NOT NULL AS has_case_issues,
    to_regclass(format('%I.ai_outputs', :'schema_name')) IS NOT NULL AS has_ai_outputs,
    to_regclass(format('%I.decision_traces', :'schema_name')) IS NOT NULL AS has_decision_traces;

ROLLBACK;
