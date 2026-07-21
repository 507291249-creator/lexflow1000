"use client";

import { useState } from "react";
import { Check, Play, Plus, Save, Trash2, X } from "lucide-react";
import type { CaseIssue, CaseWorkspace } from "@/lib/api";
import { getWorkflowStepConfig } from "@/lib/workflow-config";
import { EntityCode } from "@/components/ui/ReasoningUI";
import { EmptyState, PanelHeading, StatusBadge } from "./shared";
import { SourceTag, VersionChip, WorkspaceCard } from "./primitives";

type Request = (path: string, method?: string, body?: unknown) => Promise<boolean>;
type Draft = Pick<CaseIssue, "id" | "title" | "description" | "analysis_hint" | "importance" | "status" | "related_fact_ids">;

function relatedFacts(issue: CaseIssue, workspace: CaseWorkspace) {
  const ids = new Set((issue.related_fact_ids || []).map(Number));
  return workspace.facts.filter((fact) => ids.has(fact.id));
}

export function IssueReviewPanel({ caseId, workspace, busy, request }: { caseId: number; workspace: CaseWorkspace; busy: string; request: Request }) {
  const step = getWorkflowStepConfig("issue_review");
  const [editing, setEditing] = useState<Draft | null>(null);
  const [reason, setReason] = useState("人工核验后调整争点。");
  const issueUnit = workspace.work_units.find((unit) => unit.code === "issue_identification");
  const factsConfirmed = workspace.facts.length > 0 && workspace.facts.every((fact) => fact.status !== "待确认") && workspace.facts.some((fact) => fact.status === "已确认");
  const pending = workspace.issues.filter((issue) => !["人工确认", "分析中", "已完成"].includes(issue.status));
  const runPath = issueUnit ? `/cases/${caseId}/work-units/${issueUnit.id}/run` : "";
  const newDraft = (): Draft => ({ id: 0, title: "", description: "", analysis_hint: "", importance: "中", status: "人工确认", related_fact_ids: [] });

  async function save() {
    if (!editing) return;
    const body = {
      title: editing.title,
      description: editing.description,
      analysis_hint: editing.analysis_hint,
      importance: editing.importance,
      status: editing.status,
      related_fact_ids: editing.related_fact_ids || [],
      reason,
    };
    const ok = editing.id ? await request(`/issues/${editing.id}`, "PATCH", body) : await request(`/cases/${caseId}/issues`, "POST", body);
    if (ok) setEditing(null);
  }

  return (
    <section className="space-y-5">
      <PanelHeading title={step.title} description={step.description} action={<div className="flex flex-wrap gap-2">{issueUnit && <button className="button-secondary" disabled={Boolean(busy) || !factsConfirmed} onClick={() => request(runPath)}><Play size={16} />{workspace.issues.length ? "重新生成争点" : "生成 AI 争点"}</button>}<button className="button-primary" disabled={Boolean(busy) || !pending.length} onClick={() => request(`/cases/${caseId}/issues/confirm-all`, "POST", { reason: "人工复核 AI 争点建议后批量确认，后续按需逐项修订。" })}><Check size={16} />一键确认 AI 争点</button><button className="button-secondary" disabled={Boolean(busy)} onClick={() => setEditing(newDraft())}><Plus size={16} />新增争点</button></div>} />
      {!factsConfirmed && <div className="feedback-state border-[var(--warning)] bg-[var(--warning-bg)] text-[var(--warning)]">请先完成事实确认，再运行争点识别。</div>}
      {!workspace.issues.length ? <EmptyState title="尚未识别争点" description="完成事实确认后，点击“生成 AI 争点”。" /> : (
        <div className="space-y-3">
          {workspace.issues.map((issue) => {
            const facts = relatedFacts(issue, workspace);
            return (
              <article className="workspace-card" key={issue.id}>
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <EntityCode kind="issue" id={issue.id} />
                      <h3 className="font-semibold text-ink">{issue.title}</h3>
                      <StatusBadge status={issue.status} />
                      <span className="status-badge bg-[var(--surface-subtle)] text-slate-600">重要程度：{issue.importance}</span>
                      <VersionChip label="争点" value={`V${issue.issue_version}`} />
                    </div>
                    <p className="mt-3 text-sm leading-7 text-slate-600">{issue.description}</p>
                    {issue.analysis_hint && <p className="mt-2 text-sm text-[var(--court)]">分析提示：{issue.analysis_hint}</p>}
                    <div className="mt-4">
                      <div className="text-xs font-medium text-slate-500">关联事实</div>
                      {facts.length ? (
                        <div className="mt-2 space-y-2">
                          {facts.map((fact) => <div key={fact.id} className="rounded-md border border-line bg-[var(--surface-subtle)] px-3 py-2 text-xs leading-5 text-slate-600"><EntityCode kind="fact" id={fact.id} className="mr-2" />{fact.human_fact || fact.ai_fact}</div>)}
                        </div>
                      ) : <p className="mt-2 text-xs text-slate-400">{issue.related_facts?.join("、") || "未关联事实"}</p>}
                    </div>
                    {issue.source && <div className="mt-3"><SourceTag>来源：{issue.source}</SourceTag></div>}
                  </div>
                  <div className="flex gap-2">
                    {pending.some((item) => item.id === issue.id) && <button className="button-primary" disabled={Boolean(busy)} onClick={() => request(`/issues/${issue.id}/action`, "POST", { action: "确认", reason: "人工确认该争点可进入分析。" })}><Check size={16} />确认</button>}
                    <button className="button-secondary" disabled={Boolean(busy)} onClick={() => setEditing(issue)}>修改</button>
                    <button className="button-secondary" title="删除" disabled={Boolean(busy)} onClick={() => window.confirm(`确认删除争点“${issue.title}”吗？`) && request(`/issues/${issue.id}`, "DELETE", { action: "删除", reason: "人工判断该争点不再适用。" })}><Trash2 size={16} /></button>
                  </div>
                </div>
              </article>
            );
          })}
        </div>
      )}
      {editing && (
        <section className="workspace-card">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">{editing.id > 0 && <EntityCode kind="issue" id={editing.id} />}<h3 className="font-semibold text-ink">{editing.id ? "修改争点" : "新增争点"}</h3></div>
            <button title="关闭" onClick={() => setEditing(null)}><X size={18} /></button>
          </div>
          <div className="mt-4 space-y-3">
            <input className="w-full rounded-md border border-line px-3 py-2 text-sm focus:border-court" value={editing.title} onChange={(event) => setEditing({ ...editing, title: event.target.value })} placeholder="争点标题" />
            <textarea className="min-h-24 w-full rounded-md border border-line px-3 py-2 text-sm focus:border-court" value={editing.description} onChange={(event) => setEditing({ ...editing, description: event.target.value })} placeholder="争点描述" />
            <input className="w-full rounded-md border border-line px-3 py-2 text-sm focus:border-court" value={editing.analysis_hint} onChange={(event) => setEditing({ ...editing, analysis_hint: event.target.value })} placeholder="分析提示" />
            <select className="w-full rounded-md border border-line bg-white px-3 py-2 text-sm focus:border-court" value={editing.importance} onChange={(event) => setEditing({ ...editing, importance: event.target.value })}>{["高", "中", "低"].map((item) => <option key={item}>{item}</option>)}</select>
            <input className="w-full rounded-md border border-line px-3 py-2 text-sm focus:border-court" value={reason} onChange={(event) => setReason(event.target.value)} placeholder="修改原因" />
            <button className="button-primary" disabled={!editing.title.trim()} onClick={() => void save()}><Save size={16} />保存争点</button>
          </div>
        </section>
      )}
    </section>
  );
}
