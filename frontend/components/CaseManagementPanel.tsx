"use client";

import { FormEvent, useEffect, useState } from "react";
import { CalendarDays, Check, ClipboardList, Plus, Save } from "lucide-react";
import { api, CaseItem, FollowUp, TodoItem, WorkRecord } from "@/lib/api";

type Props = {
  caseItem: CaseItem;
  onUpdated: () => Promise<void>;
};

export function CaseManagementPanel({ caseItem, onUpdated }: Props) {
  const [todos, setTodos] = useState<TodoItem[]>([]);
  const [records, setRecords] = useState<WorkRecord[]>([]);
  const [followUps, setFollowUps] = useState<FollowUp[]>([]);
  const [error, setError] = useState("");
  const [management, setManagement] = useState(managementValues(caseItem));
  const [todo, setTodo] = useState({ title: "", due_date: "", priority: "普通" });
  const [record, setRecord] = useState("");
  const [followUp, setFollowUp] = useState({ progress: "", next_action: caseItem.next_action, follow_up_at: caseItem.next_follow_up_at, stage: caseItem.stage });

  const load = async () => {
    try {
      const [todoData, recordData, followUpData] = await Promise.all([
        api<TodoItem[]>(`/cases/${caseItem.id}/todos`),
        api<WorkRecord[]>(`/cases/${caseItem.id}/work-records`),
        api<FollowUp[]>(`/cases/${caseItem.id}/follow-ups`)
      ]);
      setTodos(todoData);
      setRecords(recordData);
      setFollowUps(followUpData);
      setError("");
    } catch {
      setError("案件管理数据暂时无法读取，请稍后重试。");
    }
  };

  useEffect(() => {
    setManagement(managementValues(caseItem));
    setFollowUp((current) => ({ ...current, next_action: caseItem.next_action, follow_up_at: caseItem.next_follow_up_at, stage: caseItem.stage }));
    void load();
  }, [caseItem.id, caseItem.case_no, caseItem.case_type, caseItem.stage, caseItem.handler, caseItem.next_action, caseItem.next_follow_up_at]);

  async function saveManagement(event: FormEvent) {
    event.preventDefault();
    await api(`/cases/${caseItem.id}/management`, { method: "PATCH", body: JSON.stringify(management) });
    await onUpdated();
  }

  async function addTodo(event: FormEvent) {
    event.preventDefault();
    if (!todo.title.trim()) return;
    await api(`/cases/${caseItem.id}/todos`, { method: "POST", body: JSON.stringify(todo) });
    setTodo({ title: "", due_date: "", priority: "普通" });
    await load();
  }

  async function toggleTodo(item: TodoItem) {
    await api(`/todos/${item.id}`, { method: "PATCH", body: JSON.stringify({ completed: !item.completed }) });
    await load();
  }

  async function addRecord(event: FormEvent) {
    event.preventDefault();
    if (!record.trim()) return;
    await api(`/cases/${caseItem.id}/work-records`, { method: "POST", body: JSON.stringify({ content: record }) });
    setRecord("");
    await load();
  }

  async function addFollowUp(event: FormEvent) {
    event.preventDefault();
    if (!followUp.progress.trim()) return;
    await api(`/cases/${caseItem.id}/follow-ups`, { method: "POST", body: JSON.stringify(followUp) });
    setFollowUp((current) => ({ ...current, progress: "" }));
    await onUpdated();
    await load();
  }

  return (
    <section className="card p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="font-semibold text-ink">案件管理</h2>
          <p className="mt-1 text-sm text-slate-500">维护案件阶段、提醒安排与过程记录。</p>
        </div>
        <div className="flex items-center gap-2 text-sm text-court"><CalendarDays size={16} />下次跟进：{caseItem.next_follow_up_at || "未设置"}</div>
      </div>

      {error && <div role="alert" className="mt-4 border-l-2 border-amber-500 pl-3 text-sm text-slate-600">{error}</div>}

      <div className="mt-5 grid gap-5 xl:grid-cols-[1.05fr_0.95fr]">
        <form onSubmit={saveManagement} className="space-y-3">
          <div className="grid gap-3 sm:grid-cols-2">
            <Field label="案件编号" value={management.case_no} onChange={(value) => setManagement({ ...management, case_no: value })} />
            <Field label="承办人" value={management.handler} onChange={(value) => setManagement({ ...management, handler: value })} />
            <Select label="案件类型" value={management.case_type} onChange={(value) => setManagement({ ...management, case_type: value })} options={["劳动仲裁", "劳动诉讼", "咨询事项"]} />
            <Select label="当前阶段" value={management.stage} onChange={(value) => setManagement({ ...management, stage: value })} options={["材料收集", "法律分析", "文书准备", "已立案", "庭审准备", "结案归档"]} />
            <Field label="下次跟进日期" type="date" value={management.next_follow_up_at} onChange={(value) => setManagement({ ...management, next_follow_up_at: value })} />
            <Field label="下一步行动" value={management.next_action} onChange={(value) => setManagement({ ...management, next_action: value })} />
          </div>
          <button className="button-secondary" type="submit"><Save size={15} />保存管理信息</button>
        </form>

        <div className="border-l-0 border-line xl:border-l xl:pl-5">
          <div className="flex items-center justify-between gap-3">
            <h3 className="text-sm font-semibold text-ink">待办提醒</h3>
            <span className="text-xs text-slate-500">未完成 {todos.filter((item) => !item.completed).length} 项</span>
          </div>
          <div className="mt-3 space-y-2">
            {todos.map((item) => (
              <label key={item.id} className="flex items-start gap-3 rounded-md border border-line px-3 py-2 text-sm">
                <input type="checkbox" className="mt-0.5 h-4 w-4 accent-court" checked={item.completed} onChange={() => void toggleTodo(item)} />
                <span className={item.completed ? "flex-1 text-slate-400 line-through" : "flex-1 text-ink"}>{item.title}</span>
                <span className={`shrink-0 text-xs ${priorityClass(item.priority)}`}>{item.due_date || "未设日期"} · {item.priority}</span>
              </label>
            ))}
          </div>
          <form onSubmit={addTodo} className="mt-3 grid gap-2 sm:grid-cols-[1fr_132px_76px_auto]">
            <input className="rounded-md border border-line px-3 py-2 text-sm" placeholder="新增待办事项" value={todo.title} onChange={(e) => setTodo({ ...todo, title: e.target.value })} />
            <input type="date" className="rounded-md border border-line px-3 py-2 text-sm" value={todo.due_date} onChange={(e) => setTodo({ ...todo, due_date: e.target.value })} />
            <select className="rounded-md border border-line bg-white px-2 py-2 text-sm" value={todo.priority} onChange={(e) => setTodo({ ...todo, priority: e.target.value })}><option>高</option><option>普通</option><option>低</option></select>
            <button className="button-primary" type="submit" title="新增待办"><Plus size={16} /></button>
          </form>
        </div>
      </div>

      <div className="mt-5 grid gap-5 xl:grid-cols-2">
        <div className="border-t border-line pt-5">
          <h3 className="flex items-center gap-2 text-sm font-semibold text-ink"><ClipboardList size={16} />工作记录</h3>
          <form onSubmit={addRecord} className="mt-3">
            <textarea className="min-h-24 w-full rounded-md border border-line px-3 py-2 text-sm" placeholder="记录已完成的沟通、材料核验或法律研究工作" value={record} onChange={(e) => setRecord(e.target.value)} />
            <button className="button-secondary mt-2" type="submit"><Plus size={15} />新增记录</button>
          </form>
          <RecordList items={records} />
        </div>

        <div className="border-t border-line pt-5">
          <h3 className="flex items-center gap-2 text-sm font-semibold text-ink"><Check size={16} />案件跟进</h3>
          <form onSubmit={addFollowUp} className="mt-3 space-y-2">
            <textarea className="min-h-24 w-full rounded-md border border-line px-3 py-2 text-sm" placeholder="记录本次沟通、进展或风险变化" value={followUp.progress} onChange={(e) => setFollowUp({ ...followUp, progress: e.target.value })} />
            <div className="grid gap-2 sm:grid-cols-2">
              <Select label="更新阶段" value={followUp.stage} onChange={(value) => setFollowUp({ ...followUp, stage: value })} options={["材料收集", "法律分析", "文书准备", "已立案", "庭审准备", "结案归档"]} />
              <Field label="下次跟进日期" type="date" value={followUp.follow_up_at} onChange={(value) => setFollowUp({ ...followUp, follow_up_at: value })} />
            </div>
            <Field label="下一步行动" value={followUp.next_action} onChange={(value) => setFollowUp({ ...followUp, next_action: value })} />
            <button className="button-primary" type="submit"><Check size={15} />保存跟进</button>
          </form>
          <FollowUpList items={followUps} />
        </div>
      </div>
    </section>
  );
}

