from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


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


class FactPublishRequest(BaseModel):
    operation_id: str = Field(min_length=1)
    reason: str = Field(min_length=1)


class FactPublishOut(BaseModel):
    case_id: int
    old_version: int
    new_version: int
    material_version: int
    fact_ids: list[int] = Field(default_factory=list)
    replayed: bool = False


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


class IssuePublishRequest(BaseModel):
    operation_id: str = Field(min_length=1)
    reason: str = Field(min_length=1)


class IssuePublishOut(BaseModel):
    case_id: int
    old_version: int
    new_version: int
    fact_version: int
    issue_ids: list[int] = Field(default_factory=list)
    replayed: bool = False


class AnalysisPublishRequest(BaseModel):
    analysis_ids: list[int] = Field(min_length=1)
    operation_id: str = Field(min_length=1)
    reason: str = Field(min_length=1)


class AnalysisPublishOut(BaseModel):
    case_id: int
    old_version: int
    new_version: int
    analysis_digest: str
    analysis_ids: list[int] = Field(default_factory=list)
    replayed: bool = False


class ReportPublishRequest(BaseModel):
    operation_id: str = Field(min_length=1)
    reason: str = Field(min_length=1)


class ReportPublishOut(BaseModel):
    case_id: int
    report_id: int
    old_version: int
    new_version: int
    report_digest: str
    analysis_version: int
    analysis_digest: str
    analysis_ids: list[int] = Field(default_factory=list)
    replayed: bool = False


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
    material_version: int = 0
    fact_version: int = 1
    issue_version: int = 1
    analysis_version: int = 0
    report_version: int = 0
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


class RedactionDetectRequest(BaseModel):
    document_id: int
    force: bool = False


class RedactionItemCreate(BaseModel):
    start_offset: int
    end_offset: int
    entity_type: str
    replacement: str = ""
    action: str = "full_replace"
    confidence: float = 1.0
    rule_code: str = "manual"
    review_status: str = "人工新增"


class RedactionItemUpdate(BaseModel):
    entity_type: Optional[str] = None
    replacement: Optional[str] = None
    action: Optional[str] = None
    review_status: Optional[str] = None


class RedactionConfirm(BaseModel):
    use_original: bool = False
    original_material_confirmed: bool = False
    risk_acknowledged: bool = False


class RedactionBatchAccept(BaseModel):
    review_status: str = "已接受"


class RedactionItemOut(BaseModel):
    id: int
    redaction_id: int
    entity_type: str
    start_offset: int
    end_offset: int
    replacement: str
    action: str
    confidence: float
    rule_code: str
    review_status: str
    original_fingerprint: str
    created_at: datetime
    updated_at: datetime


class RedactionRecordOut(BaseModel):
    id: int
    case_id: int
    document_id: int
    source_checksum: str
    version: int
    status: str
    redacted_text: str
    analysis_mode: str
    confirmed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    source_current: bool = True
    items: list[RedactionItemOut] = Field(default_factory=list)


WorkflowStepCode = Literal[
    "case_input",
    "materials",
    "fact_review",
    "issue_review",
    "legal_analysis",
    "report",
]


class BlockerSchema(BaseModel):
    code: str
    step: WorkflowStepCode
    severity: Literal["blocking", "warning", "info"]
    message: str
    entity_type: Optional[str] = None
    entity_ids: list[int] = Field(default_factory=list)
    resolution: Optional[str] = None
    details: dict[str, Any] = Field(default_factory=dict)


class StaleOutputSchema(BaseModel):
    entity_type: str
    entity_id: int
    title: str
    review_status: str
    is_stale: bool
    stale_reason: str
    stale_at: Optional[datetime] = None
    input_versions: dict[str, int] = Field(default_factory=dict)
    current_versions: dict[str, int] = Field(default_factory=dict)
    required_action: str


class CaseInputCoverageSchema(BaseModel):
    complete: bool


class MaterialsCoverageSchema(BaseModel):
    total: int
    ready: int
    has_inline_input: bool


class FactsCoverageSchema(BaseModel):
    total: int
    reviewed: int
    confirmed: int
    stale: int


class IssuesCoverageSchema(BaseModel):
    total: int
    reviewed: int
    stale: int


class AnalysisCoverageSchema(BaseModel):
    expected: int
    generated: int
    approved: int
    stale: int


