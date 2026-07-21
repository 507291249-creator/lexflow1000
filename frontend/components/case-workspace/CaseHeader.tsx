"use client";

import Link from "next/link";
import { ArrowLeft, BriefcaseBusiness, RefreshCw } from "lucide-react";
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
  const isAiCase = item.workflow_mode === "ai_case";

  return (
    <header className="rounded-lg border border-line bg-white shadow-sm">
      {/* Breadcrumb / back to cases */}
      <div className="flex items-center gap-2 border-b border-line-subtle px-5 py-2 text-xs text-slate-500">
        <Link href="/cases" className="inline-flex items-center gap-1 rounded px-1 py-0.5 font-medium text-slate-500 transition hover:text-court">
          <ArrowLeft size={13} />
          案件工作区
        </Link>
        <span className="text-slate-300">/</span>
        <span className="truncate text-slate-700">{item.title}</span>
      </div>
      <div className="flex flex-wrap items-start justify-between gap-4 px-5 py-4">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <EntityCode kind="case" id={item.id} />
            <h1 className="truncate text-lg font-semibold text-ink">{item.title}</h1>
            <span className={`badge ${isAiCase ? "bg-[var(--ai-100)] text-[var(--ai-600)]" : "bg-[var(--court-subtle)] text-[var(--court)]"}`}>
              {isAiCase ? "AI 案件" : "标准案件"}
            </span>
          </div>
          <div className="mt-3 flex flex-wrap items-center gap-2">
            <VersionChip label="事实" value={`V${item.fact_version}`} tone="court" />
            <VersionChip label="争点" value={`V${item.issue_version}`} tone="court" />
            <span className="inline-flex shrink-0 items-center gap-1 rounded border border-[var(--court-border)] bg-[var(--court-subtle)] px-1.5 py-0.5 text-[11px] font-medium text-[var(--court)]">
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

      {/* Dossier metadata strip */}
      <dl className="dl-grid border-t border-line-subtle bg-[var(--surface-subtle)] px-5 py-3">
        <div>
          <dt className="dl-term">申请人</dt>
          <dd className="dl-value">{item.claimant || "待识别"}</dd>
        </div>
        <div>
          <dt className="dl-term">被申请人</dt>
          <dd className="dl-value">{item.employer || "待识别"}</dd>
        </div>
        <div>
          <dt className="dl-term">争议金额</dt>
          <dd className="dl-value">{item.claim_amount || "未填写"}</dd>
        </div>
        <div>
          <dt className="dl-term">承办人</dt>
          <dd className="dl-value">{item.handler || "未指派"}</dd>
        </div>
        <div>
          <dt className="dl-term">案件阶段</dt>
          <dd className="dl-value">{item.stage || "未设置"}</dd>
        </div>
        <div>
          <dt className="dl-term">下一步行动</dt>
          <dd className="dl-value">{item.next_action || "—"}</dd>
        </div>
      </dl>
    </header>
  );
}
