# EduCreate-Smart-Class-Agent

师创智课 — 教育内容智能创作与课堂代理（EduCreate Smart Class Agent）

## 项目简介

面向教师的"智能备课"Web 应用，支持：
- 教学材料解析（PDF / Word / PPT / 图片 / 视频）
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
├── scripts/
│   └── push.ps1                   # 一键 git add + commit + push 脚本
├── docker-compose.yml             # 一键启动
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
| 后端 | Python 3.11 + FastAPI + SQLAlchemy + Alembic + Pydantic + Celery |
| 数据库 | PostgreSQL + pgvector（HNSW 索引）|
| 缓存 | Redis |
| 对象存储 | MinIO |
| LLM | DeepSeek 主用，OpenAI-compatible provider 兜底（通过 LangChain 适配）|
| Embedding | BGE-M3 + ColPali（视觉检索）|
| 重排 | bge-reranker-v2-m3 |
| 实时通信 | REST API 主通道 + SSE（Server-Sent Events）|
| 容器化 | Docker Compose |

> 当前仓库仍处于骨架阶段。上表中数据库、缓存、对象存储、LLM、Embedding、重排、实时通信等为架构选型和模块预留，代码中尚未完成真实接入。

## 快速开始

### 方式一：Docker Compose（推荐）

> 当前 Docker Compose 骨架阶段仅启动 `frontend` + `backend` 两个服务；PostgreSQL / Redis / MinIO / Celery Worker / 实时网关将在后续阶段接入。

```bash
# 在仓库根目录
docker compose up --build
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
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

验证：

```bash
pytest -q
curl http://127.0.0.1:8000/health
```

#### 2. 启动前端（新终端）

```bash
cd frontend
npm install
npm run dev
```

前端开发服务器默认在 `http://localhost:5173`，通过 Vite proxy 转发 `/api/*` 到 `http://localhost:8000`。

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
| `knowledge` | `/api/v1/knowledge` | 知识库 + 向量检索（pgvector） |
| `exports` | `/api/v1/exports` | 导出（.pptx / .docx / zip） |
| `gps` | `/api/v1/gps` | 教学意图澄清 |
| `quality` | `/api/v1/quality` | 大纲质量检测 |

详见 `http://localhost:8000/docs`。

## 当前阶段

✅ 已完成
- [x] 项目骨架（frontend + backend 双端）
- [x] 后端 8 个 API 路由占位（auth / teachers / materials / lessons / knowledge / exports / gps / quality）
- [x] 前端 10 个模块目录占位（features / stores / pages / components / flow / charts / preview / quality / ppt-export / services）
- [x] 后端 14 个服务层文件骨架（gps / pptagent / rag / llm / parsers / generators）
- [x] Docker Compose 一键启动 frontend + backend
- [x] README + .env.example
- [x] 一键推送脚本 `scripts/push.ps1`
- [x] 架构文档 `docs/ARCHITECTURE.md`
- [x] .gitignore 含外部参考材料 `基础/`
- [x] 前端五步工作台骨架（上传 → 澄清 → 大纲 → 预览 → 质检）
- [x] 前端路由跳转与 API base 配置对齐
- [x] 前端 `npm run build` 通过
- [x] 前端 `npm audit` 0 vulnerabilities
- [x] 后端 `pytest -q` 通过（4 passed）

⏳ 进行中（服务层骨架就绪，业务逻辑待填）
- [ ] PostgreSQL + pgvector 接入
- [ ] BGE-M3 嵌入服务接入
- [ ] LLM provider 抽象层接入 DeepSeek / fallback
- [ ] 参考资料解析流水线（PDF / Word / PPT / 图片 / 视频）
- [ ] 语音输入（Web Speech API + MediaRecorder fallback）
- [ ] GPS 教学意图结构化提取（gps/clarifier + reasoner + dag_builder）
- [ ] PPTAgent outline 生成 + 编辑 actions（pptagent/outliner + editor）
- [ ] 课件导出实现（安全版本 PptxGenJS 或等价导出方案）
- [ ] 教案 python-docx 生成
- [ ] 互动内容 Jinja2 模板生成
- [ ] 教师修改意见 → 再生成闭环
- [ ] 实时网关（WebTransport / WS / SSE）

## 当前验证结果

最近一次本地验证：

```bash
# frontend
npm run build
npm audit

# backend
pytest -q
```

结果：
- 前端构建通过。
- 前端依赖审计为 0 vulnerabilities。
- 后端测试通过：4 passed。
- 后端 pytest 在 Windows 中文路径下可能出现 `.pytest_cache` 写入警告，不影响测试结果。

## 已知边界

- 当前 API 和服务层多为占位实现，用于验证架构骨架和前后端联通。
- Docker Compose 当前只启动前端和后端，尚未接入数据库、缓存、对象存储和异步 Worker。
- `pptxgenjs` 因当前依赖链存在高危审计问题，暂未作为生产依赖安装；后续实现 `ppt-export` 时需重新评估安全版本或做图片输入隔离。
- `基础/` 为外部参考材料目录，已被 `.gitignore` 排除。

## 许可

待定
