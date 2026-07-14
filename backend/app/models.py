from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from .database import Base


class Case(Base):
    __tablename__ = "cases"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    claimant = Column(String(120), nullable=False)
    employer = Column(String(120), nullable=False)
    status = Column(String(50), default="created")
    summary = Column(Text, default="")
    # Keeps the user's original intake text separate from the AI-maintained summary.
    raw_facts = Column(Text, default="")
    claim_amount = Column(String(80), default="")
    case_no = Column(String(80), default="")
    case_type = Column(String(80), default="劳动仲裁")
    stage = Column(String(80), default="材料收集")
    handler = Column(String(120), default="")
    next_follow_up_at = Column(String(32), default="")
    next_action = Column(Text, default="")
    workflow_mode = Column(String(40), default="standard")
    fact_version = Column(Integer, default=1)
    issue_version = Column(Integer, default=1)
    created_at = Column(DateTime, default=datetime.utcnow)

    documents = relationship("Document", back_populates="case", cascade="all, delete-orphan")
    evidences = relationship("Evidence", back_populates="case", cascade="all, delete-orphan")
    outputs = relationship("AIOutput", back_populates="case", cascade="all, delete-orphan")
    traces = relationship("DecisionTrace", back_populates="case", cascade="all, delete-orphan")
    events = relationship("WorkflowEvent", back_populates="case", cascade="all, delete-orphan")
    work_records = relationship("CaseWorkRecord", back_populates="case", cascade="all, delete-orphan")
    todos = relationship("CaseTodo", back_populates="case", cascade="all, delete-orphan")
    follow_ups = relationship("CaseFollowUp", back_populates="case", cascade="all, delete-orphan")
    work_units = relationship("WorkUnit", back_populates="case", cascade="all, delete-orphan")
    facts = relationship("CaseFact", back_populates="case", cascade="all, delete-orphan")
    issues = relationship("CaseIssue", back_populates="case", cascade="all, delete-orphan")


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    case_id = Column(Integer, ForeignKey("cases.id"), nullable=False)
    filename = Column(String(255), nullable=False)
    file_type = Column(String(40), nullable=False)
    raw_text = Column(Text, default="")
    parsed_json = Column(Text, default="{}")
    uploaded_at = Column(DateTime, default=datetime.utcnow)

    case = relationship("Case", back_populates="documents")


class Evidence(Base):
    __tablename__ = "evidences"

    id = Column(Integer, primary_key=True, index=True)
    case_id = Column(Integer, ForeignKey("cases.id"), nullable=False)
    name = Column(String(255), nullable=False)
    category = Column(String(80), nullable=False)
    fact_to_prove = Column(Text, nullable=False)
    source_document = Column(String(255), default="")
    strength = Column(String(40), default="medium")
    notes = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)

    case = relationship("Case", back_populates="evidences")


class AIOutput(Base):
    __tablename__ = "ai_outputs"

    id = Column(Integer, primary_key=True, index=True)
    case_id = Column(Integer, ForeignKey("cases.id"), nullable=False)
    output_type = Column(String(50), nullable=False)
    title = Column(String(255), nullable=False)
    content = Column(Text, nullable=False)
    meta_json = Column(Text, default="{}")
    work_unit_id = Column(Integer, ForeignKey("work_units.id"), nullable=True)
    review_status = Column(String(40), default="待复核")
    version = Column(Integer, default=1)
    fact_version = Column(Integer, default=1)
    issue_version = Column(Integer, default=1)
    input_snapshot_json = Column(Text, default="{}")
    created_at = Column(DateTime, default=datetime.utcnow)

    case = relationship("Case", back_populates="outputs")


class DecisionTrace(Base):
    __tablename__ = "decision_traces"

    id = Column(Integer, primary_key=True, index=True)
    case_id = Column(Integer, ForeignKey("cases.id"), nullable=False)
    ai_output_id = Column(Integer, ForeignKey("ai_outputs.id"), nullable=True)
    ai_suggestion = Column(Text, nullable=False)
    human_revision = Column(Text, nullable=False)
    revision_reason = Column(Text, nullable=False)
    tags = Column(String(255), default="")
    work_unit_id = Column(Integer, ForeignKey("work_units.id"), nullable=True)
    action = Column(String(80), default="人工修改")
    object_type = Column(String(80), default="AI输出")
    object_id = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    case = relationship("Case", back_populates="traces")


