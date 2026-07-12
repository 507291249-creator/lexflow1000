import json
import os
import shutil
from pathlib import Path

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session

from . import models, schemas
from .agents.decision_trace import create_trace
from .agents.document_parser import parse_document
from .agents.draft_agent import generate_draft
from .agents.evidence_agent import generate_evidences
from .agents.legal_memory import memory_from_trace
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
    ensure_case_management_schema()
    seed_demo_data()


def ensure_case_management_schema() -> None:
    if engine.dialect.name != "sqlite":
        return
    with engine.connect() as connection:
        columns = {
            row[1]
            for row in connection.execute(text("PRAGMA table_info(cases)"))
        }
    additions = {
        "case_no": "TEXT NOT NULL DEFAULT ''",
        "case_type": "TEXT NOT NULL DEFAULT '劳动仲裁'",
        "stage": "TEXT NOT NULL DEFAULT '材料收集'",
        "handler": "TEXT NOT NULL DEFAULT ''",
        "next_follow_up_at": "TEXT NOT NULL DEFAULT ''",
        "next_action": "TEXT NOT NULL DEFAULT ''",
    }
    with engine.begin() as connection:
        for name, definition in additions.items():
            if name not in columns:
                connection.execute(text(f"ALTER TABLE cases ADD COLUMN {name} {definition}"))


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
    return {
        "id": output.id,
        "case_id": output.case_id,
        "output_type": output.output_type,
        "title": output.title,
        "content": output.content,
        "meta_json": from_json(output.meta_json, {}),
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
        "created_at": memory.created_at,
    }


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "LexFlow MVP"}


@app.post("/cases", response_model=schemas.CaseOut)
def create_case(payload: schemas.CaseCreate, db: Session = Depends(get_db)):
    case = models.Case(**payload.model_dump())
    db.add(case)
    db.commit()
    db.refresh(case)
    log_event(db, case.id, "case_created", "案件已创建", {"title": case.title})
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
    memories = db.query(models.LegalMemory).order_by(models.LegalMemory.created_at.desc()).all()
    return [serialize_memory(item) for item in memories]


@app.get("/cases/{case_id}/memory-recommendations")
def memory_recommendations(case_id: int, db: Session = Depends(get_db)):
    case = require_case(db, case_id)
    memories = db.query(models.LegalMemory).all()
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
