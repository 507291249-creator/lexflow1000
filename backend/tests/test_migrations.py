from __future__ import annotations

import os
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
HEAD_REVISION = "0006_report_version_lineage"


def alembic_executable() -> str:
    virtualenv_command = Path(sys.executable).with_name("alembic")
    if virtualenv_command.exists():
        return str(virtualenv_command)
    command = shutil.which("alembic")
    if command:
        return command
    raise RuntimeError("Alembic CLI is not installed in the active test environment")


def run_alembic(database_path: Path, *arguments: str) -> None:
    env = os.environ.copy()
    env["DATABASE_URL"] = f"sqlite:///{database_path}"
    subprocess.run(
        [alembic_executable(), "-c", str(BACKEND_DIR / "alembic.ini"), *arguments],
        cwd=BACKEND_DIR,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )


def columns(connection: sqlite3.Connection, table: str) -> set[str]:
    return {row[1] for row in connection.execute(f"PRAGMA table_info({table})")}


def indexes(connection: sqlite3.Connection, table: str) -> set[str]:
    return {row[1] for row in connection.execute(f"PRAGMA index_list({table})")}


def test_fresh_sqlite_upgrade_head(tmp_path: Path) -> None:
    database_path = tmp_path / "fresh.db"
    run_alembic(database_path, "upgrade", "head")

    with sqlite3.connect(database_path) as connection:
        tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert {"cases", "documents", "case_facts", "case_issues", "ai_outputs", "fact_sources", "redaction_records", "redaction_items"} <= tables
        assert connection.execute("SELECT version_num FROM alembic_version").fetchone()[0] == HEAD_REVISION
        assert {
            "original_filename",
            "mime_type",
            "file_size",
            "checksum",
            "storage_provider",
            "storage_key",
            "processing_status",
            "extraction_error",
            "updated_at",
        } <= columns(connection, "documents")
        assert {"ix_documents_case_id", "ix_documents_checksum", "ix_documents_processing_status"} <= indexes(
            connection, "documents"
        )
        assert {"ix_fact_sources_fact_id", "ix_fact_sources_document_id"} <= indexes(
            connection, "fact_sources"
        )
        assert {"ix_redaction_records_case_id", "ix_redaction_records_document_id", "ix_redaction_records_source_checksum"} <= indexes(
            connection, "redaction_records"
        )
        assert {"ix_redaction_items_redaction_id"} <= indexes(connection, "redaction_items")
        assert "analysis_version" in columns(connection, "cases")
        assert "analysis_version" in columns(connection, "ai_outputs")
        assert {"report_version", "report_digest"} <= columns(connection, "cases")
        assert "report_version" in columns(connection, "ai_outputs")


