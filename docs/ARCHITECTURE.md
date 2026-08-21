# 架构设计（GPS + PPTAgent 融合版）

> 师创智课（EduCreate-Smart-Class-Agent）系统架构、模块边界与数据流
>
> **项目性质：比赛项目。交付形式：纯 Web 应用**（浏览器端 + Web 后端，无桌面 / 无客户端）。

## 0. 文档说明

本架构基于两份核心技术论文：
- **GPS**（ICLR 2026）：Graph-guided Proactive Information Seeking — 用于"需求澄清 + 条件推理 DAG"层
- **PPTAgent**（EMNLP 2025）：Edit-based Presentation Generation — 用于"课件生成"层

这两篇论文定义了项目的**核心算法骨架**，其它技术栈围绕它们展开。

**工程化说明**：这是比赛级纯 Web 应用，架构以“核心闭环真实可用、现场部署稳定、依赖最少化”为决策顺序。在保留两篇论文核心范式（DAG 主动追问 + 编辑式 PPT 生成）的基础上做如下取舍：
- GPS：保留**追问闭环 + DAG 可视化**作为展示点，去掉强化学习训练链路（比赛不要求训模型）
- PPTAgent：比赛版用后端 **python-pptx** 从受校验的结构化大纲生成 PPTX，PptxGenJS 仅作为后续浏览器内编辑候选（详见 §5.3）
- 部署：只把已被业务真实使用的服务纳入比赛运行时；PostgreSQL + pgvector 是 Compose 数据层，Redis / Celery 已承担材料解析，MinIO 与独立实时网关不作为比赛版硬依赖

---

## 1. 系统全景

师创智课是一个面向教师的**纯备课辅助 AI 工作台**。核心 5 步闭环（比赛交付范围）：

```
   教师上传讲义 / 课件 / 视频 / 图片
                ↓
        多模态解析（PDF / DOCX / PPTX / OCR / 视频探测 / 音频字幕）
                ↓
        知识抽取 + 切块 + 向量化（BGE-M3 / pgvector）
                ↓
   ┌───────────────────────────────────────┐
   │ GPS 需求澄清（固定槽位 + 动态追问）    │
   │   - 教学意图结构化提取                │
   │   - DAG 可视化展示（展示用，非训练）  │
   │   - 缺失项检测 + 主动追问             │
   └───────────────────────────────────────┘
                ↓
        Lesson IR（中间表示）
                ↓
   ┌───────────────────────────────────────┐
   │ PPTAgent 课件生成                     │
   │   - 参考 PPT 分析（cluster + schema）│
   │   - Outline 生成                       │
   │   - HTML 中间层编辑                    │
   │   - PPTX / Word 导出                  │
   └───────────────────────────────────────┘
                ↓
        质检报告（人工确认）
```

---

## 2. 部署拓扑

> 本项目采用 **Docker Compose** 一键部署当前比赛运行时：前端、后端、材料解析 worker、Redis、PostgreSQL + pgvector。上传资料、Redis 消息和模型缓存使用 Docker 持久化卷。

```
┌───────────────────────────────────────────────────────────┐
│                    Docker Compose                          │
│                                                           │
│  ┌────────────────┐   REST    ┌────────────────────────┐  │
│  │ frontend       │ ◄────────► │ backend                │  │
│  │ React + Nginx  │            │ FastAPI + Uvicorn      │  │
│  │ :5173 → :80    │            │ :8000                  │  │
│  └────────────────┘            └──────┬─────────┬───────┘  │
│                                      │ SQL     │ enqueue   │
│                           ┌──────────▼───┐  ┌──▼────────┐  │
│                           │ PostgreSQL   │  │ Redis     │  │
│                           │ + pgvector   │  │ broker    │  │
│                           └──────────▲───┘  └──┬────────┘  │
│                                      │         │ consume   │
│                                      └────┬────┘           │
│                                     ┌─────▼──────┐         │
│                                     │ worker     │         │
│                                     │ Celery     │         │
│                                     └────────────┘         │
│                                                           │
│  uploads / exports：Docker 命名卷持久化                    │
└───────────────────────────────────────────────────────────┘
```

**说明**：

- **前端**：Nginx 托管 React 构建产物，并把 `/api/*` 反向代理到后端
- **后端**：比赛版使用 Uvicorn 部署 FastAPI；上传落盘后发布材料任务，GPS、大纲、质检和导出从统一 REST API 提供
- **Redis + Celery worker**：Redis 持久化待消费任务；单并发 worker 执行 OCR、FFmpeg 和 Whisper，和后端共享上传卷与 SQL 状态
- **PostgreSQL + pgvector**：Compose 的正式数据层；chunks 已写入 1024 维向量并建立 HNSW 索引，支持余弦检索。BGE-M3 为可选 provider，未安装模型时使用 hash embedding 降级
- **文件存储**：原始资料与生成成果使用后端目录和 Docker 命名卷，减少比赛环境依赖
- **本地开发**：允许继续使用 SQLite，保证无需 Docker 也能开发和运行测试
- **数据库迁移**：Alembic 作为结构版本控制；后端容器启动前自动升级，旧 `create_all` 数据卷会先标记基线再迁移
- **任务状态**：`materials` 保存队列 ID、进度和取消标记，前端当前轮询 SQL 状态；SSE 作为后续推送增强
- **非比赛硬依赖**：MinIO、Gunicorn 多 Worker、WebSocket / WebTransport 和独立实时网关均放入后续演进，不作为当前完成度声明

