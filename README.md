# LexFlow MVP

LexFlow MVP 是一个面向劳动仲裁案件的法律 AI 工作流与知识沉淀 Demo。

## P1 现场 AI 案件

新增“新建 AI 案件”入口，支持粘贴新的案件事实并同时上传 PDF、DOCX、TXT 材料。该流程不会读取预设案例结果，按以下顺序处理现场输入：

1. 创建案件并保存原始输入和上传材料。
2. 自动运行 `fact_extraction`，生成案件摘要、主体、关键事实、时间线、待确认事实和置信度。
3. 人工一键确认或按需修改、驳回事实；全部处理后手动运行 `issue_identification`，避免连续确认动作触发重复模型调用。
4. 人工可一键确认 AI 争点或按需修改、删除、新增；确认后系统按争点数量创建独立的 `legal_analysis` 工作单元。
5. 每个分析工作单元都可生成新版本，并记录对应的事实版本、争点版本、生成时间和输入快照。
6. 对分析执行接受、修改、驳回或补充材料后重新分析；所有人工操作写入决策记录。
7. 仅使用当前已确认事实、已确认争点和已批准分析生成结构化法律分析报告。

### 真实 LLM 配置

后端默认使用 OpenAI；也支持通过智谱 AI 的 OpenAI 兼容对话接口完成事实提取、争点识别和逐项法律分析。两种提供方均会经过服务端 Schema 校验，智谱使用 JSON 对象输出后再由系统校验字段完整性。

```bash
export OPENAI_API_KEY="你的服务端密钥"
export OPENAI_MODEL="gpt-4o-mini"
```

使用智谱 AI 时改为：

```bash
export LLM_PROVIDER="zhipu"
export ZHIPU_API_KEY="你的智谱服务端密钥"
export ZHIPU_MODEL="glm-4-flash-250414"
```

本地演示默认允许 `ALLOW_LOCAL_AI_FALLBACK=true`：未配置模型密钥时，页面会明确标记“本地备用解析”。生产环境建议设置 `ALLOW_LOCAL_AI_FALLBACK=false`，这样缺少密钥、模型调用失败或结构化输出连续校验失败时，工作单元会显示“失败”并允许人工重新运行，而不会静默替换为备用结果。

未配置密钥或模型调用暂时不可用时，系统会明确显示“备用解析”，并根据新输入材料动态生成基础结构，方便本地走通流程；它不会把预设示例答案作为新案件的主逻辑。

代码中已预留 `legal_research`、`case_retrieval` 外部数据源边界，后续可接入北大法宝等服务。

它完整跑通：

创建案件 → 上传材料 → 文档解析 → 证据结构化 → AI 法律分析 → 文书初稿生成 → 人工修改 → Decision Trace 记录 → Legal Memory 知识沉淀 → 相似案件复用提示。

## P0 最小闭环

案件详情页默认进入“工作流”，围绕以下标准链路组织工作单元：

材料理解 → 事实结构化 → 争点识别 → 法律检索 → 类案分析 → 综合论证 → 文书生成 → 人工复核 → 知识沉淀。

- 事实支持 AI 提取、人工接受、修改、驳回，并按“已确认 / 待确认 / AI 提取”展示。
- 争点支持 AI 建议、人工确认、分析中、已完成，以及新增、修改、删除。
- 法律分析以核心结论、风险等级、主要理由、支持依据、反方观点、不确定事项、下一步证据和 AI 置信度的结构化形式展示。
- 每次人工接受、修改、驳回、复核和知识沉淀都会写入决策记录，保留 AI 原始版本、人工版本与修改原因。
- 仅已批准的工作单元可生成候选法律记忆，候选项可批准沉淀、修改后沉淀或忽略。法律记忆库只展示已批准沉淀的内容。

案件管理模块还支持：案件编号、类型、承办人和阶段登记；带日期与优先级的待办提醒；人工工作记录；案件跟进记录及下一步行动安排。

