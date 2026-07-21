"use client";

import type { ReactNode } from "react";
import { AlertCircle, CheckCircle2, Loader2 } from "lucide-react";
import type { WorkflowVisualState } from "@/lib/workflow-config";
import { EmptyReasoningState, ReasoningStatusBadge } from "@/components/ui/ReasoningUI";

export const visualStateMeta: Record<WorkflowVisualState, { label: string; className: string }> = {
  waiting: { label: "等待前序步骤", className: "bg-[var(--inactive-subtle)] text-[var(--inactive)]" },
  ai_generated: { label: "AI 生成", className: "bg-[var(--ai-100)] text-[var(--ai-600)]" },
  pending_review: { label: "待人工确认", className: "bg-[var(--warning-bg)] text-[var(--warning)]" },
  human_confirmed: { label: "已人工确认", className: "bg-[var(--mint-subtle)] text-[var(--mint)]" },
  rerun_required: { label: "需重新运行", className: "bg-[var(--danger-bg)] text-[var(--danger)]" },
  failed: { label: "失败", className: "bg-[var(--danger-bg)] text-[var(--danger)]" },
  ready: { label: "可以开始", className: "bg-[var(--court-subtle)] text-[var(--court)]" },
  expired: { label: "已过期", className: "bg-[var(--inactive-subtle)] text-[var(--inactive)]" },
  unavailable: { label: "尚未接入", className: "bg-[var(--inactive-subtle)] text-[var(--inactive)]" },
};

export const recordStatusClass: Record<string, string> = {
  已批准: "bg-[var(--mint-subtle)] text-[var(--mint)]",
  已接受: "bg-[var(--mint-subtle)] text-[var(--mint)]",
  已修改: "bg-[var(--mint-subtle)] text-[var(--mint)]",
  已完成: "bg-[var(--mint-subtle)] text-[var(--mint)]",
  已确认: "bg-[var(--mint-subtle)] text-[var(--mint)]",
  人工确认: "bg-[var(--mint-subtle)] text-[var(--mint)]",
  可生成: "bg-[var(--mint-subtle)] text-[var(--mint)]",
  部分已批准: "bg-[var(--court-subtle)] text-[var(--court)]",
  待人工复核: "bg-[var(--warning-bg)] text-[var(--warning)]",
  待复核: "bg-[var(--warning-bg)] text-[var(--warning)]",
  待确认: "bg-[var(--warning-bg)] text-[var(--warning)]",
  AI建议: "bg-[var(--ai-100)] text-[var(--ai-600)]",
  分析中: "bg-[var(--ai-100)] text-[var(--ai-600)]",
  已驳回: "bg-[var(--danger-bg)] text-[var(--danger)]",
  需修改: "bg-[var(--danger-bg)] text-[var(--danger)]",
  需重新生成: "bg-[var(--warning-bg)] text-[var(--warning)]",
  失败: "bg-[var(--danger-bg)] text-[var(--danger)]",
  已失效: "bg-[var(--inactive-subtle)] text-[var(--inactive)]",
  候选: "bg-[var(--ai-100)] text-[var(--ai-600)]",
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
  if (status === "候选") return <span className="status-badge bg-[var(--ai-100)] text-[var(--ai-600)]">候选</span>;
  return <ReasoningStatusBadge status={status} label={recordStatusLabel[status]} />;
}

export function PanelHeading({ title, description, action }: { title: string; description: string; action?: ReactNode }) {
  return <div className="section-header"><div className="min-w-0"><h2>{title}</h2><p>{description}</p></div>{action && <div className="shrink-0">{action}</div>}</div>;
}

export function EmptyState({ title, description, action }: { title: string; description: string; action?: ReactNode }) {
  return <EmptyReasoningState title={title} description={description} action={action} />;
}

export function WorkspaceFeedback({ loading, error, notice, onRetry }: { loading?: boolean; error?: string; notice?: string; onRetry?: () => void }) {
  if (loading) return <div className="flex items-center gap-2 rounded-md border-l-2 border-[var(--court)] bg-[var(--court-subtle)] px-4 py-3 text-sm text-[var(--court)]"><Loader2 className="animate-spin" size={16} />正在处理，请稍候...</div>;
  if (error) return <div role="alert" className="flex flex-wrap items-center justify-between gap-3 rounded-md border-l-2 border-[var(--danger)] bg-[var(--danger-bg)] px-4 py-3 text-sm text-[var(--danger)]"><span className="flex items-center gap-2"><AlertCircle size={16} />{error}</span>{onRetry && <button className="button-secondary" type="button" onClick={onRetry}>重新加载</button>}</div>;
  if (notice) return <div role="status" className="flex items-center gap-2 rounded-md border-l-2 border-[var(--mint)] bg-[var(--mint-subtle)] px-4 py-3 text-sm text-[var(--mint)]"><CheckCircle2 size={16} />{notice}</div>;
  return null;
}

export function formatUnknown(value: unknown) {
  if (Array.isArray(value)) return value.map((item) => `• ${String(item)}`).join("\n");
  if (value && typeof value === "object") return JSON.stringify(value, null, 2);
  return String(value || "待生成");
}
