"use client";

import Link from "next/link";
import { ChangeEvent, FormEvent, useState } from "react";
import { ArrowLeft, FileUp, Scale, Sparkles } from "lucide-react";
import { useRouter } from "next/navigation";
import { api, CaseItem } from "@/lib/api";

export default function NewAICasePage() {
  const router = useRouter();
  const [form, setForm] = useState({ title: "", claimant: "", employer: "", case_type: "劳动争议", fact_text: "" });
  const [files, setFiles] = useState<File[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  function pickFiles(event: ChangeEvent<HTMLInputElement>) {
    setFiles(Array.from(event.target.files || []));
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!form.fact_text.trim() && !files.length) {
      setError("请粘贴案件事实或上传至少一份材料。");
      return;
    }
    setBusy(true);
    setError("");
    try {
      const body = new FormData();
      body.append("title", form.title.trim());
      body.append("claimant", form.claimant.trim() || "待识别");
      body.append("employer", form.employer.trim() || "待识别");
      body.append("case_type", form.case_type);
      body.append("fact_text", form.fact_text.trim());
      files.forEach((file) => body.append("files", file));
      const created = await api<CaseItem>("/ai-cases", { method: "POST", body });
      router.push(`/cases/${created.id}`);
    } catch (requestError) {
      setError(requestError instanceof Error ? "案件创建未完成，请检查材料格式或后端模型配置后重试。" : "案件创建未完成，请稍后重试。");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto max-w-4xl space-y-5">
      <Link href="/cases" className="inline-flex items-center gap-2 text-sm text-slate-600 hover:text-court"><ArrowLeft size={16} />返回案件列表</Link>
      <section className="card p-6">
        <div className="flex items-start gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-md bg-[#eaf3f8] text-court"><Sparkles size={20} /></div>
          <div><h1 className="text-xl font-semibold text-ink">新建 AI 案件</h1><p className="mt-1 text-sm leading-6 text-slate-600">提交现场事实或材料后，系统会立即创建事实提取工作单元，并生成等待人工确认的结构化事实。</p></div>
        </div>
        <form className="mt-6 space-y-5" onSubmit={submit}>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <Field label="案件名称" value={form.title} required onChange={(value) => setForm({ ...form, title: value })} placeholder="例如：李某诉某公司劳动争议" />
            <Field label="申请人" value={form.claimant} onChange={(value) => setForm({ ...form, claimant: value })} placeholder="可留空，由材料识别" />
            <Field label="被申请人" value={form.employer} onChange={(value) => setForm({ ...form, employer: value })} placeholder="可留空，由材料识别" />
            <label className="block"><span className="text-xs font-medium text-slate-600">案件类型</span><select className="mt-1 w-full rounded-md border border-line bg-white px-3 py-2 text-sm" value={form.case_type} onChange={(event) => setForm({ ...form, case_type: event.target.value })}>{["合同纠纷", "公司纠纷", "知识产权", "劳动争议", "其他"].map((item) => <option key={item}>{item}</option>)}</select></label>
          </div>
          <label className="block">
            <span className="text-sm font-medium text-ink">原始案件事实</span>
            <textarea className="mt-2 min-h-56 w-full rounded-md border border-line px-3 py-3 text-sm leading-6" value={form.fact_text} onChange={(event) => setForm({ ...form, fact_text: event.target.value })} placeholder="粘贴当事人陈述、关键经过、时间节点和已有材料。系统会保留该原文，并以其为分析来源。" />
          </label>
          <div className="rounded-md border border-dashed border-line bg-slate-50 p-4">
            <div className="flex flex-wrap items-center justify-between gap-3"><div className="flex items-center gap-2 text-sm text-slate-700"><FileUp size={18} className="text-court" />支持 PDF、DOCX、TXT，可与现场事实同时提交。</div><label className="button-secondary cursor-pointer"><FileUp size={16} />选择材料<input className="hidden" type="file" accept=".pdf,.docx,.txt" multiple onChange={pickFiles} /></label></div>
            {files.length > 0 && <div className="mt-3 flex flex-wrap gap-2">{files.map((file) => <span className="badge bg-white text-slate-600" key={`${file.name}-${file.lastModified}`}>{file.name}</span>)}</div>}
          </div>
          {error && <div role="alert" className="border-l-2 border-amber-500 bg-amber-50 px-3 py-2 text-sm text-amber-800">{error}</div>}
          <button className="button-primary w-full sm:w-auto" disabled={busy} type="submit"><Scale size={16} />{busy ? "正在提取事实" : "创建案件并提取事实"}</button>
        </form>
      </section>
    </div>
  );
}

function Field({ label, value, onChange, placeholder, required = false }: { label: string; value: string; onChange: (value: string) => void; placeholder: string; required?: boolean }) {
  return <label className="block"><span className="text-xs font-medium text-slate-600">{label}</span><input required={required} className="mt-1 w-full rounded-md border border-line px-3 py-2 text-sm" value={value} onChange={(event) => onChange(event.target.value)} placeholder={placeholder} /></label>;
}
