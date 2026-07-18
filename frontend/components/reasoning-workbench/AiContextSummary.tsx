import type { AIOutput, CaseWorkspace } from "@/lib/api";
import { CitationList } from "./CitationList";
import { EntityCode } from "@/components/ui/ReasoningUI";

function numberList(value: unknown) {
  if (!Array.isArray(value)) return [];
  return value.map(Number).filter((item) => Number.isFinite(item));
}

function snapshotFacts(value: unknown) {
  if (!Array.isArray(value)) return [];
  return value.flatMap((item) => {
    if (!item || typeof item !== "object") return [];
    const record = item as Record<string, unknown>;
    const id = Number(record.id);
    const content = String(record.human_fact || record.ai_fact || record.content || "");
    return content ? [{ id: Number.isFinite(id) ? id : 0, content }] : [];
  });
}

export function AiContextSummary({ output, workspace }: { output?: AIOutput; workspace: CaseWorkspace }) {
  if (!output) return <p className="text-sm leading-6 text-slate-500">当前步骤尚未形成可读取的 AI 输入上下文。</p>;
  const snapshot = output.input_snapshot_json || {};
  const factIds = numberList(snapshot.fact_ids);
  const embeddedFacts = snapshotFacts(snapshot.facts);
  const facts = factIds.length
    ? workspace.facts.filter((fact) => factIds.includes(fact.id)).map((fact) => ({ id: fact.id, content: fact.human_fact || fact.ai_fact }))
    : embeddedFacts;
  const documentIds = numberList(snapshot.document_ids);
  const issueId = Number(snapshot.issue_id || 0);
  const issue = workspace.issues.find((item) => item.id === issueId) || workspace.issues.find((item) => item.work_unit_id === output.work_unit_id);

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-2">
        <ContextMetric label="事实版本" value={String(snapshot.fact_version || output.fact_version || workspace.case.fact_version)} />
        <ContextMetric label="争点版本" value={String(snapshot.issue_version || output.issue_version || workspace.case.issue_version)} />
        <ContextMetric label="输出版本" value={`V${output.version}`} />
        <ContextMetric label="执行方式" value={output.execution_mode === "llm" ? "大模型" : output.execution_mode === "fallback" ? "备用模式" : "未标注"} />
      </div>
      {issue && (
        <div>
          <div className="mb-2 text-xs font-semibold text-slate-500">关联争点</div>
          <div className="flex items-start gap-2 rounded-md border border-line px-3 py-2 text-sm text-ink"><EntityCode kind="issue" id={issue.id} /><span>{issue.title}</span></div>
        </div>
      )}
      <div>
        <div className="mb-2 text-xs font-semibold text-slate-500">使用事实</div>
        <CitationList
          items={facts.map((fact) => ({ id: String(fact.id), title: fact.content, meta: fact.id ? `F-${String(fact.id).padStart(2, "0")}` : "输入快照" }))}
          emptyText="输入快照未记录具体事实编号。"
        />
      </div>
      <div>
        <div className="mb-2 text-xs font-semibold text-slate-500">依据材料</div>
        <CitationList
          items={workspace.documents.filter((document) => documentIds.includes(document.id)).map((document) => ({ id: String(document.id), title: document.original_filename || document.filename }))}
          emptyText="输入快照未记录材料编号。"
        />
      </div>
      <p className="flex items-center gap-2 text-xs leading-5 text-slate-500">关联分析：<EntityCode kind="analysis" id={output.id} /> <span>{output.title}</span></p>
    </div>
  );
}

function ContextMetric({ label, value }: { label: string; value: string }) {
  return <div className="rounded-md border border-line px-3 py-2"><div className="text-[11px] text-slate-500">{label}</div><div className="mt-1 text-sm font-semibold text-ink">{value}</div></div>;
}