---

## 3. 模块边界

### 3.1 前端 `frontend/`

| 子模块 | 职责 | 关键技术 |
|---|---|---|
| `pages/` | 教师工作台（上传、澄清、预览、导出） | React Router |
| `components/` | 通用 UI、表单、布局 | Ant Design（shadcn/ui 可选扩展） |
| `charts/` | DAG 可视化、质检雷达图 | ECharts |
| `flow/` | 算法关系图、流程结构展示 | React Flow |
| `features/` | 业务功能模块 | 业务组件 |
| `features/voice-input/` | 教师语音输入、录音状态、转写结果确认 | Web Speech API + MediaRecorder fallback |
| `services/` | API 调用；SSE 进度推送待异步任务接入 | Fetch + TanStack Query |
| `stores/` | 全局状态 | Zustand |
| `state/` | 业务流程状态机 | **XState**（澄清 → 解析 → 蓝图 → 生成 → 质检 → 修改 → 导出） |
| `preview/` | PDF 预览 | PDF.js |
| `quality/` | 本地预检：布局、碰撞、文字密度 | Web Worker |
| `ppt-export/` | 调用后端导出接口并下载 `.pptx` | Fetch + 后端 python-pptx |

**多模态输入界面落地方式**：

- **文字输入**：澄清页保留 `TextArea`，每轮消息写入 `conversation_messages`，供 GPS Reasoner 提取槽位。
- **语音输入**：前端优先使用浏览器 `SpeechRecognition` / `webkitSpeechRecognition` 做实时转写；不支持时退化为 `MediaRecorder` 录音上传，由后端 `faster-whisper` 转写。
- **教师确认**：语音转写结果先进入可编辑输入框，教师确认后再提交给 GPS，避免识别错误直接污染 Lesson IR。
- **状态反馈**：录音中、转写中、转写失败、权限拒绝四种状态必须在 UI 中显式提示。

### 3.2 后端 `backend/`

```
backend/
├── app/
│   ├── main.py
│   ├── core/                   # 配置、logging、安全、依赖注入
│   ├── api/                    # REST 路由
│   │   └── v1/
│   │       ├── auth.py
│   │       ├── teachers.py
│   │       ├── materials.py     # 上传 / 解析 / 查询
│   │       ├── lessons.py       # 教案 / 课件生成
│   │       ├── knowledge.py     # 知识库 / 向量检索（pgvector）
│   │       └── exports.py       # 导出（.pptx / .docx / zip）
│   ├── models/                 # SQLAlchemy ORM
│   ├── schemas/                # Pydantic 模型（含 DAG 节点/边）
│   ├── services/
│   │   ├── llm/                # LLM provider（DeepSeek）+ LangChain
│   │   ├── rag/                # BGE-M3 + pgvector + ColPali + 全文 + reranker
│   │   ├── gps/                # ★ GPS 模块
│   │   │   ├── reasoner.py     # 教学意图结构化提取
│   │   │   ├── clarifier.py    # 固定槽位 + 动态追问 + 缺失检测
│   │   │   └── dag_builder.py  # DAG 可视化（展示用，非训练）
│   │   ├── pptagent/           # ★ PPTAgent 模块
│   │   │   ├── analyzer.py     # Stage I：参考 PPT 分析（cluster + schema）
│   │   │   ├── outliner.py     # Outline 生成
│   │   │   ├── editor.py       # Stage II：编辑 actions 生成
│   │   │   ├── executor.py     # 5 类错误兜底 + self-correction
│   │   │   └── ppteval.py      # 视觉质检（Content/Design/Coherence）
│   │   ├── parsers/            # 文档解析 + OCR + FFmpeg/可选 Whisper
│   │   └── generators/         # python-docx（教案）+ Jinja2（模板）
│   ├── tasks/                   # Celery 材料解析任务
│   ├── worker.py                # Celery 应用与队列配置
│   ├── db/                     # PostgreSQL + Alembic 迁移
│   └── utils/
├── tests/                      # Pytest 单元测试
├── alembic/                    # Alembic 数据库迁移
└── requirements.txt
```

### 3.2.1 LLM Provider 配置与兜底

LLM 不直接散落在业务代码中调用，统一经过 `services/llm/provider.py`：

| 配置项 | 示例 | 说明 |
|---|---|---|
| `LLM_PROVIDER` | `deepseek` | 主 provider，比赛版默认 DeepSeek |
| `LLM_BASE_URL` | `https://api.deepseek.com` | OpenAI-compatible API base URL |
| `LLM_API_KEY` | `${DEEPSEEK_API_KEY}` | 仅走环境变量，不入仓 |
| `LLM_MODEL` | `deepseek-chat` / `deepseek-reasoner` | GPS、PPTAgent 可按任务切模型 |
| `LLM_TIMEOUT_SECONDS` | `60` | 单次调用超时 |
| `LLM_MAX_RETRIES` | `2` | 网络错误或 5xx 自动重试 |

**调用策略**：

