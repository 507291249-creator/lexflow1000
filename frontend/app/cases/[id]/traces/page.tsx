"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { ArrowLeft } from "lucide-react";
import { api, Trace } from "@/lib/api";
import { DecisionTracePanel } from "@/components/case-workspace/DecisionTracePanel";
import { ErrorState, LoadingState, PageHeading } from "@/components/ui/ReasoningUI";

export default function TracesPage({ params }: { params: { id: string } }) {
  const caseId = Number(params.id);
  const [traces, setTraces] = useState<Trace[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  async function load() { setLoading(true); setError(""); try { setTraces(await api<Trace[]>(`/cases/${caseId}/traces`)); } catch { setError("暂时无法读取案件决策记录。"); } finally { setLoading(false); } }
  useEffect(() => { void load(); }, [caseId]);

  return (
    <div className="space-y-5">
      <Link href={`/cases/${caseId}`} className="button-secondary">
        <ArrowLeft size={16} />
        返回案件
      </Link>
      <PageHeading eyebrow="人工复核" title="决策记录" description="AI 建议、人工修订、修改原因和操作时间构成可追溯时间线。" />
      {loading && <LoadingState label="正在读取决策记录" />}
      {error && <ErrorState message={error} onRetry={() => void load()} />}
      {!loading && !error && <DecisionTracePanel traces={traces} />}
    </div>
  );
}
