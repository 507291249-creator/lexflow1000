import Link from "next/link";
import { ArrowLeft, SearchCheck } from "lucide-react";
import { EmptyReasoningState, PageHeading, ReasoningStatusBadge } from "@/components/ui/ReasoningUI";

export default function CasesResearchPage() {
  return <div className="mx-auto max-w-5xl space-y-6"><Link href="/research" className="inline-flex items-center gap-2 text-sm text-slate-600 hover:text-court"><ArrowLeft size={16} />返回法律研究</Link><PageHeading eyebrow="预留能力" title="类案检索" description="后续将展示相似事实、相似争点、关键差异、裁判观点和来源链接。" action={<ReasoningStatusBadge status="unavailable" />} /><EmptyReasoningState title="类案检索尚未接入" description="当前版本没有案例数据源，本页不会生成虚假案例或裁判结果。" action={<SearchCheck size={22} />} /></div>;
}