1. GPS 槽位提取、动态追问、参考资料指代识别均要求 Structured Output，并通过 Pydantic / JSON Schema 校验。
2. PPTAgent 的 outline / slide JSON / edit request rewrite 必须经过 schema 校验，不合格时要求 LLM 自修正一次。
3. 主 provider 不可用时，按 `LLM_FALLBACK_PROVIDER` 切到兼容 OpenAI API 的备用模型；若备用模型也失败，降级为模板化占位内容，并在前端提示教师稍后重试。
4. 所有 LLM 输入输出写入 Langfuse trace，敏感字段和上传文件原文按脱敏策略截断。

### 3.3 PPT 生成策略

> **比赛版正式路径**：PPTX ↔ HTML 双向保真是高风险工程，因此不做双向转换，也不把生成能力绑定到浏览器运行环境：
>
> - **生成路径**：GPS / PPTAgent 结构化大纲 → Pydantic 校验 → 后端 python-pptx → `.pptx`
> - **保真边界**：字体依赖系统字体库；动画/母版支持有限；如有复杂版式需求降级为静态图片占位
> - **兜底方案**：生成失败时保留网页大纲预览和结构数据，允许教师修正后重试
> - **编辑路径**：比赛版先编辑结构化大纲并重新导出；浏览器内自由排版属于后续增强
> - **PDF 渲染**：需要将 PPT/DOCX 转换为 PDF 预览时，使用 LibreOffice Headless 转换

### 3.4 模块依赖与初始化顺序

比赛版启动依赖为 PostgreSQL/pgvector + Redis → FastAPI 自动迁移 → Celery worker + Nginx。Docker Compose 使用 healthcheck 保证顺序。本地开发使用 SQLite 且 `MATERIAL_ASYNC_ENABLED=false` 时，后端可独立启动。

---

### 3.5 参考资料解析与指代绑定

> 比赛要求"参考资料与教师输入的意图需有对应关系，比如参照这个 PDF 的哪个知识点的内容，或者内容格式"。本节说明解析 + 指代如何落到 Lesson IR。

### 3.5.1 解析能力清单

| 文件类型 | 处理方式 | 产出 |
|---|---|---|
| PDF | pypdf 提取文本；无文本页由 PDFium 渲染后交给 Tesseract | `chunks`（页码 + text/ocr 模态） |
| Word (docx) | python-docx 解析段落、表格、页眉和页脚 | `chunks`（文档级） |
| PPT (pptx) | python-pptx 提取幻灯片文本 | `chunks`（页码） |
| 图片 (png/jpg) | Pillow 预处理 + Tesseract 中英文识别 | `chunks`（ocr 模态） |
| 视频 (mp4) | FFprobe 校验 → FFmpeg 音频提取 → 可选 faster-whisper 转写 | `chunks`（时间戳 + transcript 模态） |
| 音频 (webm/wav/m4a/mp3/ogg) | FFprobe 校验 → FFmpeg 规范化 → 可选 faster-whisper 转写 | `chunks`（时间戳 + transcript 模态） |

### 3.5.1.1 解析流水线

上传不是只保存文件，而是进入统一解析任务：

> 当前实现：本地开发使用 SQLite 并默认同步解析；Compose 使用 PostgreSQL + pgvector、Redis 和 Celery worker。PDF / DOCX / PPTX / Markdown / TXT、图片 OCR、启用后的 MP4 和 WebM 等音频转写会写入 chunks 与 1024 维 embedding；扫描 PDF 仅对无文本页执行 OCR。PostgreSQL 走 pgvector 余弦检索，SQLite 走词法降级。BGE-M3 和视频关键帧理解仍待完整接入。

```
POST /api/v1/materials/upload
        ↓
materials.status = queued
        ↓
Redis → Celery materials.parse（Compose）/ 同步 parser（本地默认）
        ↓
parser dispatch by mime
        ↓
chunks + metadata + storage_path 写入数据库 / 持久化文件卷
        ↓
BGE-M3 embedding + pgvector upsert
        ↓
materials.status = parsed / uploaded / failed / cancelling / cancelled
        ↓
前端轮询状态、进度与 warning；SSE 推送待接入
```

每个 parser 至少返回统一结构：

```json
{
  "material_id": "uuid",
  "chunks": [
    {
      "chunk_index": 0,
      "content": "片段文本或字幕",
      "page_ref": 3,
      "bbox": [100, 120, 380, 210],
      "media_ref": "uploads/<material-id>/page-3.png",
      "modality": "text"
    }
  ],
  "warnings": []
}
```

前端在上传页展示 `queued / parsing / cancelling / parsed / uploaded / failed / cancelled`，轮询进度并允许安全取消，解析抽屉展示 warning、文本 chunk、PDF 页码或视频时间戳；只有 `parsed / uploaded` 材料会进入 GPS 的可用材料 ID 列表。

### 3.5.2 指代绑定 — Reference Resolution

教师上传资料后必须能说清"我要用它的什么"。前端提供 3 种绑定入口：

**入口 A — 自动抽取 + 教师确认**（默认）

```
教师上传 PDF → 解析得到 chunks（带页码/标题/bbox）
       ↓
LLM 从教师话语中识别指代：
  - "参照这个 PDF 排版风格" → 整篇 style 绑定
  - "用第 3 页的内容举例" → material_id + page=3 + bbox
  - "学习其中的案例 A" → chunk_id
       ↓
弹窗让教师确认绑定
       ↓
写入 lesson_irs.reference_materials
```

