# EduCreate-Smart-Class-Agent

师创智课 — 教育内容智能创作与课堂代理（EduCreate Smart Class Agent）

## 项目简介

面向教师的比赛级“智能备课”纯 Web 应用，目标能力包括：
- 教学材料解析（PDF / DOCX / PPTX / Markdown / TXT、图片和扫描 PDF OCR，以及可选视频/语音转写）
- 多轮对话澄清教学意图（GPS 模块）
- 课件与教案生成（PPTAgent 模块）
- 知识库检索增强（BGE-M3 + pgvector）
- 迭代优化与导出（.pptx / .docx）

完整设计见 [`docs/ARCHITECTURE.md`](./docs/ARCHITECTURE.md)。

## 目录结构

```
EduCreate-Smart-Class-Agent/
├── backend/                       # FastAPI 后端（按 §3.2 文档对齐）
├── frontend/                      # React + Vite + TS 前端（按 §3.1 文档对齐）
├── docs/
│   ├── ARCHITECTURE.md            # 架构文档（设计源）
│   ├── ASYNC_TASKS.md             # 材料任务队列、API 与运维说明
│   ├── PPTAGENT.md                # 参考 PPT 分析、编辑动作与导出版本说明
│   └── INTERACTIVE.md             # 课堂互动内容 API 与模板说明
├── docker/
│   └── postgres/init.sql           # Compose 初始化 pgvector 扩展
├── scripts/
│   └── push.ps1                   # 一键 git add + commit + push 脚本
├── docker-compose.yml             # 一键启动
├── .env.example                   # Compose 数据库配置示例
├── 基础/                          # 外部参考材料（不纳入 git 跟踪）
│   ├── 技术栈.md
│   ├── 任务要求.md
│   ├── GPS(1).pdf
│   └── PPTAgent(1).pdf
└── README.md
```

## 技术栈

| 维度 | 选型 |
|------|------|
| 前端 | React 18 + Vite + TypeScript + Ant Design + TanStack Query + Zustand + XState + React Flow + ECharts + PDF.js + Web Speech API + MediaRecorder + Vitest |
| 后端 | Python 3.11 + FastAPI + SQLAlchemy + Pydantic |
| 数据库 | 本地开发使用 SQLite；Docker Compose 使用 PostgreSQL 16 + pgvector |
| 文件存储 | 本地开发目录 / Docker 持久化卷 |
| LLM | DeepSeek 主用，OpenAI-compatible provider 兜底 |
| Embedding | PostgreSQL pgvector；默认 hash embedding，可选 BGE-M3 provider |
| OCR | PDFium + Pillow + Tesseract（简体中文 / 英文） |
| 视频 | FFmpeg + 可选 `faster-whisper`（模型显式配置） |
| 任务队列 | Compose 使用 Redis + Celery；本地默认同步解析 |
| 重排 | 词法/向量基础召回；bge-reranker-v2-m3 待接入 |
| PPTX 导出 | 后端 `python-pptx` |
| 通信 | REST API；SSE 作为后续生成进度增强 |
| 容器化 | Docker Compose |

> 比赛版遵循“核心闭环真实可用、部署依赖最少化”的原则。Compose 已用 Redis / Celery 承担 OCR、视频和音频解析；本地 SQLite 开发仍可同步解析。MinIO、WebTransport 不作为比赛交付硬依赖。

## 快速开始

### 方式一：Docker Compose（推荐）

Docker Compose 启动 `frontend`、`backend`、`worker`、`Redis`、`PostgreSQL + pgvector`，并为数据库、任务消息和上传文件配置持久化卷。
后端镜像同时安装 Tesseract 中英文语言包，可直接识别图片和扫描版 PDF。OCR 参数与排障方法见 [`docs/OCR.md`](./docs/OCR.md)。

| 常用 OCR 配置 | 默认值 | 说明 |
|---|---:|---|
| `OCR_ENABLED` | `true` | 启用图片和扫描 PDF OCR |
| `OCR_LANGUAGE` | `chi_sim` | 中文优先模型也可识别拉丁字母；纯英文资料可改为 `eng` |
| `OCR_DPI` | `200` | PDF 页面渲染清晰度 |
| `OCR_MAX_PAGES` | `30` | 单个 PDF 的 OCR 页数上限 |
| `OCR_TIMEOUT_SECONDS` | `30` | 单页识别超时秒数 |
| `OCR_MAX_PIXELS` | `20000000` | 单页进入识别前的像素上限 |

视频转写默认关闭，模型路径、下载策略和 Docker 卷配置见 [`docs/VIDEO.md`](./docs/VIDEO.md)。

```bash
# 在仓库根目录
docker compose up --build
```

数据库结构由 Alembic 管理，后端容器启动时会自动迁移；已有的 `create_all` 比赛数据卷会先安全标记基线再升级。需要手动核对时可执行：

