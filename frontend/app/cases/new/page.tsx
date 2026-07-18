"use client";

import Link from "next/link";
import { type ChangeEvent, type FormEvent, useState } from "react";
import { ArrowLeft, ArrowRight, Check, FilePlus2, FileText, Files, Scale, Upload } from "lucide-react";
import { useRouter } from "next/navigation";
import { api, type CaseItem } from "@/lib/api";
import { PageHeading } from "@/components/ui/ReasoningUI";

type InputMode = "paste" | "upload" | "blank";

const inputModes = [
  { code: "paste" as const, title: "粘贴案情", description: "输入当事人陈述、关键经过或现有事实摘要。", icon: FileText },
  { code: "upload" as const, title: "上传材料", description: "提交 PDF、DOCX 或 TXT，作为事实提取起点。", icon: Upload },
  { code: "blank" as const, title: "创建空白案件", description: "先建立工作区，稍后在材料步骤继续补充。", icon: FilePlus2 },
];

export default function NewAICasePage() {
  const router = useRouter();
  const [step, setStep] = useState<1 | 2>(1);
  const [mode, setMode] = useState<InputMode>("paste");
  const [form, setForm] = useState({ title: "", claimant: "", employer: "", case_type: "劳动争议", fact_text: "" });
  const [files, setFiles] = useState<File[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  function pickFiles(event: ChangeEvent<HTMLInputElement>) { setFiles(Array.from(event.target.files || [])); }
  function continueToInfo() {
    if (mode === "paste" && !form.fact_text.trim()) return setError("请先粘贴案件事实，或选择其他创建方式。");
    if (mode === "upload" && !files.length) return setError("请先选择至少一份 PDF、DOCX 或 TXT 材料。");
    setError(""); setStep(2);
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!form.title.trim()) return setError("请填写案件名称。");
    setBusy(true); setError("");
    try {
      let created: CaseItem;
      if (mode === "blank") {
        created = await api<CaseItem>("/cases", { method: "POST", body: JSON.stringify({ title: form.title.trim(), claimant: form.claimant.trim() || "待识别", employer: form.employer.trim() || "待识别", case_type: form.case_type, summary: "", raw_facts: "" }) });
      } else {
        const body = new FormData();
        body.append("title", form.title.trim()); body.append("claimant", form.claimant.trim() || "待识别"); body.append("employer", form.employer.trim() || "待识别"); body.append("case_type", form.case_type);
        body.append("fact_text", mode === "paste" ? form.fact_text.trim() : "");
        if (mode === "upload") files.forEach((file) => body.append("files", file));
        created = await api<CaseItem>("/ai-cases", { method: "POST", body });
      }
      router.push(`/cases/${created.id}`);
    } catch {
      setError("案件创建未完成，请检查材料格式或后端服务状态后重试。");
    } finally { setBusy(false); }
  }

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <Link href="/cases" className="inline-flex items-center gap-2 text-sm text-slate-600 hover:text-court"><ArrowLeft size={16} />返回推理工作区</Link>
      <PageHeading eyebrow={`新建分析 · 第 ${step} 步，共 2 步`} title={step === 1 ? "选择推理起点" : "补充案件信息"} description={step === 1 ? "先提供材料或案情。案件管理信息不会阻挡后续推理，可在案件信息抽屉中继续完善。" : "这些信息用于识别案件，不参与替代事实确认和法律分析。"} />
      <div className="grid gap-2 sm:grid-cols-2"><StepIndicator active={step === 1} done={step > 1} label="01 提供材料" /><StepIndicator active={step === 2} done={false} label="02 补充信息" /></div>

      {step === 1 ? (
        <section className="space-y-5">
          <div className="grid gap-3 md:grid-cols-3">
            {inputModes.map((item) => { const Icon = item.icon; const active = mode === item.code; return <button type="button" key={item.code} onClick={() => { setMode(item.code); setError(""); }} className={`reasoning-card min-h-36 text-left transition ${active ? "border-court bg-[#f1f7fa]" : "hover:border-[#9cb9ca]"}`}><Icon size={20} className={active ? "text-court" : "text-slate-400"} /><h2 className="mt-4 font-semibold text-ink">{item.title}</h2><p className="mt-2 text-sm leading-6 text-slate-500">{item.description}</p></button>; })}
          </div>
          {mode === "paste" && <textarea className="min-h-64 w-full rounded-md border border-line bg-white px-4 py-3 text-sm leading-7" value={form.fact_text} onChange={(event) => setForm({ ...form, fact_text: event.target.value })} placeholder="粘贴案件事实、时间节点、诉求和已知证据。原文将作为后续事实提取输入。" />}
          {mode === "upload" && <label className="flex min-h-64 cursor-pointer flex-col items-center justify-center rounded-lg border border-dashed border-line bg-white p-6 text-center hover:border-court"><Files size={24} className="text-court" /><span className="mt-3 font-medium text-ink">选择案件材料</span><span className="mt-2 text-sm text-slate-500">支持 PDF、DOCX、TXT</span><input className="hidden" type="file" accept=".pdf,.docx,.txt" multiple onChange={pickFiles} />{files.length > 0 && <div className="mt-5 flex flex-wrap justify-center gap-2">{files.map((file) => <span className="badge bg-slate-100 text-slate-600" key={`${file.name}-${file.lastModified}`}>{file.name}</span>)}</div>}</label>}
          {mode === "blank" && <div className="empty-state min-h-64"><FilePlus2 size={24} /><div><div className="font-medium text-ink">建立空白推理工作区</div><p>创建后可在“材料与脱敏”步骤上传文件，或通过案件信息抽屉补充基础资料。</p></div></div>}
          {error && <div className="border-l-2 border-amber-500 bg-amber-50 px-4 py-3 text-sm text-amber-800">{error}</div>}
          <div className="flex justify-end"><button className="button-primary" type="button" onClick={continueToInfo}>继续补充信息<ArrowRight size={16} /></button></div>
        </section>
      ) : (
        <form className="space-y-5" onSubmit={submit}>
          <section className="card p-5 sm:p-6">
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="案件名称" value={form.title} required onChange={(value) => setForm({ ...form, title: value })} placeholder="例如：李某与某公司劳动争议" />
              <label className="block"><span className="text-xs font-medium text-slate-600">案件类型</span><select className="mt-1 w-full rounded-md border border-line bg-white px-3 py-2 text-sm" value={form.case_type} onChange={(event) => setForm({ ...form, case_type: event.target.value })}>{["合同纠纷", "公司纠纷", "知识产权", "劳动争议", "其他"].map((item) => <option key={item}>{item}</option>)}</select></label>
              <Field label="申请人" value={form.claimant} onChange={(value) => setForm({ ...form, claimant: value })} placeholder="可留空，由材料识别" />
              <Field label="被申请人" value={form.employer} onChange={(value) => setForm({ ...form, employer: value })} placeholder="可留空，由材料识别" />
            </div>
            <div className="mt-5 rounded-md bg-slate-50 px-4 py-3 text-sm text-slate-600">推理起点：{inputModes.find((item) => item.code === mode)?.title}{mode === "upload" ? ` · ${files.length} 份材料` : ""}</div>
          </section>
          {error && <div className="border-l-2 border-amber-500 bg-amber-50 px-4 py-3 text-sm text-amber-800">{error}</div>}
          <div className="flex flex-wrap justify-between gap-3"><button className="button-secondary" type="button" onClick={() => setStep(1)}><ArrowLeft size={16} />返回材料</button><button className="button-primary" disabled={busy} type="submit"><Scale size={16} />{busy ? "正在建立工作区" : mode === "blank" ? "创建空白案件" : "创建并开始事实提取"}</button></div>
        </form>
      )}
    </div>
  );
}

function StepIndicator({ active, done, label }: { active: boolean; done: boolean; label: string }) { return <div className={`flex items-center gap-2 rounded-md border px-3 py-2 text-sm ${active ? "border-court bg-[#edf5fa] text-court" : "border-line bg-white text-slate-500"}`}>{done ? <Check size={15} /> : <span className="h-2 w-2 rounded-full bg-current" />}{label}</div>; }
function Field({ label, value, onChange, placeholder, required = false }: { label: string; value: string; onChange: (value: string) => void; placeholder: string; required?: boolean }) { return <label className="block"><span className="text-xs font-medium text-slate-600">{label}</span><input required={required} className="mt-1 w-full rounded-md border border-line px-3 py-2 text-sm" value={value} onChange={(event) => onChange(event.target.value)} placeholder={placeholder} /></label>; }
