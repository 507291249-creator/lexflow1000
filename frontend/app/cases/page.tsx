"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import { ArrowRight, Plus, Sparkles } from "lucide-react";
import { api, CaseItem } from "@/lib/api";

export default function CasesPage() {
  const [cases, setCases] = useState<CaseItem[]>([]);
  const emptyForm = {
    title: "", claimant: "", employer: "", claim_amount: "", summary: "", case_no: "", case_type: "劳动仲裁",
    stage: "材料收集", handler: "", next_follow_up_at: "", next_action: ""
  };
  const [form, setForm] = useState(emptyForm);
  const [error, setError] = useState("");

  const load = async () => {
    setError("");
    try {
      setCases(await api<CaseItem[]>("/cases"));
    } catch {
      setError("暂时无法读取案件列表，请确认后端服务已启动。");
    }
  };

  useEffect(() => { void load(); }, []);

  async function submit(event: FormEvent) {
    event.preventDefault();
    try {
      await api<CaseItem>("/cases", { method: "POST", body: JSON.stringify(form) });
      setForm(emptyForm);
      await load();
    } catch {
      setError("创建案件失败，请确认后端服务已正常运行后重试。");
    }
  }

  return (
    <div className="space-y-4">
      {error && (
        <div role="alert" className="flex items-center justify-between gap-3 border-l-2 border-amber-500 bg-white px-4 py-3 text-sm text-slate-600">
          <span>{error}</span>
          <button type="button" className="shrink-0 font-medium text-court hover:underline" onClick={load}>重新连接</button>
        </div>
      )}
      <div className="grid gap-6 lg:grid-cols-[0.9fr_1.4fr]">
        <section className="card p-5 lg:col-span-2">
          <div className="flex flex-wrap items-center justify-between gap-4"><div><h1 className="text-lg font-semibold text-ink">AI 案件工作流</h1><p className="mt-1 text-sm text-slate-500">从现场输入事实或上传材料开始，逐步完成事实确认、争点确认和逐项法律分析。</p></div><Link href="/cases/new" className="button-primary"><Sparkles size={16} />新建 AI 案件</Link></div>
        </section>
        <form onSubmit={submit} className="card p-5">
          <h1 className="text-lg font-semibold text-ink">案件登记</h1>
          <p className="mt-1 text-sm text-slate-500">登记基础信息并设置第一项跟进安排。</p>
          <div className="mt-4 grid gap-3 sm:grid-cols-2">
            <Input label="案件名称" value={form.title} onChange={(value) => setForm({ ...form, title: value })} />
            <Input label="案件编号" value={form.case_no} onChange={(value) => setForm({ ...form, case_no: value })} required={false} />
            <Input label="申请人" value={form.claimant} onChange={(value) => setForm({ ...form, claimant: value })} />
            <Input label="被申请人" value={form.employer} onChange={(value) => setForm({ ...form, employer: value })} />
            <Select label="案件类型" value={form.case_type} onChange={(value) => setForm({ ...form, case_type: value })} options={["劳动仲裁", "劳动诉讼", "咨询事项"]} />
            <Select label="当前阶段" value={form.stage} onChange={(value) => setForm({ ...form, stage: value })} options={["材料收集", "法律分析", "文书准备", "已立案", "庭审准备", "结案归档"]} />
            <Input label="承办人" value={form.handler} onChange={(value) => setForm({ ...form, handler: value })} required={false} />
            <Input label="主张金额" value={form.claim_amount} onChange={(value) => setForm({ ...form, claim_amount: value })} required={false} />
            <Input label="下次跟进日期" value={form.next_follow_up_at} onChange={(value) => setForm({ ...form, next_follow_up_at: value })} required={false} type="date" />
            <Input label="下一步行动" value={form.next_action} onChange={(value) => setForm({ ...form, next_action: value })} required={false} />
          </div>
          <label className="mt-3 block">
            <span className="text-xs font-medium text-slate-600">案件摘要</span>
            <textarea className="mt-1 min-h-28 w-full rounded-md border border-line px-3 py-2 text-sm" value={form.summary} onChange={(e) => setForm({ ...form, summary: e.target.value })} />
          </label>
          <button className="button-primary mt-4 w-full" type="submit">
            <Plus size={16} />
            登记案件
          </button>
        </form>

        <section className="card p-5">
        <h1 className="text-lg font-semibold text-ink">案件列表</h1>
        <div className="mt-4 divide-y divide-line">
          {cases.map((item) => (
            <Link key={item.id} href={`/cases/${item.id}`} className="flex items-center justify-between gap-4 py-4 hover:bg-slate-50">
              <div>
                <div className="font-medium text-ink">{item.title}</div>
                <div className="mt-1 text-sm text-slate-500">{item.case_no || "未编号"} · {item.claimant} 诉 {item.employer}</div>
                <div className="mt-1 text-xs text-slate-500">{item.stage} · {item.handler || "承办人待分配"} · {item.next_follow_up_at || "暂未设置跟进日期"}</div>
              </div>
              <span className="flex items-center gap-2 text-sm text-court">
                进入工作台 <ArrowRight size={15} />
              </span>
            </Link>
          ))}
        </div>
        </section>
      </div>
    </div>
  );
}

function Input({ label, value, onChange, required = true, type = "text" }: { label: string; value: string; onChange: (value: string) => void; required?: boolean; type?: string }) {
  return (
    <label className="block">
      <span className="text-xs font-medium text-slate-600">{label}</span>
      <input type={type} className="mt-1 w-full rounded-md border border-line px-3 py-2 text-sm" value={value} onChange={(e) => onChange(e.target.value)} required={required} />
    </label>
  );
}

function Select({ label, value, onChange, options }: { label: string; value: string; onChange: (value: string) => void; options: string[] }) {
  return (
    <label className="block">
      <span className="text-xs font-medium text-slate-600">{label}</span>
      <select className="mt-1 w-full rounded-md border border-line bg-white px-3 py-2 text-sm" value={value} onChange={(e) => onChange(e.target.value)}>
        {options.map((item) => <option key={item} value={item}>{item}</option>)}
      </select>
    </label>
  );
}
