# 云端部署

本项目采用以下拆分部署：

- Vercel：部署 `frontend/` 中的 Next.js 前端。
- Render：部署 FastAPI 后端与 PostgreSQL 数据库。

## 1. 部署后端到 Render

1. 将项目推送到 GitHub、GitLab 或 Bitbucket。
2. 在 Render 中选择 New > Blueprint，并选择该仓库。
3. Render 会读取根目录的 `render.yaml`，创建 `lexflow-api` 服务。
4. 创建一个 Render Postgres 数据库，并将它的内部连接地址填入 `DATABASE_URL`。
5. 将 `CORS_ORIGINS` 设置为 Vercel 的生产地址，例如 `https://your-project.vercel.app`。多个地址可使用逗号或空格分隔；如需允许 Vercel 预览地址，可另设 `CORS_ORIGIN_REGEX=https://.*\.vercel\.app`。
6. 在 Render 后端服务中选择模型提供方并填入对应密钥；密钥仅保存在服务端，用于新建 AI 案件的事实提取、争点识别和法律分析。
   - OpenAI：`LLM_PROVIDER=openai`、`OPENAI_API_KEY`，可选 `OPENAI_MODEL=gpt-4o-mini`。
   - 智谱 AI：`LLM_PROVIDER=zhipu`、`ZHIPU_API_KEY`，可选 `ZHIPU_MODEL=glm-4-flash-250414`。
   - 智谱默认使用 `https://open.bigmodel.cn/api/paas/v4/`；只有在使用专属网关时才设置 `ZHIPU_BASE_URL`。
8. 部署完成后，确认 `https://<render-service>.onrender.com/health` 返回正常结果。

## 1.1 PostgreSQL 迁移

Sprint 1A 引入 Alembic。当前迁移链只有一个 head：`0003_demo_redactions`。迁移命令应在 Render 后端实例或使用同一 `DATABASE_URL` 的受控终端中执行，工作目录为 `/app`。生产 Runbook 使用明确 revision，避免未来新增 migration 后旧 Runbook 意外越过已验证边界。

### 全新 PostgreSQL

```bash
cd /app
alembic -c alembic.ini upgrade 0003_demo_redactions
alembic -c alembic.ini current
```

预期当前版本为：

```text
0003_demo_redactions (head)
```

### 已有 MVP 1 PostgreSQL

先使用 Render 的数据库备份功能，或在可访问数据库的安全终端执行：

```bash
pg_dump "$DATABASE_URL" --format=custom --file=lexflow-before-mvp2.dump
```

确认备份完成后，检查数据库尚未登记 Alembic 版本：

```bash
cd /app
alembic -c alembic.ini current
```

如果没有输出版本，并且数据库中已经存在 MVP 1 的业务表，执行：

```bash
alembic -c alembic.ini stamp 0001_baseline
alembic -c alembic.ini upgrade 0003_demo_redactions
alembic -c alembic.ini current
```

不要对已有业务表直接运行 `upgrade 0001_baseline`。`0001_baseline` 用于描述旧结构；线上旧库通过 `stamp` 登记该版本，真正的数据结构修改从 `0002` 开始。

### 验证

```bash
alembic -c alembic.ini current
alembic -c alembic.ini heads
```

另外在 PostgreSQL 中确认：

```sql
SELECT version_num FROM alembic_version;
SELECT original_filename, mime_type, processing_status, storage_provider
FROM documents
ORDER BY id
LIMIT 20;
SELECT indexname FROM pg_indexes
WHERE tablename IN ('documents', 'fact_sources', 'redaction_records', 'redaction_items')
ORDER BY tablename, indexname;
```

`alembic current` 与 `SELECT version_num` 均必须显示 `0003_demo_redactions`。另外确认 `redaction_records` 和 `redaction_items` 存在，且上述四张表的预期索引完整。

### 回滚边界

只回滚 0003、保留 0002 的 Document 字段与 `fact_sources`：

