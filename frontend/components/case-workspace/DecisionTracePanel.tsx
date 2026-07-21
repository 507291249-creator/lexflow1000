"use client";

import { BookOpen } from "lucide-react";
import type { Trace } from "@/lib/api";
import { EmptyState, PanelHeading } from "./shared";

export function DecisionTracePanel({ traces }: { traces: Trace[] }) {
  return (
    <section className="space-y-5">
      <div className="flex items-start gap-3 border-b border-line pb-4">
        <BookOpen size={20} className="mt-0.5 text-court" />
        <div className="flex-1">
          <PanelHeading title="决策记录" description="事实、争点和分析的人工操作均保留 AI 原始版本、人工版本与修改原因，形成可追溯时间线。" />
        </div>
      </div>

      {!traces.length ? (
        <EmptyState title="暂无决策记录" description="完成人工确认或复核后，记录会自动显示在这里。" />
      ) : (
        <ol className="relative space-y-4 border-l border-line pl-6">
          {traces.map((trace) => (
            <li key={trace.id} className="relative">
              <span className="absolute -left-[27px] top-1.5 h-2.5 w-2.5 rounded-full border-2 border-[var(--court)] bg-white" />
              <article className="workspace-card">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-medium text-ink">{trace.action}</span>
                  <span className="badge bg-[var(--surface-subtle)] text-slate-600">{trace.object_type}</span>
                  <span className="text-xs text-slate-500">{new Date(trace.created_at).toLocaleString("zh-CN")}</span>
                  {trace.tags?.length > 0 && trace.tags.map((tag) => <span key={tag} className="badge-compact bg-[var(--ai-100)] text-[var(--ai-600)]">{tag}</span>)}
                </div>
                <p className="mt-2 text-sm leading-6 text-slate-700">原因：{trace.revision_reason || "未填写"}</p>
                {(trace.ai_suggestion || trace.human_revision) && (
                  <details className="mt-2 text-sm text-slate-600">
                    <summary className="cursor-pointer text-slate-500">查看版本差异</summary>
                    <div className="mt-2 grid gap-2 lg:grid-cols-2">
                      <div>
                        <div className="mb-1 text-[11px] font-medium text-[var(--ai-600)]">AI 原文</div>
                        <pre className="trace-diff-ai">{trace.ai_suggestion || "（无 AI 原文记录）"}</pre>
                      </div>
                      <div>
                        <div className="mb-1 text-[11px] font-medium text-[var(--mint)]">人工修订</div>
                        <pre className="trace-diff-human">{trace.human_revision || "（未作人工修订）"}</pre>
                      </div>
                    </div>
                  </details>
                )}
              </article>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}
