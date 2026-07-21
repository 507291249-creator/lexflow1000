"use client";

import { ChevronRight } from "lucide-react";
import type { CaseWorkspace } from "@/lib/api";
import { getWorkflowStepConfig, type WorkflowStepCode } from "@/lib/workflow-config";
import { SectionHeader } from "./primitives";

export function CaseOverviewPanel({ workspace, onNext }: { workspace: CaseWorkspace; onNext: (step: WorkflowStepCode) => void }) {
  const confirmed = workspace.facts.filter((item) => item.status === "已确认").length;
  const nextStep = getWorkflowStepConfig("materials");
  return (
    <section className="workspace-card space-y-5">
      <SectionHeader title="案件概况" description="本页集中展示案件输入和当前处理进度，原始内容不会因后续 AI 运行而被覆盖。" />
      <div className="grid gap-5 lg:grid-cols-[1.25fr_0.75fr]">
        <div>
          <div className="text-xs font-medium text-slate-500">案件摘要</div>
          <p className="mt-2 whitespace-pre-wrap text-sm leading-7 text-slate-700">{workspace.case.summary || workspace.case.raw_facts || "尚未补充案件摘要。"}</p>
          {workspace.case.raw_facts && workspace.case.summary && (
            <details className="mt-4 rounded-md border border-line bg-[var(--surface-subtle)] p-3">
              <summary className="cursor-pointer text-sm font-medium text-ink">查看原始案件事实</summary>
              <p className="mt-3 whitespace-pre-wrap text-sm leading-7 text-slate-600">{workspace.case.raw_facts}</p>
            </details>
          )}
        </div>
        <div>
          <div className="grid grid-cols-2 gap-2">
            <Metric label="案件材料" value={workspace.documents.length} />
            <Metric label="已确认事实" value={confirmed} />
            <Metric label="争点" value={workspace.issues.length} />
            <Metric label="决策记录" value={workspace.traces.length} />
          </div>
          <button className="button-primary mt-4 w-full" type="button" onClick={() => onNext(nextStep.code)}>进入{nextStep.title}<ChevronRight size={16} /></button>
        </div>
      </div>
    </section>
  );
}

function Metric({ label, value }: { label: string; value: string | number }) {
  return <div className="rounded-md border border-line bg-white p-3"><div className="text-xs text-slate-500">{label}</div><div className="mt-1 text-xl font-semibold text-ink">{value}</div></div>;
}
