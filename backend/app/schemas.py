from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel


class CaseCreate(BaseModel):
    title: str
    claimant: str
    employer: str
    summary: str = ""
    claim_amount: str = ""
    case_no: str = ""
    case_type: str = "劳动仲裁"
    stage: str = "材料收集"
    handler: str = ""
    next_follow_up_at: str = ""
    next_action: str = ""


class CaseManagementUpdate(BaseModel):
    case_no: Optional[str] = None
    case_type: Optional[str] = None
    stage: Optional[str] = None
    handler: Optional[str] = None
    next_follow_up_at: Optional[str] = None
    next_action: Optional[str] = None


class WorkRecordCreate(BaseModel):
    content: str
    record_type: str = "工作记录"


class TodoCreate(BaseModel):
    title: str
    due_date: str = ""
    priority: str = "普通"


class TodoUpdate(BaseModel):
    completed: bool


class FollowUpCreate(BaseModel):
    progress: str
    next_action: str = ""
    follow_up_at: str = ""
    stage: str = ""


class TraceCreate(BaseModel):
    ai_output_id: Optional[int] = None
    ai_suggestion: str
    human_revision: str
    revision_reason: str
    tags: list[str] = []


class CaseOut(BaseModel):
    id: int
    title: str
    claimant: str
    employer: str
    status: str
    summary: str
    claim_amount: str
    case_no: str
    case_type: str
    stage: str
    handler: str
    next_follow_up_at: str
    next_action: str
    created_at: datetime

    class Config:
        from_attributes = True


class DocumentOut(BaseModel):
    id: int
    case_id: int
    filename: str
    file_type: str
    raw_text: str
    parsed_json: Any
    uploaded_at: datetime


class EvidenceOut(BaseModel):
    id: int
    name: str
    category: str
    fact_to_prove: str
    source_document: str
    strength: str
    notes: str

    class Config:
        from_attributes = True


class AIOutputOut(BaseModel):
    id: int
    case_id: int
    output_type: str
    title: str
    content: str
    meta_json: Any
    created_at: datetime


class TraceOut(BaseModel):
    id: int
    case_id: int
    ai_output_id: Optional[int]
    ai_suggestion: str
    human_revision: str
    revision_reason: str
    tags: list[str]
    created_at: datetime


class MemoryOut(BaseModel):
    id: int
    title: str
    scenario: str
    legal_issue: str
    rule_summary: str
    decision_pattern: str
    tags: list[str]
    source_trace_id: Optional[int]
    created_at: datetime


class WorkflowEventOut(BaseModel):
    id: int
    event_type: str
    message: str
    payload_json: Any
    created_at: datetime


class WorkRecordOut(BaseModel):
    id: int
    case_id: int
    content: str
    record_type: str
    created_at: datetime

    class Config:
        from_attributes = True


class TodoOut(BaseModel):
    id: int
    case_id: int
    title: str
    due_date: str
    priority: str
    completed: bool
    created_at: datetime

    class Config:
        from_attributes = True


class FollowUpOut(BaseModel):
    id: int
    case_id: int
    progress: str
    next_action: str
    follow_up_at: str
    stage: str
    created_at: datetime

    class Config:
        from_attributes = True
