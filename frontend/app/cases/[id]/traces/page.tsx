"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { ArrowLeft } from "lucide-react";
import { api, Trace } from "@/lib/api";

export default function TracesPage({ params }: { params: { id: string } }) {
  const caseId = Number(params.id);
  const [traces, setTraces] = useState<Trace[]>([]);
  useEffect(() => { api<Trace[]>(`/cases/${caseId}/traces`).then(setTraces); }, [caseId]);

  return (
    <div className="space-y-5">
      <Link href={`/cases/${caseId}`} className="button-secondary">
        <ArrowLeft size={16} />
        返回案件
      </Link>
      <div>
        <h1 className="text-2xl font-semibold text-ink">决策留痕</h1>
        <p className="mt-2 text-sm text-slate-600">AI 建议、人工修订、修改原因和标签的留痕记录。</p>
      </div>
      <div className="space-y-4">
        {traces.map((trace) => (
          <article key={trace.id} className="card p-5">
            <div className="mb-3 flex flex-wrap gap-2">
              {trace.tags.map((tag) => <span key={tag} className="badge bg-[#e7f1ef] text-mint">{tag}</span>)}
            </div>
            <div className="grid gap-4 md:grid-cols-2">
              <TraceBlock title="AI 建议" text={trace.ai_suggestion} />
              <TraceBlock title="人工修订" text={trace.human_revision} />
            </div>
            <div className="mt-4 rounded-md border border-line bg-slate-50 p-3 text-sm leading-6 text-slate-700">
              <span className="font-medium text-ink">修改原因：</span>{trace.revision_reason}
            </div>
          </article>
        ))}
      </div>
    </div>
  );
}

function TraceBlock({ title, text }: { title: string; text: string }) {
  return (
    <div>
      <div className="mb-2 text-sm font-semibold text-ink">{title}</div>
      <div className="max-h-96 overflow-auto whitespace-pre-wrap rounded-md border border-line p-3 text-sm leading-6 text-slate-600">{text}</div>
    </div>
  );
}
