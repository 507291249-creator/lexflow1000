from __future__ import annotations

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app import models


def test_fact_can_reference_multiple_documents_and_cascades_on_delete(tmp_path) -> None:
    database_path = tmp_path / "relations.db"
    engine = create_engine(f"sqlite:///{database_path}")

    @event.listens_for(engine, "connect")
    def enable_sqlite_foreign_keys(dbapi_connection, _connection_record) -> None:
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

    models.Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        case = models.Case(title="来源测试", claimant="甲", employer="乙")
        session.add(case)
        session.flush()
        first_document = models.Document(
            case_id=case.id,
            filename="合同.pdf",
            original_filename="合同.pdf",
            file_type="pdf",
            mime_type="application/pdf",
            processing_status="ready",
        )
        second_document = models.Document(
            case_id=case.id,
            filename="聊天记录.txt",
            original_filename="聊天记录.txt",
            file_type="txt",
            mime_type="text/plain",
            processing_status="ready",
        )
        fact = models.CaseFact(case_id=case.id, ai_fact="双方于 2026 年签订合同")
        session.add_all([first_document, second_document, fact])
        session.flush()
        session.add_all(
            [
                models.FactSource(
                    fact_id=fact.id,
                    document_id=first_document.id,
                    source_text="合同签署日期为 2026 年 1 月 1 日",
                    page_number=1,
                    relation_type="support",
                ),
                models.FactSource(
                    fact_id=fact.id,
                    document_id=second_document.id,
                    source_text="双方确认合同已经签署",
                    paragraph_index=3,
                    relation_type="supplement",
                ),
            ]
        )
        session.commit()

        stored_fact = session.get(models.CaseFact, fact.id)
        assert stored_fact is not None
        assert len(stored_fact.sources) == 2
        assert {item.document_id for item in stored_fact.sources} == {first_document.id, second_document.id}

        session.delete(stored_fact)
        session.commit()
        assert session.query(models.FactSource).count() == 0
        assert session.query(models.Document).count() == 2
    finally:
        session.close()
        engine.dispose()