**入口 B — 教师手动 pin**

教师在 PDF 阅读器里 `点击拖选文字 → 选区进入"参考资料侧栏"` →
输入框`这段用在第 X 页讲（知识点 Y）`。直接形成绑定，无需 LLM。

**入口 C — 全局参考资料不绑定**

仅上传供 RAG 检索，不绑定到具体课件页。

### 3.5.3 数据存储（与第 6 章对齐）

每条绑定写入 `rag_evidences`：

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | PK | |
| `lesson_ir_id` | FK | 所属 Lesson IR 版本 |
| `material_id` | FK | 哪个参考资料 |
| `page_ref` | int | PDF 第几页 / PPT 第几张（媒体可填关键帧 idx）|
| `bbox` | jsonb | 页内坐标区域（文字/图片 bbox）|
| `excerpt` | text | 摘录（≤ 500 字）|
| `usage` | text | 用途：`style` / `case` / `outline` / `example` |
| `slot_binding` | text | 绑到哪个教学要素（如 `key_points[0]`、特定 slide）|

### 3.5.4 查询路径

PPTAgent 生成某页 slide 时：

```
slide 渲染逻辑：
  1. 取 outline[slide_id]
  2. 查询 lesson_ir.dag_snapshot.reference_materials
  3. 按 slot_binding 找到 rag_evidences
  4. 把 evidence.excerpt 作为该页 prompt 上下文
```

### 3.5.5 边界与兜底

| 场景 | 处理 |
|---|---|
| 视频只有 mp4，无内置字幕 | 默认仅完成 FFprobe 校验；启用并配置 Whisper 后生成时间戳转写，关键帧理解仍是后续能力 |
| 视频转写未启用或模型不可用 | 保留视频和元数据，返回 warning，不生成虚假字幕 chunk |
| 图片 OCR 失败 | 保存原始材料并返回明确 warning，不生成虚假 chunk；视觉向量检索待接入 |
| 教师没明确"用到哪里" | 默认归入 RAG 全局检索，不绑特定 slide |
| 绑定冲突（同一段绑多个 slide） | 取最相似 + 教师确认 |

---

## 4. GPS 集成（核心模块之一）

### 4.1 GPS 在系统中的角色

GPS 解决"教师需求不明确"的问题。当教师说"帮我准备一节课"，系统不知道教什么、学情、时长 — GPS 通过**固定槽位 + 动态追问**把这种不确定性显式建模，主动追问直到信息齐全。DAG 仅作**前端可视化展示**用，不做训练/RL。

### 4.2 GPS 接入点

```
教师上传资料 / 输入教学思路
        ↓
GPS Reasoner: 抽取教学意图 → 填充固定槽位
        ↓
GPS Clarifier: 检测缺失项 → 动态追问 + DAG 可视化
        ↓
Lesson IR（中间表示，交给 PPTAgent）
```

### 4.3 固定槽位设计

> 比赛版采用固定槽位而非完整 DAG 训练，兼顾可演示性和实现成本。

```
槽位 ID    字段名              追问触发条件
─────────────────────────────────────────────
S1        subject             教师未说明学科
S2        grade_level         教师未说明年级
S3        topic               教师未说明具体章节
S4        duration             教师未说明课时长度
S5        key_points[]        教师未列出知识点
S6        style               教师未说明风格（科普/应试/互动）
S7        reference_materials 教师未上传参考资料
```

### 4.4 动态追问策略

1. **缺失检测**：每轮对话后，Reasoner LLM 扫描已填槽位，输出缺失列表
2. **追问排序**：按 `S1→S7` 顺序追问，每轮最多问 1-2 个问题
3. **DAG 可视化**：后端将槽位填充状态实时同步前端，前端渲染为节点图（React Flow），教师可见进度
4. **提前结束**：若所有必填槽位已满（时长、知识点等核心字段非空），可跳过剩余非必填项

### 4.5 Lesson IR 数据结构

```json
{
  "lesson_id": "uuid",
  "slots": {
    "subject": "初中物理",
    "grade_level": "初一",
    "topic": "光的折射",
    "duration": 45,
    "key_points": ["光的折射定律", "折射率", "全反射"],
    "style": "科普互动",
    "reference_materials": [
      { "material_id": "uuid", "page_refs": [3, 5], "usage": "排版风格参考" }
    ]
  },
  "dag_snapshot": {
    "nodes": [...],
    "edges": [...],
    "filled_slots": ["S1", "S2", "S3", "S4", "S5"]
  }
}
```

### 4.6 GPS LangGraph 节点（简化版）

```python
graph = StateGraph(LessonState)

graph.add_node("slot_extractor", slot_extractor_node)       # 填槽位
graph.add_node("missing_checker", missing_checker_node)      # 检测缺失
graph.add_node("clarifier", clarifier_node)                  # 追问（最多 5 轮）
graph.add_node("dag_serializer", dag_serializer_node)        # 同步 DAG 状态到前端
graph.add_node("checkpoint", checkpoint_node)                # 人工确认

graph.add_edge("slot_extractor", "missing_checker")
graph.add_edge("missing_checker", "clarifier")
graph.add_edge("clarifier", "dag_serializer")
graph.add_edge("dag_serializer", "checkpoint")
```