## 技术栈

- Backend: FastAPI + SQLAlchemy + Alembic；本地默认 SQLite，生产环境使用 PostgreSQL
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
    services/
      storage.py
      document_files.py
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
alembic -c alembic.ini upgrade head
uvicorn app.main:app --reload --port 8000
```

`alembic upgrade head` 会创建或升级数据库结构。当前唯一 migration head 为 `0006_report_version_lineage`，迁移顺序为 `0001_baseline` → `0002_mvp2_documents_fact_sources` → `0003_demo_redactions` → `0004_workflow_version_lineage` → `0005_analysis_version_lineage` → `0006_report_version_lineage`。本地 SQLite 启动阶段暂时保留 `create_all()` 和旧版动态补字段逻辑作为兼容桥梁；PostgreSQL 启动不会自动建表，必须在应用启动前完成 Alembic 迁移，避免 `create_all()` 与 0002 冲突。Sprint 1A 新增的 Document 字段与 `fact_sources`、0003 新增的脱敏版本表、0004 新增的工作流版本谱系字段、0005 新增的分析版本谱系字段以及 0006 新增的报告版本谱系字段只由 Alembic 管理。完成两轮稳定生产迁移后将移除旧版动态迁移逻辑。

### 文件存储

本地开发默认使用 `LocalStorageService`，文件写入 `UPLOAD_DIR`。生产环境应把 `STORAGE_PROVIDER` 设为 `r2` 或 `s3`，并配置私有的 S3 兼容存储桶。业务上传逻辑只依赖统一 `StorageService`，不会直接依赖 Cloudflare R2 SDK。

```bash
# 本地
STORAGE_PROVIDER=local
UPLOAD_DIR=./app/uploads

