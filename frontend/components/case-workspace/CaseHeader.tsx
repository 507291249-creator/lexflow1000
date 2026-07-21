"use client";

import { BriefcaseBusiness, RefreshCw } from "lucide-react";
import type { CaseWorkspace } from "@/lib/api";
import { getWorkflowStepConfig, type WorkflowStepCode } from "@/lib/workflow-config";
import { EntityCode } from "@/components/ui/ReasoningUI";
import { VersionChip } from "./primitives";

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
  const currentStep = getWorkflowStepConfig(activeStep);
  return (
    <header className="rounded-lg border border-line bg-white px-4 py-4 shadow-sm">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <EntityCode kind="case" id={item.id} />
            <h1 className="truncate text-lg font-semibold text-ink">{item.title}</h1>
            <span className={`badge ${item.workflow_mode === "ai_case" ? "bg-[var(--ai-100)] text-[var(--ai-600)]" : "bg-[var(--court-subtle)] text-[var(--court)]"}`}>{item.workflow_mode === "ai_case" ? "AI 案件" : "标准案件"}</span>
          </div>
          <div className="mt-3 flex flex-wrap items-center gap-2">
            <VersionChip label="事实" value={`V${item.fact_version}`} tone="court" />
            <VersionChip label="争点" value={`V${item.issue_version}`} tone="court" />
            <span className="inline-flex shrink-0 items-center gap-1 rounded border border-[var(--court)] bg-[var(--court-subtle)] px-1.5 py-0.5 text-[11px] font-medium text-[var(--court)]">
              当前阶段 · {currentStep.title}
            </span>
            <span className="text-[11px] text-slate-400">{item.case_type || "案件分析"}</span>
          </div>
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
