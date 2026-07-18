import type { CaseWorkspace } from "@/lib/api";

export type WorkflowStepCode =
  | "case_input"
  | "materials"
  | "fact_review"
  | "issue_review"
  | "legal_analysis"
  | "report";

export type ReservedWorkflowCode = "redaction" | "legal_research" | "case_retrieval";

export type WorkflowIcon =
  | "input"
  | "materials"
  | "facts"
  | "issues"
  | "analysis"
  | "report"
  | "redaction"
  | "research"
  | "cases";

export type CompletionRule =
  | "has_case_input"
  | "has_materials"
  | "facts_confirmed"
  | "issues_confirmed"
  | "analysis_approved"
  | "report_generated";

export type WorkflowStepConfig = {
  code: WorkflowStepCode;
  title: string;
  description: string;
  order: number;
  icon: WorkflowIcon;
  completionRule: CompletionRule;
  nextStep: WorkflowStepCode | null;
};

export type ReservedWorkflowConfig = {
  code: ReservedWorkflowCode;
  title: string;
  description: string;
  icon: WorkflowIcon;
  availability: "planned";
};

const workflowSteps: WorkflowStepConfig[] = [
  {
    code: "case_input",
    title: "案件输入",
    description: "核对案件摘要与原始事实。",
    order: 1,
    icon: "input",
    completionRule: "has_case_input",
    nextStep: "materials",
  },
  {
    code: "materials",
    title: "材料与脱敏",
    description: "管理原始材料；脱敏能力尚未接入。",
    order: 2,
    icon: "materials",
    completionRule: "has_materials",
    nextStep: "fact_review",
  },
  {
    code: "fact_review",
    title: "事实确认",
    description: "复核 AI 提取事实并形成事实版本。",
    order: 3,
    icon: "facts",
    completionRule: "facts_confirmed",
    nextStep: "issue_review",
  },
  {
    code: "issue_review",
    title: "争点确认",
    description: "确认争议焦点及其关联事实。",
    order: 4,
    icon: "issues",
    completionRule: "issues_confirmed",
    nextStep: "legal_analysis",
  },
  {
    code: "legal_analysis",
    title: "法律分析",
    description: "逐项运行分析并完成人工复核。",
    order: 5,
    icon: "analysis",
    completionRule: "analysis_approved",
    nextStep: "report",
  },
  {
    code: "report",
    title: "结果输出",
    description: "生成报告并查看完整决策记录。",
    order: 6,
    icon: "report",
    completionRule: "report_generated",
    nextStep: null,
  },
];

export const WORKFLOW_STEPS = [...workflowSteps].sort((a, b) => a.order - b.order);

export const RESERVED_WORKFLOW_STEPS: ReservedWorkflowConfig[] = [
  { code: "redaction", title: "材料脱敏", description: "敏感信息检测与人工确认", icon: "redaction", availability: "planned" },
  { code: "legal_research", title: "法规检索", description: "围绕争点召回适用法规", icon: "research", availability: "planned" },
  { code: "case_retrieval", title: "类案对比", description: "检索相似事实与裁判观点", icon: "cases", availability: "planned" },
];

export type WorkflowRailItem =
  | (WorkflowStepConfig & { implemented: true })
  | (ReservedWorkflowConfig & { order: number; implemented: false });

// The rail is the single source of truth for the visible reasoning sequence.
// Planned steps stay visible in their future position but cannot be selected.
export const WORKFLOW_RAIL_STEPS: WorkflowRailItem[] = [
  { ...workflowSteps[0], implemented: true },
  { ...workflowSteps[1], implemented: true },
  { ...workflowSteps[2], implemented: true },
  { ...workflowSteps[3], implemented: true },
  { ...RESERVED_WORKFLOW_STEPS.find((item) => item.code === "legal_research")!, order: 5, implemented: false },
  { ...RESERVED_WORKFLOW_STEPS.find((item) => item.code === "case_retrieval")!, order: 6, implemented: false },
  { ...workflowSteps[4], order: 7, implemented: true },
  { ...workflowSteps[5], order: 8, implemented: true },
];

