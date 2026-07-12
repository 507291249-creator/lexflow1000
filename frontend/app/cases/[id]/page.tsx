"use client";

import Link from "next/link";
import { ChangeEvent, FormEvent, useEffect, useMemo, useState } from "react";
import { BookPlus, FileUp, Play, RefreshCw, Save, Wand2 } from "lucide-react";
import { CaseManagementPanel } from "@/components/CaseManagementPanel";
import { WorkflowStepper } from "@/components/WorkflowStepper";
import { api, AIOutput, CaseItem, DocumentItem, Evidence, MemoryItem, Trace, WorkflowEvent } from "@/lib/api";

type CaseDetail = CaseItem & {
  documents: DocumentItem[];
  evidences: Evidence[];
  ai_outputs: AIOutput[];
};

export default function CaseDetailPage({ params }: { params: { id: string } }) {
  const caseId = Number(params.id);
  const [detail, setDetail] = useState<CaseDetail | null>(null);
  const [events, setEvents] = useState<WorkflowEvent[]>([]);
  const [traces, setTraces] = useState<Trace[]>([]);
  const [recommendations, setRecommendations] = useState<MemoryItem[]>([]);
  const [draftText, setDraftText] = useState("");
  const [reason, setReason] = useState("补强事实顺序、证据引用和仲裁请求表述。");
  const [busy, setBusy] = useState(false);

  const load = async () => {
    const [caseData, eventData, traceData, memoryData] = await Promise.all([
      api<CaseDetail>(`/cases/${caseId}`),
      api<WorkflowEvent[]>(`/cases/${caseId}/workflow/events`),
      api<Trace[]>(`/cases/${caseId}/traces`),
      api<MemoryItem[]>(`/cases/${caseId}/memory-recommendations`)
    ]);
    setDetail(caseData);
    setEvents(eventData);
    setTraces(traceData);
    setRecommendations(memoryData);
    const draft = caseData.ai_outputs.find((item) => item.output_type === "draft");
    if (draft && !draftText) setDraftText(draft.content);
  };

  useEffect(() => { load(); }, [caseId]);

  const outputs = useMemo(() => {
    const items = detail?.ai_outputs || [];
    return {
      analysis: items.find((item) => item.output_type === "analysis"),
      draft: items.find((item) => item.output_type === "draft"),
      risk: items.find((item) => item.output_type === "risk")
    };
  }, [detail]);

  async function run(path: string) {
    setBusy(true);
    try {
      await api(path, { method: "POST" });
      await load();
    } finally {
      setBusy(false);
    }
  }

  async function upload(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    const form = new FormData();
    form.append("file", file);
    await api(`/cases/${caseId}/documents/upload`, { method: "POST", body: form });
    await load();
  }

  async function submitTrace(event: FormEvent) {
    event.preventDefault();
    const source = outputs.draft;
    if (!source || !draftText.trim()) return;
    const trace = await api<Trace>(`/cases/${caseId}/traces`, {
      method: "POST",
      body: JSON.stringify({
        ai_output_id: source.id,
        ai_suggestion: source.content,
        human_revision: draftText,
        revision_reason: reason,
        tags: ["文书修订", "劳动仲裁", "证据策略"]
      })
    });
    await api(`/memory/from-trace/${trace.id}`, { method: "POST" });
    await load();
  }

  if (!detail) return <div className="card p-6 text-sm text-slate-500">正在打开案件工作台...</div>;

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-ink">{detail.title}</h1>
          <p className="mt-2 text-sm text-slate-600">{detail.claimant} 诉 {detail.employer} · {detail.claim_amount || "金额待定"}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button className="button-primary" disabled={busy} onClick={() => run(`/cases/${caseId}/workflow/run-demo`)}>
            <Play size={16} />
            一键运行完整流程
          </button>
          <Link className="button-secondary" href={`/cases/${caseId}/traces`}>决策留痕</Link>
        </div>
      </div>

      <CaseManagementPanel caseItem={detail} onUpdated={load} />

      <WorkflowStepper status={detail.status} hasDocuments={detail.documents.length > 0} hasTrace={traces.length > 0} />

      <div className="grid gap-5 lg:grid-cols-[1.45fr_0.8fr]">
        <div className="space-y-5">
          <section className="card p-5">
            <div className="mb-4 flex items-center justify-between gap-3">
              <h2 className="font-semibold text-ink">材料与解析</h2>
              <label className="button-secondary cursor-pointer">
                <FileUp size={16} />
                上传材料
                <input className="hidden" type="file" accept=".txt,.pdf,.docx" onChange={upload} />
              </label>
            </div>
            <div className="grid gap-3 md:grid-cols-2">
              {detail.documents.map((doc) => (
                <div key={doc.id} className="rounded-md border border-line p-3">
                  <div className="font-medium text-ink">{doc.filename}</div>
                  <div className="mt-1 text-xs text-slate-500">{doc.file_type} · {String((doc.parsed_json.keywords as string[] | undefined)?.join("、") || "已解析")}</div>
                  <p className="mt-3 line-clamp-3 text-sm leading-6 text-slate-600">{doc.raw_text}</p>
                </div>
              ))}
            </div>
          </section>

          <section className="card p-5">
            <PanelHeader title="证据表" action="生成证据" onClick={() => run(`/cases/${caseId}/workflow/run-evidence`)} />
            <div className="mt-4 overflow-hidden rounded-md border border-line">
              <table className="w-full text-left text-sm">
                <thead className="bg-slate-50 text-xs text-slate-500">
                  <tr>
                    <th className="px-3 py-2">证据</th>
                    <th className="px-3 py-2">类别</th>
                    <th className="px-3 py-2">证明事实</th>
                    <th className="px-3 py-2">强度</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-line">
                  {detail.evidences.map((item) => (
                    <tr key={item.id}>
                      <td className="px-3 py-3 font-medium text-ink">{item.name}</td>
                      <td className="px-3 py-3 text-slate-600">{item.category}</td>
                      <td className="px-3 py-3 text-slate-600">{item.fact_to_prove}</td>
                      <td className="px-3 py-3"><span className="badge bg-slate-100 text-slate-700">{evidenceStrengthLabel(item.strength)}</span></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          <OutputPanel title="法律分析结果" button="生成分析" output={outputs.analysis} onClick={() => run(`/cases/${caseId}/workflow/run-analysis`)} />
          <OutputPanel title="风险提示" button="生成风险" output={outputs.risk} onClick={() => run(`/cases/${caseId}/workflow/run-risk`)} />

          <section className="card p-5">
            <PanelHeader title="文书初稿编辑区" action="生成初稿" onClick={() => run(`/cases/${caseId}/workflow/run-draft`)} />
            <form onSubmit={submitTrace} className="mt-4 space-y-3">
              <textarea className="min-h-96 w-full rounded-md border border-line px-3 py-3 font-mono text-sm leading-6" value={draftText || outputs.draft?.content || ""} onChange={(e) => setDraftText(e.target.value)} />
              <label className="block">
                <span className="text-xs font-medium text-slate-600">人工修改原因</span>
                <input className="mt-1 w-full rounded-md border border-line px-3 py-2 text-sm" value={reason} onChange={(e) => setReason(e.target.value)} />
              </label>
              <button className="button-primary" type="submit">
                <Save size={16} />
                提交决策留痕并沉淀知识
              </button>
            </form>
          </section>
        </div>

        <aside className="space-y-5">
          <section className="card p-5">
            <h2 className="font-semibold text-ink">法律知识库推荐</h2>
            <div className="mt-4 space-y-3">
              {recommendations.map((item) => (
                <div key={item.id} className="rounded-md border border-line p-3">
                  <div className="font-medium text-ink">{item.title}</div>
                  <div className="mt-1 text-xs text-court">{item.legal_issue}</div>
                  <p className="mt-2 text-sm leading-6 text-slate-600">{item.scenario}</p>
                </div>
              ))}
            </div>
          </section>

          <section className="card p-5">
            <h2 className="font-semibold text-ink">工作流记录</h2>
            <div className="mt-4 space-y-3">
              {events.map((item) => (
                <div key={item.id} className="border-l-2 border-court pl-3">
                  <div className="text-sm font-medium text-ink">{item.message}</div>
                  <div className="mt-1 text-xs text-slate-500">{new Date(item.created_at).toLocaleString()}</div>
                </div>
              ))}
            </div>
          </section>

          <section className="card p-5">
            <div className="flex items-center justify-between">
              <h2 className="font-semibold text-ink">决策留痕</h2>
              <BookPlus size={17} className="text-court" />
            </div>
            <div className="mt-4 space-y-3">
              {traces.slice(0, 3).map((item) => (
                <div key={item.id} className="rounded-md bg-slate-50 p-3 text-sm leading-6 text-slate-700">{item.revision_reason}</div>
              ))}
            </div>
          </section>
        </aside>
      </div>
    </div>
  );
}

function PanelHeader({ title, action, onClick }: { title: string; action: string; onClick: () => void }) {
  return (
    <div className="flex items-center justify-between gap-3">
      <h2 className="font-semibold text-ink">{title}</h2>
      <button className="button-secondary" onClick={onClick} type="button">
        <RefreshCw size={15} />
        {action}
      </button>
    </div>
  );
}

function OutputPanel({ title, button, output, onClick }: { title: string; button: string; output?: AIOutput; onClick: () => void }) {
  return (
    <section className="card p-5">
      <PanelHeader title={title} action={button} onClick={onClick} />
      <div className="mt-4 whitespace-pre-wrap rounded-md border border-line bg-slate-50 p-4 text-sm leading-6 text-slate-700">
        {output?.content || (
          <div className="flex items-center gap-2 text-slate-500">
            <Wand2 size={16} />
            等待生成
          </div>
        )}
      </div>
    </section>
  );
}

function evidenceStrengthLabel(strength: string) {
  const labels: Record<string, string> = {
    high: "较强",
    medium: "中等",
    low: "较弱"
  };

  return labels[strength] || "待评估";
}
