import { BookOpenCheck, Database, SearchCheck, ShieldCheck } from "lucide-react";
import { CapabilityPlaceholder } from "@/components/ui/CapabilityPlaceholder";
import { PageHeading } from "@/components/ui/ReasoningUI";

export default function ResearchPage() {
  return (
    <div className="mx-auto max-w-7xl space-y-7">
      <PageHeading eyebrow="法律研究" title="为法律分析组织可核验的依据" description="法规、类案与脱敏能力采用独立模块接入；在数据源真正启用前，系统不会生成虚假引用。" />
      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        <CapabilityPlaceholder title="材料脱敏" description="检测身份证号、手机号、邮箱及其他敏感信息，人工确认后再进入事实提取。" icon={ShieldCheck} href="/redaction" />
        <CapabilityPlaceholder title="法规检索" description="围绕已确认争点召回法规条文，经人工选择后进入法律分析上下文。" icon={BookOpenCheck} href="/research/laws" />
        <CapabilityPlaceholder title="类案检索" description="比较相似事实、裁判观点与关键差异，保留来源链接和检索条件。" icon={SearchCheck} href="/research/cases" />
      </section>
      <section className="border-t border-line pt-6">
        <div className="flex items-start gap-3"><Database size={18} className="mt-1 text-court" /><div><h2 className="font-semibold text-ink">当前可用依据</h2><p className="mt-2 text-sm leading-6 text-slate-500">现阶段法律分析仍使用现有规则文件、已确认事实、争点和人工复核机制。法规库与类案数据源尚未接入。</p></div></div>
      </section>
    </div>
  );
}