```bash
cd /app
alembic -c alembic.ini downgrade 0002_mvp2_documents_fact_sources
alembic -c alembic.ini current
```

该操作会删除 `redaction_records`、`redaction_items` 及其中全部脱敏版本数据。只有在确认不需要保留这些数据，并且应用同步回滚到兼容 0002 的版本时才能执行。

从当前 head 同时回滚 0003 和 0002、恢复到 MVP 1 baseline：

```bash
cd /app
alembic -c alembic.ini downgrade 0001_baseline
alembic -c alembic.ini current
```

该操作除删除脱敏表外，还会删除 `fact_sources` 及 Document 新字段。只有在确认不需要保留 Sprint 1A 与脱敏数据、已完成备份，并且应用同步回滚到只依赖 MVP 1 schema 的版本时才能执行。

## 1.2 生产迁移到 0003 Runbook

以下步骤适用于生产 PostgreSQL 从未登记 Alembic 的 MVP 1 结构、`0001_baseline` 或 `0002_mvp2_documents_fact_sources` 升级到当前唯一 head `0003_demo_redactions`。执行人必须同时具备 Render 服务管理权限、数据库备份权限和数据库连接权限。整个迁移窗口内不要进行其他应用或数据库部署。

### 步骤 1：备份生产 PostgreSQL

**前置条件**：确认 `DATABASE_URL` 指向生产 PostgreSQL，并在安全终端中操作；不要把连接串写入仓库或聊天记录。

优先使用 Render 数据库页面提供的快照或备份。如果使用命令行，执行：

```bash
mkdir -p migration-backups
pg_dump "$DATABASE_URL" --format=custom --no-owner \
  --file="migration-backups/lexflow-before-mvp2-$(date +%Y%m%d-%H%M%S).dump"
pg_restore --list migration-backups/lexflow-before-mvp2-*.dump | head
```

只有 `pg_dump` 返回 0 且 `pg_restore --list` 能读取目录时才继续。若备份失败，立即停止，不得 stamp 或 upgrade；先检查磁盘空间、数据库权限和网络连接。

### 步骤 2：记录当前应用版本

**前置条件**：生产服务当前健康检查正常。

```bash
git rev-parse HEAD
git status --short
curl --fail --show-error "https://<render-service>.onrender.com/health"
```

把 commit SHA、Render 当前部署 ID、迁移时间和执行人记录到变更单。工作区必须干净；如 `git status` 有未提交内容，应改用仓库中的已发布 commit，不要从该目录部署。

### 步骤 3：暂停自动部署和业务写入

**前置条件**：已确定维护窗口并通知使用者。

在 Render 服务设置中暂时关闭 Auto-Deploy。停止前端操作，确保没有正在进行的案件创建、材料上传或人工复核。当前 MVP 没有维护模式时，应暂时限制前端访问，或短时停止 Web Service。

如果无法可靠阻止写入，不执行迁移。数据库迁移期间出现新写入会使备份恢复点与实际状态分叉。

### 步骤 4：只读审计生产 schema

**前置条件**：使用只读数据库账号；如只能使用所有者账号，脚本自身仍会开启只读事务。

```bash
cd backend
psql "$DATABASE_URL" -v schema_name=public \
  -f scripts/audit_production_schema.sql \
  | tee "../migration-backups/production-schema-before.txt"
```

确认 `missing_mvp1_table` 没有返回记录，且关键检查全部为 `t`。如果已经存在 `alembic_version`，先确认其值：如果是 `0003_demo_redactions`，不要重复 stamp 或 upgrade，转到步骤 7；如果是 `0001_baseline` 或 `0002_mvp2_documents_fact_sources`，不要 stamp，继续执行步骤 6；如果是其他 revision、出现多个 revision 或结构包含未记录的手工改动，停止迁移并先做差异评审。

将线上结构与 `0001_baseline` 比对时，在**另一个临时 PostgreSQL 数据库**执行：

