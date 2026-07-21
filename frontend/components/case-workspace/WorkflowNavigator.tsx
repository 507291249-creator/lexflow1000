"use client";

import type { CaseWorkspace } from "@/lib/api";
import { getWorkflowStepState, WORKFLOW_RAIL_STEPS, type WorkflowStepCode } from "@/lib/workflow-config";
import { reasoningIcons } from "@/components/reasoning-workbench/ReasoningRail";
import { visualStateMeta } from "./shared";

export function WorkflowNavigator({ workspace, activeStep, onChange }: { workspace: CaseWorkspace; activeStep: WorkflowStepCode; onChange: (step: WorkflowStepCode) => void }) {
  return (
    <nav aria-label="案件工作流" className="overflow-x-auto rounded-lg border border-line bg-white shadow-sm">
      <div className="flex min-w-max">
        {WORKFLOW_RAIL_STEPS.map((step) => {
          const Icon = reasoningIcons[step.icon];
          const state = step.implemented ? getWorkflowStepState(workspace, step.code) : "unavailable";
          const meta = visualStateMeta[state];
          const active = step.implemented && activeStep === step.code;
          return (
            <button
              key={step.code}
              type="button"
              aria-current={active ? "step" : undefined}
              disabled={!step.implemented}
              onClick={() => step.implemented && onChange(step.code)}
              className={`flex min-w-36 items-center gap-3 border-r border-line px-4 py-3 text-left last:border-r-0 ${active ? "bg-[var(--court-subtle)]" : step.implemented ? "hover:bg-[var(--surface-subtle)]" : "cursor-default opacity-60"}`}
            >
              <span className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full ${active ? "bg-court text-white" : "bg-[var(--surface-subtle)] text-slate-500"}`}><Icon size={15} /></span>
              <span>
                <span className="block text-sm font-semibold text-ink">{step.title}</span>
                <span className={`mt-1 block text-[11px] ${meta.className.split(" ").slice(1).join(" ")}`}>{meta.label}</span>
              </span>
            </button>
          );
        })}
      </div>
    </nav>
  );
}
