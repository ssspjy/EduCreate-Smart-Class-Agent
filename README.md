# EduCreate-Smart-Class-Agent

师创智课 — 教育内容智能创作与课堂代理（EduCreate Smart Class Agent）

## 项目简介

面向教师的"备课—课堂—反馈"全流程智能体，支持：
- 教学材料解析（PDF / Word / PPT / 图片 / 视频）
- 多轮对话澄清教学意图（GPS 模块）
- 课件与教案生成（PPTAgent 模块）
- 课堂互动内容生成（动画 / 小游戏）
- 知识库检索增强（BGE-M3 + pgvector + ColPali）
- 迭代优化与导出（.pptx / .docx / html5）

完整设计见 [`docs/ARCHITECTURE.md`](./docs/ARCHITECTURE.md)。

## 目录结构

```
EduCreate-Smart-Class-Agent/
├── backend/                       # FastAPI 后端（按 §3.2 文档对齐）
├── frontend/                      # React + Vite + TS 前端（按 §3.1 文档对齐）
├── docs/
│   └── ARCHITECTURE.md            # 架构文档（设计源）
├── docker-compose.yml             # 一键启动
├── 技术栈.md                       # 技术栈清单
├── 任务要求.md                     # 比赛任务说明
└── README.md
```

## 技术栈

| 维度 | 选型 |
|------|------|
| 前端 | React 18 + Vite + TypeScript + Ant Design + TanStack Query + Zustand + XState + React Flow + ECharts + PDF.js + PptxGenJS |
| 后端 | Python 3.11 + FastAPI + SQLAlchemy + Alembic + Pydantic + Celery |
| 数据库 | PostgreSQL + pgvector（HNSW 索引）|
| 缓存 | Redis |
| 对象存储 | MinIO |
| LLM | DeepSeek / Qwen（通过 LangChain 适配）|
| Embedding | BGE-M3 + ColPali（视觉检索）|
| 重排 | bge-reranker-v2-m3 |
| 实时通信 | WebTransport 主通道 + WebSocket / SSE 降级 |
| 容器化 | Docker Compose |

## 快速开始

### 方式一：Docker Compose（推荐）

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

#### 2. 启动前端（新终端）

```bash
cd frontend
npm install
npm run dev
```

前端开发服务器默认在 `http://localhost:5173`，通过 Vite proxy 转发 `/api/*` 到 `http://localhost:8000`。

## 后端 API 路由（按 §3.2 文档）

| 模块 | 前缀 | 功能 |
|------|------|------|
| `auth` | `/api/v1/auth` | 登录 / 鉴权（OAuth2 + JWT） |
| `teachers` | `/api/v1/teachers` | 教师管理 |
| `materials` | `/api/v1/materials` | 参考资料上传 / 解析 |
| `lessons` | `/api/v1/lessons` | 教案 / 课件生成 |
| `knowledge` | `/api/v1/knowledge` | 知识库 + 向量检索（pgvector） |
| `exports` | `/api/v1/exports` | 导出（.pptx / .docx / zip） |

详见 `http://localhost:8000/docs`。

## 当前阶段

✅ 已完成
- [x] 项目骨架（frontend + backend）
- [x] 后端 6 个 API 路由占位
- [x] 前端 11 个模块目录占位
- [x] Docker Compose 一键启动
- [x] README + .env.example

⏳ 进行中
- [ ] PostgreSQL + pgvector 接入
- [ ] BGE-M3 嵌入服务接入
- [ ] GPS 教学意图结构化提取
- [ ] PPTAgent outline 生成 + 编辑 actions
- [ ] 课件 PptxGenJS 浏览器侧直出
- [ ] 教案 python-docx 生成
- [ ] 互动内容 Jinja2 模板生成
- [ ] 实时网关（WebTransport / WS / SSE）

## 许可

待定