```bash
docker compose exec backend alembic -c alembic.ini upgrade head
```

启动后访问：

| 端点 | 地址 |
|------|------|
| 前端 SPA | http://localhost:5173 |
| 后端 API | http://localhost:8000 |
| 后端交互式文档 | http://localhost:8000/docs |
| 健康检查 | http://localhost:8000/health |

### 方式二：本地开发模式

> ⚠️ **Windows 提示**：`requirements.txt` 必须保持 **ASCII 编码**（只用英文注释），否则 pip 在 Windows 默认 GBK 环境下会报 `UnicodeDecodeError: 'gbk' codec can't decode byte 0x89`。

#### 1. 启动后端

```bash
cd backend
python -m venv .venv
# Windows PowerShell（首次需要放开执行策略）
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
.venv\Scripts\Activate.ps1
# Linux / macOS
source .venv/bin/activate

pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8001
```

验证：

```bash
pytest -q
curl http://127.0.0.1:8001/health
```

#### 2. 启动前端（新终端）

```bash
cd frontend
npm install
npm run dev
```

前端开发服务器默认在 `http://localhost:5173`，通过 Vite proxy 转发 `/api/*` 到本地后端 `http://localhost:8001`。Docker 模式由 Nginx 转发到容器内的 `backend:8000`。

验证：

```bash
npm run build
npm test
npm audit
```

## 后端 API 路由（按 §3.2 文档）

| 模块 | 前缀 | 功能 |
|------|------|------|
| `auth` | `/api/v1/auth` | 登录 / 鉴权（OAuth2 + JWT） |
| `teachers` | `/api/v1/teachers` | 教师管理 |
| `materials` | `/api/v1/materials` | 参考资料上传、后台解析、进度查询与取消 |
| `lessons` | `/api/v1/lessons` | 教案 / 课件生成 |
| `knowledge` | `/api/v1/knowledge` | PostgreSQL 使用 pgvector 余弦检索；SQLite/无模型环境自动词法降级 |
| `exports` | `/api/v1/exports` | 使用 `python-pptx` / `python-docx` 生成和下载 `.pptx` / `.docx` |
| `gps` | `/api/v1/gps` | 教学意图澄清 |
| `quality` | `/api/v1/quality` | 大纲质量检测 |

本地开发详见 `http://localhost:8001/docs`；Docker Compose 模式详见 `http://localhost:8000/docs`。

## 当前阶段

✅ 已完成
- [x] 项目骨架（frontend + backend 双端）
- [x] 后端 API 路由（auth / teachers / materials / lessons / knowledge / exports / gps / quality / pptagent / interactive）
- [x] 前端 10 个模块目录占位（features / stores / pages / components / flow / charts / preview / quality / ppt-export / services）
- [x] 后端 14 个服务层文件骨架（gps / pptagent / rag / llm / parsers / generators）
- [x] Docker Compose 一键启动 frontend + backend + PostgreSQL/pgvector
- [x] Redis + Celery 材料解析 Worker，支持进度轮询、协作式取消和 Web 进程故障降级
- [x] README + .env.example
- [x] 一键推送脚本 `scripts/push.ps1`
- [x] 架构文档 `docs/ARCHITECTURE.md`
- [x] .gitignore 含外部参考材料 `基础/`
- [x] 前端五步工作台骨架（上传 → 澄清 → 大纲 → 预览 → 质检）
- [x] 前端路由跳转与 API base 配置对齐
- [x] 前端 `npm run build` 通过
- [x] 前端 `npm audit` 0 vulnerabilities
- [x] 后端测试覆盖健康检查、材料、GPS、LLM、导出与流程接口
- [x] SQLite 默认数据库与核心表自动建表（materials / chunks / lessons / lesson_irs / generation_jobs / generated_artifacts / edit_requests / rag_evidences）
- [x] 参考资料安全上传落盘（UUID 目录、扩展名白名单、大小限制）
- [x] PDF / DOCX / PPTX 文本解析并写入 chunks
- [x] 图片及扫描 PDF 使用 Tesseract 中英文 OCR，保留页码和 `ocr` 模态；失败时明确降级告警
- [x] 视频 FFmpeg 探测、音频提取和可选 Whisper 转写接口（默认关闭模型下载）
- [x] Whisper 模型显式预下载脚本与模型缺失/时长上限防护
- [x] 澄清页 Web Speech API 语音输入与 MediaRecorder 音频转写回退
- [x] 上传页支持 PDF/Office/图片/MP4 选择、服务端材料同步、解析 warning 和 chunk/页码/视频时间戳抽屉预览
- [x] 前端 Vitest 回归门禁（材料可用状态、上传格式和来源标签）
- [x] **阶段一完成**：意图澄清页面（ClarifyPage）完整实现，含 DAG 可视化、追问建议、提交后 session_id 持久化、GPT-4o 预览能力、Ant Design 五步进度条、Vite 代理端口修正（8001）
- [x] GPS 槽位提取、动态追问与 DAG 完成度计算
- [x] 基于 GPS 字段动态生成课件大纲
- [x] 后端 `python-pptx` 真实生成与下载 PPTX
- [x] 基于大纲结构的清晰度 / 覆盖度 / 互动性质检
- [x] DeepSeek / OpenAI-compatible LLM provider 抽象、重试与结构化输出校验

