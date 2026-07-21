from __future__ import annotations

import os
import shutil
import subprocess
import sys
import uuid
from contextlib import contextmanager
from pathlib import Path

import psycopg2
import pytest
from psycopg2 import sql
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker


BACKEND_DIR = Path(__file__).resolve().parents[1]
HEAD_REVISION = "0006_report_version_lineage"
MVP1_TABLES = {
    "cases",
    "work_units",
    "documents",
    "evidences",
    "ai_outputs",
    "decision_traces",
    "legal_memories",
    "case_facts",
    "case_issues",
    "workflow_events",
    "case_work_records",
    "case_todos",
    "case_follow_ups",
}
DOCUMENT_COLUMNS = {
    "original_filename",
    "mime_type",
    "file_size",
    "checksum",
    "storage_provider",
    "storage_key",
    "processing_status",
    "extraction_error",
    "updated_at",
}


def alembic_executable() -> str:
    virtualenv_command = Path(sys.executable).with_name("alembic")
    if virtualenv_command.exists():
        return str(virtualenv_command)
    command = shutil.which("alembic")
    if command:
        return command
    raise RuntimeError("Alembic CLI is not installed in the active test environment")


def run_alembic(database_url: str, *arguments: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["DATABASE_URL"] = database_url
    return subprocess.run(
        [alembic_executable(), "-c", str(BACKEND_DIR / "alembic.ini"), *arguments],
        cwd=BACKEND_DIR,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )


@contextmanager
def temporary_postgres_database():
    admin_url = os.getenv("TEST_POSTGRES_URL", "").strip()
    if not admin_url:
        pytest.skip("TEST_POSTGRES_URL is not configured; PostgreSQL migration test was not run")

    parsed = make_url(admin_url)
    database_name = f"lexflow_sprint1a5_{uuid.uuid4().hex[:12]}"
    database_url = parsed.set(database=database_name).render_as_string(hide_password=False)
    admin_connection = psycopg2.connect(admin_url)
    admin_connection.autocommit = True
    try:
        with admin_connection.cursor() as cursor:
            cursor.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database_name)))
        yield database_url
    finally:
        with admin_connection.cursor() as cursor:
            cursor.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = %s AND pid <> pg_backend_pid()",
                (database_name,),
            )
            cursor.execute(sql.SQL("DROP DATABASE IF EXISTS {}").format(sql.Identifier(database_name)))
        admin_connection.close()


def seed_unversioned_mvp1_database(database_url: str) -> None:
    run_alembic(database_url, "upgrade", "0001_baseline")
    engine = create_engine(database_url)
    try:
        with engine.begin() as connection:
            connection.execute(text("DROP TABLE alembic_version"))
            connection.execute(text(
                "INSERT INTO cases (id, title, claimant, employer, workflow_mode, fact_version, issue_version) "
                "VALUES (1, '旧案件', '张某', '某公司', 'ai_case', 2, 3)"
            ))
            connection.execute(text(
                "INSERT INTO documents (id, case_id, filename, file_type, raw_text, uploaded_at) VALUES "
                "(1, 1, '材料.pdf', 'pdf', '已有解析文本', TIMESTAMP '2026-07-01 10:00:00'), "
                "(2, 1, '空材料.docx', 'docx', '', TIMESTAMP '2026-07-02 11:00:00'), "
                "(3, 1, '陈述.txt', 'txt', '陈述内容', TIMESTAMP '2026-07-03 12:00:00')"
            ))
            connection.execute(text(
                "INSERT INTO case_facts (id, case_id, ai_fact, human_fact, status, fact_version) "
                "VALUES (1, 1, '既有事实', '既有事实', '已确认', 2)"
            ))
            connection.execute(text(
                "INSERT INTO case_issues (id, case_id, title, status, related_fact_ids, issue_version) "
                "VALUES (1, 1, '既有争点', '人工确认', '[\"1\"]', 3)"
            ))
            connection.execute(text(
                "INSERT INTO ai_outputs "
                "(id, case_id, output_type, title, content, review_status, version, fact_version, issue_version) "
                "VALUES (1, 1, 'legal_analysis', '既有分析', '分析内容', '已接受', 1, 2, 3)"
            ))
            connection.execute(text(
                "INSERT INTO decision_traces "
                "(id, case_id, ai_output_id, ai_suggestion, human_revision, revision_reason, action, object_type) "
                "VALUES (1, 1, 1, 'AI 原始结论', '人工确认结论', '旧库复核记录', '接受', 'AI输出')"
            ))
            for table_name in (
                "cases",
                "documents",
                "case_facts",
                "case_issues",
                "ai_outputs",
                "decision_traces",
            ):
                connection.execute(text(
                    f"SELECT setval(pg_get_serial_sequence('{table_name}', 'id'), "
                    f"(SELECT max(id) FROM {table_name}), true)"
                ))
    finally:
        engine.dispose()


