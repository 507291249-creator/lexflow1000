const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

export type CaseItem = {
  id: number;
  title: string;
  claimant: string;
  employer: string;
  status: string;
  summary: string;
  raw_facts: string;
  claim_amount: string;
  case_no: string;
  case_type: string;
  stage: string;
  handler: string;
  next_follow_up_at: string;
  next_action: string;
  workflow_mode: string;
  material_version: number;
  fact_version: number;
  issue_version: number;
  analysis_version: number;
  report_version: number;
  created_at: string;
};

export type Evidence = {
  id: number;
  name: string;
  category: string;
  fact_to_prove: string;
  source_document: string;
  strength: string;
  notes: string;
};

export type AIOutput = {
  id: number;
  case_id: number;
  output_type: string;
  title: string;
  content: string;
  reviewed_content?: string;
  meta_json: unknown;
  work_unit_id: number | null;
  review_status: string;
  version: number;
  material_version: number;
  fact_version: number;
  issue_version: number;
  analysis_version: number;
  report_version: number;
  input_snapshot_json: Record<string, unknown>;
  execution_mode: "llm" | "fallback" | "unknown";
  created_at: string;
};

export type DocumentItem = {
  id: number;
  filename: string;
  file_type: string;
  raw_text: string;
  parsed_json: Record<string, unknown>;
  uploaded_at: string;
  original_filename: string;
  mime_type: string;
  file_size: number | null;
  checksum: string | null;
  storage_provider: string;
  storage_key: string | null;
  processing_status: string;
  extraction_error: string;
  updated_at: string;
};

export type RedactionItem = {
  id: number;
  redaction_id: number;
  entity_type: string;
  start_offset: number;
  end_offset: number;
  replacement: string;
  action: "consistent_alias" | "partial_mask" | "full_replace" | "keep";
  confidence: number;
  rule_code: string;
  review_status: string;
  original_fingerprint: string;
  created_at: string;
  updated_at: string;
};

export type RedactionRecord = {
  id: number;
  case_id: number;
  document_id: number;
  source_checksum: string;
  version: number;
  status: "detected" | "draft" | "confirmed" | "superseded" | "original_confirmed";
  redacted_text: string;
  analysis_mode: "redacted" | "original";
  confirmed_at: string | null;
  created_at: string;
  updated_at: string;
  source_current: boolean;
  items: RedactionItem[];
};

export type Trace = {
  id: number;
  case_id: number;
  ai_output_id: number | null;
  ai_suggestion: string;
  human_revision: string;
  revision_reason: string;
  tags: string[];
  work_unit_id: number | null;
  action: string;
  object_type: string;
  object_id: number | null;
  created_at: string;
};

export type MemoryItem = {
  id: number;
  title: string;
  scenario: string;
  legal_issue: string;
  rule_summary: string;
  decision_pattern: string;
  tags: string[];
  source_trace_id: number | null;
  source_work_unit_id: number | null;
  category: string;
  status: string;
  review_reason: string;
  created_at: string;
};

export type WorkflowEvent = {
  id: number;
  event_type: string;
  message: string;
  payload_json: unknown;
  created_at: string;
};

export type WorkflowVersions = {
  material_version: number;
  fact_version: number;
  issue_version: number;
  analysis_version: number;
  report_version: number;
};

export type WorkflowBlocker = {
  code: string;
  step: string;
  severity: "blocking" | "warning" | "info";
  message: string;
  entity_type: string | null;
  entity_ids: number[];
  resolution: string | null;
  details: Record<string, unknown>;
};

export type StaleOutput = {
  entity_type: string;
  entity_id: number;
  title: string;
  review_status: string;
  is_stale: boolean;
  stale_reason: string;
  stale_at: string | null;
  input_versions: Record<string, number>;
  current_versions: Record<string, number>;
  required_action: string;
};

export type VersionHistoryEntry = {
  event_id: string;
  entry_type: "generation" | "publication";
  event_type: string;
  object_type: string;
  object_id: number | null;
  ai_output_id: number | null;
  work_unit_id: number | null;
  generation_version: number | null;
  published_version: number | null;
  before_versions: Record<string, number> | null;
  after_versions: Record<string, number> | null;
  input_versions: Record<string, number> | null;
  digest: string | null;
  reason: string | null;
  is_current: boolean;
  is_stale: boolean;
  stale_reason: string | null;
  created_at: string;
};