class LegalMemory(Base):
    __tablename__ = "legal_memories"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    scenario = Column(Text, nullable=False)
    legal_issue = Column(String(255), nullable=False)
    rule_summary = Column(Text, nullable=False)
    decision_pattern = Column(Text, nullable=False)
    tags = Column(String(255), default="")
    source_trace_id = Column(Integer, ForeignKey("decision_traces.id"), nullable=True)
    source_work_unit_id = Column(Integer, ForeignKey("work_units.id"), nullable=True)
    category = Column(String(80), default="案件经验")
    status = Column(String(40), default="已沉淀")
    review_reason = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)


class WorkUnit(Base):
    __tablename__ = "work_units"

    id = Column(Integer, primary_key=True, index=True)
    case_id = Column(Integer, ForeignKey("cases.id"), nullable=False)
    code = Column(String(80), nullable=False)
    title = Column(String(120), nullable=False)
    sequence = Column(Integer, nullable=False)
    status = Column(String(40), default="待处理")
    description = Column(Text, default="")
    input_json = Column(Text, default="{}")
    output_json = Column(Text, default="{}")
    # Kept as an identifier to avoid a cyclic DDL dependency with ai_outputs.
    ai_output_id = Column(Integer, nullable=True)
    parent_issue_id = Column(Integer, nullable=True)
    version = Column(Integer, default=1)
    reviewer = Column(String(120), default="")
    reviewed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    case = relationship("Case", back_populates="work_units")


class CaseFact(Base):
    __tablename__ = "case_facts"

    id = Column(Integer, primary_key=True, index=True)
    case_id = Column(Integer, ForeignKey("cases.id"), nullable=False)
    work_unit_id = Column(Integer, ForeignKey("work_units.id"), nullable=True)
    category = Column(String(80), default="一般事实")
    ai_fact = Column(Text, nullable=False)
    human_fact = Column(Text, default="")
    source_document = Column(String(255), default="")
    status = Column(String(40), default="待确认")
    confidence = Column(String(40), default="中")
    fact_version = Column(Integer, default=1)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    case = relationship("Case", back_populates="facts")


class CaseIssue(Base):
    __tablename__ = "case_issues"

    id = Column(Integer, primary_key=True, index=True)
    case_id = Column(Integer, ForeignKey("cases.id"), nullable=False)
    work_unit_id = Column(Integer, ForeignKey("work_units.id"), nullable=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, default="")
    analysis_hint = Column(Text, default="")
    source = Column(String(40), default="AI建议")
    status = Column(String(40), default="AI建议")
    importance = Column(String(40), default="中")
    related_facts = Column(Text, default="[]")
    # JSON array of CaseFact IDs. related_facts is retained for historical records.
    related_fact_ids = Column(Text, default="[]")
    issue_version = Column(Integer, default=1)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    case = relationship("Case", back_populates="issues")


class WorkflowEvent(Base):
    __tablename__ = "workflow_events"

    id = Column(Integer, primary_key=True, index=True)
    case_id = Column(Integer, ForeignKey("cases.id"), nullable=False)
    event_type = Column(String(80), nullable=False)
    message = Column(Text, nullable=False)
    payload_json = Column(Text, default="{}")
    created_at = Column(DateTime, default=datetime.utcnow)

    case = relationship("Case", back_populates="events")


class CaseWorkRecord(Base):
    __tablename__ = "case_work_records"

    id = Column(Integer, primary_key=True, index=True)
    case_id = Column(Integer, ForeignKey("cases.id"), nullable=False)
    content = Column(Text, nullable=False)
    record_type = Column(String(80), default="工作记录")
    created_at = Column(DateTime, default=datetime.utcnow)

    case = relationship("Case", back_populates="work_records")


class CaseTodo(Base):
    __tablename__ = "case_todos"

    id = Column(Integer, primary_key=True, index=True)
    case_id = Column(Integer, ForeignKey("cases.id"), nullable=False)
    title = Column(String(255), nullable=False)
    due_date = Column(String(32), default="")
    priority = Column(String(32), default="普通")
    completed = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    case = relationship("Case", back_populates="todos")


class CaseFollowUp(Base):
    __tablename__ = "case_follow_ups"

    id = Column(Integer, primary_key=True, index=True)
    case_id = Column(Integer, ForeignKey("cases.id"), nullable=False)
    progress = Column(Text, nullable=False)
    next_action = Column(Text, default="")
    follow_up_at = Column(String(32), default="")
    stage = Column(String(80), default="")
    created_at = Column(DateTime, default=datetime.utcnow)

    case = relationship("Case", back_populates="follow_ups")
