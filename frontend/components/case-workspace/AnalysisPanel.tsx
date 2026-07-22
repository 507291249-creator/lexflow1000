"use client";

import { useEffect, useMemo, useState } from "react";
import { Check, History, Play, RefreshCw, Sparkles } from "lucide-react";
import { operationId, type AIOutput, type CaseWorkspace, type MemoryItem, type WorkUnit } from "@/lib/api";
import { getWorkflowStepConfig } from "@/lib/workflow-config";
import { EntityCode } from "@/components/ui/ReasoningUI";
import { EmptyState, formatUnknown, PanelHeading, StatusBadge } from "./shared";

type Request = (path: string, method?: string, body?: unknown) => Promise<boolean>;

function StructuredAnalysis({ output }: { output: AIOutput }) {
  const structured = ((output.meta_json as { structured?: Record<string, unknown> })?.structured || {}) as Record<string, unknown>;
  const fields: Array<[string, unknown]> = [
    ["核心结论", structured.core_conclusion],
    ["风险等级", structured.risk_level],
    ["主要理由", structured.main_reasons],
    ["适用法律 / 支持依据", structured.applicable_laws || structured.supporting_basis],
    ["反方观点", structured.counter_arguments],
    ["不确定事项", structured.uncertainties],
    ["证据需求", structured.evidence_needs || structured.next_evidence],
    ["下一步行动", structured.next_actions],
    ["AI 置信度", structured.confidence],
  ];
  return (
    <div className="grid gap-3 lg:grid-cols-2">
      {fields.map(([label, value], index) => (
        <section
          key={label}
          className={`rounded-md border p-4 ${index === 0 ? "border-[var(--court-border)] bg-[var(--court-subtle)] lg:col-span-2" : "border-line bg-white"}`}
        >
          <div className="text-xs font-semibold text-slate-500">{label}</div>
          <div className="mt-2 whitespace-pre-wrap text-sm leading-7 text-slate-700">{formatUnknown(value)}</div>
        </section>
      ))}
    </div>
  );
}

function AnalysisVersionHistory({ outputs }: { outputs: AIOutput[] }) {
  const [open, setOpen] = useState(false);
  const [activeId, setActiveId] = useState<number | null>(null);
  if (outputs.length <= 1) return null;
  const active = outputs.find((item) => item.id === activeId) || outputs[0];
  return (
    <div className="mt-4 rounded-md border border-line bg-[var(--surface-subtle)]">
      <button type="button" className="flex w-full items-center justify-between gap-2 px-3 py-2 text-left" onClick={() => setOpen((value) => !value)}>
        <span className="flex items-center gap-2 text-xs font-medium text-slate-600">
          <History size={14} className="text-slate-400" />
          分析生成历史
        </span>
        <span className="text-[11px] text-slate-500">{outputs.length} 次生成 · 最新 G{outputs[0].version}</span>
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
                <span className="text-slate-400">生成 G</span>
                <span className="font-semibold">{item.version}</span>
                {item.fact_version !== undefined && <span className="ml-1 text-[10px] text-slate-400">F{item.fact_version}</span>}
              </button>
            ))}
          </div>
          <pre className="ai-surface mt-3 max-h-56 overflow-auto whitespace-pre-wrap text-xs leading-6 text-slate-700">{active.reviewed_content || active.content}</pre>
          <p className="mt-2 text-[11px] text-slate-500">
            生成于 {new Date(active.created_at).toLocaleString("zh-CN")} · {active.review_status || "未复核"} · {active.execution_mode === "llm" ? "大模型" : active.execution_mode === "fallback" ? "备用模式" : "未标注"}
          </p>
        </div>
      )}
    </div>
  );
}