def assert_postgres_head_structure(database_url: str) -> None:
    engine = create_engine(database_url)
    try:
        inspector = inspect(engine)
        tables = set(inspector.get_table_names())
        assert MVP1_TABLES <= tables
        assert {"fact_sources", "redaction_records", "redaction_items", "alembic_version"} <= tables
        assert DOCUMENT_COLUMNS <= {item["name"] for item in inspector.get_columns("documents")}
        assert "analysis_version" in {item["name"] for item in inspector.get_columns("cases")}
        assert "analysis_version" in {item["name"] for item in inspector.get_columns("ai_outputs")}
        assert {"report_version", "report_digest"} <= {
            item["name"] for item in inspector.get_columns("cases")
        }
        assert "report_version" in {
            item["name"] for item in inspector.get_columns("ai_outputs")
        }
        assert {
            "ix_documents_case_id",
            "ix_documents_checksum",
            "ix_documents_processing_status",
        } <= {item["name"] for item in inspector.get_indexes("documents")}
        assert {
            "ix_fact_sources_fact_id",
            "ix_fact_sources_document_id",
        } <= {item["name"] for item in inspector.get_indexes("fact_sources")}
        assert {
            "ix_redaction_records_case_id",
            "ix_redaction_records_document_id",
            "ix_redaction_records_source_checksum",
        } <= {item["name"] for item in inspector.get_indexes("redaction_records")}
        assert {"ix_redaction_items_redaction_id"} <= {item["name"] for item in inspector.get_indexes("redaction_items")}

        foreign_keys = inspector.get_foreign_keys("fact_sources")
        by_column = {tuple(item["constrained_columns"]): item for item in foreign_keys}
        assert by_column[("fact_id",)]["referred_table"] == "case_facts"
        assert by_column[("document_id",)]["referred_table"] == "documents"
        assert by_column[("fact_id",)]["options"].get("ondelete") == "CASCADE"
        assert by_column[("document_id",)]["options"].get("ondelete") == "CASCADE"

        redaction_foreign_keys = inspector.get_foreign_keys("redaction_records")
        redaction_by_column = {tuple(item["constrained_columns"]): item for item in redaction_foreign_keys}
        assert redaction_by_column[("case_id",)]["referred_table"] == "cases"
        assert redaction_by_column[("document_id",)]["referred_table"] == "documents"
        assert redaction_by_column[("case_id",)]["options"].get("ondelete") == "CASCADE"
        assert redaction_by_column[("document_id",)]["options"].get("ondelete") == "CASCADE"

        expected_work_unit_foreign_keys = (
            ("ai_outputs", "work_unit_id"),
            ("decision_traces", "work_unit_id"),
            ("legal_memories", "source_work_unit_id"),
        )
        for table_name, column_name in expected_work_unit_foreign_keys:
            table_foreign_keys = inspector.get_foreign_keys(table_name)
            matching = [
                item for item in table_foreign_keys
                if item["constrained_columns"] == [column_name]
            ]
            assert len(matching) == 1
            assert matching[0]["referred_table"] == "work_units"

        with engine.connect() as connection:
            assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == HEAD_REVISION
    finally:
        engine.dispose()


def test_fresh_postgres_upgrade_head() -> None:
    with temporary_postgres_database() as database_url:
        run_alembic(database_url, "upgrade", "head")
        assert_postgres_head_structure(database_url)


