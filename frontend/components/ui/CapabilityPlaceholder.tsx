import Link from "next/link";
import { ArrowRight, type LucideIcon } from "lucide-react";
import { ReasoningStatusBadge } from "./ReasoningUI";

export function CapabilityPlaceholder({
  title,
  description,
  icon: Icon,
  href,
  actionLabel = "查看能力说明",
}: {
  title: string;
  description: string;
  icon: LucideIcon;
  href?: string;
  actionLabel?: string;
}) {
  return (
    <article className="reasoning-card flex min-h-44 flex-col">
      <div className="flex items-start justify-between gap-3">
        <span className="flex h-9 w-9 items-center justify-center rounded-md bg-[var(--surface-sunken)] text-slate-500"><Icon size={18} /></span>
        <ReasoningStatusBadge status="unavailable" />
      </div>
      <h2 className="mt-4 font-semibold text-ink">{title}</h2>
      <p className="mt-2 text-sm leading-6 text-slate-500">{description}</p>
      {href && <Link href={href} className="mt-auto flex items-center gap-1 pt-4 text-sm font-medium text-court">{actionLabel}<ArrowRight size={15} /></Link>}
    </article>
  );
}
