"use client";

import { useEffect, useState } from "react";
import { BookOpen } from "lucide-react";
import { api, type ReasoningTraceEntry, type ReasoningTracePage } from "@/lib/api";
import { EmptyState, PanelHeading } from "./shared";

function versionSummary(value: Record<string, number> | null) {
  if (!value) return "";
  const labels: Record<string, string> = { material_version: "材料", fact_version: "事实", issue_version: "争点", analysis_version: "分析", report_version: "报告" };
  return Object.entries(value).map(([key, version]) => `${labels[key] || key} ${version > 0 ? `V${version}` : "未发布"}`).join(" · ");
}

export function DecisionTracePanel({ caseId, refreshKey = "" }: { caseId: number; refreshKey?: string }) {
  const [entries, setEntries] = useState<ReasoningTraceEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    setLoading(true);
    api<ReasoningTracePage>(`/cases/${caseId}/reasoning-trace?page=1&page_size=100`)
      .then((result) => { if (active) { setEntries(result.items); setError(""); } })
      .catch(() => { if (active) setError("暂时无法读取统一推理轨迹。"); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [caseId, refreshKey]);

  return (
    <section className="space-y-5">
      <div className="flex items-start gap-3 border-b border-line pb-4">
        <BookOpen size={20} className="mt-0.5 text-court" />
        <div className="flex-1"><PanelHeading title="推理与决策轨迹" description="统一展示人工决策与正式版本发布事件；旧记录缺失的字段保持为空。" /></div>
      </div>
      {loading ? <p className="text-sm text-slate-500">正在读取推理轨迹...</p> : error ? (
        <div className="feedback-state border-[var(--danger-border)] bg-[var(--danger-bg)] text-[var(--danger)]">{error}</div>
      ) : !entries.length ? <EmptyState title="暂无推理轨迹" description="完成人工确认、复核或正式发布后，记录会自动显示在这里。" /> : (
        <ol className="relative space-y-4 border-l border-line pl-6">
          {entries.map((entry) => <li key={entry.event_id} className="relative">
            <span className="absolute -left-[27px] top-1.5 h-2.5 w-2.5 rounded-full border-2 border-[var(--court)] bg-white" />
            <article className="workspace-card">
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-medium text-ink">{entry.action || entry.event_type}</span>
                <span className="badge bg-[var(--surface-subtle)] text-slate-600">{entry.object_type || "工作流"}</span>
                <span className="badge-compact bg-[var(--ai-100)] text-[var(--ai-600)]">{entry.event_source === "decision_trace" ? "人工决策" : "版本事件"}</span>
                <span className="text-xs text-slate-500">{new Date(entry.created_at).toLocaleString("zh-CN")}</span>
                {entry.tags?.map((tag) => <span key={tag} className="badge-compact bg-[var(--ai-100)] text-[var(--ai-600)]">{tag}</span>)}
              </div>
              {entry.revision_reason && <p className="mt-2 text-sm leading-6 text-slate-700">原因：{entry.revision_reason}</p>}
              {(entry.before_versions || entry.after_versions || entry.input_versions) && <div className="mt-3 grid gap-2 text-xs text-slate-600 lg:grid-cols-3">
                {entry.before_versions && <div className="neutral-surface p-2"><span className="font-medium">发布前</span><div className="mt-1">{versionSummary(entry.before_versions)}</div></div>}
                {entry.after_versions && <div className="human-surface p-2"><span className="font-medium">发布后</span><div className="mt-1">{versionSummary(entry.after_versions)}</div></div>}
                {entry.input_versions && <div className="ai-surface p-2"><span className="font-medium">输入版本</span><div className="mt-1">{versionSummary(entry.input_versions)}</div></div>}
              </div>}
              {(entry.ai_suggestion || entry.human_revision) && <details className="mt-2 text-sm text-slate-600">
                <summary className="cursor-pointer text-slate-500">查看版本差异</summary>
                <div className="mt-2 grid gap-2 lg:grid-cols-2">
                  <div><div className="mb-1 text-[11px] font-medium text-[var(--ai-600)]">AI 原文</div><pre className="trace-diff-ai">{entry.ai_suggestion || "（无 AI 原文记录）"}</pre></div>
                  <div><div className="mb-1 text-[11px] font-medium text-[var(--mint)]">人工修订</div><pre className="trace-diff-human">{entry.human_revision || "（未作人工修订）"}</pre></div>
                </div>
              </details>}
            </article>
          </li>)}
        </ol>
      )}
    </section>
  );
}