def test_existing_postgres_upgrade_regression_and_downgrade(monkeypatch: pytest.MonkeyPatch) -> None:
    with temporary_postgres_database() as database_url:
        seed_unversioned_mvp1_database(database_url)
        run_alembic(database_url, "stamp", "0001_baseline")
        run_alembic(database_url, "upgrade", "head")
        assert_postgres_head_structure(database_url)

        engine = create_engine(database_url)
        try:
            with engine.connect() as connection:
                documents = connection.execute(text(
                    "SELECT id, original_filename, mime_type, processing_status, storage_provider, updated_at, "
                    "file_size, checksum, storage_key FROM documents ORDER BY id"
                )).mappings().all()
                assert documents[0]["original_filename"] == "材料.pdf"
                assert documents[0]["mime_type"] == "application/pdf"
                assert documents[0]["processing_status"] == "ready"
                assert documents[1]["mime_type"] == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                assert documents[1]["processing_status"] == "uploaded"
                assert documents[2]["mime_type"] == "text/plain"
                assert documents[2]["processing_status"] == "ready"
                assert all(item["storage_provider"] == "legacy_local" for item in documents)
                assert documents[0]["updated_at"] == connection.execute(
                    text("SELECT uploaded_at FROM documents WHERE id = 1")
                ).scalar_one()
                assert all(item["file_size"] is None for item in documents)
                assert all(item["checksum"] is None for item in documents)
                assert all(item["storage_key"] is None for item in documents)
                assert connection.execute(text("SELECT count(*) FROM cases WHERE id = 1")).scalar_one() == 1
                assert connection.execute(text("SELECT count(*) FROM case_facts WHERE id = 1")).scalar_one() == 1
                assert connection.execute(text("SELECT count(*) FROM case_issues WHERE id = 1")).scalar_one() == 1
                assert connection.execute(text("SELECT count(*) FROM ai_outputs WHERE id = 1")).scalar_one() == 1
                assert connection.execute(text("SELECT count(*) FROM decision_traces WHERE id = 1")).scalar_one() == 1

            run_mvp1_regression(engine, monkeypatch)
        finally:
            engine.dispose()

        run_alembic(database_url, "downgrade", "0001_baseline")
        downgraded_engine = create_engine(database_url)
        try:
            inspector = inspect(downgraded_engine)
            assert "fact_sources" not in inspector.get_table_names()
            assert "redaction_records" not in inspector.get_table_names()
            assert "redaction_items" not in inspector.get_table_names()
            assert DOCUMENT_COLUMNS.isdisjoint({item["name"] for item in inspector.get_columns("documents")})
            assert "analysis_version" not in {item["name"] for item in inspector.get_columns("cases")}
            assert "analysis_version" not in {item["name"] for item in inspector.get_columns("ai_outputs")}
            assert "report_version" not in {item["name"] for item in inspector.get_columns("cases")}
            assert "report_digest" not in {item["name"] for item in inspector.get_columns("cases")}
            assert "report_version" not in {item["name"] for item in inspector.get_columns("ai_outputs")}
            for table_name, column_name in (
                ("ai_outputs", "work_unit_id"),
                ("decision_traces", "work_unit_id"),
                ("legal_memories", "source_work_unit_id"),
            ):
                assert not any(
                    item["constrained_columns"] == [column_name]
                    for item in inspector.get_foreign_keys(table_name)
                )
            with downgraded_engine.connect() as connection:
                assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == "0001_baseline"
                assert connection.execute(text("SELECT title FROM cases WHERE id = 1")).scalar_one() == "旧案件"
                assert connection.execute(text("SELECT count(*) FROM documents")).scalar_one() == 3
                assert connection.execute(text("SELECT count(*) FROM case_facts")).scalar_one() >= 1
                assert connection.execute(text("SELECT count(*) FROM case_issues")).scalar_one() >= 1
                assert connection.execute(text("SELECT count(*) FROM ai_outputs")).scalar_one() >= 1
                assert connection.execute(text("SELECT count(*) FROM decision_traces")).scalar_one() >= 1
        finally:
            downgraded_engine.dispose()


