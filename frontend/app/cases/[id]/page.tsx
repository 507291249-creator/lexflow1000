"use client";

import { useEffect, useState } from "react";
import { RefreshCw } from "lucide-react";
import { CaseWorkspaceView } from "@/components/case-workspace/CaseWorkspaceView";
import { api, type CaseWorkspace } from "@/lib/api";
import type { WorkflowStepCode } from "@/lib/workflow-config";

function loadErrorMessage(error: unknown) {
  if (!(error instanceof Error)) return "案件加载失败，请重试。";
  if (error.message === "Failed to fetch" || error.message.toLowerCase().includes("networkerror")) return "暂时无法连接后端服务。请等待 Render 服务唤醒后重新加载。";
  try { return (JSON.parse(error.message) as { detail?: string }).detail || error.message; } catch { return error.message; }
}

export default function CaseDetailPage({ params }: { params: { id: string } }) {
  const caseId = Number(params.id);
  const [workspace, setWorkspace] = useState<CaseWorkspace | null>(null);
  const [activeStep, setActiveStep] = useState<WorkflowStepCode>("case_input");
  const [error, setError] = useState("");

  async function load(): Promise<boolean> {
    for (let attempt = 0; attempt < 3; attempt += 1) {
      try {
        setWorkspace(await api<CaseWorkspace>(`/cases/${caseId}/workspace`));
        setError("");
        return true;
      } catch (loadError) {
        if (attempt < 2) { await new Promise((resolve) => window.setTimeout(resolve, attempt === 0 ? 500 : 1200)); continue; }
        setError(loadErrorMessage(loadError));
      }
    }
    return false;
  }

  useEffect(() => { void load(); }, [caseId]);

  if (!workspace) return <section className="card p-6"><div className="flex flex-wrap items-center justify-between gap-3 text-sm text-slate-600"><span>{error || "正在加载案件工作台..."}</span>{error && <button className="button-secondary" type="button" onClick={() => void load()}><RefreshCw size={16} />重新加载案件</button>}</div></section>;

  return <CaseWorkspaceView caseId={caseId} workspace={workspace} activeStep={activeStep} onStepChange={setActiveStep} onReload={load} />;
}