```bash
export DATABASE_URL="postgresql://.../lexflow_baseline_check"
cd backend
alembic -c alembic.ini upgrade 0001_baseline
psql "$DATABASE_URL" -v schema_name=public \
  -f scripts/audit_production_schema.sql \
  > ../migration-backups/baseline-schema.txt
```

对比两个审计文件中的表清单、字段明细、`column_signature`、索引和外键。也可分别执行 `pg_dump --schema-only --no-owner --no-privileges` 后使用 `diff -u`。允许的差异必须逐项记录；未解释差异会阻止 stamp。

### 步骤 5：登记 baseline

**前置条件**：生产库确认为未登记 Alembic 的 MVP 1 结构，备份和 schema 比对均通过。

```bash
cd /app
alembic -c alembic.ini current
alembic -c alembic.ini stamp 0001_baseline
alembic -c alembic.ini current
```

预期当前版本为 `0001_baseline`。`stamp` 不修改业务表。如果 `current` 原本已有版本，或 stamp 后不是该版本，立即停止，不运行 upgrade；先核查 `alembic_version` 和连接的数据库是否正确。

### 步骤 6：升级到 head

**前置条件**：应用写入已停止，当前版本已确认是 `0001_baseline` 或 `0002_mvp2_documents_fact_sources`；未登记 Alembic 的 MVP 1 旧库必须先完成步骤 5。

```bash
alembic -c alembic.ini upgrade 0003_demo_redactions
alembic -c alembic.ini current
```

预期为 `0003_demo_redactions (head)`。若命令失败，不要启动新版本应用，也不要反复执行未知状态的命令；先保存完整日志，运行只读审计确认事务是否已回滚。PostgreSQL DDL 在本迁移中应随事务回滚，确认版本仍为升级前的 `0001` 或 `0002` 后再定位错误。

### 步骤 7：验证迁移和回填

**前置条件**：`upgrade 0003_demo_redactions` 成功，或步骤 4 已确认数据库原本就在 `0003_demo_redactions`。

再次运行审计脚本，并执行：

```sql
SELECT version_num FROM alembic_version;
SELECT id, filename, original_filename, mime_type, processing_status,
       storage_provider, updated_at, uploaded_at, file_size, checksum, storage_key
FROM documents
ORDER BY id
LIMIT 100;
SELECT count(*) FROM fact_sources;
SELECT to_regclass('public.redaction_records') AS redaction_records_table,
       to_regclass('public.redaction_items') AS redaction_items_table;
SELECT count(*) FROM redaction_records;
SELECT count(*) FROM redaction_items;
SELECT tablename, indexname
FROM pg_indexes
WHERE schemaname = 'public'
  AND tablename IN ('redaction_records', 'redaction_items')
ORDER BY tablename, indexname;
```

确认 `version_num` 为 `0003_demo_redactions`，两张脱敏表及其预期索引存在。确认文件名、MIME、状态和时间回填符合规则，无法推断的 size/checksum/storage_key 为 `NULL`。对迁移前后各业务表执行 `SELECT count(*)`，记录数量并核对无意外减少。任何版本、结构或数据不一致都应停止部署并进入恢复流程。

### 步骤 8：部署应用

**前置条件**：数据库验证通过，待部署 commit 已通过 Sprint 1A.5 测试。

部署记录的 commit，确认 Render 构建日志中依赖安装成功。暂时保持 Auto-Deploy 关闭，以便出现问题时能够控制回滚。应用启动后先只访问健康检查，不立即开放前端写入。

PostgreSQL 环境不会在应用启动时执行 `create_all()`，也不会动态补齐 Sprint 1A 字段或 0003 脱敏表，因此第 6 步的 Alembic 升级是强制前置条件。若跳过迁移，应用应保持停止状态，而不是依赖启动逻辑修改生产结构。

如果应用启动失败，优先保留数据库在 `0003_demo_redactions`，回滚到兼容 0003 的前一个已验证应用 commit；不要在应用仍读取脱敏表或 Document 新字段时 downgrade 数据库。

