"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { ArrowRight, Clock3, Search, Sparkles } from "lucide-react";
import { api, type CaseItem, type CaseWorkspace } from "@/lib/api";
import { WORKFLOW_STEPS, getWorkflowStepState } from "@/lib/workflow-config";
import { EntityCode, ErrorState, LoadingState, PageHeading, ReasoningStatusBadge } from "@/components/ui/ReasoningUI";

type CaseSnapshot = {
  stage: string;
  status: "ai_generated" | "pending_review" | "human_confirmed" | "rerun_required" | "failed";
  pending: number;
  latestAction: string;
};

function summarizeWorkspace(workspace: CaseWorkspace): CaseSnapshot {
  const states = WORKFLOW_STEPS.map((step) => ({ step, state: getWorkflowStepState(workspace, step.code) }));
  const current = states.find(({ state }) => !["human_confirmed"].includes(state)) || states[states.length - 1];
  const pendingFacts = workspace.facts.filter((item) => item.status === "待确认").length;
  const pendingIssues = workspace.issues.filter((item) => !["人工确认", "分析中", "已完成"].includes(item.status)).length;
  const pendingAnalysis = workspace.ai_outputs.filter((item) => item.output_type === "legal_analysis" && !["已接受", "已修改"].includes(item.review_status)).length;
  const latest = [...workspace.ai_outputs].sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())[0];
  const mapped = current.state === "failed" ? "failed" : current.state === "rerun_required" ? "rerun_required" : current.state === "pending_review" ? "pending_review" : current.state === "human_confirmed" ? "human_confirmed" : "ai_generated";
  return { stage: current.step.title, status: mapped, pending: pendingFacts + pendingIssues + pendingAnalysis, latestAction: latest ? `${latest.title} · V${latest.version}` : "尚未生成 AI 输出" };
}

export default function CasesPage() {
  const [cases, setCases] = useState<CaseItem[]>([]);
  const [snapshots, setSnapshots] = useState<Record<number, CaseSnapshot>>({});
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  async function load() {
    setLoading(true);
    setError("");
    try {
      const caseItems = await api<CaseItem[]>("/cases");
      setCases(caseItems);
      const settled = await Promise.allSettled(caseItems.map((item) => api<CaseWorkspace>(`/cases/${item.id}/workspace`)));
      const next: Record<number, CaseSnapshot> = {};
      settled.forEach((result, index) => { if (result.status === "fulfilled") next[caseItems[index].id] = summarizeWorkspace(result.value); });
      setSnapshots(next);
    } catch {
      setError("暂时无法读取案件分析工作区，请等待后端服务唤醒后重试。");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { void load(); }, []);
  const filtered = useMemo(() => cases.filter((item) => `${item.title} ${item.case_type} ${item.summary}`.toLowerCase().includes(query.toLowerCase())), [cases, query]);

  return (
    <div className="mx-auto max-w-7xl space-y-6">
      <PageHeading eyebrow="案件分析" title="推理工作区" description="按当前推理阶段、待复核对象和最近 AI 动作继续案件，不在主界面堆叠案件管理字段。" action={<Link href="/cases/new" className="button-primary"><Sparkles size={16} />开始法律分析</Link>} />
      <div className="flex items-center gap-3 rounded-md border border-line bg-white px-3 py-2">
        <Search size={17} className="text-slate-400" />
        <input className="w-full border-0 bg-transparent text-sm shadow-none focus:shadow-none" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="搜索案件名称、类型或摘要" />
        <span className="shrink-0 text-xs text-slate-400">{filtered.length} 个工作区</span>
      </div>
      {loading && <LoadingState label="正在读取案件推理进度" />}
      {error && <ErrorState message={error} onRetry={() => void load()} />}
      {!loading && !error && !filtered.length && <div className="empty-state"><div><div className="font-medium text-ink">没有匹配的案件</div><p>创建一个新的法律分析，或调整搜索条件。</p></div></div>}
      <section className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        {filtered.map((item) => {
          const snapshot = snapshots[item.id];
          return (
            <Link href={`/cases/${item.id}`} key={item.id} className="group card-compact flex min-h-56 flex-col justify-between px-4 transition hover:border-[var(--court)]">
              <div className="flex items-start justify-between gap-2">
                <EntityCode kind="case" id={item.id} />
                <ReasoningStatusBadge status={snapshot?.status || "ai_generated"} label={snapshot ? undefined : "读取中"} />
              </div>
              <h2 className="mt-3 text-sm font-semibold leading-6 text-ink truncate">{item.title}</h2>
              <p className="mt-1 line-clamp-2 text-xs leading-5 text-slate-600">{item.summary || item.raw_facts || "尚未形成案件摘要。"}</p>
              <div className="mt-3 grid grid-cols-3 gap-2 border-y border-line py-2 text-center">
                <Metric label="阶段" value={snapshot?.stage || "读取中"} />
                <Metric label="待处理" value={String(snapshot?.pending ?? "-")} />
                <Metric label="版本" value={`F${item.fact_version} / I${item.issue_version}`} />
              </div>
              <div className="mt-auto flex items-end justify-between gap-2 pt-3">
                <div className="min-w-0"><div className="flex items-center gap-1 text-[11px] text-slate-400"><Clock3 size={12} />最近 AI 动作</div><div className="mt-0.5 truncate text-xs text-slate-600">{snapshot?.latestAction || "正在读取"}</div></div>
                <ArrowRight size={14} className="shrink-0 text-slate-400 transition group-hover:translate-x-0.5 group-hover:text-court" />
              </div>
            </Link>
          );
        })}
      </section>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return <div className="min-w-0"><div className="text-[11px] text-slate-400">{label}</div><div className="mt-0.5 truncate text-xs font-semibold text-ink">{value}</div></div>;
}
