from __future__ import annotations

import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app import models
from app.services.versioning import (
    ConcurrentVersionUpdateError,
    compute_analysis_digest,
    publish_analysis_version,
)


@pytest.fixture()
def db(tmp_path) -> Session:
    engine = create_engine(f"sqlite:///{tmp_path / 'analysis-versioning.db'}")
    models.Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def add_case(db: Session) -> models.Case:
    case = models.Case(
        title="分析版本测试",
        claimant="甲",
        employer="乙",
        material_version=2,
        fact_version=3,
        issue_version=4,
        analysis_version=0,
    )
    db.add(case)
    db.commit()
    db.refresh(case)
    return case


def add_analysis(
    db: Session,
    case: models.Case,
    *,
    title: str,
    content: str,
    work_unit_id: int | None = None,
) -> models.AIOutput:
    output = models.AIOutput(
        case_id=case.id,
        work_unit_id=work_unit_id,
        output_type="legal_analysis",
        title=title,
        content=content,
        review_status="已接受",
        version=1,
        material_version=case.material_version,
        fact_version=case.fact_version,
        issue_version=case.issue_version,
        analysis_version=case.analysis_version,
    )
    db.add(output)
    db.commit()
    db.refresh(output)
    return output


def test_publish_analysis_version_increments_and_records_event(db: Session) -> None:
    case = add_case(db)
    first = add_analysis(db, case, title="争点一分析", content="分析一")
    second = add_analysis(db, case, title="争点二分析", content="分析二")

    result = publish_analysis_version(
        db,
        case.id,
        analysis_ids=[second.id, first.id],
        reason="律师已审核完整分析集",
        source="analysis_publish_test",
        operation_id="analysis-publish-001",
    )
    db.commit()
    db.refresh(case)
    db.refresh(first)
    db.refresh(second)

    assert (result.old_version, result.new_version) == (0, 1)
    assert result.analysis_ids == (first.id, second.id)
    assert len(result.analysis_digest) == 64
    assert result.replayed is False
    assert case.analysis_version == 1
    assert {first.analysis_version, second.analysis_version} == {1}

    event = db.query(models.WorkflowEvent).filter_by(
        case_id=case.id,
        event_type="ANALYSIS_VERSION_PUBLISHED",
    ).one()
    assert json.loads(event.payload_json) == {
        "old_version": 0,
        "new_version": 1,
        "analysis_digest": result.analysis_digest,
        "analysis_ids": [first.id, second.id],
        "material_version": 2,
        "fact_version": 3,
        "issue_version": 4,
        "reason": "律师已审核完整分析集",
        "source": "analysis_publish_test",
        "operation_id": "analysis-publish-001",
    }


def test_analysis_digest_is_stable_and_ignores_display_title(db: Session) -> None:
    case = add_case(db)
    first = add_analysis(db, case, title="旧标题一", content="分析一")
    second = add_analysis(db, case, title="旧标题二", content="分析二")

    digest = compute_analysis_digest(db, case.id, [second.id, first.id, first.id])
    assert digest == compute_analysis_digest(db, case.id, [first.id, second.id])

    first.title = "仅修改展示标题"
    db.commit()
    assert compute_analysis_digest(db, case.id, [first.id, second.id]) == digest

    db.add(models.DecisionTrace(
        case_id=case.id,
        ai_output_id=first.id,
        ai_suggestion=first.content,
        human_revision="律师修订后的有效分析",
        revision_reason="修正结论",
        action="修改",
        object_type="AI输出",
        object_id=first.id,
    ))
    db.commit()
    assert compute_analysis_digest(db, case.id, [first.id, second.id]) != digest


def test_analysis_version_and_event_rollback_together(db: Session) -> None:
    case = add_case(db)
    output = add_analysis(db, case, title="待回滚分析", content="分析正文")

    publish_analysis_version(
        db,
        case.id,
        analysis_ids=[output.id],
        reason="回滚测试",
        source="analysis_publish_test",
    )
    db.rollback()
    db.refresh(case)
    db.refresh(output)

    assert case.analysis_version == 0
    assert output.analysis_version == 0
    assert db.query(models.WorkflowEvent).filter_by(
        case_id=case.id,
        event_type="ANALYSIS_VERSION_PUBLISHED",
    ).count() == 0


def test_analysis_operation_id_is_idempotent(db: Session) -> None:
    case = add_case(db)
    output = add_analysis(db, case, title="幂等分析", content="分析正文")

    first = publish_analysis_version(
        db,
        case.id,
        analysis_ids=[output.id],
        reason="首次发布",
        source="analysis_publish_test",
        operation_id="analysis-operation-001",
    )
    db.commit()
    repeated = publish_analysis_version(
        db,
        case.id,
        analysis_ids=[output.id],
        reason="客户端重试",
        source="analysis_publish_test",
        operation_id="analysis-operation-001",
    )
    db.commit()
    db.refresh(case)

    assert repeated == first.__class__(**{**first.__dict__, "replayed": True})
    assert case.analysis_version == 1
    assert db.query(models.WorkflowEvent).filter_by(
        case_id=case.id,
        event_type="ANALYSIS_VERSION_PUBLISHED",
    ).count() == 1


def test_analysis_operation_id_rejects_different_analysis_set(db: Session) -> None:
    case = add_case(db)
    first = add_analysis(db, case, title="分析一", content="正文一")
    second = add_analysis(db, case, title="分析二", content="正文二")
    publish_analysis_version(
        db,
        case.id,
        analysis_ids=[first.id],
        reason="首次发布",
        source="analysis_publish_test",
        operation_id="analysis-operation-conflict",
    )
    db.commit()

    with pytest.raises(ConcurrentVersionUpdateError):
        publish_analysis_version(
            db,
            case.id,
            analysis_ids=[first.id, second.id],
            reason="错误复用操作号",
            source="analysis_publish_test",
            operation_id="analysis-operation-conflict",
        )
    db.rollback()


def test_analysis_publish_lock_prevents_lost_updates(tmp_path) -> None:
    database_path = tmp_path / "analysis-concurrency.db"
    engine = create_engine(f"sqlite:///{database_path}")
    models.Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    setup = session_factory()
    first = session_factory()
    stale = session_factory()
    try:
        case = add_case(setup)
        output = add_analysis(setup, case, title="并发分析", content="分析正文")
        stale_case = stale.get(models.Case, case.id)
        assert stale_case is not None and stale_case.analysis_version == 0

        first_result = publish_analysis_version(
            first,
            case.id,
            analysis_ids=[output.id],
            reason="第一次发布",
            source="concurrency_test",
            operation_id="concurrent-analysis-1",
        )
        first.commit()
        second_result = publish_analysis_version(
            stale,
            case.id,
            analysis_ids=[output.id],
            reason="第二次发布",
            source="concurrency_test",
            operation_id="concurrent-analysis-2",
        )
        stale.commit()

        setup.expire_all()
        stored_case = setup.get(models.Case, case.id)
        assert stored_case is not None and stored_case.analysis_version == 2
        assert (first_result.old_version, first_result.new_version) == (0, 1)
        assert (second_result.old_version, second_result.new_version) == (1, 2)
    finally:
        setup.close()
        first.close()
        stale.close()
        engine.dispose()