function AnalysisReview({ output, busy, request }: { output: AIOutput; busy: string; request: Request }) {
  const [revision, setRevision] = useState(output.reviewed_content || output.content);
  const [reason, setReason] = useState("人工复核后确认本版本分析结论。");
  const [supplement, setSupplement] = useState("");
  useEffect(() => setRevision(output.reviewed_content || output.content), [output.id, output.reviewed_content, output.content]);
  const reviewPath = `/ai-outputs/${output.id}/review`;
  const submit = (action: string, human_revision = "", supplementary_material = "") => request(reviewPath, "POST", { action, human_revision, reason, supplementary_material });

  return (
    <div className="mt-5 border-t border-line pt-5">
      <h4 className="font-medium text-ink">人工复核</h4>
      <textarea className="mt-3 min-h-40 w-full rounded-md border border-line px-3 py-3 text-sm leading-6 focus:border-court" value={revision} onChange={(event) => setRevision(event.target.value)} />
      <input className="mt-3 w-full rounded-md border border-line px-3 py-2 text-sm focus:border-court" value={reason} onChange={(event) => setReason(event.target.value)} placeholder="复核或修改原因" />
      <div className="mt-3 flex flex-wrap gap-2">
        <button className="button-primary" disabled={Boolean(busy)} onClick={() => submit("接受", output.content)}><Check size={16} />接受</button>
        <button className="button-secondary" disabled={Boolean(busy)} onClick={() => submit("修改", revision)}>保存修改</button>
        <button className="button-secondary" disabled={Boolean(busy)} onClick={() => submit("驳回")}>驳回</button>
      </div>
      <textarea className="mt-4 min-h-20 w-full rounded-md border border-line px-3 py-2 text-sm focus:border-court" value={supplement} onChange={(event) => setSupplement(event.target.value)} placeholder="补充材料后重新分析（可填写新增证据或事实）" />
      <button className="button-secondary mt-2" disabled={Boolean(busy) || !supplement.trim()} onClick={() => submit("补充材料后重新分析", "", supplement)}>
        <RefreshCw size={16} />补充后重新分析
      </button>
    </div>
  );
}

