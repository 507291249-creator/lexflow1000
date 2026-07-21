import Link from "next/link";
import { ArrowLeft, ArrowRight, ShieldCheck } from "lucide-react";
import { EmptyReasoningState, PageHeading } from "@/components/ui/ReasoningUI";

export default function RedactionPage() {
  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <Link href="/research" className="inline-flex items-center gap-2 text-sm text-slate-600 hover:text-court"><ArrowLeft size={16} />返回法律研究</Link>
      <PageHeading
        eyebrow="法律 AI 分析安全边界"
        title="材料脱敏"
        description="在具体案件的“材料与脱敏”步骤中，检测、预览、修改并确认将进入 AI 分析空间的脱敏副本。"
      />
      <EmptyReasoningState
        title="请在案件内完成脱敏复核"
        description="脱敏版本与原始材料、人工修改和确认记录绑定，避免在独立页面产生无法追溯的分析副本。"
        action={<Link className="button-primary" href="/cases"><ShieldCheck size={16} />进入案件分析<ArrowRight size={16} /></Link>}
      />
    </div>
  );
}
