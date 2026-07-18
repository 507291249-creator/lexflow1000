"use client";

import { useEffect, useState } from "react";
import { BookOpen, Layers3 } from "lucide-react";
import { api, MemoryItem } from "@/lib/api";
import { EmptyReasoningState, EntityCode, ErrorState, LoadingState, PageHeading, ReasoningStatusBadge } from "@/components/ui/ReasoningUI";

export default function MemoryPage() {
  const [items, setItems] = useState<MemoryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  async function load() { setLoading(true); setError(""); try { setItems(await api<MemoryItem[]>("/memory")); } catch { setError("暂时无法读取法律记忆，请稍后重试。"); } finally { setLoading(false); } }
  useEffect(() => { void load(); }, []);

  return (
    <div className="space-y-5">
      <PageHeading eyebrow="知识沉淀" title="法律记忆" description="仅展示经人工批准沉淀的裁判规则、案件经验、论证模式、证据规则与工作流经验。" action={<div className="flex items-center gap-2 text-sm text-slate-500"><Layers3 size={16} />{items.length} 条</div>} />
      {loading && <LoadingState label="正在读取法律记忆" />}
      {error && <ErrorState message={error} onRetry={() => void load()} />}
      {!loading && !error && !items.length && <EmptyReasoningState title="暂无法律记忆" description="被人工批准的分析可以在案件工作台中形成候选记忆，批准沉淀后显示在这里。" />}
      <div className="grid gap-4 md:grid-cols-2">
        {items.map((item) => (
          <article key={item.id} className="reasoning-card p-5">
            <div className="flex items-start gap-3">
              <EntityCode kind="report" id={item.id} />
              <BookOpen size={19} className="mt-1 text-court" />
              <div className="min-w-0 flex-1">
                <h2 className="font-semibold text-ink">{item.title}</h2>
                <div className="mt-1 text-sm text-court">{item.category} · {item.legal_issue}</div>
              </div>
              <ReasoningStatusBadge status="human_confirmed" />
            </div>
            <p className="mt-4 text-sm leading-6 text-slate-600">{item.scenario}</p>
            <div className="mt-3 rounded-md bg-slate-50 p-3 text-sm leading-6 text-slate-700">{item.decision_pattern}</div>
            <div className="mt-4 flex flex-wrap gap-2">
              {item.tags.map((tag) => <span key={tag} className="badge bg-[#e7f1ef] text-mint">{tag}</span>)}
            </div>
          </article>
        ))}
      </div>
    </div>
  );
}