**去掉了**：Hybrid Reward、训练质检节点、拓扑序期望成本选择、Evidence 对齐。保留追问闭环和 DAG 可视化作为核心展示点。

---

## 5. PPTAgent 集成（核心模块之二）

### 5.1 PPTAgent 在系统中的角色

PPTAgent 解决"如何生成好看 PPT"的问题。它把"从零生成"换成"参考页 + 编辑 actions"，让 AI 像人一样做 PPT。

### 5.2 PPTAgent 接入点

```
GPS 输出 Lesson IR（意图 + 蓝图）
        ↓
PPTAgent Stage I：分析参考 PPT 库（slide cluster + schema）
        ↓
PPTAgent Stage II：
  1. Outline 生成（每张页：目的 + 参考页 + 内容来源）
  2. Slide Generation（循环）：LLM 生成结构化编辑指令（JSON）
  3. 后端 python-pptx 执行受校验的结构化生成指令
        ↓
PPTEVAL 质检（Content / Design / Coherence）
        ↓
合格 → 导出 .pptx / .docx
```

### 5.3 核心范式：服务端 python-pptx

**比赛版不走 PPTX ↔ HTML 双向转换**。前端负责预览和编辑结构化大纲，后端用 python-pptx 根据经过 Pydantic 校验的数据生成 `.pptx` 文件，再通过受控下载接口交付。

理由：
- PPTX XML 平均 1006 行/页，LLM 难以稳定操作
- HTML ↔ PPTX 双向保真实现成本高，比赛时间不允许
- 服务端生成结果不受浏览器、下载权限和前端运行状态影响，现场演示更稳定
- python-pptx 已进入后端依赖并完成真实文件生成和下载闭环
- LLM 只产出结构化内容，不产出或执行 Python 代码，避免服务端代码执行风险

**LLM 输出格式（简化版）**：

```json
{
  "slides": [
    {
      "layout": "title",
      "title": "光的折射",
      "subtitle": "初中物理 · 初一"
    },
    {
      "layout": "content",
      "title": "折射定律",
      "bullets": ["入射角与折射角成正比", "入射光线、折射光线、法线共面"],
      "image": { "type": "diagram", "description": "光的折射示意图" }
    }
  ]
}
```

**保真边界与兜底**：

| 场景 | 支持情况 | 兜底方案 |
|---|---|---|
| 文字、标题、要点 | 完整支持 | — |
| 基础图形、图片 | 可扩展支持 | 使用预设布局和受控媒体路径 |
| 动画、复杂母版 | 有限支持 | 降级为静态页面或图片占位 |
| 字体依赖 | 依赖系统字体 | 预设 3 种安全字体兜底 |
| 复杂排版（如参考 PPT） | 部分支持 | 近似布局 + 图片占位符 |
| 生成失败 | — | 保留网页大纲和结构数据，修改后重试 |

PptxGenJS 不再是比赛版运行时依赖；只有在后续确认需要浏览器内自由排版时，才作为独立增强方案评估。

### 5.4 PPTAgent 与 Lesson IR 的接口

```python
# Lesson IR 结构（GPS 产出 intent + PPTAgent 产出 outline + 证据锚点）
{
  "intent": {                          # GPS 产出
    "subject": "初中物理",
    "topic": "光的折射",
    "duration": 45,
    "key_points": ["光的折射定律", "折射率", "应用举例"]
  },
  "outline": [                         # PPTAgent 产出
    {
      "slide_id": 1,
      "purpose": "引入",
      "reference_layout": "Opening-TitleIcon",
      "content_source": "lesson_ir.intent.topic",
      "key_points": []
    },
    ...
  ],
  "evidence_anchors": [                # GPS 产出
    {"page": 12, "bbox": [100,200,300,400], "type": "diagram"}
  ]
}
```

### 5.5 PPTAgent 编排节点（当前比赛版）

当前阶段不引入 LangGraph 运行时，采用可审计的 HTTP 服务编排：

```python
graph.add_node("ppt_analyzer", ppt_analyzer_node)        # Stage I：分析参考
graph.add_node("ppt_outliner", ppt_outliner_node)        # Outline 生成
graph.add_node("ppt_slide_gen", ppt_slide_gen_node)       # 循环生成每张
graph.add_node("ppt_executor", ppt_executor_node)        # python-pptx 执行 + self-correction
graph.add_node("ppt_quality", ppt_quality_node)          # PPTEVAL 质检
```

实际入口为 `POST /api/v1/pptagent/analyze-reference`（读取已解析的 PPTX）和
`POST /api/v1/pptagent/apply-actions`（校验并应用结构化动作）。导出接口可携带
`lesson_id` 生成 `GeneratedArtifact` 版本记录；预览页提供章节上移/下移操作。

### 5.6 Self-correction 闭环（边界）

> 自动 self-correction 和复杂版式误差回传仍是后续增强；当前服务端只执行固定的 python-pptx 生成器，不执行 LLM 返回的代码。

```
for 轮次 in [1, 2]:
    1. LLM 生成结构化 JSON（slides + metadata）
    2. 后端校验 JSON，并交给固定的 python-pptx 生成器
    3. 捕获错误（5 类）：SYNTAX / LAYOUT / IMAGE / TEXT / OVERFLOW
    4. 错误信息回传 LLM
    5. LLM 生成修正后的 JSON
end
```

