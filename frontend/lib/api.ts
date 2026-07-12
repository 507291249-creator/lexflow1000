const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

export type CaseItem = {
  id: number;
  title: string;
  claimant: string;
  employer: string;
  status: string;
  summary: string;
  claim_amount: string;
  case_no: string;
  case_type: string;
  stage: string;
  handler: string;
  next_follow_up_at: string;
  next_action: string;
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
  output_type: "analysis" | "draft" | "risk";
  title: string;
  content: string;
  meta_json: unknown;
  created_at: string;
};

export type DocumentItem = {
  id: number;
  filename: string;
  file_type: string;
  raw_text: string;
  parsed_json: Record<string, unknown>;
  uploaded_at: string;
};

export type Trace = {
  id: number;
  case_id: number;
  ai_output_id: number | null;
  ai_suggestion: string;
  human_revision: string;
  revision_reason: string;
  tags: string[];
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