def run_mvp1_regression(engine, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALLOW_LOCAL_AI_FALLBACK", "true")
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    from app import main, models, schemas

    session = sessionmaker(bind=engine)()
    try:
        old_case = session.get(models.Case, 1)
        assert old_case is not None and old_case.title == "旧案件"

        case = models.Case(
            title="Sprint 1A.5 回归案件",
            claimant="王某",
            employer="测试公司",
            case_type="劳动仲裁",
            workflow_mode="ai_case",
            raw_facts="王某于2025年1月入职测试公司。2026年6月公司解除劳动合同，双方对解除理由和补偿发生争议。",
        )
        session.add(case)
        session.flush()
        fact_unit = models.WorkUnit(
            case_id=case.id,
            code="fact_extraction",
            title="事实提取",
            sequence=1,
            status="待处理",
        )
        session.add(fact_unit)
        session.flush()

        main.run_ai_fact_extraction(session, case, fact_unit)
        session.commit()
        assert fact_unit.status == "待人工复核"
        assert session.query(models.AIOutput).filter_by(case_id=case.id, output_type="fact_extraction").count() == 1

        draft_fact_version = case.fact_version
        main.confirm_all_facts(case.id, schemas.BatchReview(reason="回归测试批量确认事实"), session)
        session.refresh(case)
        assert case.fact_version == draft_fact_version
        main.publish_facts(
            case.id,
            schemas.FactPublishRequest(
                operation_id="postgres-regression-facts-publish",
                reason="回归测试发布事实集",
            ),
            session,
        )
        session.refresh(case)
        assert case.fact_version == draft_fact_version + 1
        assert all(item.status in {"已确认", "已驳回"} for item in main.current_facts(session, case))

        issue_unit = session.query(models.WorkUnit).filter_by(case_id=case.id, code="issue_identification").one()
        main.run_ai_issue_identification(session, case, issue_unit)
        session.commit()
        draft_issue_version = case.issue_version
        main.confirm_all_issues(case.id, schemas.BatchReview(reason="回归测试批量确认争点"), session)
        session.refresh(case)
        assert case.issue_version == draft_issue_version
        main.publish_issues(
            case.id,
            schemas.IssuePublishRequest(
                operation_id="postgres-regression-issues-publish",
                reason="回归测试发布争点集",
            ),
            session,
        )
        session.refresh(case)
        assert case.issue_version == draft_issue_version + 1
        assert all(item.status == "人工确认" for item in main.current_issues(session, case))

        analysis_units = session.query(models.WorkUnit).filter(
            models.WorkUnit.case_id == case.id,
            models.WorkUnit.code.like("legal_analysis:%"),
        ).order_by(models.WorkUnit.id).all()
        assert analysis_units
        for index, unit in enumerate(analysis_units):
            main.run_ai_legal_analysis(session, case, unit)
            session.commit()
            if index == 0:
                main.run_ai_legal_analysis(session, case, unit)
                session.commit()
                versions = [item.version for item in session.query(models.AIOutput).filter_by(
                    case_id=case.id,
                    work_unit_id=unit.id,
                    output_type="legal_analysis",
                ).order_by(models.AIOutput.version).all()]
                assert versions == [1, 2]
            current_output = session.get(models.AIOutput, unit.ai_output_id)
            main.review_ai_output(
                current_output.id,
                schemas.AIReview(action="接受", reason="回归测试人工批准"),
                session,
            )

        analysis_ids = [
            session.get(models.WorkUnit, unit.id).ai_output_id
            for unit in analysis_units
        ]
        main.publish_analyses(
            case.id,
            schemas.AnalysisPublishRequest(
                analysis_ids=analysis_ids,
                operation_id="postgres-regression-analyses-publish",
                reason="回归测试发布分析集",
            ),
            session,
        )
        session.refresh(case)
        report = main.generate_legal_report(session, case)
        session.commit()
        from app.services.versioning import publish_report_version

        publish_report_version(
            session,
            case.id,
            report_id=report.id,
            reason="回归测试发布报告",
            source="postgres_regression",
            operation_id="postgres-regression-report-publish",
        )
        session.commit()
        session.refresh(case)
        session.refresh(report)
        assert report.output_type == "legal_report"
        assert report.fact_version == case.fact_version
        assert report.issue_version == case.issue_version
        assert report.analysis_version == case.analysis_version
        assert report.report_version == case.report_version
        assert case.report_digest
        assert "法律分析报告" in report.content
        assert session.query(models.DecisionTrace).filter(models.DecisionTrace.case_id == case.id).count() > 0
        assert session.query(models.AIOutput).filter_by(case_id=case.id, review_status="已接受").count() >= len(analysis_units)
    finally:
        session.close()