错误分类：SYNTAX（JSON 格式错误）/ LAYOUT（布局超出边界）/ IMAGE（图片 URL 失效）/ TEXT（文字溢出）/ OVERFLOW（内容超出页面）。

### 5.6.1 教师修改意见 → 再生成闭环

比赛要求的迭代优化不只依赖自动 self-correction，还需要教师反馈闭环：

```
教师在预览页提交结构化修改动作
        ↓
edit_requests 记录原文、目标页、目标元素、当前 artifact 版本
        ↓
后端 Pydantic 校验 action（不接受代码、路径或任意主题令牌）
        ↓
PPTAgent Editor 应用到 Lesson IR / slide JSON
        ↓
python-pptx 根据更新后的结构数据重新生成成果
        ↓
PPTEVAL 局部复检
        ↓
生成新 artifact version，教师确认或继续修改
```

当前支持的首批修改动作：

| 教师说法 | 结构化动作 | 处理范围 |
|---|---|---|
| 章节上移/下移 | `move_section` | outline |
| 修改章节标题 | `rename_section` | outline |
| 修改/追加/删除要点 | `replace_bullet` / `append_bullet` / `remove_bullet` | 单章节 |
| 切换固定主题 | `set_style`（classic / modern / minimal） | 整套 PPT |

越界动作会返回 warning 并保留可用结果；未知动作由 schema 直接拒绝。

每次修改都保留版本号，教师可回退到上一版，避免一次再生成覆盖已满意内容。

### 5.7 PPTEVAL 评估

三维评分（1-5 分），用 Qwen2-VL 做多模态 judge：

| 维度 | 标准 |
|---|---|
| **Content** | 文字简洁有重点，图片相关且支持内容 |
| **Design** | 色彩和谐，有几何/图标/图像等视觉元素，避免重叠 |
| **Coherence** | 故事线流畅，含背景信息（讲者/日期/致谢） |

与人类评分 Pearson 相关性 0.71，可作为自动质检依据。

---

### 5.8 互动内容生成（动画 / 小游戏）

> 比赛要求"至少支持一种"。采用**前端模板 + LLM 参数填充**的策略，避免从零生成 HTML/JS。

### 5.8.1 支持类型与触发条件

| 类型 | 触发关键词示例 | 模板 | 输出 |
|---|---|---|---|
| 知识点动画 | "解释光的折射过程"、"演示..." | 5 个 HTML5 动画模板（折射、抛物线、化学键、太阳系等） | HTML5（嵌入 PPT 或独立 .html） |
| 选择题互动 | "出几道选择题"、"来个测验" | 题型模板 | HTML5 单页 quiz |
| 拖拽配对游戏 | "连连看"、"配对练习" | 拖拽配对模板 | HTML5 单页 game |
| 概念卡片翻转 | "做几个闪卡"、"flashcard" | 卡片翻转模板 | HTML5 单页 deck |

### 5.8.2 LLM 输出 → 模板填充

```json
{
  "interactive_type": "drag_match",
  "topic": "光的折射 · 概念配对",
  "items": [
    {"left": "入射角", "right": "光线进入界面时与法线的夹角"},
    {"left": "折射角", "right": "光线折射后与法线的夹角"}
  ]
}
```

前端模板引擎负责把 JSON 渲染为最终 HTML/JS。无服务端代码生成风险。

### 5.8.3 边界情况

- **LLM 参数越界**（如 items 超过模板支持上限）：截断 + 教师提示
- **类型不匹配**：回退为"提示词级引导"，建议教师改用支持的类型
- **模板未覆盖**：降级为静态文本说明页

---

### 5.9 导出方案

比赛版先保证 `.pptx` 和 `.docx` 两个评分相关主产物；HTML5 互动内容在实现模板后接入。GIF / MP4 属于增强项，不计入当前完成能力。

### 5.9.1 导出矩阵

| 产物 | 格式 | 导出方式 | 适用场景 |
|---|---|---|---|
| 课件 PPT | `.pptx` | 后端 python-pptx → 下载接口 | **已实现，比赛主交付物** |
| 教案 Word | `.docx` | 后端 python-docx → 下载接口 | **已实现，比赛主交付物** |
| 互动内容 | `.html` | 模板渲染后独立下载或打包 | 待实现，至少交付一种互动类型 |
| 整体成果 | `.zip` | 服务端打包已生成成果 | 后续增强 |
| 动画动图 / 视频 | `.gif` / `.mp4` | 预渲染或录制 | 非比赛版硬依赖 |

### 5.9.2 关键库

- **PPT**：`python-pptx`（服务端）
- **Word**：`python-docx`（服务端）
- **HTML5 互动**：自研模板引擎，无依赖
- **PptxGenJS / GIF / MP4**：仅作为后续增强评估，不进入当前运行时

### 5.9.3 集成路径

- **互动内容嵌入 PPT**：比赛版优先在 PPT 中放置互动说明或入口，同时提供独立 HTML；后续再评估渲染为静态预览图。
- **批量导出**：支持"一键导出 .zip"，含 PPT / 教案 / 所有互动 HTML / 所有 GIF。

### 5.9.4 边界与保真

