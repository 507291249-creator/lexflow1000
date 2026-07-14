# 云端部署

本项目采用以下拆分部署：

- Vercel：部署 `frontend/` 中的 Next.js 前端。
- Render：部署 FastAPI 后端与 PostgreSQL 数据库。

## 1. 部署后端到 Render

1. 将项目推送到 GitHub、GitLab 或 Bitbucket。
2. 在 Render 中选择 New > Blueprint，并选择该仓库。
3. Render 会读取根目录的 `render.yaml`，创建 `lexflow-api` 服务。
4. 创建一个 Render Postgres 数据库，并将它的内部连接地址填入 `DATABASE_URL`。
5. 将 `CORS_ORIGINS` 设置为 Vercel 的生产地址，例如 `https://your-project.vercel.app`。
6. 在 Render 后端服务中新增 `OPENAI_API_KEY`；该密钥仅保存在服务端，用于新建 AI 案件的事实提取、争点识别和法律分析。
7. 可选新增 `OPENAI_MODEL`，例如 `gpt-4o-mini`。
8. 部署完成后，确认 `https://<render-service>.onrender.com/health` 返回正常结果。

## 2. 部署前端到 Vercel

1. 在 Vercel 中导入同一仓库。
2. 将 Root Directory 设置为 `frontend`。
3. 在 Vercel 项目环境变量中添加 `NEXT_PUBLIC_API_BASE`，值为 Render 后端地址，例如 `https://<render-service>.onrender.com`。
4. 部署后打开 Vercel 地址，确认首页能加载示例案件。

## 3. 文件上传说明

当前云端版本会在后端实例的临时目录中解析上传文件，并把解析后的文本和案件信息保存到 PostgreSQL。原始文件长期归档建议连接 Vercel Blob，并在生产环境中使用私有存储桶。

## 本地环境变量

前端可复制 `frontend/.env.example` 为 `frontend/.env.local`，并设置实际后端地址。

后端可设置以下环境变量：

- `DATABASE_URL`：PostgreSQL 连接地址；不设置时继续使用本地 SQLite。
- `CORS_ORIGINS`：允许访问 API 的前端地址，多个地址使用逗号分隔。
- `UPLOAD_DIR`：上传解析文件的临时目录。
- `OPENAI_API_KEY`：真实 LLM 的服务端密钥，不要设置到 Vercel 或任何 `NEXT_PUBLIC_` 变量中。
- `OPENAI_MODEL`：可选的 OpenAI 模型名称，默认 `gpt-4o-mini`。
