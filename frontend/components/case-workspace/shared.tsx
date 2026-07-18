"use client";

import type { ReactNode } from "react";
import { AlertCircle, CheckCircle2, Loader2 } from "lucide-react";
import type { WorkflowVisualState } from "@/lib/workflow-config";
import { EmptyReasoningState, ReasoningStatusBadge } from "@/components/ui/ReasoningUI";

export const visualStateMeta: Record<WorkflowVisualState, { label: string; className: string }> = {
  waiting: { label: "等待前序步骤", className: "bg-slate-100 text-slate-600" },
  ai_generated: { label: "AI 生成", className: "bg-blue-50 text-blue-700" },
  pending_review: { label: "待人工确认", className: "bg-amber-50 text-amber-700" },
  human_confirmed: { label: "已人工确认", className: "bg-[#e7f1ef] text-mint" },
  rerun_required: { label: "需重新运行", className: "bg-rose-50 text-rose-700" },
  failed: { label: "失败", className: "bg-rose-50 text-rose-700" },
  ready: { label: "可以开始", className: "bg-cyan-50 text-cyan-700" },
  expired: { label: "已过期", className: "bg-slate-100 text-slate-500" },
  unavailable: { label: "尚未接入", className: "bg-slate-100 text-slate-500" },
};

export const recordStatusClass: Record<string, string> = {
  已批准: "bg-[#e7f1ef] text-mint",
  已接受: "bg-[#e7f1ef] text-mint",
  已修改: "bg-blue-50 text-blue-700",
  已完成: "bg-[#e7f1ef] text-mint",
  已确认: "bg-[#e7f1ef] text-mint",
  人工确认: "bg-[#e7f1ef] text-mint",
  可生成: "bg-[#e7f1ef] text-mint",
  部分已批准: "bg-blue-50 text-blue-700",
  待人工复核: "bg-amber-50 text-amber-700",
  待复核: "bg-amber-50 text-amber-700",
  待确认: "bg-amber-50 text-amber-700",
  AI建议: "bg-blue-50 text-blue-700",
  分析中: "bg-blue-50 text-blue-700",
  已驳回: "bg-rose-50 text-rose-700",
  需修改: "bg-rose-50 text-rose-700",
  需重新生成: "bg-amber-50 text-amber-700",
  失败: "bg-rose-50 text-rose-700",
  已失效: "bg-slate-100 text-slate-500",
  候选: "bg-violet-50 text-violet-700",
};

const recordStatusLabel: Record<string, string> = {
  AI建议: "AI 生成",
  待人工复核: "待人工确认",
  待复核: "待人工确认",
  待确认: "待人工确认",
  已批准: "已人工确认",
  已接受: "已人工确认",
  已修改: "已人工确认",
  已确认: "已人工确认",
  人工确认: "已人工确认",
  需修改: "需重新运行",
  需重新生成: "需重新运行",
};

export function StatusBadge({ status }: { status: string }) {
  if (status === "已驳回") return <span className="status-badge status-expired">已驳回</span>;
  if (status === "候选") return <span className="status-badge bg-violet-50 text-violet-700">候选</span>;
  return <ReasoningStatusBadge status={status} label={recordStatusLabel[status]} />;
}

export function PanelHeading({ title, description, action }: { title: string; description: string; action?: ReactNode }) {
  return <div className="flex flex-wrap items-start justify-between gap-3"><div><h2 className="text-lg font-semibold text-ink">{title}</h2><p className="mt-1 text-sm leading-6 text-slate-600">{description}</p></div>{action}</div>;
}

export function EmptyState({ title, description, action }: { title: string; description: string; action?: ReactNode }) {
  return <EmptyReasoningState title={title} description={description} action={action} />;
}

export function WorkspaceFeedback({ loading, error, notice, onRetry }: { loading?: boolean; error?: string; notice?: string; onRetry?: () => void }) {
  if (loading) return <div className="flex items-center gap-2 border-l-2 border-court bg-blue-50 px-4 py-3 text-sm text-court"><Loader2 className="animate-spin" size={16} />正在处理，请稍候...</div>;
  if (error) return <div role="alert" className="flex flex-wrap items-center justify-between gap-3 border-l-2 border-rose-500 bg-rose-50 px-4 py-3 text-sm text-rose-800"><span className="flex items-center gap-2"><AlertCircle size={16} />{error}</span>{onRetry && <button className="button-secondary" type="button" onClick={onRetry}>重新加载</button>}</div>;
  if (notice) return <div role="status" className="flex items-center gap-2 border-l-2 border-emerald-500 bg-emerald-50 px-4 py-3 text-sm text-emerald-800"><CheckCircle2 size={16} />{notice}</div>;
  return null;
}

export function formatUnknown(value: unknown) {
  if (Array.isArray(value)) return value.map((item) => `• ${String(item)}`).join("\n");
  if (value && typeof value === "object") return JSON.stringify(value, null, 2);
  return String(value || "待生成");
}