| 风险 | 兜底 |
|---|---|
| 互动 HTML 嵌入 PPT 失真 | 降级为占位框 + 单独 HTML 文件附在 zip |
| PPT 复杂母版 / 动画保真不足 | 使用比赛版安全模板，复杂效果降级为静态表达 |

---

## 6. 数据模型概览

```
teachers             lessons             materials           chunks
─────────            ──────────          ──────────          ───────
id (PK)              id (PK)            id (PK)             id (PK)
name                 teacher_id (FK)     teacher_id (FK)     material_id (FK)
email                title               filename            content
                     status              mime                tokens
                     created_at          size                vector (pgvector)
                     updated_at          parsed_at           chunk_index
                     storage_path        storage_path
                                         task_id / progress
                                         cancel_requested

slot_filling        lesson_irs          generation_jobs     quality_reports
────────────         ──────────          ────────────────   ──────────────
id (PK)              id (PK)             id (PK)            id (PK)
lesson_id (FK)       lesson_id (FK)      lesson_id (FK)      job_id (FK)
filled_slots (jsonb) slots (jsonb)        status              scores (jsonb)
dag_snapshot (jsonb) dag_snapshot (jsonb) output_json         created_at
created_at           created_at          created_at
                     version             retry_count
                     version

generated_artifacts  edit_requests       rag_evidences
─────────────────    ────────────────   ──────────────
id (PK)              id (PK)            id (PK)
job_id (FK)          lesson_id (FK)     lesson_ir_id (FK)
type (pptx/docx)     instruction (text)  material_id (FK)
version              target_page        page_ref (int)
storage_path         status             bbox (jsonb)
created_at           action_json        excerpt (text)
                     from_artifact_id   usage
                     created_at         slot_binding
                     resolved_at
```

**说明**：

- 所有实体存储于 **PostgreSQL**，支持事务 ACID、JSONB、pgvector 向量列
- `chunks.vector` 使用 **pgvector**（余弦相似度 / 欧氏距离），`chunks.token_count` 用于估算上下文大小
- `rag_evidences.bbox` 为 JSONB，存页内坐标区域
- `lesson_irs.slots` / `dag_snapshot` 使用 JSONB 内联（去掉了 dag_nodes / dag_edges 独立表）
- `generation_jobs.output_json` 内联 PPT 生成结果（去掉了 ppt_outlines / ppt_versions 独立表）
- `generated_artifacts.version` 与 `edit_requests.from_artifact_id` 支持教师修改后的版本回退
- `edit_requests.action_json` 存 LLM 改写后的结构化编辑动作，便于复现和审计
- Alembic 管理 schema 版本迁移

---

## 7. 关键技术决策