⏳ 进行中（服务层骨架就绪，业务逻辑待填）
- [x] 为 chunks 增加 1024 维向量字段、写入和 pgvector 检索查询（Compose 已提供 pgvector 数据库）
- [ ] BGE-M3 模型服务接入（当前支持 `EMBEDDING_PROVIDER=bge`，未安装模型时自动 hash 降级）
- [x] 图片 / 扫描 PDF OCR 解析流水线
- [ ] 视频转写模型在比赛环境预下载并完成真实长视频验收
- [x] 语音输入（Web Speech API + MediaRecorder fallback；录音在 Compose 中后台转写）
- [x] PPTAgent PPTX 参考页结构分析 + 严格校验编辑 actions + python-pptx 安全重渲染
- [x] 教师自然语言修改意见改写为安全结构化动作，并在预览页确认应用
- [x] 教案 python-docx 生成与下载
- [ ] 互动内容 Jinja2 模板生成
- [x] 教师修改意见 → 结构化动作 → 预览页确认 → 再生成闭环
- [x] 选择题 / 判断题 / 填空题固定模板生成与 sandbox 预览
- [x] OCR / 视频 / 音频解析接入 Redis + Celery，前端轮询任务进度并支持取消
- [ ] 使用 SSE 替代材料状态轮询，并扩展到课件生成任务

## 当前验证结果

2026-08-21 本地验证（Python 3.12）：

```bash
# frontend
npm test
npm run build
npm audit

# backend
pytest -q
```

结果（阶段十三验证）：

- 前端 Vitest `5 passed`，TypeScript 检查和 Vite 生产构建通过。
- 后端测试通过：`83 passed`；仍有 `datetime.utcnow()` 弃用警告，不影响当前结果。
- Compose 中 `postgres`、`redis`、`backend`、`worker`、`frontend` 已实际启动并通过健康检查或任务消费检查。
- 已用无文本层 PDF 验证 Docker 内中英文 Tesseract 运行链路，OCR chunk 带页码和模态信息。
- 已在 Docker 容器内生成并上传带音轨的 MP4，FFprobe/FFmpeg 链路通过；默认关闭 Whisper 时保留视频并返回明确 warning，不生成虚假字幕。
- 已通过显式模型准备脚本下载 tiny 模型，并在临时开启转写的后端容器中完成真实短视频上传，生成带时间戳的 transcript chunk；验证后已恢复默认关闭转写。
- 已验证 WebM 音频材料可上传并进入解析链路；MediaRecorder 回退会把真实录音交给后端，Whisper 未启用时返回 warning 而不伪造输入。

测试使用 `backend/tests/_tmp/` 隔离 SQLite 数据库、上传文件和 pytest cache，避免污染开发数据。Docker 模式单独使用 PostgreSQL + pgvector。

## 已知边界

- GPS、动态大纲、规则质检、PPTX 导出和互动内容生成已有可运行实现；PPTAgent 当前支持 PPTX 结构统计、教师自然语言意见改写、章节顺序/要点编辑、三种固定主题和导出版本记录，LLM 增强与复杂自由排版仍是后续增强。
- `/knowledge/search` 在 PostgreSQL 上已使用 chunks 的 pgvector 余弦检索；本地 SQLite 或未安装 BGE 模型时使用确定性的 hash embedding/词法降级。
- Compose 中 OCR、视频和音频解析由单并发 Celery worker 执行；进度当前通过材料列表轮询，SSE 属于后续增强。本地开发默认同步执行以保持零额外服务依赖。
- 视频转写默认不下载模型；启用后由 Worker 使用持久化模型卷，仍需在赛前监控模型缓存和单任务耗时。
- 本地直接运行默认使用 SQLite，数据位于 `backend/data/` 与 `backend/uploads/`；Docker 使用 PostgreSQL 和命名卷，测试数据位于 `backend/tests/_tmp/`。
- 比赛版正式 PPT 导出路径是后端 `python-pptx`；PptxGenJS 仅保留为未来浏览器内编辑的候选方案。
- Redis / Celery 已作为材料解析的真实运行时依赖；MinIO 和 WebTransport 仍不进入比赛版运行时。
- `基础/` 为外部参考材料目录，已被 `.gitignore` 排除。

## 许可

待定
