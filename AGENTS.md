# 项目协作规则

## 项目定位

本仓库是比赛级纯 Web 智能备课应用。比赛版优先保证可运行闭环、现场稳定和最少部署依赖；设计目标与当前实现有差异时，以代码和 `README.md` 的“当前阶段”为准，并同步修正 `docs/ARCHITECTURE.md`。

## 运行与验证

- 后端本地测试：在 `backend/` 运行 `pytest -q`。
- 前端门禁：在 `frontend/` 运行 `npm run build`。
- 比赛环境：在仓库根目录运行 `docker compose up --build -d`。
- Docker 冒烟检查：`docker compose ps`，并访问 `/health`、前端首页及本阶段新增接口。
- 数据库结构由 Alembic 管理；新增模型字段或表时必须同时生成迁移并验证升级。

## 架构边界

- Compose 当前只包含 frontend、backend、PostgreSQL + pgvector；不要在没有真实业务消费者时加入 Redis、Celery 或 MinIO。
- 本地开发默认 SQLite，Compose 使用 PostgreSQL；数据库代码和测试必须兼容两种模式。
- PPTX 和 DOCX 由后端固定生成器产生，不执行 LLM 返回的代码。
- OCR 仅处理图片及 PDF 无文本页，失败必须降级为 warning，不能导致已有文本解析失败。
- OCR 参数必须保留页数、DPI、像素、超时和并发边界；长耗时任务引入后再迁移到任务队列。
- 视频转写默认关闭模型下载；必须先通过 FFprobe/FFmpeg 校验和提取音频，失败只返回 warning，不生成虚假字幕。
- Whisper 模型不可随上传隐式联网下载；使用本地模型路径或显式开启下载，并持久化模型缓存。
- 比赛部署前使用 `scripts/prepare_whisper.ps1` 显式准备模型；上传侧保持 `VIDEO_ALLOW_MODEL_DOWNLOAD=false`，并通过 `VIDEO_WHISPER_MODEL_PATH` 指向已准备目录。
- Embedding 默认使用确定性 hash；BGE-M3 是可选 provider，缺失时必须可降级。

## 修改原则

- 保留用户已有改动，不覆盖无关文件。
- 新增环境变量时同步 `.env.example`、`backend/.env.example`、Compose 和相关文档。
- 每个阶段完成后运行相称的回归测试、构建、Docker 冒烟检查和 `git diff --check`，再提交。
- 提交信息使用中文并说明该阶段实际完成的能力。
