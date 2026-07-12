import { CheckCircle2, Circle } from "lucide-react";

const steps = [
  { key: "created", label: "创建案件" },
  { key: "documents", label: "上传材料" },
  { key: "evidence_ready", label: "证据结构化" },
  { key: "analysis_ready", label: "AI 法律分析" },
  { key: "draft_ready", label: "文书初稿" },
  { key: "memory", label: "知识沉淀" }
];

const order: Record<string, number> = {
  created: 1,
  evidence_ready: 3,
  analysis_ready: 4,
  draft_ready: 5
};

export function WorkflowStepper({ status, hasDocuments, hasTrace }: { status: string; hasDocuments: boolean; hasTrace: boolean }) {
  const current = Math.max(order[status] || 1, hasDocuments ? 2 : 1, hasTrace ? 6 : 1);
  return (
    <div className="card p-4">
      <div className="grid gap-3 md:grid-cols-6">
        {steps.map((step, index) => {
          const done = index + 1 <= current;
          const Icon = done ? CheckCircle2 : Circle;
          return (
            <div key={step.key} className="flex items-center gap-2">
              <Icon size={18} className={done ? "text-mint" : "text-slate-400"} />
              <span className={done ? "text-sm font-medium text-ink" : "text-sm text-slate-500"}>{step.label}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