function AiAnalysisUnits({ caseId, workspace, busy, request }: { caseId: number; workspace: CaseWorkspace; busy: string; request: Request }) {
  const issueIds = new Set(workspace.issues.map((issue) => issue.id));
  const units = workspace.work_units.filter((unit) => unit.code.startsWith("legal_analysis:") && issueIds.has(unit.parent_issue_id || -1));

  const outputsByUnit = useMemo(() => {
    const map = new Map<number, AIOutput[]>();
    units.forEach((unit) => {
      const all = workspace.ai_outputs
        .filter((output) => output.work_unit_id === unit.id && output.output_type === "legal_analysis")
        .sort((a, b) => b.version - a.version);
      map.set(unit.id, all);
    });
    return map;
  }, [units, workspace.ai_outputs]);

  const currentByUnit = useMemo(() => {
    const map = new Map<number, AIOutput | undefined>();
    units.forEach((unit) => {
      const all = outputsByUnit.get(unit.id) || [];
      map.set(unit.id, all.find((output) => output.fact_version === workspace.case.fact_version && output.issue_version === workspace.case.issue_version));
    });
    return map;
  }, [units, outputsByUnit, workspace.case.fact_version, workspace.case.issue_version]);

  const pending = units.filter((unit) => currentByUnit.get(unit.id)?.review_status === "待复核");
  const publishableIds = units
    .map((unit) => currentByUnit.get(unit.id))
    .filter((output): output is AIOutput => Boolean(output) && ["已接受", "已修改"].includes(output!.review_status))
    .map((output) => output.id);

  return (
    <div className="space-y-4">
      {pending.length > 0 && (
        <div className="flex justify-end">
          <button
            className="button-primary"
            disabled={Boolean(busy)}
            onClick={() => request(`/cases/${caseId}/analyses/confirm-all`, "POST", { reason: "人工复核当前版本法律分析后批量接受，后续按需逐项修订。" })}
          >
            <Check size={16} />一键接受全部分析
          </button>
        </div>
      )}
      {publishableIds.length > 0 && pending.length === 0 && (
        <div className="flex flex-wrap items-center justify-end gap-2">
          <span className="version-chip version-chip-court"><span className="text-slate-400">正式分析</span><span className="font-semibold">{workspace.case.analysis_version > 0 ? `V${workspace.case.analysis_version}` : "未发布"}</span></span>
          <button
            className="button-primary"
            disabled={Boolean(busy) || workspace.case.fact_version <= 0 || workspace.case.issue_version <= 0}
            onClick={() => request(`/cases/${caseId}/analyses/publish`, "POST", {
              analysis_ids: publishableIds,
              operation_id: operationId(`analyses-${caseId}`),
              reason: "人工复核当前法律分析集合后正式发布。",
            })}
          >
            <Check size={16} />正式发布分析
          </button>
        </div>
      )}

      {!units.length ? (
        <EmptyState title="尚未创建分析任务" description="确认争点后，系统会按争点数量动态创建法律分析工作单元。" />
      ) : (
        units.map((unit) => {
          const output = currentByUnit.get(unit.id);
          const lineage = outputsByUnit.get(unit.id) || [];
          return (
            <article className="workspace-card" key={unit.id}>
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <EntityCode kind="analysis" id={output?.id || unit.id} />
                    <h3 className="font-semibold text-ink">{unit.title}</h3>
                    <StatusBadge status={output?.review_status || unit.status} />
                  </div>
                  <p className="mt-2 text-sm text-slate-600">{unit.description}</p>
                  <p className="mt-2 flex flex-wrap items-center gap-2 text-xs text-slate-500">
                    <span className="version-chip"><span className="text-slate-400">事实</span><span className="font-semibold">V{workspace.case.fact_version}</span></span>
                    <span className="version-chip"><span className="text-slate-400">争点</span><span className="font-semibold">V{workspace.case.issue_version}</span></span>
                    {output && (
                      <>
                        <span className="version-chip"><span className="text-slate-400">生成</span><span className="font-semibold">G{output.version}</span></span>
                        <span className="version-chip"><span className="text-slate-400">正式分析</span><span className="font-semibold">{output.analysis_version > 0 ? `V${output.analysis_version}` : "未发布"}</span></span>
                        <span className={`status-badge ${output.execution_mode === "llm" ? "bg-[var(--ai-100)] text-[var(--ai-600)]" : "bg-[var(--inactive-subtle)] text-[var(--inactive)]"}`}>
                          {output.execution_mode === "llm" ? "大模型" : "备用模式"}
                        </span>
                      </>
                    )}
                  </p>
                </div>
                <button className="button-secondary" disabled={Boolean(busy)} onClick={() => request(`/cases/${caseId}/work-units/${unit.id}/run`)}>
                  <Play size={16} />{output ? "重新分析" : "运行分析"}
                </button>
              </div>

              {output ? (
                <>
                  <div className="mt-5"><StructuredAnalysis output={output} /></div>
                  <div className="mt-4 rounded-md border border-line bg-[var(--surface-subtle)] px-3 py-2 text-xs leading-5 text-slate-500">
                    依据事实、材料和输入版本已整理在右侧“AI 上下文”，法规与类案引用仅在真实检索接入后显示。
                  </div>
                  <AnalysisVersionHistory outputs={lineage} />
                  <AnalysisReview output={output} busy={busy} request={request} />
                </>
              ) : (
                <div className="mt-5">
                  {lineage.length > 0 ? (
                    <>
                      <EmptyState title="当前版本尚未运行" description="已存在历史版本，可在版本谱系中查看；运行后将生成当前事实/争点版本的分析。" />
                      <AnalysisVersionHistory outputs={lineage} />
                    </>
                  ) : (
                    <EmptyState title="等待运行" description="运行后将在此显示结构化法律分析和人工复核区。" />
                  )}
                </div>
              )}
            </article>
          );
        })
      )}
    </div>
  );
}

