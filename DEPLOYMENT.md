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
- `CORS_ORIGINS`：允许访问 API 的前端地址，多个地址可使用逗号或空格分隔。
- `CORS_ORIGIN_REGEX`：可选的前端地址正则；需要使用 Vercel 预览部署时可设为 `https://.*\.vercel\.app`。
- `UPLOAD_DIR`：上传解析文件的临时目录。
- `LLM_PROVIDER`：模型提供方，支持 `openai`（默认）或 `zhipu`。
- `OPENAI_API_KEY`、`OPENAI_MODEL`：OpenAI 的服务端密钥和模型名称，默认模型为 `gpt-4o-mini`。
- `ZHIPU_API_KEY`、`ZHIPU_MODEL`：智谱 AI 的服务端密钥和模型名称，默认模型为 `glm-4-flash-250414`。
- `ZHIPU_BASE_URL`：可选的智谱网关地址，默认 `https://open.bigmodel.cn/api/paas/v4/`。
- `ALLOW_LOCAL_AI_FALLBACK`：本地可设为 `true` 以启用明确标记的备用解析；生产环境建议设为 `false`，让模型配置、调用或结构校验问题以“失败并可重试”的工作单元状态呈现。
