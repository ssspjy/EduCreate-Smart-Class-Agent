# EduCreate-Smart-Class-Agent

师创智课 — 教育内容智能创作与课堂代理（EduCreate Smart Class Agent）

## 项目简介

面向教师的比赛级“智能备课”纯 Web 应用，目标能力包括：
- 教学材料解析（PDF / DOCX / PPTX / Markdown / TXT；图片和视频保留上传接口）
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
│   └── ARCHITECTURE.md            # 架构文档（设计源）
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
| 前端 | React 18 + Vite + TypeScript + Ant Design + TanStack Query + Zustand + XState + React Flow + ECharts + PDF.js |
| 后端 | Python 3.11 + FastAPI + SQLAlchemy + Pydantic |
| 数据库 | 本地开发使用 SQLite；Docker Compose 使用 PostgreSQL 16 + pgvector |
| 文件存储 | 本地开发目录 / Docker 持久化卷 |
| LLM | DeepSeek 主用，OpenAI-compatible provider 兜底 |
| Embedding | BGE-M3 + ColPali（视觉检索）|
| 重排 | bge-reranker-v2-m3 |
| PPTX 导出 | 后端 `python-pptx` |
| 通信 | REST API；SSE 作为后续生成进度增强 |
| 容器化 | Docker Compose |

> 比赛版遵循“核心闭环真实可用、部署依赖最少化”的原则。Redis / Celery 只在 OCR、视频转写等耗时任务异步化后接入；MinIO、WebTransport 不作为比赛交付硬依赖。

## 快速开始

### 方式一：Docker Compose（推荐）

Docker Compose 启动 `frontend`、`backend`、`PostgreSQL + pgvector`，并为数据库和上传文件配置持久化卷。

```bash
# 在仓库根目录
docker compose up --build
```

数据库结构由 Alembic 管理。首次部署或升级后端时可执行：

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
npm audit
```

## 后端 API 路由（按 §3.2 文档）

| 模块 | 前缀 | 功能 |
|------|------|------|
| `auth` | `/api/v1/auth` | 登录 / 鉴权（OAuth2 + JWT） |
| `teachers` | `/api/v1/teachers` | 教师管理 |
| `materials` | `/api/v1/materials` | 参考资料上传 / 解析 |
| `lessons` | `/api/v1/lessons` | 教案 / 课件生成 |
| `knowledge` | `/api/v1/knowledge` | PostgreSQL 使用 pgvector 余弦检索；SQLite/无模型环境自动词法降级 |
| `exports` | `/api/v1/exports` | 使用 `python-pptx` / `python-docx` 生成和下载 `.pptx` / `.docx` |
| `gps` | `/api/v1/gps` | 教学意图澄清 |
| `quality` | `/api/v1/quality` | 大纲质量检测 |

本地开发详见 `http://localhost:8001/docs`；Docker Compose 模式详见 `http://localhost:8000/docs`。

## 当前阶段

✅ 已完成
- [x] 项目骨架（frontend + backend 双端）
- [x] 后端 8 个 API 路由占位（auth / teachers / materials / lessons / knowledge / exports / gps / quality）
- [x] 前端 10 个模块目录占位（features / stores / pages / components / flow / charts / preview / quality / ppt-export / services）
- [x] 后端 14 个服务层文件骨架（gps / pptagent / rag / llm / parsers / generators）
- [x] Docker Compose 一键启动 frontend + backend + PostgreSQL/pgvector
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
- [x] 图片 / 视频上传保存，但不伪造 OCR/字幕内容，等待后续 OCR / Whisper 接入
- [x] **阶段一完成**：意图澄清页面（ClarifyPage）完整实现，含 DAG 可视化、追问建议、提交后 session_id 持久化、GPT-4o 预览能力、Ant Design 五步进度条、Vite 代理端口修正（8001）
- [x] GPS 槽位提取、动态追问与 DAG 完成度计算
- [x] 基于 GPS 字段动态生成课件大纲
- [x] 后端 `python-pptx` 真实生成与下载 PPTX
- [x] 基于大纲结构的清晰度 / 覆盖度 / 互动性质检
- [x] DeepSeek / OpenAI-compatible LLM provider 抽象、重试与结构化输出校验

⏳ 进行中（服务层骨架就绪，业务逻辑待填）
- [x] 为 chunks 增加 1024 维向量字段、写入和 pgvector 检索查询（Compose 已提供 pgvector 数据库）
- [ ] BGE-M3 模型服务接入（当前支持 `EMBEDDING_PROVIDER=bge`，未安装模型时自动 hash 降级）
- [ ] OCR / 视频转写解析流水线（图片 / 视频）
- [ ] 语音输入（Web Speech API + MediaRecorder fallback）
- [ ] PPTAgent 参考页分析 + 编辑 actions + self-correction
- [x] 教案 python-docx 生成与下载
- [ ] 互动内容 Jinja2 模板生成
- [ ] 教师修改意见 → 再生成闭环
- [ ] 耗时任务异步化后接入 Redis + Celery，并通过 SSE 推送进度

## 当前验证结果

最近一次本地验证（2026-08-21，Python 3.12）：

```bash
# frontend
npm run build
npm audit

# backend
pytest -q
```

结果：

- 前端 TypeScript 检查和 Vite 生产构建通过。
- 后端测试通过：`55 passed`；存在 29 条 `datetime.utcnow()` 弃用警告，不影响当前结果。
- Compose YAML 静态解析通过，包含 `postgres`、`backend`、`frontend` 三个服务和两个持久化卷。
- 当前验证环境未安装 Docker，尚未在本机实际启动 PostgreSQL 容器。

测试使用 `backend/tests/_tmp/` 隔离 SQLite 数据库、上传文件和 pytest cache，避免污染开发数据。Docker 模式单独使用 PostgreSQL + pgvector。

## 已知边界

- GPS、动态大纲、规则质检和 PPTX 导出已有可运行实现；PPTAgent 的参考页编辑范式和模型增强仍需补齐。
- `/knowledge/search` 在 PostgreSQL 上已使用 chunks 的 pgvector 余弦检索；本地 SQLite 或未安装 BGE 模型时使用确定性的 hash embedding/词法降级。
- 本地直接运行默认使用 SQLite，数据位于 `backend/data/` 与 `backend/uploads/`；Docker 使用 PostgreSQL 和命名卷，测试数据位于 `backend/tests/_tmp/`。
- 比赛版正式 PPT 导出路径是后端 `python-pptx`；PptxGenJS 仅保留为未来浏览器内编辑的候选方案。
- Redis / Celery、MinIO 和 WebTransport 暂不进入比赛版运行时，除非对应业务能力真正接入。
- `基础/` 为外部参考材料目录，已被 `.gitignore` 排除。

## 许可

待定
