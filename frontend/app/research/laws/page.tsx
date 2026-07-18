import Link from "next/link";
import { ArrowLeft, BookOpenCheck } from "lucide-react";
import { EmptyReasoningState, PageHeading, ReasoningStatusBadge } from "@/components/ui/ReasoningUI";

export default function LawsPage() {
  return <div className="mx-auto max-w-5xl space-y-6"><Link href="/research" className="inline-flex items-center gap-2 text-sm text-slate-600 hover:text-court"><ArrowLeft size={16} />返回法律研究</Link><PageHeading eyebrow="预留能力" title="法规检索" description="后续将从争点生成检索条件，召回法规候选并由人工选择后进入分析。" action={<ReasoningStatusBadge status="unavailable" />} /><EmptyReasoningState title="尚未执行法规检索" description="法规数据源尚未接入，因此当前页面不返回条文标题、内容或引用编号。" action={<BookOpenCheck size={22} />} /></div>;
}
