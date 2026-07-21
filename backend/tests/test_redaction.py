from __future__ import annotations

import json
from dataclasses import replace
from hashlib import sha256

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app import models
from app.main import serialize_redaction_item
from app.services.redaction import USCC_CHARS, USCC_WEIGHTS, RedactionService


def valid_uscc(prefix: str) -> str:
    """Build an 18-character test USCC from a valid 17-character prefix."""
    total = sum(USCC_CHARS.index(char) * weight for char, weight in zip(prefix, USCC_WEIGHTS))
    return prefix + USCC_CHARS[(31 - total % 31) % 31]


@pytest.fixture()
def session(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'redaction.db'}")

    @event.listens_for(engine, "connect")
    def enable_sqlite_foreign_keys(dbapi_connection, _connection_record) -> None:
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

    models.Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    try:
        yield db
    finally:
        db.close()
        engine.dispose()


def create_case_and_document(session, raw_text: str):
    case = models.Case(title="脱敏回归案件", claimant="张三", employer="北京星河科技有限公司")
    session.add(case)
    session.flush()
    document = models.Document(
        case_id=case.id,
        filename="演示材料.txt",
        original_filename="演示材料.txt",
        file_type="txt",
        mime_type="text/plain",
        processing_status="ready",
        raw_text=raw_text,
    )
    session.add(document)
    session.commit()
    return case, document


def test_detects_checksum_validated_identifiers_and_masks() -> None:
    service = RedactionService()
    uscc = valid_uscc("91110000100000000")
    source = (
        "张三身份证11010519491231002X，手机号13800138000，邮箱zhangsan@example.com，"
        "银行卡4532015112830366，统一社会信用代码" + uscc + "。"
    )

    items = service.detect(source, subject_names=["张三"])
    entity_types = {item.entity_type for item in items}

    assert service.validate_id_card("11010519491231002X")
    assert not service.validate_id_card("11010519490231002X")
    assert service.validate_bank_card("4532015112830366")
    assert not service.validate_bank_card("4532015112830367")
    assert service.validate_uscc(uscc)
    assert not service.validate_uscc(uscc[:-1] + "0")
    assert {"身份证", "手机号", "邮箱", "银行卡", "统一社会信用代码"} <= entity_types

    preview = service.build_preview(source, items)
    assert "11010519491231002X" not in preview
    assert "13800138000" not in preview
    assert "zhangsan@example.com" not in preview
    assert "4532015112830366" not in preview
    assert uscc not in preview
    assert "138****8000" in preview
    assert "银行卡尾号0366" in preview


def test_case_subject_aliases_are_consistent_and_candidates_hold_no_original_values() -> None:
    service = RedactionService()
    source = "张三向北京星河科技有限公司主张权利，张三提交了补充说明。"

    items = service.detect(source, subject_names=["张三", "北京星河科技有限公司"])
    person_items = [item for item in items if item.entity_type == "自然人姓名"]
    company_items = [item for item in items if item.entity_type == "企业名称"]

    assert len(person_items) == 2
    assert {item.replacement for item in person_items} == {"自然人A"}
    assert len(company_items) == 1
    assert company_items[0].replacement == "公司A"
    assert "张三" not in repr(items)
    assert "北京星河科技有限公司" not in repr(items)
    assert service.build_preview(source, items) == "自然人A向公司A主张权利，自然人A提交了补充说明。"


def test_keep_action_and_overlap_resolution_are_safe() -> None:
    service = RedactionService()
    source = "联系方式：13800138000"
    mobile = service.detect(source)[0]
    overlapping = service.manual_item(
        source,
        start_offset=source.index("13800138000") + 2,
        end_offset=source.index("13800138000") + 8,
        entity_type="自定义敏感信息",
        replacement="已脱敏",
        action="full_replace",
    )

    resolved = service.resolve_overlaps([mobile, overlapping])
    assert resolved == [mobile]
    assert service.build_preview(source, [replace(mobile, action="keep")]) == source


def test_manual_item_and_redaction_models_preserve_the_original_text(session) -> None:
    source = "张三住址为北京市海淀区中关村大街1号。"
    case, document = create_case_and_document(session, source)
    service = RedactionService()
    item = service.manual_item(
        source,
        start_offset=source.index("北京市"),
        end_offset=source.index("号") + 1,
        entity_type="地址",
        replacement="北京市海淀区***",
        action="partial_mask",
    )
    record = models.RedactionRecord(
        case_id=case.id,
        document_id=document.id,
        source_checksum=sha256(source.encode("utf-8")).hexdigest(),
        redacted_text=service.build_preview(source, [item]),
    )
    session.add(record)
    session.flush()
    stored_item = models.RedactionItem(
        redaction_id=record.id,
        entity_type=item.entity_type,
        start_offset=item.start_offset,
        end_offset=item.end_offset,
        replacement=item.replacement,
        action=item.action,
        confidence=item.confidence,
        rule_code=item.rule_code,
        review_status="人工新增",
        original_fingerprint=item.original_fingerprint,
    )
    session.add(stored_item)
    session.commit()

    assert document.raw_text == source
    assert "中关村大街1号" not in record.redacted_text
    payload = serialize_redaction_item(stored_item)
    assert "original_text" not in payload
    assert "中关村大街1号" not in json.dumps(payload, ensure_ascii=False, default=str)

    document.raw_text = "张三住址更新为北京市朝阳区建国路1号。"
    session.commit()
    assert sha256(document.raw_text.encode("utf-8")).hexdigest() != record.source_checksum


def test_redaction_items_cascade_when_record_is_deleted(session) -> None:
    case, document = create_case_and_document(session, "张三手机号13800138000")
    item = RedactionService().detect(document.raw_text, subject_names=[case.claimant])[0]
    record = models.RedactionRecord(
        case_id=case.id,
        document_id=document.id,
        source_checksum=sha256(document.raw_text.encode("utf-8")).hexdigest(),
    )
    session.add(record)
    session.flush()
    session.add(
        models.RedactionItem(
            redaction_id=record.id,
            entity_type=item.entity_type,
            start_offset=item.start_offset,
            end_offset=item.end_offset,
            replacement=item.replacement,
            action=item.action,
            confidence=item.confidence,
            rule_code=item.rule_code,
            original_fingerprint=item.original_fingerprint,
        )
    )
    session.commit()

    session.delete(record)
    session.commit()
    assert session.query(models.RedactionItem).count() == 0
    assert session.query(models.Document).count() == 1
