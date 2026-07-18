export type EntityKind = "document" | "fact" | "issue" | "law" | "case" | "analysis" | "report";

export const entityPrefix: Record<EntityKind, string> = {
  document: "D",
  fact: "F",
  issue: "I",
  law: "L",
  case: "C",
  analysis: "A",
  report: "R",
};

export type ProductStatus =
  | "ai_generated"
  | "pending_review"
  | "human_confirmed"
  | "rerun_required"
  | "expired"
  | "failed"
  | "unavailable";

export const productStatusMeta: Record<ProductStatus, { label: string; className: string }> = {
  ai_generated: { label: "AI 生成", className: "status-ai" },
  pending_review: { label: "待人工确认", className: "status-pending" },
  human_confirmed: { label: "已人工确认", className: "status-confirmed" },
  rerun_required: { label: "需重新运行", className: "status-rerun" },
  expired: { label: "已过期", className: "status-expired" },
  failed: { label: "失败", className: "status-failed" },
  unavailable: { label: "尚未接入", className: "status-unavailable" },
};

const statusAliases: Record<string, ProductStatus> = {
  "AI建议": "ai_generated",
  "AI 生成": "ai_generated",
  uploaded: "ai_generated",
  parsing: "ai_generated",
  parsed: "ai_generated",
  analyzing: "ai_generated",
  ready: "human_confirmed",
  parse_failed: "failed",
  analysis_failed: "failed",
  "已上传": "ai_generated",
  "解析中": "ai_generated",
  "已解析": "ai_generated",
  "分析中": "ai_generated",
  "待处理": "pending_review",
  "待人工复核": "pending_review",
  "待复核": "pending_review",
  "待确认": "pending_review",
  "已批准": "human_confirmed",
  "已接受": "human_confirmed",
  "已修改": "human_confirmed",
  "已完成": "human_confirmed",
  "已确认": "human_confirmed",
  "人工确认": "human_confirmed",
  "需修改": "rerun_required",
  "需重新生成": "rerun_required",
  "需重新运行": "rerun_required",
  "已失效": "expired",
  "已过期": "expired",
  "失败": "failed",
  "解析失败": "failed",
  "分析失败": "failed",
  "待接入": "unavailable",
  "尚未接入": "unavailable",
};

export function normalizeProductStatus(status: string): ProductStatus | null {
  return statusAliases[status] || null;
}

export function formatEntityCode(kind: EntityKind, id: number | string) {
  const value = String(id).replace(/^0+/, "") || "0";
  return `${entityPrefix[kind]}-${value.padStart(2, "0")}`;
}