### 步骤 9：冒烟测试

**前置条件**：`/health` 返回 200，后端日志无数据库字段错误。

按顺序验证：案件列表、旧案件读取、新建测试案件、材料上传、脱敏检测与确认、事实提取、批量确认事实、争点识别、批量确认争点、法律分析、人工批准、最终报告。随后检查：

```sql
SELECT id, version, fact_version, issue_version, review_status
FROM ai_outputs ORDER BY id DESC LIMIT 20;
SELECT id, case_id, action, object_type, created_at
FROM decision_traces ORDER BY id DESC LIMIT 20;
```

全部通过后恢复前端访问并重新开启 Auto-Deploy。若业务链路失败，保持维护状态，收集对应请求日志和数据库记录，再决定仅回滚应用还是执行完整数据库恢复。

### 步骤 10：恢复策略

**优先策略：应用回滚**。如果 0003 已成功且数据完整，但新应用有问题，部署兼容 `0003_demo_redactions` 的已验证 commit；不要删除新表或新字段。

**只回滚 0003** 仅适用于确认没有脱敏版本数据需要保留，且应用也将同步回滚到兼容 0002 的情况：

```bash
cd /app
alembic -c alembic.ini downgrade 0002_mvp2_documents_fact_sources
alembic -c alembic.ini current
```

**回滚到 MVP 1 baseline** 仅适用于确认没有 Sprint 1A 与脱敏数据需要保留，且应用也将同步回滚到只依赖 MVP 1 schema 的情况：

```bash
cd /app
alembic -c alembic.ini downgrade 0001_baseline
alembic -c alembic.ini current
```

**备份恢复** 用于迁移造成数据不一致或 downgrade 无法修复的情况。先隔离错误数据库，创建新的空 PostgreSQL 实例，再使用：

```bash
pg_restore --clean --if-exists --no-owner \
  --dbname="$RESTORE_DATABASE_URL" migration-backups/lexflow-before-mvp2-*.dump
```

恢复后先做只读审计和数据计数，再将应用切换到恢复库。不要在原生产库上边写入边恢复。

### 自动化验证

仓库中的 `.github/workflows/mvp2-sprint1a5-validation.yml` 会启动 PostgreSQL 18 临时服务并执行 `pytest -q`。本地也可使用任意临时 PostgreSQL：

```bash
cd backend
export TEST_POSTGRES_URL="postgresql://postgres:postgres@127.0.0.1:5432/postgres"
python -m pip install -r requirements.txt
pytest -q
```

测试会自行创建并删除随机命名的临时数据库，不会修改 `TEST_POSTGRES_URL` 指向的管理数据库中的业务表。该账号必须具备 `CREATE DATABASE` 和 `DROP DATABASE` 权限。

## 2. 部署前端到 Vercel

1. 在 Vercel 中导入同一仓库。
2. 将 Root Directory 设置为 `frontend`。
3. 在 Vercel 项目环境变量中添加 `NEXT_PUBLIC_API_BASE`，值为 Render 后端地址，例如 `https://<render-service>.onrender.com`。
4. 部署后打开 Vercel 地址，确认首页能加载示例案件。

## 3. 私有对象存储

Sprint 1B 起，新上传的原始材料必须写入私有的 S3 兼容对象存储，Render 的 `/tmp` 只用于解析期间的临时下载，不再承担原始文件持久化。可使用 Cloudflare R2 或标准 S3 兼容服务，业务代码通过 `StorageService` 访问，不绑定供应商 SDK。

### 3.1 创建存储桶和凭据

1. 创建一个专用于 LexFlow 的私有存储桶，不开启公开访问和静态网站托管。
2. 创建仅供后端使用的访问凭据，至少授予该桶的对象读取、写入、删除和列举/检查权限。
3. 不要把访问密钥写入仓库、Vercel 或浏览器端变量；只保存到 Render 后端服务的 Secret 环境变量。
4. Cloudflare R2 的 endpoint 通常形如 `https://<account-id>.r2.cloudflarestorage.com`，区域可填写 `auto`。其他 S3 服务按供应商给出的 endpoint 和 region 配置。

