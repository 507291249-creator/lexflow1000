"use client";

import {
  BookOpenCheck,
  FileInput,
  FileSearch,
  Files,
  Gavel,
  ScanText,
  Scale,
  ScrollText,
  SearchCheck,
} from "lucide-react";
import type { CaseWorkspace } from "@/lib/api";
import {
  getWorkflowStepState,
  WORKFLOW_RAIL_STEPS,
  type WorkflowIcon,
  type WorkflowStepCode,
} from "@/lib/workflow-config";
import { visualStateMeta } from "@/components/case-workspace/shared";

export const reasoningIcons: Record<WorkflowIcon, typeof FileInput> = {
  input: FileInput,
  materials: Files,
  facts: FileSearch,
  issues: Gavel,
  analysis: Scale,
  report: ScrollText,
  redaction: ScanText,
  research: BookOpenCheck,
  cases: SearchCheck,
};

export function ReasoningRail({
  workspace,
  activeStep,
  onChange,
}: {
  workspace: CaseWorkspace;
  activeStep: WorkflowStepCode;
  onChange: (step: WorkflowStepCode) => void;
}) {
  return (
    <nav aria-label="法律推理流程" className="rounded-lg border border-line bg-white px-4 py-5 shadow-sm">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-sm font-semibold text-ink">推理流程</h2>
        <span className="text-xs text-slate-400">材料到结论</span>
      </div>
      <div>
        {WORKFLOW_RAIL_STEPS.map((step, index) => {
          const Icon = reasoningIcons[step.icon];
          const state = step.implemented ? getWorkflowStepState(workspace, step.code) : "unavailable";
          const meta = visualStateMeta[state];
          const active = step.implemented && activeStep === step.code;
          return (
            <div key={step.code} className="relative pb-2 last:pb-0">
              {index < WORKFLOW_RAIL_STEPS.length - 1 && <span className="absolute left-[17px] top-9 h-[calc(100%-24px)] w-px bg-line" />}
              <button
                type="button"
                aria-current={active ? "step" : undefined}
                disabled={!step.implemented}
                onClick={() => step.implemented && onChange(step.code)}
                className={`relative flex w-full gap-3 rounded-md px-2 py-3 text-left transition ${active ? "bg-[#edf5fa]" : step.implemented ? "hover:bg-slate-50" : "cursor-default opacity-70"}`}
              >
                <span className={`relative z-10 flex h-9 w-9 shrink-0 items-center justify-center rounded-full border ${active ? "border-court bg-court text-white" : "border-line bg-white text-slate-500"}`}>
                  <Icon size={16} />
                </span>
                <span className="min-w-0 flex-1">
                  <span className="flex items-center justify-between gap-2">
                    <span className={`text-sm font-semibold ${active ? "text-court" : "text-ink"}`}>{step.title}</span>
                    <span className="text-[11px] text-slate-400">{String(step.order).padStart(2, "0")}</span>
                  </span>
                  <span className="mt-1 block text-xs leading-5 text-slate-500">{step.description}</span>
                  <span className={`mt-2 inline-flex rounded px-2 py-1 text-[11px] font-medium ${meta.className}`}>{meta.label}</span>
                </span>
              </button>
            </div>
          );
        })}
      </div>

      <div className="mt-4 border-t border-line pt-3 text-xs leading-5 text-slate-500">灰色节点为已预留能力，不产生虚构检索结果。</div>
    </nav>
  );
}
