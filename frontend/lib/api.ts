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
  fact_version: number;
  issue_version: number;
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
  fact_version: number;
  issue_version: number;
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

export { API_BASE };