function managementValues(caseItem: CaseItem) {
  return {
    case_no: caseItem.case_no,
    case_type: caseItem.case_type,
    stage: caseItem.stage,
    handler: caseItem.handler,
    next_follow_up_at: caseItem.next_follow_up_at,
    next_action: caseItem.next_action,
  };
}

function Field({ label, value, onChange, type = "text" }: { label: string; value: string; onChange: (value: string) => void; type?: string }) {
  return <label className="block"><span className="text-xs font-medium text-slate-600">{label}</span><input type={type} className="mt-1 w-full rounded-md border border-line px-3 py-2 text-sm" value={value} onChange={(e) => onChange(e.target.value)} /></label>;
}

function Select({ label, value, onChange, options }: { label: string; value: string; onChange: (value: string) => void; options: string[] }) {
  return <label className="block"><span className="text-xs font-medium text-slate-600">{label}</span><select className="mt-1 w-full rounded-md border border-line bg-white px-3 py-2 text-sm" value={value} onChange={(e) => onChange(e.target.value)}>{options.map((item) => <option key={item}>{item}</option>)}</select></label>;
}

function RecordList({ items }: { items: WorkRecord[] }) {
  return <div className="mt-4 space-y-3">{items.slice(0, 4).map((item) => <div key={item.id} className="border-l-2 border-court pl-3 text-sm"><div className="text-slate-700">{item.content}</div><div className="mt-1 text-xs text-slate-500">{formatDate(item.created_at)}</div></div>)}</div>;
}

function FollowUpList({ items }: { items: FollowUp[] }) {
  return <div className="mt-4 space-y-3">{items.slice(0, 4).map((item) => <div key={item.id} className="border-l-2 border-mint pl-3 text-sm"><div className="text-slate-700">{item.progress}</div><div className="mt-1 text-xs text-slate-500">{item.stage || "未更新阶段"} · 下次跟进 {item.follow_up_at || "未设置"}</div></div>)}</div>;
}

function priorityClass(priority: string) {
  return priority === "高" ? "text-rose-600" : priority === "低" ? "text-slate-400" : "text-amber-600";
}

function formatDate(value: string) {
  return new Date(value).toLocaleString("zh-CN", { dateStyle: "short", timeStyle: "short" });
}