export type VersionHistoryPage = {
  current_versions: WorkflowVersions;
  page: number;
  page_size: number;
  total: number;
  items: VersionHistoryEntry[];
};

export type ReasoningTraceEntry = {
  event_id: string;
  event_source: "decision_trace" | "workflow_event";
  event_type: string;
  action: string | null;
  object_type: string | null;
  object_id: number | null;
  ai_output_id: number | null;
  work_unit_id: number | null;
  ai_suggestion: string | null;
  human_revision: string | null;
  revision_reason: string | null;
  tags: string[] | null;
  before_versions: Record<string, number> | null;
  after_versions: Record<string, number> | null;
  input_versions: Record<string, number> | null;
  created_at: string;
};

export type ReasoningTracePage = {
  page: number;
  page_size: number;
  total: number;
  items: ReasoningTraceEntry[];
};

export type WorkRecord = {
  id: number;
  case_id: number;
  content: string;
  record_type: string;
  created_at: string;
};

export type TodoItem = {
  id: number;
  case_id: number;
  title: string;
  due_date: string;
  priority: string;
  completed: boolean;
  created_at: string;
};

export type FollowUp = {
  id: number;
  case_id: number;
  progress: string;
  next_action: string;
  follow_up_at: string;
  stage: string;
  created_at: string;
};

export type WorkUnit = {
  id: number;
  case_id: number;
  code: string;
  title: string;
  sequence: number;
  status: string;
  description: string;
  input_json: Record<string, unknown>;
  output_json: Record<string, unknown>;
  ai_output_id: number | null;
  parent_issue_id: number | null;
  version: number;
  reviewer: string;
  reviewed_at: string | null;
  created_at: string;
  updated_at: string;
};

export type CaseFact = {
  id: number;
  case_id: number;
  work_unit_id: number | null;
  category: string;
  ai_fact: string;
  human_fact: string;
  source_document: string;
  status: string;
  confidence: string;
  material_version: number;
  fact_version: number;
  created_at: string;
  updated_at: string;
};

export type CaseIssue = {
  id: number;
  case_id: number;
  work_unit_id: number | null;
  title: string;
  description: string;
  analysis_hint: string;
  source: string;
  status: string;
  importance: string;
  related_facts: string[];
  related_fact_ids: string[];
  fact_version: number;
  issue_version: number;
  created_at: string;
  updated_at: string;
};

export type CaseWorkspace = {
  case: CaseItem;
  documents: DocumentItem[];
  evidences: Evidence[];
  work_units: WorkUnit[];
  facts: CaseFact[];
  issues: CaseIssue[];
  ai_outputs: AIOutput[];
  traces: Trace[];
  memory_candidates: MemoryItem[];
  workflow_state?: {
    current_step: string;
    completed_steps: string[];
    available_steps: string[];
    blockers: WorkflowBlocker[];
    stale_outputs: StaleOutput[];
    versions: WorkflowVersions;
    report_status: "REPORT_DRAFT_EXISTS" | "REPORT_PENDING_REVIEW" | "REPORT_PUBLISHED" | null;
    coverage: Record<string, unknown>;
    next_action: { code: string; label: string; entity_type: string | null; entity_ids: number[] } | null;
    facts_confirmed: boolean;
    issues_confirmed: boolean;
    approved_analysis_count: number;
    analysis_count: number;
    report_ready: boolean;
    report_current?: boolean;
  };
};

export async function api<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: options?.body instanceof FormData ? options.headers : {
      "Content-Type": "application/json",
      ...(options?.headers || {})
    },
    cache: "no-store"
  });
  if (!response.ok) {
    throw new Error(await response.text());
  }
  return response.json();
}

export function operationId(scope: string) {
  const suffix = typeof crypto !== "undefined" && "randomUUID" in crypto
    ? crypto.randomUUID()
    : `${Date.now()}-${Math.random().toString(16).slice(2)}`;
  return `${scope}-${suffix}`;
}

export { API_BASE };
