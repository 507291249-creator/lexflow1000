# LexFlow MVP

LexFlow MVP 是一个面向劳动仲裁案件的法律 AI 工作流与知识沉淀 Demo。

它完整跑通：

创建案件 → 上传材料 → 文档解析 → 证据结构化 → AI 法律分析 → 文书初稿生成 → 人工修改 → Decision Trace 记录 → Legal Memory 知识沉淀 → 相似案件复用提示。

案件管理模块还支持：案件编号、类型、承办人和阶段登记；带日期与优先级的待办提醒；人工工作记录；案件跟进记录及下一步行动安排。

## 技术栈

- Backend: FastAPI + SQLite + SQLAlchemy
- Frontend: Next.js + React + Tailwind CSS
- LLM: 已封装为可替换 agent，默认使用 mock 输出
- Demo 数据: 内置劳动仲裁示例、`labor_law_rules.json`、`sample_memory.json`

## 项目结构

```text
backend/
  app/
    agents/
      document_parser.py
      evidence_agent.py
      research_agent.py
      draft_agent.py
      risk_agent.py
      decision_trace.py
      legal_memory.py
      similarity_search.py
    mock/
      labor_law_rules.json
      sample_case.txt
      sample_memory.json
    main.py
    models.py
    schemas.py
    database.py
frontend/
  app/
    cases/
    memory/
  components/
  lib/
```

## 启动后端

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

后端启动后会自动创建 SQLite 数据库并写入 Demo 案件与示例 Legal Memory。

API 文档：

- http://localhost:8000/docs
- http://localhost:8000/health

## 启动前端

另开一个终端：

```bash
cd frontend
npm install
npm run dev
```

访问：

- http://localhost:3000

## 运行 Demo

1. 打开 Dashboard。
2. 点击“打开 Demo”进入示例案件。
3. 点击“一键运行 Demo”。
4. 页面会生成证据表、法律分析、风险提示和劳动仲裁申请书初稿。
5. 在文书初稿编辑区修改内容，填写修改原因。
6. 点击“提交 Trace 并沉淀 Memory”。
7. 在 Decision Trace 页面查看修改记录，在 Legal Memory 页面查看知识沉淀。

## 案件管理

1. 在“案件”页面登记案件基础信息、承办人、阶段和首次跟进日期。
2. 打开案件详情，在“案件管理”区维护编号、阶段、下一步行动和下次跟进日期。
3. 在“待办提醒”中新增待办，勾选后即可标记完成。
4. 在“工作记录”中沉淀沟通、材料核验和研究工作。
5. 在“案件跟进”中记录本次进展，保存后会同步更新案件阶段、下一步行动和下次跟进日期。

## 已实现 API

- `POST /cases`
- `GET /cases`
- `GET /cases/{case_id}`
- `PATCH /cases/{case_id}/management`
- `GET /cases/{case_id}/work-records`
- `POST /cases/{case_id}/work-records`
- `GET /cases/{case_id}/todos`
- `POST /cases/{case_id}/todos`
- `PATCH /todos/{todo_id}`
- `GET /cases/{case_id}/follow-ups`
- `POST /cases/{case_id}/follow-ups`
- `POST /cases/{case_id}/documents/upload`
- `GET /cases/{case_id}/documents`
- `POST /cases/{case_id}/workflow/run-evidence`
- `POST /cases/{case_id}/workflow/run-analysis`
- `POST /cases/{case_id}/workflow/run-draft`
- `POST /cases/{case_id}/workflow/run-risk`
- `POST /cases/{case_id}/workflow/run-demo`
- `POST /cases/{case_id}/traces`
- `GET /cases/{case_id}/traces`
- `POST /memory/from-trace/{trace_id}`
- `GET /memory`
- `GET /cases/{case_id}/memory-recommendations`
- `GET /cases/{case_id}/workflow/events`

## 替换真实 LLM

当前 AI 能力位于 `backend/app/agents/`。后续接入真实模型时，可以保持 API 不变，只替换 agent 内部实现，例如：

- `research_agent.py` 接入法律检索或 RAG
- `draft_agent.py` 接入文书生成模型
- `risk_agent.py` 接入证据缺口检查模型

这样前端和数据结构可以继续复用。
