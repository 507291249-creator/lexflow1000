from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel


class CaseCreate(BaseModel):
    title: str
    claimant: str
    employer: str
    summary: str = ""
    raw_facts: str = ""
    claim_amount: str = ""
    case_no: str = ""
    case_type: str = "劳动仲裁"
    stage: str = "材料收集"
    handler: str = ""
    next_follow_up_at: str = ""
    next_action: str = ""


class AICaseCreate(BaseModel):
    title: str
    claimant: str = "待识别"
    employer: str = "待识别"
    fact_text: str = ""
    case_type: str = "劳动争议"


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


class FactReview(BaseModel):
    action: str
    human_fact: str = ""
    reason: str


class BatchReview(BaseModel):
    reason: str = "人工复核 AI 建议后批量确认，后续按需逐项修订。"


class IssueCreate(BaseModel):
    title: str
    description: str = ""
    analysis_hint: str = ""
    importance: str = "中"
    related_facts: list[str] = []
    related_fact_ids: list[str] = []
    reason: str


class IssueUpdate(BaseModel):
    title: str
    description: str = ""
    analysis_hint: str = ""
    status: str = "人工确认"
    importance: str = "中"
    related_facts: list[str] = []
    related_fact_ids: list[str] = []
    reason: str


class IssueAction(BaseModel):
    action: str
    reason: str


class AIReview(BaseModel):
    action: str
    human_revision: str = ""
    reason: str
    supplementary_material: str = ""


class WorkUnitReview(BaseModel):
    action: str
    reason: str
    reviewer: str = "承办律师"


class MemoryDecision(BaseModel):
    action: str
    title: str = ""
    rule_summary: str = ""
    decision_pattern: str = ""
    category: str = "案件经验"
    reason: str


class CaseOut(BaseModel):
    id: int
    title: str
    claimant: str
    employer: str
    status: str
    summary: str
    raw_facts: str = ""
    claim_amount: str
    case_no: str
    case_type: str
    stage: str
    handler: str
    next_follow_up_at: str
    next_action: str
    workflow_mode: str = "standard"
    fact_version: int = 1
    issue_version: int = 1
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
    original_filename: str = ""
    mime_type: str = "application/octet-stream"
    file_size: Optional[int] = None
    checksum: Optional[str] = None
    storage_provider: str = "legacy_local"
    storage_key: Optional[str] = None
    processing_status: str = "uploaded"
    extraction_error: str = ""
    updated_at: datetime


class FactSourceOut(BaseModel):
    id: int
    fact_id: int
    document_id: int
    source_text: str
    page_number: Optional[int] = None
    paragraph_index: Optional[int] = None
    start_offset: Optional[int] = None
    end_offset: Optional[int] = None
    relation_type: str = "support"
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


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
    reviewed_content: str = ""
    meta_json: Any
    work_unit_id: Optional[int] = None
    review_status: str = "待复核"
    version: int = 1
    fact_version: int = 1
    issue_version: int = 1
    input_snapshot_json: Any = {}
    execution_mode: str = "llm"
    created_at: datetime


class TraceOut(BaseModel):
    id: int
    case_id: int
    ai_output_id: Optional[int]
    ai_suggestion: str
    human_revision: str
    revision_reason: str
    tags: list[str]
    work_unit_id: Optional[int] = None
    action: str = "人工修改"
    object_type: str = "AI输出"
    object_id: Optional[int] = None
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
    source_work_unit_id: Optional[int] = None
    category: str = "案件经验"
    status: str = "已沉淀"
    review_reason: str = ""
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


class WorkUnitOut(BaseModel):
    id: int
    case_id: int
    code: str
    title: str
    sequence: int
    status: str
    description: str
    input_json: Any
    output_json: Any
    ai_output_id: Optional[int]
    parent_issue_id: Optional[int] = None
    version: int = 1
    reviewer: str
    reviewed_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime


class FactOut(BaseModel):
    id: int
    case_id: int
    work_unit_id: Optional[int]
    category: str
    ai_fact: str
    human_fact: str
    source_document: str
    status: str
    confidence: str
    fact_version: int = 1
    created_at: datetime
    updated_at: datetime


class IssueOut(BaseModel):
    id: int
    case_id: int
    work_unit_id: Optional[int]
    title: str
    description: str
    analysis_hint: str
    source: str
    status: str
    importance: str = "中"
    related_facts: list[str] = []
    related_fact_ids: list[str] = []
    issue_version: int = 1
    created_at: datetime
    updated_at: datetime