function LegacyUnit({ unit, candidate, busy, request }: { unit: WorkUnit; candidate?: MemoryItem; busy: string; request: Request }) {
  const [reason, setReason] = useState("已完成材料与逻辑核验，可进入下一工作环节。");
  const [memoryEdit, setMemoryEdit] = useState(candidate);

  return (
    <article className="card p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <h3 className="font-semibold text-ink">{unit.sequence}. {unit.title}</h3>
            <StatusBadge status={unit.status} />
          </div>
          <p className="mt-2 text-sm leading-6 text-slate-600">{unit.description}</p>
        </div>
        <button className="button-secondary" disabled={Boolean(busy)} onClick={() => request(`/cases/${unit.case_id}/work-units/${unit.id}/run`)}>
          <Play size={16} />运行
        </button>
      </div>

      {Object.keys(unit.output_json || {}).length > 0 && (
        <pre className="mt-4 max-h-72 overflow-auto whitespace-pre-wrap rounded-md border border-line bg-[var(--surface-subtle)] p-4 text-xs leading-5 text-slate-700">{JSON.stringify(unit.output_json, null, 2)}</pre>
      )}

      {unit.status === "待人工复核" && (
        <div className="mt-4">
          <input className="w-full rounded-md border border-line px-3 py-2 text-sm focus:border-court" value={reason} onChange={(event) => setReason(event.target.value)} />
          <div className="mt-2 flex gap-2">
            <button className="button-primary" onClick={() => request(`/cases/${unit.case_id}/work-units/${unit.id}/review`, "POST", { action: "批准", reason, reviewer: "承办律师" })}>批准</button>
            <button className="button-secondary" onClick={() => request(`/cases/${unit.case_id}/work-units/${unit.id}/review`, "POST", { action: "退回修改", reason, reviewer: "承办律师" })}>退回修改</button>
          </div>
        </div>
      )}

      {unit.status === "已批准" && !candidate && (
        <button className="button-secondary mt-4" onClick={() => request(`/work-units/${unit.id}/memory-candidate`)}>
          <Sparkles size={16} />生成候选知识
        </button>
      )}

      {candidate && (
        <div className="mt-4 rounded-md border border-[var(--ai-border)] bg-[var(--ai-100)] p-4">
          <div className="flex items-center gap-2">
            <h4 className="font-medium text-ink">候选法律记忆</h4>
            <StatusBadge status={candidate.status} />
          </div>
          <p className="mt-2 text-sm text-slate-600">{candidate.title}</p>
          {candidate.status === "候选" && (
            <div className="mt-3 flex flex-wrap gap-2">
              <button className="button-primary" onClick={() => request(`/memory/${candidate.id}/decision`, "POST", { action: "批准沉淀", reason: "人工核验后确认具有复用价值。", title: candidate.title, rule_summary: candidate.rule_summary, decision_pattern: candidate.decision_pattern, category: candidate.category })}>批准沉淀</button>
              <button className="button-secondary" onClick={() => setMemoryEdit(candidate)}>修改后沉淀</button>
              <button className="button-secondary" onClick={() => request(`/memory/${candidate.id}/decision`, "POST", { action: "忽略", reason: "当前经验不具备稳定复用价值。", title: candidate.title, rule_summary: candidate.rule_summary, decision_pattern: candidate.decision_pattern, category: candidate.category })}>忽略</button>
            </div>
          )}
          {memoryEdit?.id === candidate.id && (
            <div className="mt-3 space-y-2">
              <input className="w-full rounded-md border border-line px-3 py-2 text-sm focus:border-court" value={memoryEdit.title} onChange={(event) => setMemoryEdit({ ...memoryEdit, title: event.target.value })} />
              <textarea className="min-h-20 w-full rounded-md border border-line px-3 py-2 text-sm focus:border-court" value={memoryEdit.rule_summary} onChange={(event) => setMemoryEdit({ ...memoryEdit, rule_summary: event.target.value })} />
              <button className="button-primary" onClick={() => request(`/memory/${candidate.id}/decision`, "POST", { action: "修改后沉淀", reason: "人工修改后确认沉淀。", title: memoryEdit.title, rule_summary: memoryEdit.rule_summary, decision_pattern: memoryEdit.decision_pattern, category: memoryEdit.category })}>保存并沉淀</button>
            </div>
          )}
        </div>
      )}
    </article>
  );
}

export function AnalysisPanel({ caseId, workspace, busy, request }: { caseId: number; workspace: CaseWorkspace; busy: string; request: Request }) {
  const step = getWorkflowStepConfig("legal_analysis");
  return (
    <section className="space-y-5">
      <PanelHeading title={step.title} description={step.description} />
      {workspace.case.workflow_mode === "ai_case" ? (
        <AiAnalysisUnits caseId={caseId} workspace={workspace} busy={busy} request={request} />
      ) : (
        <div className="space-y-4">
          {workspace.work_units.map((unit) => (
            <LegacyUnit key={unit.id} unit={unit} candidate={workspace.memory_candidates.find((item) => item.source_work_unit_id === unit.id)} busy={busy} request={request} />
          ))}
        </div>
      )}
    </section>
  );
}