def test_existing_sqlite_upgrade_backfills_and_preserves_mvp1_data(tmp_path: Path) -> None:
    database_path = tmp_path / "existing.db"
    run_alembic(database_path, "upgrade", "0001_baseline")

    with sqlite3.connect(database_path) as connection:
        connection.execute(
            "INSERT INTO cases (id, title, claimant, employer, fact_version, issue_version) VALUES (1, ?, ?, ?, 2, 3)",
            ("旧案件", "张某", "某公司"),
        )
        connection.execute(
            "INSERT INTO documents (id, case_id, filename, file_type, raw_text, uploaded_at) VALUES (1, 1, ?, ?, ?, ?)",
            ("材料.pdf", "pdf", "已有解析文本", "2026-07-01 10:00:00"),
        )
        connection.execute(
            "INSERT INTO documents (id, case_id, filename, file_type, raw_text, uploaded_at) VALUES (2, 1, ?, ?, ?, ?)",
            ("空材料.docx", "docx", "", "2026-07-02 11:00:00"),
        )
        connection.execute(
            "INSERT INTO documents (id, case_id, filename, file_type, raw_text, uploaded_at) VALUES (3, 1, ?, ?, ?, ?)",
            ("陈述.txt", "txt", "陈述内容", "2026-07-03 12:00:00"),
        )
        connection.execute(
            "INSERT INTO case_facts (id, case_id, ai_fact, fact_version) VALUES (1, 1, ?, 2)",
            ("既有事实",),
        )
        connection.execute(
            "INSERT INTO case_issues (id, case_id, title, issue_version) VALUES (1, 1, ?, 3)",
            ("既有争点",),
        )
        connection.execute(
            "INSERT INTO ai_outputs (id, case_id, output_type, title, content, fact_version, issue_version) VALUES (1, 1, ?, ?, ?, 2, 3)",
            ("legal_analysis", "既有分析", "分析内容"),
        )
        connection.execute(
            "INSERT INTO decision_traces (id, case_id, ai_output_id, ai_suggestion, human_revision, revision_reason, action, object_type) "
            "VALUES (1, 1, 1, ?, ?, ?, ?, ?)",
            ("AI 原始结论", "人工确认结论", "旧库复核记录", "接受", "AI输出"),
        )
        connection.commit()

    run_alembic(database_path, "upgrade", "head")

    with sqlite3.connect(database_path) as connection:
        documents = connection.execute(
            "SELECT id, original_filename, mime_type, processing_status, storage_provider, updated_at, file_size, checksum, storage_key "
            "FROM documents ORDER BY id"
        ).fetchall()
        assert documents[0][1:5] == ("材料.pdf", "application/pdf", "ready", "legacy_local")
        assert documents[1][1:5] == (
            "空材料.docx",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "uploaded",
            "legacy_local",
        )
        assert documents[2][1:5] == ("陈述.txt", "text/plain", "ready", "legacy_local")
        assert documents[0][5].startswith("2026-07-01 10:00:00")
        assert documents[0][6:] == (None, None, None)
        assert connection.execute("SELECT title, fact_version, issue_version FROM cases WHERE id = 1").fetchone() == (
            "旧案件",
            2,
            3,
        )
        assert connection.execute("SELECT ai_fact, fact_version FROM case_facts WHERE id = 1").fetchone() == (
            "既有事实",
            2,
        )
        assert connection.execute("SELECT title, issue_version FROM case_issues WHERE id = 1").fetchone() == (
            "既有争点",
            3,
        )
        assert connection.execute("SELECT title, content FROM ai_outputs WHERE id = 1").fetchone() == (
            "既有分析",
            "分析内容",
        )
        assert connection.execute("SELECT analysis_version FROM cases WHERE id = 1").fetchone()[0] == 0
        assert connection.execute("SELECT analysis_version FROM ai_outputs WHERE id = 1").fetchone()[0] == 0
        assert connection.execute(
            "SELECT report_version, report_digest FROM cases WHERE id = 1"
        ).fetchone() == (0, None)
        assert connection.execute("SELECT report_version FROM ai_outputs WHERE id = 1").fetchone()[0] == 0
        assert connection.execute(
            "SELECT ai_suggestion, human_revision, revision_reason FROM decision_traces WHERE id = 1"
        ).fetchone() == ("AI 原始结论", "人工确认结论", "旧库复核记录")

    run_alembic(database_path, "downgrade", "0001_baseline")
    with sqlite3.connect(database_path) as connection:
        tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert "fact_sources" not in tables
        assert "redaction_records" not in tables
        assert "redaction_items" not in tables
        assert "original_filename" not in columns(connection, "documents")
        assert "analysis_version" not in columns(connection, "cases")
        assert "analysis_version" not in columns(connection, "ai_outputs")
        assert "report_version" not in columns(connection, "cases")
        assert "report_digest" not in columns(connection, "cases")
        assert "report_version" not in columns(connection, "ai_outputs")
        assert connection.execute("SELECT filename FROM documents WHERE id = 1").fetchone()[0] == "材料.pdf"
