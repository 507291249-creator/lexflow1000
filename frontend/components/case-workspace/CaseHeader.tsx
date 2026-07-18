"use client";

import { BriefcaseBusiness, RefreshCw } from "lucide-react";
import type { CaseWorkspace } from "@/lib/api";
import { getWorkflowStepConfig, type WorkflowStepCode } from "@/lib/workflow-config";
import { EntityCode } from "@/components/ui/ReasoningUI";

export function CaseHeader({
  workspace,
  activeStep,
  busy,
  onRefreshFacts,
  onOpenCaseInfo,
}: {
  workspace: CaseWorkspace;
  activeStep: WorkflowStepCode;
  busy: boolean;
  onRefreshFacts?: () => void;
  onOpenCaseInfo: () => void;
}) {
  const item = workspace.case;
  return (
    <header className="border-b border-line bg-white px-1 pb-4 pt-1">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <EntityCode kind="case" id={item.id} />
            <h1 className="truncate text-xl font-semibold text-ink">{item.title}</h1>
            <span className="badge bg-[#eaf3f8] text-court">{item.workflow_mode === "ai_case" ? "AI 案件" : "标准案件"}</span>
          </div>
          <p className="mt-2 text-sm text-slate-500">
            法律 AI 推理工作台 · 事实 V{item.fact_version} · 争点 V{item.issue_version} · 当前步骤 {getWorkflowStepConfig(activeStep).title}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          {onRefreshFacts && (
            <button className="button-secondary" type="button" disabled={busy} onClick={onRefreshFacts}>
              <RefreshCw size={16} />重新提取事实
            </button>
          )}
          <button className="button-secondary" type="button" onClick={onOpenCaseInfo}>
            <BriefcaseBusiness size={16} />案件信息
          </button>
        </div>
      </div>
    </header>
  );
}