export function getWorkflowStepConfig(code: WorkflowStepCode) {
  const step = WORKFLOW_STEPS.find((item) => item.code === code);
  if (!step) throw new Error(`Unknown workflow step: ${code}`);
  return step;
}

export type WorkflowVisualState =
  | "waiting"
  | "ai_generated"
  | "pending_review"
  | "human_confirmed"
  | "rerun_required"
  | "failed"
  | "ready"
  | "expired"
  | "unavailable";

function currentAnalysisOutputs(workspace: CaseWorkspace) {
  return workspace.ai_outputs.filter(
    (output) =>
      output.output_type === "legal_analysis" &&
      output.fact_version === workspace.case.fact_version &&
      output.issue_version === workspace.case.issue_version
  );
}

export function getWorkflowStepState(
  workspace: CaseWorkspace,
  code: WorkflowStepCode
): WorkflowVisualState {
  const factsConfirmed =
    workspace.facts.length > 0 &&
    workspace.facts.every((fact) => fact.status !== "待确认") &&
    workspace.facts.some((fact) => fact.status === "已确认");
  const issuesConfirmed =
    workspace.issues.length > 0 &&
    workspace.issues.every((issue) => ["人工确认", "分析中", "已完成"].includes(issue.status));
  const currentOutputs = currentAnalysisOutputs(workspace);
  const approved = currentOutputs.filter((output) => ["已接受", "已修改"].includes(output.review_status));

  if (code === "case_input") {
    return workspace.case.raw_facts || workspace.case.summary ? "human_confirmed" : "waiting";
  }
  if (code === "materials") {
    if (!workspace.documents.length) return workspace.case.raw_facts ? "ready" : "waiting";
    if (workspace.documents.some((document) => ["parse_failed", "analysis_failed"].includes(document.processing_status))) return "failed";
    if (workspace.documents.some((document) => ["uploaded", "parsing", "analyzing"].includes(document.processing_status))) return "ai_generated";
    return "human_confirmed";
  }
  if (code === "fact_review") {
    const factUnit = workspace.work_units.find((unit) => unit.code === "fact_extraction");
    if (factsConfirmed) return "human_confirmed";
    if (workspace.facts.length) return "pending_review";
    if (factUnit?.status === "失败") return "failed";
    if (["需修改", "需重新生成"].includes(factUnit?.status || "")) return "rerun_required";
    if (workspace.ai_outputs.some((output) => output.output_type === "fact_extraction")) return "ai_generated";
    return "waiting";
  }
  if (code === "issue_review") {
    const issueUnit = workspace.work_units.find((unit) => unit.code === "issue_identification");
    if (issuesConfirmed) return "human_confirmed";
    if (workspace.issues.length) return "pending_review";
    if (issueUnit?.status === "失败") return "failed";
    if (["需修改", "需重新生成"].includes(issueUnit?.status || "")) return "rerun_required";
    if (workspace.ai_outputs.some((output) => output.output_type === "issue_identification")) return "ai_generated";
    if (factsConfirmed) return "ready";
    return "waiting";
  }
  if (code === "legal_analysis") {
    const analysisUnits = workspace.work_units.filter((unit) => unit.code.startsWith("legal_analysis:"));
    if (analysisUnits.some((unit) => unit.status === "失败")) return "failed";
    if (analysisUnits.some((unit) => ["需修改", "需重新生成"].includes(unit.status))) return "rerun_required";
    if (currentOutputs.length && approved.length === currentOutputs.length) return "human_confirmed";
    if (currentOutputs.length) return "pending_review";
    if (issuesConfirmed) return "ready";
    return "waiting";
  }
  const report = workspace.ai_outputs.some(
    (output) =>
      output.output_type === "legal_report" &&
      output.fact_version === workspace.case.fact_version &&
      output.issue_version === workspace.case.issue_version
  );
  if (report) return "human_confirmed";
  if (approved.length) return "ready";
  return "waiting";
}

export function getNextWorkflowStep(code: WorkflowStepCode) {
  return getWorkflowStepConfig(code).nextStep;
}