# Cloudflare R2 / S3 兼容存储
STORAGE_PROVIDER=r2
S3_ENDPOINT_URL=https://<account-id>.r2.cloudflarestorage.com
S3_ACCESS_KEY_ID=<server-side-access-key>
S3_SECRET_ACCESS_KEY=<server-side-secret>
S3_BUCKET_NAME=lexflow-private
S3_REGION=auto
MAX_UPLOAD_SIZE_BYTES=20971520
```

存储桶必须保持私有。后端仅为下载生成最长 5 分钟的短期地址；密钥不得放入前端环境变量。当前仅接受扩展名、MIME 和文件签名相符的 PDF、DOCX、TXT 文件。对象键格式为 `cases/{case_id}/documents/{document_id}/{checksum}-{safe_filename}`，同名文件不会互相覆盖。

旧版 `legacy_local` 材料不会自动迁移，也不会生成不存在的对象地址；页面仍保留其已解析文本并显示兼容提示。

### 数据库迁移

查看迁移历史和当前版本：

```bash
cd backend
alembic -c alembic.ini history
alembic -c alembic.ini current
```

全新数据库直接执行：

```bash
alembic -c alembic.ini upgrade head
alembic -c alembic.ini current
```

当前代码预期 `current` 返回 `0006_report_version_lineage (head)`。

已有 MVP 1 SQLite 数据库必须先停止后端并备份：

```bash
cp data/lexflow.db "data/lexflow-before-mvp2-$(date +%Y%m%d-%H%M%S).db"
```

确认数据库中已经存在 `cases`、`documents`、`case_facts` 等旧表，并且尚未由 Alembic 管理后，执行：

```bash
alembic -c alembic.ini stamp 0001_baseline
alembic -c alembic.ini upgrade head
alembic -c alembic.ini current
```

`stamp` 只登记已有结构，不创建或修改现有表。不要对已有 MVP 1 数据库直接执行 `upgrade 0001_baseline`，否则会尝试重复创建表。

只回滚 0006 报告版本谱系字段、保留 0005 分析版本谱系：

```bash
alembic -c alembic.ini downgrade 0005_analysis_version_lineage
```

该操作会删除 `cases.report_version`、`cases.report_digest` 和 `ai_outputs.report_version`。只有在应用同步回滚到不依赖报告版本谱系的 0005 兼容版本时才能执行；已有报告输出本身不会被删除。

继续回滚 0005 分析版本谱系字段、保留 0004 工作流版本谱系：

```bash
alembic -c alembic.ini downgrade 0004_workflow_version_lineage
```

该操作会删除 `cases.analysis_version` 和 `ai_outputs.analysis_version`。只有在应用同步回滚到不依赖分析版本谱系的 0004 兼容版本时才能执行；已有分析输出本身不会被删除。

继续回滚 0004 工作流版本谱系字段、保留 0003 的脱敏表：

```bash
alembic -c alembic.ini downgrade 0003_demo_redactions
```

该操作会删除案件、事实、争点和 AI 输出上的 W1 版本谱系字段。只有在应用同步回滚到不依赖这些字段的 0003 兼容版本时才能执行；downgrade 不会恢复升级前已被回填或覆盖的业务语义。

继续回滚 0003 脱敏迁移、保留 0002 的 Document 字段与 `fact_sources`：

```bash
alembic -c alembic.ini downgrade 0002_mvp2_documents_fact_sources
```

该操作会删除 `redaction_records`、`redaction_items` 及其中全部脱敏版本数据。只有在确认不需要保留这些数据，并且应用同步回滚到兼容 0002 的版本时才能执行。

从当前 head 回滚 0006、0005、0004、0003 和 0002，恢复到 MVP 1 baseline：

```bash
alembic -c alembic.ini downgrade 0001_baseline
```

该操作除删除报告、分析与工作流版本谱系字段和脱敏表外，还会删除 `fact_sources` 和新增的 Document 字段。只有在确认不需要保留 Sprint 1A、脱敏与版本谱系数据、已完成备份，并且应用同步回滚到只依赖 MVP 1 schema 的版本时才能执行。

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
3. 默认停留在“工作流”，点击“运行 P0 标准工作流”。
4. 在“事实”接受、修改或驳回 AI 提取事实；在“争点”确认或补充争点。
5. 在“分析”查看结构化结论，并填写修改原因后接受、修改、驳回或补充材料重跑。
6. 返回“工作流”，批准任一待人工复核的工作单元并生成候选知识。
7. 批准沉淀后，在“法律记忆库”查看已沉淀条目；在“决策记录”查看完整时间线。

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
- `GET /documents/{document_id}/download-url`
- `GET /documents/{document_id}/download`
- `DELETE /cases/{case_id}/documents/{document_id}`
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
- `GET /cases/{case_id}/workspace`
- `GET /cases/{case_id}/work-units`
- `GET /work-units/{work_unit_id}`
- `POST /cases/{case_id}/work-units/{work_unit_id}/run`
- `POST /cases/{case_id}/workflow/run-standard`
- `POST /cases/{case_id}/work-units/{work_unit_id}/review`
- `GET /cases/{case_id}/facts`
- `POST /facts/{fact_id}/review`
- `GET /cases/{case_id}/issues`
- `POST /cases/{case_id}/issues`
- `PATCH /issues/{issue_id}`
- `POST /issues/{issue_id}/action`
- `DELETE /issues/{issue_id}`
- `POST /ai-outputs/{output_id}/review`
- `POST /work-units/{work_unit_id}/memory-candidate`
- `POST /memory/{memory_id}/decision`

## 替换真实 LLM

当前 AI 能力位于 `backend/app/agents/`。后续接入真实模型时，可以保持 API 不变，只替换 agent 内部实现，例如：

- `research_agent.py` 接入法律检索或 RAG
- `draft_agent.py` 接入文书生成模型
- `risk_agent.py` 接入证据缺口检查模型

这样前端和数据结构可以继续复用。
