"use client";

import { useEffect, useState } from "react";
import { BookOpen } from "lucide-react";
import { api, MemoryItem } from "@/lib/api";

export default function MemoryPage() {
  const [items, setItems] = useState<MemoryItem[]>([]);
  useEffect(() => { api<MemoryItem[]>("/memory").then(setItems); }, []);

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-2xl font-semibold text-ink">法律知识库</h1>
        <p className="mt-2 text-sm text-slate-600">从人工修订和案件经验中沉淀出的可复用判断。</p>
      </div>
      <div className="grid gap-4 md:grid-cols-2">
        {items.map((item) => (
          <article key={item.id} className="card p-5">
            <div className="flex items-start gap-3">
              <BookOpen size={19} className="mt-1 text-court" />
              <div>
                <h2 className="font-semibold text-ink">{item.title}</h2>
                <div className="mt-1 text-sm text-court">{item.legal_issue}</div>
              </div>
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