### 3.2 Render 环境变量

在 `lexflow-api` 的 Environment 页面配置：

```text
STORAGE_PROVIDER=r2
S3_ENDPOINT_URL=https://<account-id>.r2.cloudflarestorage.com
S3_ACCESS_KEY_ID=<仅保存在 Render 的访问密钥 ID>
S3_SECRET_ACCESS_KEY=<仅保存在 Render 的访问密钥>
S3_BUCKET_NAME=<私有桶名称>
S3_REGION=auto
MAX_UPLOAD_SIZE_BYTES=20971520
```

标准 S3 兼容服务可将 `STORAGE_PROVIDER` 改为 `s3`。保存变量后手动部署当前版本。生产环境不要把 `STORAGE_PROVIDER` 留空或设置为 `local`；代码检测到 Render 环境但没有该变量时会拒绝文件存储请求，避免静默回退到实例文件系统。

### 3.3 云端验证

1. 新建测试案件并上传一个小型 TXT、PDF 或 DOCX。
2. 材料页应显示存储提供方、大小、类型、状态和上传时间，状态最终为“已就绪”。
3. 在对象存储控制台确认对象键符合 `cases/<case_id>/documents/<document_id>/<checksum>-<filename>`。
4. 点击下载，确认能够通过短期签名地址取得原文件；签名地址约 5 分钟后应失效。
5. 删除测试材料，确认数据库记录和桶内对象同时消失。
6. 检查 Render 日志，确认错误信息未输出访问密钥。不要把签名 URL 粘贴到公开日志，因为它在有效期内具有临时读取权限。

若上传失败，Document 会保留错误状态以便排查；若解析失败，原始对象仍会保留。旧 `legacy_local` 材料不会自动迁移，页面会说明原始文件可能不可用，但继续展示已解析文本。

## 本地环境变量

前端可复制 `frontend/.env.example` 为 `frontend/.env.local`，并设置实际后端地址。

后端可设置以下环境变量：

- `DATABASE_URL`：PostgreSQL 连接地址；不设置时继续使用本地 SQLite。
- `CORS_ORIGINS`：允许访问 API 的前端地址，多个地址可使用逗号或空格分隔。
- `CORS_ORIGIN_REGEX`：可选的前端地址正则；需要使用 Vercel 预览部署时可设为 `https://.*\.vercel\.app`。
- `STORAGE_PROVIDER`：本地为 `local`；生产使用 `r2` 或 `s3`。
- `UPLOAD_DIR`：仅在 `STORAGE_PROVIDER=local` 时使用的本地目录。
- `S3_ENDPOINT_URL`、`S3_ACCESS_KEY_ID`、`S3_SECRET_ACCESS_KEY`、`S3_BUCKET_NAME`、`S3_REGION`：私有 S3 兼容对象存储配置。
- `MAX_UPLOAD_SIZE_BYTES`：单文件大小上限，默认 `20971520`（20 MiB）。
- `LLM_PROVIDER`：模型提供方，支持 `openai`（默认）或 `zhipu`。
- `OPENAI_API_KEY`、`OPENAI_MODEL`：OpenAI 的服务端密钥和模型名称，默认模型为 `gpt-4o-mini`。
- `ZHIPU_API_KEY`、`ZHIPU_MODEL`：智谱 AI 的服务端密钥和模型名称，默认模型为 `glm-4-flash-250414`。
- `ZHIPU_BASE_URL`：可选的智谱网关地址，默认 `https://open.bigmodel.cn/api/paas/v4/`。
- `ALLOW_LOCAL_AI_FALLBACK`：本地可设为 `true` 以启用明确标记的备用解析；生产环境建议设为 `false`，让模型配置、调用或结构校验问题以“失败并可重试”的工作单元状态呈现。
