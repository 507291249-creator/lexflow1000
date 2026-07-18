"use client";

import { useEffect, useMemo, useState } from "react";
import { BookOpenCheck, FileText, Scale, SearchCheck, Sparkles } from "lucide-react";
import type { CaseWorkspace, DocumentItem } from "@/lib/api";
import type { WorkflowStepCode } from "@/lib/workflow-config";
import { StatusBadge } from "@/components/case-workspace/shared";
import { AiContextSummary } from "./AiContextSummary";
import { SourceExcerptViewer } from "./SourceExcerptViewer";
import { EntityCode } from "@/components/ui/ReasoningUI";

type ContextTab = "materials" | "facts" | "laws" | "cases" | "ai";

const tabs: { code: ContextTab; label: string; icon: typeof FileText }[] = [
  { code: "materials", label: "材料", icon: FileText },
  { code: "facts", label: "事实", icon: Scale },
  { code: "laws", label: "法规", icon: BookOpenCheck },
  { code: "cases", label: "类案", icon: SearchCheck },
  { code: "ai", label: "AI 上下文", icon: Sparkles },
];

function outputTypeForStep(step: WorkflowStepCode) {
  if (step === "fact_review") return "fact_extraction";
  if (step === "issue_review") return "issue_identification";
  if (step === "legal_analysis") return "legal_analysis";
  if (step === "report") return "legal_report";
  return "";
}

export function ContextRail({ workspace, activeStep }: { workspace: CaseWorkspace; activeStep: WorkflowStepCode }) {
  const [activeTab, setActiveTab] = useState<ContextTab>(activeStep === "fact_review" ? "facts" : "materials");
  const [selectedDocumentId, setSelectedDocumentId] = useState<number | null>(workspace.documents[0]?.id || null);
  const selectedDocument = workspace.documents.find((item) => item.id === selectedDocumentId) as DocumentItem | undefined;
  const latestOutput = useMemo(() => {
    const type = outputTypeForStep(activeStep);
    const candidates = type ? workspace.ai_outputs.filter((item) => item.output_type === type) : workspace.ai_outputs;
    return [...candidates].sort((a, b) => b.version - a.version || b.id - a.id)[0];
  }, [activeStep, workspace.ai_outputs]);

  useEffect(() => {
    if (activeStep === "materials") setActiveTab("materials");
    if (activeStep === "fact_review" || activeStep === "issue_review") setActiveTab("facts");
    if (activeStep === "legal_analysis" || activeStep === "report") setActiveTab("ai");
  }, [activeStep]);

  return (
    <section className="overflow-hidden rounded-lg border border-line bg-white shadow-sm">
      <div className="border-b border-line px-4 pt-4">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-sm font-semibold text-ink">推理上下文</h2>
          <span className="text-xs text-slate-400">实时引用</span>
        </div>
        <div className="flex gap-1 overflow-x-auto pb-0">
          {tabs.map((tab) => {
            const Icon = tab.icon;
            return (
              <button
                key={tab.code}
                type="button"
                onClick={() => setActiveTab(tab.code)}
                className={`flex shrink-0 items-center gap-1 border-b-2 px-2 py-2 text-xs font-medium ${activeTab === tab.code ? "border-court text-court" : "border-transparent text-slate-500 hover:text-ink"}`}
              >
                <Icon size={13} />
                {tab.label}
              </button>
            );
          })}
        </div>
      </div>
      <div className="max-h-[calc(100vh-190px)] overflow-y-auto p-4">
        {activeTab === "materials" && (
          <div className="space-y-3">
            {!workspace.documents.length && <ContextPlaceholder title="暂无材料" description="上传案件材料后将在此形成引用入口。" />}
            {workspace.documents.map((item) => (
              <button
                type="button"
                key={item.id}
                onClick={() => setSelectedDocumentId(item.id)}
                className={`flex w-full items-start gap-3 rounded-md border px-3 py-3 text-left ${selectedDocumentId === item.id ? "border-court bg-[#edf5fa]" : "border-line hover:bg-slate-50"}`}
              >
                <EntityCode kind="document" id={item.id} className="mt-0.5 shrink-0" />
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-sm font-medium text-ink">{item.original_filename || item.filename}</span>
                  <span className="mt-1 block text-xs text-slate-500">{item.file_type?.toUpperCase() || "文件"} · {item.processing_status || "已上传"}</span>
                </span>
              </button>
            ))}
            <SourceExcerptViewer document={selectedDocument} />
          </div>
        )}
        {activeTab === "facts" && (
          <div className="space-y-3">
            {!workspace.facts.length && <ContextPlaceholder title="暂无事实" description="运行事实提取后，事实正文和来源会显示在这里。" />}
            {workspace.facts.map((fact) => (
              <article key={fact.id} className="rounded-md border border-line p-3">
                <div className="flex items-center justify-between gap-2">
                  <EntityCode kind="fact" id={fact.id} />
                  <StatusBadge status={fact.status} />
                </div>
                <p className="mt-2 text-sm leading-6 text-slate-700">{fact.human_fact || fact.ai_fact}</p>
                <p className="mt-2 text-xs leading-5 text-slate-500">来源：{fact.source_document || "案件输入"}</p>
              </article>
            ))}
          </div>
        )}
        {activeTab === "laws" && <ContextPlaceholder title="尚未执行法规检索" description="法规检索能力尚未接入，本页不会生成或展示虚假法规。" />}
        {activeTab === "cases" && <ContextPlaceholder title="类案检索尚未接入" description="后续接入案例数据源后，将展示相似事实、裁判观点与关键差异。" />}
        {activeTab === "ai" && <AiContextSummary output={latestOutput} workspace={workspace} />}
      </div>
    </section>
  );
}

function ContextPlaceholder({ title, description }: { title: string; description: string }) {
  return <div className="rounded-md border border-dashed border-line bg-slate-50 px-4 py-8 text-center"><div className="text-sm font-medium text-ink">{title}</div><p className="mt-2 text-xs leading-5 text-slate-500">{description}</p></div>;
}
