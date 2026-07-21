"use client";

import { useEffect, useState } from "react";
import { FileText, History } from "lucide-react";
import type { AIOutput, CaseWorkspace } from "@/lib/api";
import { getWorkflowStepConfig } from "@/lib/workflow-config";
import { EntityCode } from "@/components/ui/ReasoningUI";
import { EmptyState, PanelHeading, StatusBadge } from "./shared";

type Request = (path: string, method?: string, body?: unknown) => Promise<boolean>;

function LegacyDraft({ output, busy, request }: { output: AIOutput; busy: string; request: Request }) {
  const [draft, setDraft] = useState(output.reviewed_content || output.content);
  const [reason, setReason] = useState("人工复核文书初稿。");
  useEffect(() => setDraft(output.reviewed_content || output.content), [output.id, output.reviewed_content, output.content]);
  const submit = (action: string, human_revision = "") => request(`/ai-outputs/${output.id}/review`, "POST", { action, human_revision, reason, supplementary_material: "" });

  return (
    <section className="workspace-card">
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <EntityCode kind="report" id={output.id} />
          <h3 className="font-semibold text-ink">{output.title}</h3>
        </div>
        <StatusBadge status={output.review_status} />
      </div>
      <textarea className="mt-4 min-h-96 w-full rounded-md border border-line px-3 py-3 font-mono text-sm leading-6 focus:border-court" value={draft} onChange={(event) => setDraft(event.target.value)} />
      <input className="mt-3 w-full rounded-md border border-line px-3 py-2 text-sm focus:border-court" value={reason} onChange={(event) => setReason(event.target.value)} />
      <div className="mt-3 flex flex-wrap gap-2">
        <button className="button-primary" disabled={Boolean(busy)} onClick={() => submit("接受", output.content)}>接受初稿</button>
        <button className="button-secondary" disabled={Boolean(busy)} onClick={() => submit("修改", draft)}>保存人工修改</button>
        <button className="button-secondary" disabled={Boolean(busy)} onClick={() => submit("驳回")}>驳回</button>
      </div>
    </section>
  );
}

function ReportVersionHistory({ outputs, current }: { outputs: AIOutput[]; current?: AIOutput }) {
  const [open, setOpen] = useState(false);
  const [activeId, setActiveId] = useState<number | null>(null);
  const history = outputs.filter((item) => item.id !== current?.id);
  if (!history.length) return null;
  const active = outputs.find((item) => item.id === activeId) || history[0];
  const isCurrent = current && active.id === current.id;
  return (
    <div className="rounded-md border border-line bg-[var(--surface-subtle)]">
      <button type="button" className="flex w-full items-center justify-between gap-2 px-3 py-2 text-left" onClick={() => setOpen((value) => !value)}>
        <span className="flex items-center gap-2 text-xs font-medium text-slate-600">
          <History size={14} className="text-slate-400" />
          报告版本谱系
        </span>
        <span className="text-[11px] text-slate-500">{outputs.length} 个版本 · 当前 V{current?.version ?? outputs[0].version}</span>
      </button>
      {open && (
        <div className="border-t border-line-subtle px-3 py-3">
          <div className="flex flex-wrap gap-2">
            {outputs.map((item) => (
              <button
                key={item.id}
                type="button"
                onClick={() => setActiveId(item.id)}
                className={`version-chip ${item.id === active.id ? "version-chip-court" : ""}`}
              >
                <span className="text-slate-400">V</span>
                <span className="font-semibold">{item.version}</span>
                <span className="ml-1 text-[10px] text-slate-400">F{item.fact_version}/I{item.issue_version}</span>
              </button>
            ))}
          </div>
          <pre className={`mt-3 max-h-56 overflow-auto whitespace-pre-wrap rounded-md p-3 text-xs leading-6 text-slate-700 ${isCurrent ? "human-surface" : "neutral-surface"}`}>
            {active.reviewed_content || active.content}
          </pre>
          <p className="mt-2 text-[11px] text-slate-500">
            生成于 {new Date(active.created_at).toLocaleString("zh-CN")} · {active.review_status || "未复核"}{isCurrent ? " · 当前版本" : " · 历史版本"}
          </p>
        </div>
      )}
    </div>
  );
}

export function ReportPanel({ caseId, workspace, busy, request }: { caseId: number; workspace: CaseWorkspace; busy: string; request: Request }) {
  const step = getWorkflowStepConfig("report");

  if (workspace.case.workflow_mode !== "ai_case") {
    const draft = workspace.ai_outputs.filter((output) => output.output_type === "draft").sort((a, b) => b.version - a.version)[0];
    return (
      <section className="space-y-5">
        <PanelHeading title={step.title} description={step.description} />
        {draft ? <LegacyDraft output={draft} busy={busy} request={request} /> : <EmptyState title="尚未生成文书" description="在法律分析步骤运行“文书生成”工作单元后显示初稿。" />}
      </section>
    );
  }

  const reports = workspace.ai_outputs.filter((output) => output.output_type === "legal_report").sort((a, b) => b.version - a.version);
  const report = reports.find((output) => output.fact_version === workspace.case.fact_version && output.issue_version === workspace.case.issue_version);
  const approved = workspace.ai_outputs.filter(
    (output) => output.output_type === "legal_analysis" && output.fact_version === workspace.case.fact_version && output.issue_version === workspace.case.issue_version && ["已接受", "已修改"].includes(output.review_status),
  ).length;
  const ready = workspace.workflow_state?.report_ready ?? approved > 0;

  return (
    <section className="space-y-5">
      <PanelHeading
        title={step.title}
        description={step.description}
        action={
          <button className="button-primary" disabled={Boolean(busy) || !ready} onClick={() => request(`/cases/${caseId}/legal-analysis-report`)}>
            <FileText size={16} />{report ? "重新生成报告" : "生成法律分析报告"}
          </button>
        }
      />

      {!ready && <div className="feedback-state border-[var(--warning-border)] bg-[var(--warning-bg)] text-[var(--warning)]">至少完成一项当前版本法律分析并通过人工复核后，才能生成报告。</div>}

      {report ? (
        <article className="workspace-card">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <div className="flex items-center gap-2">
                <EntityCode kind="report" id={report.id} />
                <h3 className="font-semibold text-ink">{report.title}</h3>
              </div>
              <p className="mt-2 flex flex-wrap items-center gap-2 text-xs text-slate-500">
                <span className="version-chip version-chip-court"><span className="text-slate-400">报告</span><span className="font-semibold">V{report.version}</span></span>
                <span className="version-chip"><span className="text-slate-400">事实</span><span className="font-semibold">V{report.fact_version}</span></span>
                <span className="version-chip"><span className="text-slate-400">争点</span><span className="font-semibold">V{report.issue_version}</span></span>
              </p>
            </div>
            <StatusBadge status={report.review_status || "已完成"} />
          </div>
          <div className="mt-5 border-t border-line pt-5 whitespace-pre-wrap text-sm leading-8 text-slate-700">{report.reviewed_content || report.content}</div>
          {reports.length > 1 && <div className="mt-5"><ReportVersionHistory outputs={reports} current={report} /></div>}
        </article>
      ) : (
        <EmptyState title="尚未生成法律分析报告" description="完成分析复核后，点击右上角按钮生成当前版本报告。" />
      )}
    </section>
  );
}
