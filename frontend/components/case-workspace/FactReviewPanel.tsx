"use client";

import { useState } from "react";
import { Check, Play, Save, X } from "lucide-react";
import type { AIOutput, CaseFact, CaseWorkspace, WorkUnit } from "@/lib/api";
import { getWorkflowStepConfig } from "@/lib/workflow-config";
import { EntityCode } from "@/components/ui/ReasoningUI";
import { EmptyState, PanelHeading, StatusBadge } from "./shared";
import { SourceTag, VersionChip, WorkspaceCard } from "./primitives";

type Request = (path: string, method?: string, body?: unknown) => Promise<boolean>;

function hasHumanRevision(fact: CaseFact) {
  return Boolean(fact.human_fact?.trim()) && fact.human_fact !== fact.ai_fact;
}

function FactCard({ fact, busy, onReview, onEdit }: { fact: CaseFact; busy: boolean; onReview: (fact: CaseFact, action: string, humanFact?: string, reason?: string) => void; onEdit: (fact: CaseFact) => void }) {
  const revised = hasHumanRevision(fact);
  return (
    <article className="workspace-card">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex flex-wrap items-center gap-2">
          <EntityCode kind="fact" id={fact.id} />
          <span className="text-xs font-medium text-slate-500">{fact.category || "关键事实"}</span>
        </div>
        <StatusBadge status={fact.status} />
      </div>
      {revised ? (
        <div className="mt-3 space-y-2">
          <div>
            <div className="text-[11px] font-medium text-[var(--ai-600)]">AI 原文</div>
            <p className="ai-surface mt-1 text-sm leading-7 text-slate-700">{fact.ai_fact}</p>
          </div>
          <div>
            <div className="text-[11px] font-medium text-[var(--mint)]">人工修订</div>
            <p className="human-surface mt-1 text-sm leading-7 text-slate-700">{fact.human_fact}</p>
          </div>
        </div>
      ) : (
        <p className="mt-3 text-sm leading-7 text-slate-700">{fact.human_fact || fact.ai_fact}</p>
      )}
      <div className="mt-3 flex flex-wrap items-center gap-2 text-xs leading-5 text-slate-500">
        <SourceTag>来源：{fact.source_document || "案件输入"}</SourceTag>
        <span>置信度：{fact.confidence || "未标注"}</span>
        <VersionChip label="事实" value={`V${fact.fact_version}`} />
      </div>
      {fact.status === "待确认" && (
        <div className="mt-4 flex flex-wrap gap-2">
          <button className="button-primary" disabled={busy} onClick={() => onReview(fact, "接受", fact.ai_fact, "人工核验后接受 AI 提取事实。")}><Check size={15} />确认</button>
          <button className="button-secondary" disabled={busy} onClick={() => onEdit(fact)}>修改</button>
          <button className="button-secondary" disabled={busy} onClick={() => onReview(fact, "驳回", "", "现有材料不足以支持该事实。")}>驳回</button>
        </div>
      )}
    </article>
  );
}

export function FactReviewPanel({ caseId, workspace, busy, request }: { caseId: number; workspace: CaseWorkspace; busy: string; request: Request }) {
  const step = getWorkflowStepConfig("fact_review");
  const [editing, setEditing] = useState<CaseFact | null>(null);
  const [revision, setRevision] = useState("");
  const [reason, setReason] = useState("根据原始材料修订事实表述。");
  const factUnit = workspace.work_units.find((unit) => unit.code === "fact_extraction") as WorkUnit | undefined;
  const latestOutput = workspace.ai_outputs.filter((output) => output.output_type === "fact_extraction").sort((a, b) => b.version - a.version)[0] as AIOutput | undefined;
  const pending = workspace.facts.filter((fact) => fact.status === "待确认");
  const confirmed = workspace.facts.filter((fact) => fact.status === "已确认");
  const rejected = workspace.facts.filter((fact) => fact.status === "已驳回");

  const review = (fact: CaseFact, action: string, human_fact = "", revision_reason = "人工核验案件材料后作出判断。") => request(`/facts/${fact.id}/review`, "POST", { action, human_fact, reason: revision_reason });
  const openEdit = (fact: CaseFact) => { setEditing(fact); setRevision(fact.human_fact || fact.ai_fact); setReason("根据原始材料修订事实表述。"); };

  const orderedFacts = [...pending, ...confirmed, ...rejected];
  return (
    <section className="space-y-5">
      <PanelHeading title={step.title} description={step.description} action={<div className="flex flex-wrap gap-2">{factUnit && <button className="button-secondary" disabled={Boolean(busy)} onClick={() => request(`/cases/${caseId}/work-units/${factUnit.id}/run`)}><Play size={16} />{factUnit.status === "失败" ? "重新运行" : "运行事实提取"}</button>}<button className="button-primary" disabled={Boolean(busy) || !pending.length} onClick={() => request(`/cases/${caseId}/facts/confirm-all`, "POST", { reason: "人工复核 AI 提取事实后批量确认，后续按需逐项修订。" })}><Check size={16} />一键确认 AI 事实</button></div>} />
      <div className="flex flex-wrap gap-2 text-sm"><span className="status-badge status-pending">待人工确认 {pending.length}</span><span className="status-badge status-confirmed">已人工确认 {confirmed.length}</span><span className="status-badge status-expired">已驳回 {rejected.length}</span></div>
      {latestOutput && (
        <details className="workspace-card">
          <summary className="cursor-pointer text-sm font-medium text-ink">查看 AI 事实提取摘要 · 版本 {latestOutput.version}</summary>
          <pre className="ai-surface mt-3 max-h-72 overflow-auto whitespace-pre-wrap text-sm leading-6 text-slate-700">{latestOutput.reviewed_content || latestOutput.content}</pre>
        </details>
      )}
      {!workspace.facts.length ? <EmptyState title="尚未生成事实" description="点击“运行事实提取”，系统将继续使用当前后端 AI 流程生成结构化事实。" /> : <div className="space-y-3">{orderedFacts.map((fact) => <FactCard key={fact.id} fact={fact} busy={Boolean(busy)} onReview={review} onEdit={openEdit} />)}</div>}
      {editing && (
        <section className="workspace-card">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2"><EntityCode kind="fact" id={editing.id} /><h3 className="font-semibold text-ink">修改事实</h3></div>
            <button title="关闭" onClick={() => setEditing(null)}><X size={18} /></button>
          </div>
          <textarea className="mt-4 min-h-28 w-full rounded-md border border-line px-3 py-2 text-sm leading-6 focus:border-court" value={revision} onChange={(event) => setRevision(event.target.value)} />
          <input className="mt-3 w-full rounded-md border border-line px-3 py-2 text-sm focus:border-court" value={reason} onChange={(event) => setReason(event.target.value)} placeholder="填写修改原因" />
          <button className="button-primary mt-3" onClick={() => void review(editing, "修改", revision, reason).then((ok) => ok && setEditing(null))}><Save size={16} />保存人工版本</button>
        </section>
      )}
    </section>
  );
}