class ReportCoverageSchema(BaseModel):
    generated: bool
    current: bool


class CoverageSchema(BaseModel):
    case_input: CaseInputCoverageSchema
    materials: MaterialsCoverageSchema
    facts: FactsCoverageSchema
    issues: IssuesCoverageSchema
    analysis: AnalysisCoverageSchema
    report: ReportCoverageSchema


class NextActionSchema(BaseModel):
    code: str
    label: str
    entity_type: Optional[str] = None
    entity_ids: list[int] = Field(default_factory=list)


class WorkflowVersionsSchema(BaseModel):
    material_version: int
    fact_version: int
    issue_version: int
    analysis_version: int
    report_version: int


ReportLifecycleStatus = Literal[
    "REPORT_DRAFT_EXISTS",
    "REPORT_PENDING_REVIEW",
    "REPORT_PUBLISHED",
]


class WorkflowStateSchema(BaseModel):
    current_step: WorkflowStepCode
    completed_steps: list[WorkflowStepCode] = Field(default_factory=list)
    available_steps: list[WorkflowStepCode] = Field(default_factory=list)
    blockers: list[BlockerSchema] = Field(default_factory=list)
    stale_outputs: list[StaleOutputSchema] = Field(default_factory=list)
    coverage: CoverageSchema
    next_action: Optional[NextActionSchema] = None
    versions: WorkflowVersionsSchema
    report_status: Optional[ReportLifecycleStatus] = None

    facts_confirmed: bool = False
    issues_confirmed: bool = False
    approved_analysis_count: int = 0
    analysis_count: int = 0
    report_ready: bool = False
    report_current: bool = False


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
    material_version: int = 0
    fact_version: int = 1
    issue_version: int = 1
    analysis_version: int = 0
    report_version: int = 0
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


class VersionHistoryEntry(BaseModel):
    event_id: str
    entry_type: Literal["generation", "publication"]
    event_type: str
    object_type: str
    object_id: Optional[int] = None
    ai_output_id: Optional[int] = None
    work_unit_id: Optional[int] = None
    generation_version: Optional[int] = None
    published_version: Optional[int] = None
    before_versions: Optional[dict[str, int]] = None
    after_versions: Optional[dict[str, int]] = None
    input_versions: Optional[dict[str, int]] = None
    digest: Optional[str] = None
    reason: Optional[str] = None
    is_current: bool
    is_stale: bool
    stale_reason: Optional[str] = None
    created_at: datetime


class VersionHistoryPage(BaseModel):
    current_versions: WorkflowVersionsSchema
    page: int
    page_size: int
    total: int
    items: list[VersionHistoryEntry] = Field(default_factory=list)


class ReasoningTraceEntry(BaseModel):
    event_id: str
    event_source: Literal["decision_trace", "workflow_event"]
    event_type: str
    action: Optional[str] = None
    object_type: Optional[str] = None
    object_id: Optional[int] = None
    ai_output_id: Optional[int] = None
    work_unit_id: Optional[int] = None
    ai_suggestion: Optional[str] = None
    human_revision: Optional[str] = None
    revision_reason: Optional[str] = None
    tags: Optional[list[str]] = None
    before_versions: Optional[dict[str, int]] = None
    after_versions: Optional[dict[str, int]] = None
    input_versions: Optional[dict[str, int]] = None
    created_at: datetime


class ReasoningTracePage(BaseModel):
    page: int
    page_size: int
    total: int
    items: list[ReasoningTraceEntry] = Field(default_factory=list)


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
    material_version: int = 0
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
    fact_version: int = 0
    issue_version: int = 1
    created_at: datetime
    updated_at: datetime


class WorkspaceSchema(BaseModel):
    case: CaseOut
    documents: list[DocumentOut] = Field(default_factory=list)
    evidences: list[EvidenceOut] = Field(default_factory=list)
    work_units: list[WorkUnitOut] = Field(default_factory=list)
    facts: list[FactOut] = Field(default_factory=list)
    issues: list[IssueOut] = Field(default_factory=list)
    ai_outputs: list[AIOutputOut] = Field(default_factory=list)
    traces: list[TraceOut] = Field(default_factory=list)
    memory_candidates: list[MemoryOut] = Field(default_factory=list)
    workflow_state: WorkflowStateSchema
