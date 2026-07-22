"use client";

import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import { DecisionTracePanel } from "@/components/case-workspace/DecisionTracePanel";
import { PageHeading } from "@/components/ui/ReasoningUI";

export default function TracesPage({ params }: { params: { id: string } }) {
  const caseId = Number(params.id);
  return (
    <div className="space-y-5">
      <Link href={`/cases/${caseId}`} className="button-secondary">
        <ArrowLeft size={16} />
        返回案件
      </Link>
      <PageHeading eyebrow="版本与决策" title="推理轨迹" description="人工复核与正式版本发布事件构成统一、可追溯的时间线。" />
      <DecisionTracePanel caseId={caseId} />
    </div>
  );
}