| 主题 | 决策 | 理由 |
|---|---|---|
| 前端构建 | Vite + React + TypeScript | 启动快，HMR 体验好 |
| UI 组件库 | Ant Design | 已安装并覆盖当前五步工作台 |
| 图表可视化 | **ECharts**（质检雷达图、数据概览） | 丰富图表，支持响应式 |
| DAG / 流程图 | **React Flow**（GPS DAG 可视化） | 专业节点图库 |
| PDF 预览 | **PDF.js** | 浏览器内交互式 PDF 阅读器 |
| 状态管理 | Zustand + TanStack Query + **XState** | XState 管业务流程状态机（澄清→生成→质检→修改→导出） |
| 表单 | React Hook Form + Zod | 性能 + 类型化校验 |
| 语音输入 | Web Speech API + MediaRecorder + faster-whisper fallback | 浏览器优先实时识别；不支持时上传 WebM 等音频，Compose 由 Celery worker 后台转写 |
| 前端测试 | **Vitest + TypeScript 检查 + 生产构建** | 已覆盖材料可用状态、上传格式和 chunk 来源标签；组件交互测试后续扩展 |
| 后端框架 | **FastAPI** + Uvicorn | 异步 API，OpenAPI 自文档；比赛版单实例依赖更少 |
| ORM | SQLAlchemy 2.x | 支持多种数据库，async 支持 |
| 数据库迁移 | **Alembic** | 版本化管理 schema 演进 |
| 数据库 | **PostgreSQL** + pgvector | 关系数据 + 向量检索一体，ACID 支持 |
| 向量索引 | pgvector HNSW | 比赛数据规模足够，避免无实际收益的 GPU 索引依赖 |
| 全文检索 | PostgreSQL 全文搜索 | 内置，无需额外服务 |
| 缓存 / 任务队列 | Redis 7 + Celery 5 | 已用于 OCR / 视频 / 音频材料解析；SQL 保存业务状态 |
| 部署 | **Docker Compose** + **Nginx** | 一键部署，负载均衡，静态托管 |
| 后端测试 | **Pytest** | 单元测试 + 集成测试 |
| OCR | **pypdfium2 + Pillow + Tesseract** | 仅处理图片和 PDF 无文本页；Docker 内置中英文语言包并设置资源边界 |
| 视频转写 | **FFmpeg + faster-whisper（可选）** | 默认不下载模型；模型路径显式配置，避免上传请求隐式联网和资源失控 |
| Embedding | **BGE-M3**（中文 dense / sparse / multi-vector 三路召回） | 多语言，文本检索主力 |
| 视觉检索 | **ColPali**（PDF / PPT 页面图像细粒度视觉检索） | 图像型资料的语义定位 |
| 重排 | **bge-reranker-v2-m3** | 检索后重排序，提升相关性 |
| 检索策略 | 混合全双工搜索（全文 + 向量 + rerank） | 双层答案匹配，兼顾精确与语义 |
| LLM 框架 | 自有 provider 抽象层 | 已实现 DeepSeek / OpenAI-compatible 调用、重试和结构化输出；暂不引入未使用框架 |
| LLM 调用 | DeepSeek 主模型 + OpenAI-compatible fallback + **Structured Output** | 结构化输出，确保 JSON Schema 合规 |
| 可观测性 | 结构化日志；Langfuse 为后续增强 | 比赛版减少外部服务依赖 |
| 视觉质检 | **Qwen2-VL**（多模态 judge） | PPTEVAL Content/Design/Coherence 评分 |
| PPT 操作 | **服务端 python-pptx** | 已完成生成与下载闭环，比赛现场稳定可控 |
| PDF 转换 | **LibreOffice Headless** | PPT/DOCX → PDF 渲染预览 |
| 文档生成 | **python-docx**（教案）+ **Jinja2**（模板引擎） | 动态 Word 文档，HTML/文本合并到结构化文档 |
| 信息图表 | **ECharts / Mermaid** | 动态生成信息图表，实时渲染可视化数据 |
| Word 文档 | **OOXML 文档规范** | 生成含表格、流程、方法、代码的文档 |
| 实时通信 | **WebSocket + SSE** | 双向实时推送 + 进度流推送 |
| **需求澄清** | **固定槽位 + 动态追问 + DAG 可视化** | 可演示，无训练成本 |
| **PPT 生成** | **受校验大纲 → python-pptx → .pptx** | LLM 不执行代码，后端统一生成、存储和下载 |
| Word 生成 | **python-docx**（服务端） | 标准库，够用 |
| 互动内容 | **HTML5 模板 + LLM JSON 填充** | 4 种模板（动画/选择题/拖拽/卡片），浏览器侧渲染 |
| GIF 导出 | **gif.js**（浏览器侧 Web Worker） | 动画 → 静态动图 |
| MP4 导出 | **MediaRecorder API** | 动画 → 短视频 |
| **视觉质检** | **PPTEVAL + self-correction 最多 2 轮** | 与人类评估一致 |
| **数据流采集** | **MockRecorder.js**（开发调试） | 记录虚拟操作序列，调试 LLM 输入用，**不进生产** |
| **开发辅助** | **Cursor / Claude-Code**（开发期 IDE） | 通用多模态对话 AI 平台，仅开发阶段使用，**非运行时依赖** |
| 鉴权 | JWT（可配置） | `AUTH_REQUIRED=true` 时校验签名 token；细粒度 RBAC 仍待补齐 |

---

## 8. 暂未确定项

| 项 | 决策 | 说明 |
|---|---|---|
| LLM 后端 | **DeepSeek 主用，OpenAI-compatible provider 兜底** | `services/llm/` 统一配置、重试、schema 校验、fallback |
| 多租户 | 单租户起步 | 后续按需扩展 |

---

## 9. 安全与合规

### 9.1 常规安全

- 生产部署应在反向代理层启用 HTTPS；本地和 Compose 演示环境使用 HTTP
- JWT 鉴权可通过 `AUTH_REQUIRED=true` 启用；细粒度 RBAC 待实现
- 文件上传校验：mime + 大小上限（默认 50MB）+ 后缀白名单（pdf/docx/doc/pptx/ppt/jpg/png/mp4）
- 上传文件保存到受控文件目录 / Docker 命名卷，数据库只记录元数据和受控路径，不直接执行上传内容
- GPS 会话当前持久化到数据库；Redis 只承担 Celery broker/result backend，不存业务真相
- 用户密码 bcrypt 哈希
- 敏感配置走环境变量，不入仓
- Docker Compose 隔离网络，最小化容器权限

### 9.2 LLM 调用安全

- **API 白名单**：LLM 调用仅限内部服务发起，不暴露客户端；后端对 LLM 返回内容做 JSON Schema 校验
- **超时限制**：LLM 调用超时 60s，生成任务超时 300s，超时自动取消
- **资源限制**：图片 URL 必须属于白名单域名；文件上传大小受限
- **内容过滤**：Prompt 层面防御提示词注入
- **PPT 生成边界**：Pydantic / JSON Schema 限定 slides 数组最大长度（50 页）和单页最大文字量（2000 字符）
- **无动态代码执行**：服务端只把受校验的结构化数据交给固定 python-pptx 生成器，不执行 LLM 返回的 Python / JavaScript

---

## 10. 配套文档

- `docs/OCR.md` — OCR 配置、运行边界与冒烟排障（已提供）
- `docs/VIDEO.md` — 视频探测、音频提取和 Whisper 配置（已提供）
- `docs/VOICE.md` — 澄清页语音输入、录音回退和排障（已提供）
- `docs/ASYNC_TASKS.md` — 材料解析任务、状态 API、迁移和 Worker 排障（已提供）

GPS、PPTAgent、互动内容、参考资料绑定和完整 API 参考目前仍以内嵌章节及 FastAPI `/docs` 为准；对应独立文档在相关能力实现时再创建，避免保留不存在的路径。
