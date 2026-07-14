import json
import os
import shutil
from datetime import datetime
from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from . import models, schemas
from .agents.decision_trace import create_trace
from .agents.document_parser import parse_document
from .agents.draft_agent import generate_draft
from .agents.evidence_agent import generate_evidences
from .agents.legal_memory import memory_from_trace
from .agents.p0_workflow import STANDARD_WORKFLOW, analysis_content, mock_facts, mock_issues, structured_analysis
from .agents.p1_workflow import P1_INITIAL_WORKFLOW, fact_extraction, issue_identification, legal_analysis, render_analysis
from .agents.llm_provider import StructuredOutputError
from .agents.research_agent import generate_analysis
from .agents.risk_agent import generate_risk
from .agents.similarity_search import recommend_memories
from .database import Base, SessionLocal, engine, get_db
from .utils import from_json, join_tags, log_event, split_tags, to_json


APP_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", str(APP_DIR / "uploads")))
MOCK_DIR = APP_DIR / "mock"
UPLOAD_DIR.mkdir(exist_ok=True)

app = FastAPI(title="LexFlow MVP API", version="0.1.0")

cors_origins = [
    item.strip()
    for item in os.getenv("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(",")
    if item.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_origin_regex=os.getenv("CORS_ORIGIN_REGEX") or None,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup() -> None:
    Base.metadata.create_all(bind=engine)
    ensure_existing_schema()
    seed_demo_data()


def ensure_existing_schema() -> None:
    additions = {
        "cases": {
            "case_no": "TEXT NOT NULL DEFAULT ''",
            "case_type": "TEXT NOT NULL DEFAULT '劳动仲裁'",
            "raw_facts": "TEXT NOT NULL DEFAULT ''",
            "stage": "TEXT NOT NULL DEFAULT '材料收集'",
            "handler": "TEXT NOT NULL DEFAULT ''",
            "next_follow_up_at": "TEXT NOT NULL DEFAULT ''",
            "next_action": "TEXT NOT NULL DEFAULT ''",
            "workflow_mode": "TEXT NOT NULL DEFAULT 'standard'",
            "fact_version": "INTEGER NOT NULL DEFAULT 1",
            "issue_version": "INTEGER NOT NULL DEFAULT 1",
        },
        "ai_outputs": {
            "work_unit_id": "INTEGER",
            "review_status": "TEXT NOT NULL DEFAULT '待复核'",
            "version": "INTEGER NOT NULL DEFAULT 1",
            "fact_version": "INTEGER NOT NULL DEFAULT 1",
            "issue_version": "INTEGER NOT NULL DEFAULT 1",
            "input_snapshot_json": "TEXT NOT NULL DEFAULT '{}'",
        },
        "decision_traces": {
            "work_unit_id": "INTEGER",
            "action": "TEXT NOT NULL DEFAULT '人工修改'",
            "object_type": "TEXT NOT NULL DEFAULT 'AI输出'",
            "object_id": "INTEGER",
        },
        "legal_memories": {
            "source_work_unit_id": "INTEGER",
            "category": "TEXT NOT NULL DEFAULT '案件经验'",
            "status": "TEXT NOT NULL DEFAULT '已沉淀'",
            "review_reason": "TEXT NOT NULL DEFAULT ''",
        },
        "work_units": {
            "parent_issue_id": "INTEGER",
            "version": "INTEGER NOT NULL DEFAULT 1",
        },
        "case_facts": {
            "fact_version": "INTEGER NOT NULL DEFAULT 1",
        },
        "case_issues": {
            "importance": "TEXT NOT NULL DEFAULT '中'",
            "related_facts": "TEXT NOT NULL DEFAULT '[]'",
            "related_fact_ids": "TEXT NOT NULL DEFAULT '[]'",
            "issue_version": "INTEGER NOT NULL DEFAULT 1",
        },
    }
    inspector = inspect(engine)
    with engine.begin() as connection:
        for table, fields in additions.items():
            if table not in inspector.get_table_names():
                continue
            existing = {item["name"] for item in inspector.get_columns(table)}
            for name, definition in fields.items():
                if name not in existing:
                    connection.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {definition}"))


def seed_demo_data() -> None:
    db = SessionLocal()
    try:
        if not db.query(models.Case).first():
            sample_text = (MOCK_DIR / "sample_case.txt").read_text(encoding="utf-8")
            case = models.Case(
                title="王某诉上海某科技公司劳动仲裁案",
                claimant="王某",
                employer="上海某科技公司",
                status="created",
                summary=sample_text,
                claim_amount="约 120,000 元",
            )
            db.add(case)
            db.commit()
            db.refresh(case)

            document = models.Document(
                case_id=case.id,
                filename="sample_case.txt",
                file_type="txt",
                raw_text=sample_text,
                parsed_json=to_json({
                    "file_name": "sample_case.txt",
                    "file_type": "txt",
                    "keywords": ["劳动合同", "工资", "解除", "微信", "劳动关系"],
                    "preview": sample_text[:500],
                }),
            )
            db.add(document)
            log_event(db, case.id, "demo_seeded", "已内置劳动仲裁示例案件和材料")

        if not db.query(models.LegalMemory).first():
            memories = json.loads((MOCK_DIR / "sample_memory.json").read_text(encoding="utf-8"))
            for item in memories:
                db.add(models.LegalMemory(
                    title=item["title"],
                    scenario=item["scenario"],
                    legal_issue=item["legal_issue"],
                    rule_summary=item["rule_summary"],
                    decision_pattern=item["decision_pattern"],
                    tags=join_tags(item.get("tags", [])),
                ))
            db.commit()

        case = db.query(models.Case).first()
        if case:
            case.case_no = case.case_no or "LA-2024-001"
            case.case_type = case.case_type or "劳动仲裁"
            case.stage = case.stage or "文书准备"
            case.handler = case.handler or "张律师"
            case.next_follow_up_at = case.next_follow_up_at or "2026-07-15"
            case.next_action = case.next_action or "核验解除通知原始载体，并确认仲裁请求金额。"

            if not case.todos:
                db.add_all([
                    models.CaseTodo(case_id=case.id, title="核验微信解除通知原始载体", due_date="2026-07-15", priority="高"),
                    models.CaseTodo(case_id=case.id, title="整理工资流水与考勤材料", due_date="2026-07-18", priority="普通"),
                ])
            if not case.work_records:
                db.add(models.CaseWorkRecord(
                    case_id=case.id,
                    content="已完成基础材料梳理，确认工资流水、聊天记录和入职邮件可作为初步证据。",
                ))
            if not case.follow_ups:
                db.add(models.CaseFollowUp(
                    case_id=case.id,
                    progress="已与当事人沟通仲裁请求及现有材料，等待补充原始聊天记录。",
                    next_action=case.next_action,
                    follow_up_at=case.next_follow_up_at,
                    stage=case.stage,
                ))
            ensure_standard_work_units(db, case)
            db.commit()
    finally:
        db.close()


def require_case(db: Session, case_id: int) -> models.Case:
    case = db.query(models.Case).filter(models.Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="未找到案件")
    return case


def serialize_document(document: models.Document) -> dict:
    return {
        "id": document.id,
        "case_id": document.case_id,
        "filename": document.filename,
        "file_type": document.file_type,
        "raw_text": document.raw_text,
        "parsed_json": from_json(document.parsed_json, {}),
        "uploaded_at": document.uploaded_at,
    }


def serialize_output(output: models.AIOutput) -> dict:
    meta = from_json(output.meta_json, {})
    llm = meta.get("llm") or (meta.get("structured") or {}).get("_llm", {})
    return {
        "id": output.id,
        "case_id": output.case_id,
        "output_type": output.output_type,
        "title": output.title,
        "content": output.content,
        "meta_json": meta,
        "execution_mode": llm.get("execution_mode", "fallback" if llm.get("provider") == "local-fallback" else "llm"),
        "work_unit_id": output.work_unit_id,
        "review_status": output.review_status,
        "version": output.version,
        "fact_version": output.fact_version,
        "issue_version": output.issue_version,
        "input_snapshot_json": from_json(output.input_snapshot_json, {}),
        "created_at": output.created_at,
    }


def serialize_trace(trace: models.DecisionTrace) -> dict:
    return {
        "id": trace.id,
        "case_id": trace.case_id,
        "ai_output_id": trace.ai_output_id,
        "ai_suggestion": trace.ai_suggestion,
        "human_revision": trace.human_revision,
        "revision_reason": trace.revision_reason,
        "tags": split_tags(trace.tags),
        "work_unit_id": trace.work_unit_id,
        "action": trace.action,
        "object_type": trace.object_type,
        "object_id": trace.object_id,
        "created_at": trace.created_at,
    }


def serialize_memory(memory: models.LegalMemory) -> dict:
    return {
        "id": memory.id,
        "title": memory.title,
        "scenario": memory.scenario,
        "legal_issue": memory.legal_issue,
        "rule_summary": memory.rule_summary,
        "decision_pattern": memory.decision_pattern,
        "tags": split_tags(memory.tags),
        "source_trace_id": memory.source_trace_id,
        "source_work_unit_id": memory.source_work_unit_id,
        "category": memory.category,
        "status": memory.status,
        "review_reason": memory.review_reason,
        "created_at": memory.created_at,
    }


def serialize_work_unit(unit: models.WorkUnit) -> dict:
    return {
        "id": unit.id,
        "case_id": unit.case_id,
        "code": unit.code,
        "title": unit.title,
        "sequence": unit.sequence,
        "status": unit.status,
        "description": unit.description,
        "input_json": from_json(unit.input_json, {}),
        "output_json": from_json(unit.output_json, {}),
        "ai_output_id": unit.ai_output_id,
        "parent_issue_id": unit.parent_issue_id,
        "version": unit.version,
        "reviewer": unit.reviewer,
        "reviewed_at": unit.reviewed_at,
        "created_at": unit.created_at,
        "updated_at": unit.updated_at,
    }


def serialize_fact(item: models.CaseFact) -> dict:
    return {
        "id": item.id,
        "case_id": item.case_id,
        "work_unit_id": item.work_unit_id,
        "category": item.category,
        "ai_fact": item.ai_fact,
        "human_fact": item.human_fact,
        "source_document": item.source_document,
        "status": item.status,
        "confidence": item.confidence,
        "fact_version": item.fact_version,
        "created_at": item.created_at,
        "updated_at": item.updated_at,
    }


def serialize_issue(item: models.CaseIssue) -> dict:
    return {
        "id": item.id,
        "case_id": item.case_id,
        "work_unit_id": item.work_unit_id,
        "title": item.title,
        "description": item.description,
        "analysis_hint": item.analysis_hint,
        "source": item.source,
        "status": item.status,
        "importance": item.importance,
        "related_facts": from_json(item.related_facts, []),
        "related_fact_ids": [str(value) for value in from_json(item.related_fact_ids, [])],
        "issue_version": item.issue_version,
        "created_at": item.created_at,
        "updated_at": item.updated_at,
    }


def ensure_standard_work_units(db: Session, case: models.Case) -> list[models.WorkUnit]:
    existing = {item.code for item in case.work_units}
    for sequence, (code, title, description) in enumerate(STANDARD_WORKFLOW, start=1):
        if code not in existing:
            db.add(models.WorkUnit(
                case_id=case.id,
                code=code,
                title=title,
                description=description,
                sequence=sequence,
                status="待处理",
            ))
    db.flush()
    return db.query(models.WorkUnit).filter(models.WorkUnit.case_id == case.id).order_by(models.WorkUnit.sequence).all()


def ensure_ai_case_workflow(db: Session, case: models.Case) -> list[models.WorkUnit]:
    existing = {item.code for item in case.work_units}
    for sequence, (code, title, description) in enumerate(P1_INITIAL_WORKFLOW, start=1):
        if code not in existing:
            db.add(models.WorkUnit(
                case_id=case.id,
                code=code,
                title=title,
                description=description,
                sequence=sequence,
                status="待处理",
            ))
    db.flush()
    return db.query(models.WorkUnit).filter(models.WorkUnit.case_id == case.id).order_by(models.WorkUnit.sequence).all()


def ensure_case_workflow(db: Session, case: models.Case) -> list[models.WorkUnit]:
    if case.workflow_mode == "ai_case":
        return ensure_ai_case_workflow(db, case)
    return ensure_standard_work_units(db, case)


def current_facts(db: Session, case: models.Case) -> list[models.CaseFact]:
    query = db.query(models.CaseFact).filter(models.CaseFact.case_id == case.id)
    if case.workflow_mode == "ai_case":
        query = query.filter(models.CaseFact.fact_version == case.fact_version)
    return query.order_by(models.CaseFact.created_at.asc()).all()


def current_issues(db: Session, case: models.Case) -> list[models.CaseIssue]:
    query = db.query(models.CaseIssue).filter(models.CaseIssue.case_id == case.id)
    if case.workflow_mode == "ai_case":
        query = query.filter(models.CaseIssue.issue_version == case.issue_version)
    return query.order_by(models.CaseIssue.created_at.asc()).all()


def case_material_text(db: Session, case: models.Case) -> str:
    documents = db.query(models.Document).filter(models.Document.case_id == case.id).all()
    parts = [f"[{item.filename}]\n{item.raw_text}" for item in documents if item.raw_text]
    if case.raw_facts and case.raw_facts not in "\n".join(parts):
        parts.insert(0, f"[用户原始事实]\n{case.raw_facts}")
    elif case.summary and case.summary not in "\n".join(parts):
        parts.insert(0, f"[案件登记]\n{case.summary}")
    return "\n\n".join(parts) or "尚未提供可解析的案件事实。"


def next_output_version(db: Session, unit: models.WorkUnit) -> int:
    latest = db.query(models.AIOutput.version).filter(
        models.AIOutput.work_unit_id == unit.id
    ).order_by(models.AIOutput.version.desc()).first()
    return (latest[0] if latest else 0) + 1


def validate_related_fact_ids(case: models.Case, values: list[str], db: Session) -> list[str]:
    available = {str(item.id) for item in current_facts(db, case) if item.status != "已驳回"}
    normalized = [str(value).strip() for value in values if str(value).strip()]
    invalid = [value for value in normalized if value not in available]
    if invalid:
        raise HTTPException(status_code=400, detail=f"关联事实 ID 不存在或已驳回：{', '.join(invalid)}")
    return list(dict.fromkeys(normalized))


def mark_work_unit_failed(db: Session, case: models.Case, unit: models.WorkUnit, error: StructuredOutputError) -> models.WorkUnit:
    unit.status = "失败"
    unit.output_json = to_json({
        "error": {"code": error.code, "message": str(error), "attempts": error.attempts},
        "retryable": True,
    })
    log_event(db, case.id, "structured_ai_failed", f"{unit.title} 执行失败，可重新运行", {"work_unit_id": unit.id, "code": error.code})
    return unit


def invalidate_analysis_units(db: Session, case: models.Case) -> None:
    db.query(models.WorkUnit).filter(
        models.WorkUnit.case_id == case.id,
        models.WorkUnit.code.like("legal_analysis:%"),
        models.WorkUnit.status.in_(["待处理", "待人工复核", "已批准"]),
    ).update({"status": "需重新分析"}, synchronize_session=False)


def advance_fact_version(db: Session, case: models.Case) -> int:
    old_version = case.fact_version
    case.fact_version += 1
    db.query(models.CaseFact).filter(
        models.CaseFact.case_id == case.id,
        models.CaseFact.fact_version == old_version,
    ).update({"fact_version": case.fact_version}, synchronize_session=False)
    invalidate_analysis_units(db, case)
    return case.fact_version


def advance_issue_version(db: Session, case: models.Case) -> int:
    old_version = case.issue_version
    case.issue_version += 1
    db.query(models.CaseIssue).filter(
        models.CaseIssue.case_id == case.id,
        models.CaseIssue.issue_version == old_version,
    ).update({"issue_version": case.issue_version}, synchronize_session=False)
    invalidate_analysis_units(db, case)
    return case.issue_version


def facts_are_confirmed(db: Session, case: models.Case) -> bool:
    facts = current_facts(db, case)
    return bool(facts) and all(item.status in {"已确认", "已驳回"} for item in facts) and any(
        item.status == "已确认" for item in facts
    )


def run_ai_fact_extraction(db: Session, case: models.Case, unit: models.WorkUnit) -> models.WorkUnit:
    existing = current_facts(db, case)
    if existing:
        case.fact_version += 1
    try:
        result = fact_extraction(case, case_material_text(db, case))
    except StructuredOutputError as error:
        return mark_work_unit_failed(db, case, unit, error)
    case.summary = result.get("case_summary") or case.summary
    parties = result.get("parties", {})
    if case.claimant in {"", "待识别"}:
        case.claimant = parties.get("claimant") or case.claimant
    if case.employer in {"", "待识别"}:
        case.employer = parties.get("employer") or case.employer
    source_name = "现场输入或上传材料"
    for item in result.get("key_facts", []):
        db.add(models.CaseFact(
            case_id=case.id,
            work_unit_id=unit.id,
            category=item.get("category") or "一般事实",
            ai_fact=item.get("content") or "",
            source_document=item.get("source") or source_name,
            confidence=item.get("confidence") or result.get("fact_confidence") or "中",
            fact_version=case.fact_version,
        ))
    for item in result.get("pending_facts", []):
        db.add(models.CaseFact(
            case_id=case.id,
            work_unit_id=unit.id,
            category="待确认事项",
            ai_fact=item,
            source_document=source_name,
            confidence="待核验",
            fact_version=case.fact_version,
        ))
    db.flush()
    output = models.AIOutput(
        case_id=case.id,
        work_unit_id=unit.id,
        output_type="fact_extraction",
        title="AI 事实提取",
        content=json.dumps(result, ensure_ascii=False, indent=2),
        meta_json=to_json({"structured": result, "llm": result.get("_llm", {})}),
        review_status="待复核",
        version=next_output_version(db, unit),
        fact_version=case.fact_version,
        issue_version=case.issue_version,
        input_snapshot_json=to_json({"material": case_material_text(db, case)[:12000]}),
    )
    db.add(output)
    db.flush()
    unit.ai_output_id = output.id
    unit.version += 1
    unit.output_json = to_json({"structured": result, "output_id": output.id, "fact_version": case.fact_version})
    unit.status = "待人工复核"
    log_event(db, case.id, "fact_extraction_generated", "AI 已生成结构化事实，等待人工确认", {"fact_version": case.fact_version})
    return unit


def run_ai_issue_identification(db: Session, case: models.Case, unit: models.WorkUnit) -> models.WorkUnit:
    if not facts_are_confirmed(db, case):
        raise HTTPException(status_code=400, detail="请先确认或驳回全部事实，再进入争点识别")
    if current_issues(db, case):
        case.issue_version += 1
    facts = current_facts(db, case)
    try:
        result = issue_identification(case, facts)
    except StructuredOutputError as error:
        return mark_work_unit_failed(db, case, unit, error)
    try:
        for item in result.get("issues", []):
            item["related_fact_ids"] = validate_related_fact_ids(case, item.get("related_fact_ids") or [], db)
    except HTTPException as error:
        return mark_work_unit_failed(
            db, case, unit,
            StructuredOutputError(error.detail, code="invalid_related_fact_ids", attempts=1),
        )
    for item in result.get("issues", []):
        db.add(models.CaseIssue(
            case_id=case.id,
            work_unit_id=unit.id,
            title=item.get("title") or "待确认争点",
            description=item.get("description") or "",
            analysis_hint="请结合关联事实、适用法律和证据需求进行分析。",
            source="AI建议",
            status="AI建议",
            importance=item.get("importance") or "中",
            related_facts=to_json([]),
            related_fact_ids=to_json(item.get("related_fact_ids") or []),
            issue_version=case.issue_version,
        ))
    db.flush()
    output = models.AIOutput(
        case_id=case.id,
        work_unit_id=unit.id,
        output_type="issue_identification",
        title="AI 争点识别",
        content=json.dumps(result, ensure_ascii=False, indent=2),
        meta_json=to_json({"structured": result, "llm": result.get("_llm", {})}),
        review_status="待复核",
        version=next_output_version(db, unit),
        fact_version=case.fact_version,
        issue_version=case.issue_version,
        input_snapshot_json=to_json({"fact_version": case.fact_version, "facts": [serialize_fact(item) for item in facts]}),
    )
    db.add(output)
    db.flush()
    unit.ai_output_id = output.id
    unit.version += 1
    unit.output_json = to_json({"structured": result, "output_id": output.id, "issue_version": case.issue_version})
    unit.status = "待人工复核"
    log_event(db, case.id, "issue_identification_generated", "AI 已生成争点建议，等待人工确认", {"issue_version": case.issue_version})
    return unit


def sync_analysis_units(db: Session, case: models.Case) -> list[models.WorkUnit]:
    confirmed = [item for item in current_issues(db, case) if item.status == "人工确认"]
    existing = {item.parent_issue_id: item for item in db.query(models.WorkUnit).filter(
        models.WorkUnit.case_id == case.id,
        models.WorkUnit.code.like("legal_analysis:%"),
    ).all()}
    sequence = db.query(models.WorkUnit).filter(models.WorkUnit.case_id == case.id).count() + 1
    units = []
    for issue in confirmed:
        unit = existing.get(issue.id)
        if not unit:
            unit = models.WorkUnit(
                case_id=case.id,
                code=f"legal_analysis:{issue.id}",
                title=f"法律分析：{issue.title}",
                description="围绕已确认争点运行结构化法律分析。",
                sequence=sequence,
                status="待处理",
                parent_issue_id=issue.id,
                input_json=to_json({"issue_id": issue.id}),
            )
            db.add(unit)
            sequence += 1
        units.append(unit)
    db.flush()
    return units


def run_ai_legal_analysis(db: Session, case: models.Case, unit: models.WorkUnit, supplementary_material: str = "") -> models.WorkUnit:
    issue = db.query(models.CaseIssue).filter(
        models.CaseIssue.id == unit.parent_issue_id,
        models.CaseIssue.case_id == case.id,
        models.CaseIssue.issue_version == case.issue_version,
    ).first()
    if not issue or issue.status != "人工确认":
        raise HTTPException(status_code=400, detail="请先确认该争点，再运行法律分析")
    facts = [item for item in current_facts(db, case) if item.status == "已确认"]
    memories = db.query(models.LegalMemory).filter(models.LegalMemory.status == "已沉淀").all()
    memory_context = recommend_memories(case, memories, limit=3)
    try:
        result = legal_analysis(case, issue, facts, memory_context, supplementary_material)
    except StructuredOutputError as error:
        return mark_work_unit_failed(db, case, unit, error)
    snapshot = {
        "fact_version": case.fact_version,
        "issue_version": case.issue_version,
        "facts": [serialize_fact(item) for item in facts],
        "issue": serialize_issue(issue),
        "legal_memory": memory_context,
        "supplementary_material": supplementary_material,
    }
    output = models.AIOutput(
        case_id=case.id,
        work_unit_id=unit.id,
        output_type="legal_analysis",
        title=f"法律分析：{issue.title}",
        content=render_analysis(result),
        meta_json=to_json({"structured": result, "llm": result.get("_llm", {}), "legal_memory_matches": memory_context}),
        review_status="待复核",
        version=next_output_version(db, unit),
        fact_version=case.fact_version,
        issue_version=case.issue_version,
        input_snapshot_json=to_json(snapshot),
    )
    db.add(output)
    db.flush()
    unit.ai_output_id = output.id
    unit.output_json = to_json({"structured": result, "output_id": output.id, "input_versions": {"facts": case.fact_version, "issues": case.issue_version}})
    unit.status = "待人工复核"
    log_event(db, case.id, "legal_analysis_generated", f"已生成争点法律分析：{issue.title}", {"work_unit_id": unit.id, "version": output.version})
    return unit


def reviewed_output_content(db: Session, output: models.AIOutput) -> str:
    trace = db.query(models.DecisionTrace).filter(
        models.DecisionTrace.ai_output_id == output.id,
        models.DecisionTrace.action == "修改",
    ).order_by(models.DecisionTrace.created_at.desc()).first()
    return trace.human_revision if trace else output.content


def generate_legal_report(db: Session, case: models.Case) -> models.AIOutput:
    facts = [item for item in current_facts(db, case) if item.status == "已确认"]
    issues = [item for item in current_issues(db, case) if item.status == "人工确认"]
    analyses = db.query(models.AIOutput).filter(
        models.AIOutput.case_id == case.id,
        models.AIOutput.output_type == "legal_analysis",
        models.AIOutput.review_status.in_(["已接受", "已修改"]),
        models.AIOutput.fact_version == case.fact_version,
        models.AIOutput.issue_version == case.issue_version,
    ).order_by(models.AIOutput.created_at.asc()).all()
    if not facts or not issues or not analyses:
        raise HTTPException(status_code=400, detail="请先确认事实和争点，并至少批准一份当前版本的法律分析")
    analyses_by_issue = {item.work_unit_id: item for item in analyses}
    sections = []
    for issue in issues:
        unit = db.query(models.WorkUnit).filter(models.WorkUnit.parent_issue_id == issue.id).first()
        output = analyses_by_issue.get(unit.id if unit else None)
        if output:
            sections.append({"issue": serialize_issue(issue), "analysis": reviewed_output_content(db, output), "analysis_version": output.version})
    if not sections:
        raise HTTPException(status_code=400, detail="尚无与当前确认争点对应的已批准分析")
    report = {
        "case_summary": case.summary,
        "fact_framework": [item.human_fact or item.ai_fact for item in facts],
        "issues": [serialize_issue(item) for item in issues],
        "issue_analyses": sections,
        "risk_summary": "请结合每项分析中的风险等级、反方观点和不确定事项综合判断。",
        "evidence_recommendations": ["优先固定原始载体、完整聊天上下文、工资流水和工作管理记录。"],
        "next_actions": ["核对各项证据的真实性、完整性与关联性。", "根据已批准分析整理仲裁请求及证据目录。"],
    }
    content = "\n\n".join([
        "法律分析报告",
        f"一、案件摘要\n{report['case_summary']}",
        "二、事实框架\n" + "\n".join(f"- {item}" for item in report["fact_framework"]),
        "三、争点列表\n" + "\n".join(f"- {item.title}（{item.importance}）" for item in issues),
        "四、逐项法律分析\n" + "\n\n".join(f"【{item['issue']['title']}｜版本 {item['analysis_version']}】\n{item['analysis']}" for item in sections),
        f"五、风险总结\n{report['risk_summary']}",
        "六、证据建议\n" + "\n".join(f"- {item}" for item in report["evidence_recommendations"]),
        "七、下一步行动\n" + "\n".join(f"- {item}" for item in report["next_actions"]),
    ])
    report_unit = db.query(models.WorkUnit).filter(
        models.WorkUnit.case_id == case.id,
        models.WorkUnit.code == "legal_analysis_report",
    ).first()
    if not report_unit:
        report_unit = models.WorkUnit(
            case_id=case.id,
            code="legal_analysis_report",
            title="法律分析报告",
            description="汇总已确认事实、争点和已批准法律分析。",
            sequence=db.query(models.WorkUnit).filter(models.WorkUnit.case_id == case.id).count() + 1,
            status="分析中",
        )
        db.add(report_unit)
        db.flush()
    output = models.AIOutput(
        case_id=case.id,
        work_unit_id=report_unit.id,
        output_type="legal_report",
        title="法律分析报告",
        content=content,
        meta_json=to_json({"structured": report}),
        review_status="已接受",
        version=next_output_version(db, report_unit),
        fact_version=case.fact_version,
        issue_version=case.issue_version,
        input_snapshot_json=to_json({"fact_version": case.fact_version, "issue_version": case.issue_version, "analysis_ids": [item.id for item in analyses]}),
    )
    db.add(output)
    db.flush()
    report_unit.ai_output_id = output.id
    report_unit.status = "已完成"
    report_unit.output_json = to_json({"structured": report, "output_id": output.id})
    log_event(db, case.id, "legal_report_generated", "已根据已批准分析生成法律分析报告", {"output_id": output.id})
    return output


def execute_ai_case_work_unit(db: Session, case: models.Case, unit: models.WorkUnit) -> models.WorkUnit:
    if unit.code == "fact_extraction":
        return run_ai_fact_extraction(db, case, unit)
    if unit.code == "issue_identification":
        return run_ai_issue_identification(db, case, unit)
    if unit.code.startswith("legal_analysis:"):
        return run_ai_legal_analysis(db, case, unit)
    if unit.code == "legal_analysis_report":
        generate_legal_report(db, case)
        return unit
    raise HTTPException(status_code=400, detail="该 AI 案件工作单元暂不支持直接运行")


def maybe_generate_issues_after_fact_review(db: Session, case: models.Case) -> None:
    if case.workflow_mode != "ai_case" or not facts_are_confirmed(db, case):
        return
    existing = current_issues(db, case)
    if existing:
        return
    unit = db.query(models.WorkUnit).filter(
        models.WorkUnit.case_id == case.id,
        models.WorkUnit.code == "issue_identification",
    ).first()
    if not unit:
        unit = models.WorkUnit(
            case_id=case.id,
            code="issue_identification",
            title="争点识别",
            description="基于已确认事实识别需要人工确认的争点。",
            sequence=db.query(models.WorkUnit).filter(models.WorkUnit.case_id == case.id).count() + 1,
            status="待处理",
        )
        db.add(unit)
        db.flush()
    run_ai_issue_identification(db, case, unit)


def record_human_trace(
    db: Session,
    *,
    case_id: int,
    action: str,
    object_type: str,
    object_id: int | None,
    ai_suggestion: str,
    human_revision: str,
    reason: str,
    work_unit_id: int | None = None,
    tags: list[str] | None = None,
) -> models.DecisionTrace:
    trace = models.DecisionTrace(
        case_id=case_id,
        ai_suggestion=ai_suggestion or "无 AI 原始建议",
        human_revision=human_revision or "未形成替代文本",
        revision_reason=reason,
        tags=join_tags(tags or [object_type, action]),
        work_unit_id=work_unit_id,
        action=action,
        object_type=object_type,
        object_id=object_id,
    )
    db.add(trace)
    db.flush()
    return trace


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "LexFlow MVP"}


@app.post("/cases", response_model=schemas.CaseOut)
def create_case(payload: schemas.CaseCreate, db: Session = Depends(get_db)):
    case = models.Case(**payload.model_dump())
    if not case.raw_facts:
        case.raw_facts = case.summary
    db.add(case)
    db.commit()
    db.refresh(case)
    ensure_standard_work_units(db, case)
    db.commit()
    log_event(db, case.id, "case_created", "案件已创建", {"title": case.title})
    return case


@app.post("/ai-cases", response_model=schemas.CaseOut)
def create_ai_case(
    title: str = Form(...),
    claimant: str = Form("待识别"),
    employer: str = Form("待识别"),
    case_type: str = Form("劳动争议"),
    fact_text: str = Form(""),
    files: list[UploadFile] = File(default=[]),
    db: Session = Depends(get_db),
):
    if not fact_text.strip() and not files:
        raise HTTPException(status_code=400, detail="请粘贴案件事实或至少上传一份材料")
    case = models.Case(
        title=title.strip(),
        claimant=claimant.strip() or "待识别",
        employer=employer.strip() or "待识别",
        summary=fact_text.strip(),
        raw_facts=fact_text.strip(),
        case_type=case_type.strip() or "其他",
        status="fact_review",
        stage="事实确认",
        next_action="确认 AI 提取的案件事实后进入争点识别。",
        workflow_mode="ai_case",
    )
    db.add(case)
    db.commit()
    db.refresh(case)
    if fact_text.strip():
        db.add(models.Document(
            case_id=case.id,
            filename="现场输入案件事实.txt",
            file_type="txt",
            raw_text=fact_text.strip(),
            parsed_json=to_json({"file_name": "现场输入案件事实.txt", "source": "现场粘贴"}),
        ))
    case_dir = UPLOAD_DIR / str(case.id)
    case_dir.mkdir(exist_ok=True)
    for file in files:
        safe_name = Path(file.filename or "案件材料").name
        target = case_dir / safe_name
        with target.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        parsed = parse_document(target)
        db.add(models.Document(
            case_id=case.id,
            filename=safe_name,
            file_type=target.suffix.replace(".", "") or "unknown",
            raw_text=parsed["raw_text"],
            parsed_json=to_json(parsed["parsed_json"]),
        ))
    db.commit()
    unit = ensure_ai_case_workflow(db, case)[0]
    run_ai_fact_extraction(db, case, unit)
    db.commit()
    db.refresh(case)
    log_event(db, case.id, "ai_case_created", "已保存原始材料并生成 AI 事实提取任务", {"work_unit_id": unit.id})
    return case


@app.get("/cases", response_model=list[schemas.CaseOut])
def list_cases(db: Session = Depends(get_db)):
    return db.query(models.Case).order_by(models.Case.created_at.desc()).all()


@app.get("/cases/{case_id}")
def get_case(case_id: int, db: Session = Depends(get_db)):
    case = require_case(db, case_id)
    outputs = db.query(models.AIOutput).filter(models.AIOutput.case_id == case_id).order_by(models.AIOutput.created_at.desc()).all()
    return {
        **schemas.CaseOut.model_validate(case).model_dump(mode="json"),
        "documents": [serialize_document(item) for item in case.documents],
        "evidences": case.evidences,
        "ai_outputs": [serialize_output(item) for item in outputs],
    }


@app.get("/cases/{case_id}/workspace")
def get_workspace(case_id: int, db: Session = Depends(get_db)):
    case = require_case(db, case_id)
    ensure_case_workflow(db, case)
    db.commit()
    outputs = db.query(models.AIOutput).filter(
        models.AIOutput.case_id == case_id
    ).order_by(models.AIOutput.created_at.desc()).all()
    work_units = db.query(models.WorkUnit).filter(
        models.WorkUnit.case_id == case_id
    ).order_by(models.WorkUnit.sequence).all()
    facts = current_facts(db, case)
    issues = current_issues(db, case)
    traces = db.query(models.DecisionTrace).filter(
        models.DecisionTrace.case_id == case_id
    ).order_by(models.DecisionTrace.created_at.desc()).all()
    candidates = []
    if work_units:
        candidates = db.query(models.LegalMemory).filter(
            models.LegalMemory.source_work_unit_id.in_([item.id for item in work_units])
        ).order_by(models.LegalMemory.created_at.desc()).all()
    return {
        "case": schemas.CaseOut.model_validate(case).model_dump(mode="json"),
        "documents": [serialize_document(item) for item in case.documents],
        "evidences": [schemas.EvidenceOut.model_validate(item).model_dump(mode="json") for item in case.evidences],
        "work_units": [serialize_work_unit(item) for item in work_units],
        "facts": [serialize_fact(item) for item in facts],
        "issues": [serialize_issue(item) for item in issues],
        "ai_outputs": [serialize_output(item) for item in outputs],
        "traces": [serialize_trace(item) for item in traces],
        "memory_candidates": [serialize_memory(item) for item in candidates],
    }


def require_work_unit(db: Session, case_id: int, work_unit_id: int) -> models.WorkUnit:
    unit = db.query(models.WorkUnit).filter(
        models.WorkUnit.id == work_unit_id,
        models.WorkUnit.case_id == case_id,
    ).first()
    if not unit:
        raise HTTPException(status_code=404, detail="未找到工作单元")
    return unit


def create_structured_output(
    db: Session,
    case: models.Case,
    unit: models.WorkUnit,
    title: str,
    supplementary_material: str = "",
) -> models.AIOutput:
    issues = db.query(models.CaseIssue).filter(models.CaseIssue.case_id == case.id).all()
    payload = structured_analysis(case, issues)
    if supplementary_material:
        payload["next_evidence"].append(f"已收到补充材料：{supplementary_material}")
        payload["confidence"] = "0.78"
    output = models.AIOutput(
        case_id=case.id,
        work_unit_id=unit.id,
        output_type="analysis",
        title=title,
        content=analysis_content(payload),
        meta_json=to_json({"structured": payload}),
        review_status="待复核",
    )
    db.add(output)
    db.flush()
    return output


def execute_work_unit(db: Session, case: models.Case, unit: models.WorkUnit) -> models.WorkUnit:
    if case.workflow_mode == "ai_case":
        return execute_ai_case_work_unit(db, case, unit)
    documents = db.query(models.Document).filter(models.Document.case_id == case.id).all()
    source_document = documents[0].filename if documents else "案件摘要"
    unit.status = "分析中"
    payload: dict = {}

    if unit.code == "material_understanding":
        payload = {
            "summary": case.summary[:800] or "暂未上传材料，已基于案件登记信息创建理解任务。",
            "document_count": len(documents),
            "material_focus": ["劳动关系", "工资支付", "解除行为", "仲裁请求"],
        }
    elif unit.code == "fact_structuring":
        facts = db.query(models.CaseFact).filter(models.CaseFact.case_id == case.id).all()
        if not facts:
            for item in mock_facts(case, source_document):
                db.add(models.CaseFact(case_id=case.id, work_unit_id=unit.id, **item))
            db.flush()
            facts = db.query(models.CaseFact).filter(models.CaseFact.case_id == case.id).all()
        payload = {"facts": [serialize_fact(item) for item in facts]}
    elif unit.code == "issue_identification":
        issues = db.query(models.CaseIssue).filter(models.CaseIssue.case_id == case.id).all()
        if not issues:
            for item in mock_issues():
                db.add(models.CaseIssue(case_id=case.id, work_unit_id=unit.id, **item))
            db.flush()
            issues = db.query(models.CaseIssue).filter(models.CaseIssue.case_id == case.id).all()
        payload = {"issues": [serialize_issue(item) for item in issues]}
    elif unit.code in {"legal_research", "similar_case_analysis", "integrated_argument"}:
        title = {"legal_research": "AI 法律检索", "similar_case_analysis": "AI 类案分析", "integrated_argument": "AI 综合论证"}[unit.code]
        output = create_structured_output(db, case, unit, title)
        unit.ai_output_id = output.id
        payload = from_json(output.meta_json, {})
    elif unit.code == "document_generation":
        analysis = db.query(models.AIOutput).filter(
            models.AIOutput.case_id == case.id,
            models.AIOutput.output_type == "analysis",
        ).order_by(models.AIOutput.created_at.desc()).first()
        draft = generate_draft(case, analysis.content if analysis else None, case.evidences)
        output = models.AIOutput(
            case_id=case.id,
            work_unit_id=unit.id,
            output_type="draft",
            title=draft["title"],
            content=draft["content"],
            meta_json=to_json({"structured": {"核心结论": "劳动仲裁申请书初稿", "AI 置信度": "0.72"}}),
            review_status="待复核",
        )
        db.add(output)
        db.flush()
        unit.ai_output_id = output.id
        payload = {"draft_ready": True, "output_id": output.id}
    elif unit.code == "human_review":
        payload = {"instruction": "请在事实、争点和分析视图中完成接受、修改或驳回。"}
    elif unit.code == "knowledge_deposition":
        payload = {"instruction": "批准工作单元后，可生成候选 Legal Memory。"}

    unit.output_json = to_json(payload)
    unit.status = "待人工复核" if unit.code not in {"human_review", "knowledge_deposition"} else "待处理"
    db.flush()
    log_event(db, case.id, "work_unit_completed", f"工作单元已生成：{unit.title}", {"work_unit_id": unit.id})
    return unit


@app.get("/cases/{case_id}/work-units", response_model=list[schemas.WorkUnitOut])
def list_work_units(case_id: int, db: Session = Depends(get_db)):
    case = require_case(db, case_id)
    ensure_case_workflow(db, case)
    db.commit()
    items = db.query(models.WorkUnit).filter(models.WorkUnit.case_id == case_id).order_by(models.WorkUnit.sequence).all()
    return [serialize_work_unit(item) for item in items]


@app.get("/work-units/{work_unit_id}", response_model=schemas.WorkUnitOut)
def get_work_unit(work_unit_id: int, db: Session = Depends(get_db)):
    unit = db.query(models.WorkUnit).filter(models.WorkUnit.id == work_unit_id).first()
    if not unit:
        raise HTTPException(status_code=404, detail="未找到工作单元")
    return serialize_work_unit(unit)


@app.post("/cases/{case_id}/work-units/{work_unit_id}/run", response_model=schemas.WorkUnitOut)
def run_work_unit(case_id: int, work_unit_id: int, db: Session = Depends(get_db)):
    case = require_case(db, case_id)
    unit = require_work_unit(db, case_id, work_unit_id)
    execute_work_unit(db, case, unit)
    db.commit()
    db.refresh(unit)
    return serialize_work_unit(unit)


@app.post("/cases/{case_id}/workflow/run-standard")
def run_standard_workflow(case_id: int, db: Session = Depends(get_db)):
    case = require_case(db, case_id)
    if case.workflow_mode == "ai_case":
        raise HTTPException(status_code=400, detail="AI 案件请按事实确认、争点确认和逐项分析顺序运行")
    units = ensure_standard_work_units(db, case)
    for unit in units:
        if unit.code not in {"human_review", "knowledge_deposition"}:
            execute_work_unit(db, case, unit)
    case.status = "review_ready"
    db.commit()
    return {"message": "P0 标准工作流已生成，等待人工复核", "work_units": [serialize_work_unit(item) for item in units]}


@app.post("/cases/{case_id}/work-units/{work_unit_id}/review", response_model=schemas.WorkUnitOut)
def review_work_unit(case_id: int, work_unit_id: int, payload: schemas.WorkUnitReview, db: Session = Depends(get_db)):
    unit = require_work_unit(db, case_id, work_unit_id)
    unit.status = "已批准" if payload.action == "批准" else "需修改"
    unit.reviewer = payload.reviewer
    unit.reviewed_at = datetime.utcnow()
    record_human_trace(
        db,
        case_id=case_id,
        work_unit_id=unit.id,
        action=payload.action,
        object_type="WorkUnit",
        object_id=unit.id,
        ai_suggestion=from_json(unit.output_json, {}).get("summary", unit.title),
        human_revision=unit.status,
        reason=payload.reason,
        tags=["工作单元", payload.action],
    )
    log_event(db, case_id, "work_unit_reviewed", f"人工复核：{unit.title} {unit.status}")
    db.commit()
    db.refresh(unit)
    return serialize_work_unit(unit)


@app.get("/cases/{case_id}/facts", response_model=list[schemas.FactOut])
def list_facts(case_id: int, db: Session = Depends(get_db)):
    case = require_case(db, case_id)
    items = current_facts(db, case)
    return [serialize_fact(item) for item in items]


@app.post("/facts/{fact_id}/review", response_model=schemas.FactOut)
def review_fact(fact_id: int, payload: schemas.FactReview, db: Session = Depends(get_db)):
    fact = db.query(models.CaseFact).filter(models.CaseFact.id == fact_id).first()
    if not fact:
        raise HTTPException(status_code=404, detail="未找到事实")
    case = require_case(db, fact.case_id)
    status_map = {"接受": "已确认", "修改": "已确认", "驳回": "已驳回"}
    if payload.action not in status_map:
        raise HTTPException(status_code=400, detail="不支持的事实操作")
    fact.status = status_map[payload.action]
    if payload.action == "修改":
        fact.human_fact = payload.human_fact.strip()
        if not fact.human_fact:
            raise HTTPException(status_code=400, detail="修改事实时需要填写人工版本")
    elif payload.action == "接受":
        fact.human_fact = fact.ai_fact
    if case.workflow_mode == "ai_case":
        advance_fact_version(db, case)
        fact.fact_version = case.fact_version
    record_human_trace(
        db,
        case_id=fact.case_id,
        work_unit_id=fact.work_unit_id,
        action=payload.action,
        object_type="事实",
        object_id=fact.id,
        ai_suggestion=fact.ai_fact,
        human_revision=fact.human_fact or "已驳回该事实",
        reason=payload.reason,
        tags=["事实结构化", payload.action],
    )
    log_event(db, fact.case_id, "fact_reviewed", f"事实已{payload.action}", {"fact_id": fact.id})
    maybe_generate_issues_after_fact_review(db, case)
    db.commit()
    db.refresh(fact)
    return serialize_fact(fact)


@app.get("/cases/{case_id}/issues", response_model=list[schemas.IssueOut])
def list_issues(case_id: int, db: Session = Depends(get_db)):
    case = require_case(db, case_id)
    items = current_issues(db, case)
    return [serialize_issue(item) for item in items]


@app.post("/cases/{case_id}/issues", response_model=schemas.IssueOut)
def add_issue(case_id: int, payload: schemas.IssueCreate, db: Session = Depends(get_db)):
    case = require_case(db, case_id)
    if case.workflow_mode == "ai_case" and not facts_are_confirmed(db, case):
        raise HTTPException(status_code=400, detail="请先确认事实，再新增争点")
    unit = db.query(models.WorkUnit).filter(
        models.WorkUnit.case_id == case_id,
        models.WorkUnit.code == "issue_identification",
    ).first()
    issue = models.CaseIssue(
        case_id=case_id,
        work_unit_id=unit.id if unit else None,
        title=payload.title,
        description=payload.description,
        analysis_hint=payload.analysis_hint,
        source="人工新增",
        status="人工确认",
        importance=payload.importance,
        related_facts=to_json(payload.related_facts),
        related_fact_ids=to_json(validate_related_fact_ids(case, payload.related_fact_ids, db)),
        issue_version=case.issue_version,
    )
    if case.workflow_mode == "ai_case":
        advance_issue_version(db, case)
        issue.issue_version = case.issue_version
    db.add(issue)
    db.flush()
    record_human_trace(
        db,
        case_id=case_id,
        work_unit_id=issue.work_unit_id,
        action="新增",
        object_type="争点",
        object_id=issue.id,
        ai_suggestion="无 AI 原始建议",
        human_revision=issue.title,
        reason=payload.reason,
        tags=["争点识别", "人工新增"],
    )
    log_event(db, case_id, "issue_added", f"已新增争点：{issue.title}")
    if case.workflow_mode == "ai_case":
        sync_analysis_units(db, case)
    db.commit()
    db.refresh(issue)
    return serialize_issue(issue)


@app.patch("/issues/{issue_id}", response_model=schemas.IssueOut)
def update_issue(issue_id: int, payload: schemas.IssueUpdate, db: Session = Depends(get_db)):
    issue = db.query(models.CaseIssue).filter(models.CaseIssue.id == issue_id).first()
    if not issue:
        raise HTTPException(status_code=404, detail="未找到争点")
    case = require_case(db, issue.case_id)
    original = f"{issue.title}\n{issue.description}"
    issue.title = payload.title
    issue.description = payload.description
    issue.analysis_hint = payload.analysis_hint
    issue.status = payload.status
    issue.importance = payload.importance
    issue.related_facts = to_json(payload.related_facts)
    if payload.related_fact_ids:
        issue.related_fact_ids = to_json(validate_related_fact_ids(case, payload.related_fact_ids, db))
    if case.workflow_mode == "ai_case":
        advance_issue_version(db, case)
        issue.issue_version = case.issue_version
    record_human_trace(
        db,
        case_id=issue.case_id,
        work_unit_id=issue.work_unit_id,
        action="修改",
        object_type="争点",
        object_id=issue.id,
        ai_suggestion=original,
        human_revision=f"{issue.title}\n{issue.description}",
        reason=payload.reason,
        tags=["争点识别", "修改"],
    )
    log_event(db, issue.case_id, "issue_updated", f"争点已修改：{issue.title}")
    if case.workflow_mode == "ai_case":
        sync_analysis_units(db, case)
    db.commit()
    db.refresh(issue)
    return serialize_issue(issue)


@app.post("/issues/{issue_id}/action", response_model=schemas.IssueOut)
def issue_action(issue_id: int, payload: schemas.IssueAction, db: Session = Depends(get_db)):
    issue = db.query(models.CaseIssue).filter(models.CaseIssue.id == issue_id).first()
    if not issue:
        raise HTTPException(status_code=404, detail="未找到争点")
    case = require_case(db, issue.case_id)
    if payload.action == "确认":
        issue.status = "人工确认"
    elif payload.action == "开始分析":
        issue.status = "分析中"
    elif payload.action == "完成":
        issue.status = "已完成"
    else:
        raise HTTPException(status_code=400, detail="不支持的争点操作")
    if case.workflow_mode == "ai_case":
        advance_issue_version(db, case)
        issue.issue_version = case.issue_version
    record_human_trace(
        db,
        case_id=issue.case_id,
        work_unit_id=issue.work_unit_id,
        action=payload.action,
        object_type="争点",
        object_id=issue.id,
        ai_suggestion=issue.title,
        human_revision=issue.status,
        reason=payload.reason,
        tags=["争点识别", payload.action],
    )
    log_event(db, issue.case_id, "issue_action", f"争点状态更新为：{issue.status}")
    if case.workflow_mode == "ai_case" and payload.action == "确认":
        sync_analysis_units(db, case)
    db.commit()
    db.refresh(issue)
    return serialize_issue(issue)


@app.delete("/issues/{issue_id}")
def delete_issue(issue_id: int, payload: schemas.IssueAction, db: Session = Depends(get_db)):
    issue = db.query(models.CaseIssue).filter(models.CaseIssue.id == issue_id).first()
    if not issue:
        raise HTTPException(status_code=404, detail="未找到争点")
    record_human_trace(
        db,
        case_id=issue.case_id,
        work_unit_id=issue.work_unit_id,
        action="删除",
        object_type="争点",
        object_id=issue.id,
        ai_suggestion=issue.title,
        human_revision="已删除",
        reason=payload.reason,
        tags=["争点识别", "删除"],
    )
    case_id = issue.case_id
    title = issue.title
    case = require_case(db, case_id)
    db.delete(issue)
    db.flush()
    if case.workflow_mode == "ai_case":
        advance_issue_version(db, case)
    log_event(db, case_id, "issue_deleted", f"已删除争点：{title}")
    db.commit()
    return {"message": "争点已删除"}


@app.post("/cases/{case_id}/legal-analysis-report", response_model=schemas.AIOutputOut)
def create_legal_analysis_report(case_id: int, db: Session = Depends(get_db)):
    case = require_case(db, case_id)
    if case.workflow_mode != "ai_case":
        raise HTTPException(status_code=400, detail="该报告入口仅用于新建 AI 案件")
    output = generate_legal_report(db, case)
    db.commit()
    db.refresh(output)
    return serialize_output(output)


@app.post("/ai-outputs/{output_id}/review", response_model=schemas.AIOutputOut)
def review_ai_output(output_id: int, payload: schemas.AIReview, db: Session = Depends(get_db)):
    output = db.query(models.AIOutput).filter(models.AIOutput.id == output_id).first()
    if not output:
        raise HTTPException(status_code=404, detail="未找到 AI 输出")
    case = require_case(db, output.case_id)
    if payload.action == "接受":
        output.review_status = "已接受"
        human_revision = output.content
    elif payload.action == "修改":
        if not payload.human_revision.strip():
            raise HTTPException(status_code=400, detail="修改 AI 内容时需要填写人工版本")
        output.review_status = "已修改"
        human_revision = payload.human_revision
    elif payload.action == "驳回":
        output.review_status = "已驳回"
        human_revision = "已驳回该 AI 输出"
    elif payload.action == "补充材料后重新分析":
        unit = db.query(models.WorkUnit).filter(models.WorkUnit.id == output.work_unit_id).first()
        if not unit:
            raise HTTPException(status_code=400, detail="该输出未关联工作单元，无法重新分析")
        output.review_status = "待补充材料"
        record_human_trace(
            db,
            case_id=case.id,
            work_unit_id=unit.id,
            action=payload.action,
            object_type="AI输出",
            object_id=output.id,
            ai_suggestion=output.content,
            human_revision=payload.supplementary_material or "待补充材料",
            reason=payload.reason,
            tags=["AI复核", "补充材料"],
        )
        if case.workflow_mode == "ai_case" and unit.code.startswith("legal_analysis:"):
            run_ai_legal_analysis(db, case, unit, payload.supplementary_material)
            new_output = db.query(models.AIOutput).filter(models.AIOutput.id == unit.ai_output_id).first()
        elif output.output_type == "draft":
            execute_work_unit(db, case, unit)
            new_output = db.query(models.AIOutput).filter(models.AIOutput.id == unit.ai_output_id).first()
        else:
            new_output = create_structured_output(db, case, unit, "AI 补充材料后重新分析", payload.supplementary_material)
            unit.ai_output_id = new_output.id
        unit.status = "待人工复核"
        log_event(db, case.id, "analysis_regenerated", "已根据补充材料重新生成结构化分析")
        db.commit()
        if not new_output:
            raise HTTPException(status_code=500, detail="重新生成 AI 输出失败")
        db.refresh(new_output)
        return serialize_output(new_output)
    else:
        raise HTTPException(status_code=400, detail="不支持的 AI 复核操作")

    record_human_trace(
        db,
        case_id=case.id,
        work_unit_id=output.work_unit_id,
        action=payload.action,
        object_type="AI输出",
        object_id=output.id,
        ai_suggestion=output.content,
        human_revision=human_revision,
        reason=payload.reason,
        tags=["AI复核", payload.action],
    )
    unit = db.query(models.WorkUnit).filter(models.WorkUnit.id == output.work_unit_id).first()
    if unit and case.workflow_mode == "ai_case" and unit.code.startswith("legal_analysis:"):
        unit.status = "已批准" if payload.action in {"接受", "修改"} else "需修改"
    log_event(db, case.id, "ai_output_reviewed", f"AI 输出已{payload.action}", {"output_id": output.id})
    db.commit()
    db.refresh(output)
    return serialize_output(output)


@app.post("/work-units/{work_unit_id}/memory-candidate", response_model=schemas.MemoryOut)
def create_memory_candidate(work_unit_id: int, db: Session = Depends(get_db)):
    unit = db.query(models.WorkUnit).filter(models.WorkUnit.id == work_unit_id).first()
    if not unit:
        raise HTTPException(status_code=404, detail="未找到工作单元")
    if unit.status != "已批准":
        raise HTTPException(status_code=400, detail="仅已批准的工作单元可以生成候选知识")
    existing = db.query(models.LegalMemory).filter(models.LegalMemory.source_work_unit_id == unit.id).first()
    if existing:
        return serialize_memory(existing)
    case = require_case(db, unit.case_id)
    output = from_json(unit.output_json, {})
    memory = models.LegalMemory(
        title=f"{unit.title}：{case.title}",
        scenario=case.summary[:500] or f"{case.claimant} 与 {case.employer} 的劳动争议",
        legal_issue=unit.title,
        rule_summary=str(output.get("summary") or output.get("instruction") or "人工批准的工作单元结论"),
        decision_pattern=json.dumps(output, ensure_ascii=False)[:1200],
        tags=join_tags(["候选知识", unit.title, "劳动仲裁"]),
        source_work_unit_id=unit.id,
        category="案件经验",
        status="候选",
    )
    db.add(memory)
    db.flush()
    record_human_trace(
        db,
        case_id=case.id,
        work_unit_id=unit.id,
        action="生成候选知识",
        object_type="LegalMemory",
        object_id=memory.id,
        ai_suggestion=unit.title,
        human_revision=memory.title,
        reason="已批准工作单元，可进入知识沉淀审核",
        tags=["Legal Memory", "候选"],
    )
    log_event(db, case.id, "memory_candidate_created", f"已生成候选 Legal Memory：{memory.title}")
    db.commit()
    db.refresh(memory)
    return serialize_memory(memory)


@app.post("/memory/{memory_id}/decision", response_model=schemas.MemoryOut)
def decide_memory(memory_id: int, payload: schemas.MemoryDecision, db: Session = Depends(get_db)):
    memory = db.query(models.LegalMemory).filter(models.LegalMemory.id == memory_id).first()
    if not memory:
        raise HTTPException(status_code=404, detail="未找到 Legal Memory")
    unit = db.query(models.WorkUnit).filter(models.WorkUnit.id == memory.source_work_unit_id).first()
    if payload.action == "批准沉淀":
        memory.status = "已沉淀"
    elif payload.action == "修改后沉淀":
        memory.status = "已沉淀"
        memory.title = payload.title or memory.title
        memory.rule_summary = payload.rule_summary or memory.rule_summary
        memory.decision_pattern = payload.decision_pattern or memory.decision_pattern
    elif payload.action == "忽略":
        memory.status = "已忽略"
    else:
        raise HTTPException(status_code=400, detail="不支持的知识沉淀操作")
    memory.category = payload.category or memory.category
    memory.review_reason = payload.reason
    if unit:
        record_human_trace(
            db,
            case_id=unit.case_id,
            work_unit_id=unit.id,
            action=payload.action,
            object_type="LegalMemory",
            object_id=memory.id,
            ai_suggestion=memory.title,
            human_revision=memory.status,
            reason=payload.reason,
            tags=["Legal Memory", payload.action],
        )
        log_event(db, unit.case_id, "memory_reviewed", f"Legal Memory 已{payload.action}")
    db.commit()
    db.refresh(memory)
    return serialize_memory(memory)


@app.patch("/cases/{case_id}/management", response_model=schemas.CaseOut)
def update_case_management(case_id: int, payload: schemas.CaseManagementUpdate, db: Session = Depends(get_db)):
    case = require_case(db, case_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(case, field, value)
    db.commit()
    db.refresh(case)
    log_event(db, case_id, "case_management_updated", "案件管理信息已更新")
    return case


@app.get("/cases/{case_id}/work-records", response_model=list[schemas.WorkRecordOut])
def list_work_records(case_id: int, db: Session = Depends(get_db)):
    require_case(db, case_id)
    return db.query(models.CaseWorkRecord).filter(
        models.CaseWorkRecord.case_id == case_id
    ).order_by(models.CaseWorkRecord.created_at.desc()).all()


@app.post("/cases/{case_id}/work-records", response_model=schemas.WorkRecordOut)
def add_work_record(case_id: int, payload: schemas.WorkRecordCreate, db: Session = Depends(get_db)):
    require_case(db, case_id)
    record = models.CaseWorkRecord(case_id=case_id, **payload.model_dump())
    db.add(record)
    db.commit()
    db.refresh(record)
    log_event(db, case_id, "work_record_added", "已新增工作记录")
    return record


@app.get("/cases/{case_id}/todos", response_model=list[schemas.TodoOut])
def list_todos(case_id: int, db: Session = Depends(get_db)):
    require_case(db, case_id)
    return db.query(models.CaseTodo).filter(
        models.CaseTodo.case_id == case_id
    ).order_by(models.CaseTodo.completed.asc(), models.CaseTodo.due_date.asc()).all()


@app.post("/cases/{case_id}/todos", response_model=schemas.TodoOut)
def add_todo(case_id: int, payload: schemas.TodoCreate, db: Session = Depends(get_db)):
    require_case(db, case_id)
    todo = models.CaseTodo(case_id=case_id, **payload.model_dump())
    db.add(todo)
    db.commit()
    db.refresh(todo)
    log_event(db, case_id, "todo_added", f"已新增待办：{todo.title}")
    return todo


@app.patch("/todos/{todo_id}", response_model=schemas.TodoOut)
def update_todo(todo_id: int, payload: schemas.TodoUpdate, db: Session = Depends(get_db)):
    todo = db.query(models.CaseTodo).filter(models.CaseTodo.id == todo_id).first()
    if not todo:
        raise HTTPException(status_code=404, detail="未找到待办事项")
    todo.completed = payload.completed
    db.commit()
    db.refresh(todo)
    message = f"已完成待办：{todo.title}" if todo.completed else f"已恢复待办：{todo.title}"
    log_event(db, todo.case_id, "todo_updated", message)
    return todo


@app.get("/cases/{case_id}/follow-ups", response_model=list[schemas.FollowUpOut])
def list_follow_ups(case_id: int, db: Session = Depends(get_db)):
    require_case(db, case_id)
    return db.query(models.CaseFollowUp).filter(
        models.CaseFollowUp.case_id == case_id
    ).order_by(models.CaseFollowUp.created_at.desc()).all()


@app.post("/cases/{case_id}/follow-ups", response_model=schemas.FollowUpOut)
def add_follow_up(case_id: int, payload: schemas.FollowUpCreate, db: Session = Depends(get_db)):
    case = require_case(db, case_id)
    follow_up = models.CaseFollowUp(case_id=case_id, **payload.model_dump())
    if payload.stage:
        case.stage = payload.stage
    if payload.next_action:
        case.next_action = payload.next_action
    if payload.follow_up_at:
        case.next_follow_up_at = payload.follow_up_at
    db.add(follow_up)
    db.commit()
    db.refresh(follow_up)
    log_event(db, case_id, "follow_up_added", "已记录案件跟进")
    return follow_up


@app.post("/cases/{case_id}/documents/upload", response_model=schemas.DocumentOut)
def upload_document(case_id: int, file: UploadFile = File(...), db: Session = Depends(get_db)):
    require_case(db, case_id)
    case_dir = UPLOAD_DIR / str(case_id)
    case_dir.mkdir(exist_ok=True)
    target = case_dir / file.filename
    with target.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    parsed = parse_document(target)
    document = models.Document(
        case_id=case_id,
        filename=file.filename,
        file_type=target.suffix.replace(".", "") or "unknown",
        raw_text=parsed["raw_text"],
        parsed_json=to_json(parsed["parsed_json"]),
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    log_event(db, case_id, "document_uploaded", f"已上传并解析材料：{file.filename}", parsed["parsed_json"])
    record_human_trace(
        db,
        case_id=case_id,
        action="补充材料",
        object_type="材料",
        object_id=document.id,
        ai_suggestion="无 AI 原始建议",
        human_revision=file.filename,
        reason="人工上传案件材料",
        tags=["材料", "上传"],
    )
    db.commit()
    return serialize_document(document)


@app.get("/cases/{case_id}/documents", response_model=list[schemas.DocumentOut])
def list_documents(case_id: int, db: Session = Depends(get_db)):
    require_case(db, case_id)
    documents = db.query(models.Document).filter(models.Document.case_id == case_id).all()
    return [serialize_document(item) for item in documents]


@app.post("/cases/{case_id}/workflow/run-evidence", response_model=list[schemas.EvidenceOut])
def run_evidence(case_id: int, db: Session = Depends(get_db)):
    case = require_case(db, case_id)
    documents = db.query(models.Document).filter(models.Document.case_id == case_id).all()
    db.query(models.Evidence).filter(models.Evidence.case_id == case_id).delete()
    for item in generate_evidences(case, documents):
        db.add(models.Evidence(case_id=case_id, **item))
    case.status = "evidence_ready"
    db.commit()
    evidences = db.query(models.Evidence).filter(models.Evidence.case_id == case_id).all()
    log_event(db, case_id, "evidence_generated", "证据表已生成", {"count": len(evidences)})
    return evidences


@app.post("/cases/{case_id}/workflow/run-analysis", response_model=schemas.AIOutputOut)
def run_analysis(case_id: int, db: Session = Depends(get_db)):
    case = require_case(db, case_id)
    evidences = db.query(models.Evidence).filter(models.Evidence.case_id == case_id).all()
    result = generate_analysis(case, evidences)
    output = models.AIOutput(
        case_id=case_id,
        output_type="analysis",
        title=result["title"],
        content=result["content"],
        meta_json=to_json({"rules": result["rules"]}),
    )
    case.status = "analysis_ready"
    db.add(output)
    db.commit()
    db.refresh(output)
    log_event(db, case_id, "analysis_generated", "AI 法律分析已生成")
    return serialize_output(output)


@app.post("/cases/{case_id}/workflow/run-draft", response_model=schemas.AIOutputOut)
def run_draft(case_id: int, db: Session = Depends(get_db)):
    case = require_case(db, case_id)
    evidences = db.query(models.Evidence).filter(models.Evidence.case_id == case_id).all()
    analysis = db.query(models.AIOutput).filter(
        models.AIOutput.case_id == case_id,
        models.AIOutput.output_type == "analysis",
    ).order_by(models.AIOutput.created_at.desc()).first()
    result = generate_draft(case, analysis.content if analysis else None, evidences)
    output = models.AIOutput(
        case_id=case_id,
        output_type="draft",
        title=result["title"],
        content=result["content"],
    )
    case.status = "draft_ready"
    db.add(output)
    db.commit()
    db.refresh(output)
    log_event(db, case_id, "draft_generated", "劳动仲裁申请书初稿已生成")
    return serialize_output(output)


@app.post("/cases/{case_id}/workflow/run-risk", response_model=schemas.AIOutputOut)
def run_risk(case_id: int, db: Session = Depends(get_db)):
    case = require_case(db, case_id)
    evidences = db.query(models.Evidence).filter(models.Evidence.case_id == case_id).all()
    result = generate_risk(case, evidences)
    output = models.AIOutput(
        case_id=case_id,
        output_type="risk",
        title=result["title"],
        content=result["content"],
    )
    db.add(output)
    db.commit()
    db.refresh(output)
    log_event(db, case_id, "risk_generated", "风险提示已生成")
    return serialize_output(output)


@app.post("/cases/{case_id}/workflow/run-demo")
def run_demo(case_id: int, db: Session = Depends(get_db)):
    run_evidence(case_id, db)
    analysis = run_analysis(case_id, db)
    draft = run_draft(case_id, db)
    risk = run_risk(case_id, db)
    return {"message": "演示工作流已完成", "analysis": analysis, "draft": draft, "risk": risk}


@app.post("/cases/{case_id}/traces", response_model=schemas.TraceOut)
def add_trace(case_id: int, payload: schemas.TraceCreate, db: Session = Depends(get_db)):
    require_case(db, case_id)
    trace = create_trace(
        db,
        case_id=case_id,
        ai_output_id=payload.ai_output_id,
        ai_suggestion=payload.ai_suggestion,
        human_revision=payload.human_revision,
        revision_reason=payload.revision_reason,
        tags=payload.tags,
    )
    log_event(db, case_id, "decision_trace_created", "已记录人工修改与决策原因", {"trace_id": trace.id})
    return serialize_trace(trace)


@app.get("/cases/{case_id}/traces", response_model=list[schemas.TraceOut])
def list_traces(case_id: int, db: Session = Depends(get_db)):
    require_case(db, case_id)
    traces = db.query(models.DecisionTrace).filter(models.DecisionTrace.case_id == case_id).order_by(models.DecisionTrace.created_at.desc()).all()
    return [serialize_trace(item) for item in traces]


@app.post("/memory/from-trace/{trace_id}", response_model=schemas.MemoryOut)
def create_memory_from_trace(trace_id: int, db: Session = Depends(get_db)):
    trace = db.query(models.DecisionTrace).filter(models.DecisionTrace.id == trace_id).first()
    if not trace:
        raise HTTPException(status_code=404, detail="未找到决策留痕记录")
    case = require_case(db, trace.case_id)
    payload = memory_from_trace(trace, case)
    memory = models.LegalMemory(source_trace_id=trace.id, **payload)
    db.add(memory)
    db.commit()
    db.refresh(memory)
    log_event(db, case.id, "memory_created", "已从决策留痕沉淀法律知识", {"memory_id": memory.id})
    return serialize_memory(memory)


@app.get("/memory", response_model=list[schemas.MemoryOut])
def list_memory(db: Session = Depends(get_db)):
    memories = db.query(models.LegalMemory).filter(
        models.LegalMemory.status == "已沉淀"
    ).order_by(models.LegalMemory.created_at.desc()).all()
    return [serialize_memory(item) for item in memories]


@app.get("/cases/{case_id}/memory-recommendations")
def memory_recommendations(case_id: int, db: Session = Depends(get_db)):
    case = require_case(db, case_id)
    memories = db.query(models.LegalMemory).filter(models.LegalMemory.status == "已沉淀").all()
    return recommend_memories(case, memories)


@app.get("/cases/{case_id}/workflow/events", response_model=list[schemas.WorkflowEventOut])
def workflow_events(case_id: int, db: Session = Depends(get_db)):
    require_case(db, case_id)
    events = db.query(models.WorkflowEvent).filter(models.WorkflowEvent.case_id == case_id).order_by(models.WorkflowEvent.created_at.asc()).all()
    return [
        {
            "id": item.id,
            "event_type": item.event_type,
            "message": item.message,
            "payload_json": from_json(item.payload_json, {}),
            "created_at": item.created_at,
        }
        for item in events
    ]
