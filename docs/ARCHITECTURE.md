# 架构设计（GPS + PPTAgent 融合版）

> 师创智课（EduCreate-Smart-Class-Agent）系统架构、模块边界与数据流
>
> **项目性质：比赛项目。交付形式：纯 Web 应用**（浏览器端 + Web 后端，无桌面 / 无客户端）。

## 0. 文档说明

本架构基于两份核心技术论文：
- **GPS**（ICLR 2026）：Graph-guided Proactive Information Seeking — 用于"需求澄清 + 条件推理 DAG"层
- **PPTAgent**（EMNLP 2025）：Edit-based Presentation Generation — 用于"课件生成"层

这两篇论文定义了项目的**核心算法骨架**，其它技术栈围绕它们展开。

**工程化说明**：架构在保留两篇论文核心范式（DAG 主动追问 + 编辑式 PPT 生成）的基础上做了工程取舍——
- GPS：保留**追问闭环 + DAG 可视化**作为展示点，去掉强化学习训练链路（比赛不要求训模型）
- PPTAgent：用**PptxGenJS 浏览器侧直出**替代原论文的 PPTX XML 直接操作，避免双向保真工程风险（详见 §5.3）

---

## 1. 系统全景

师创智课是一个面向教师的**纯备课辅助 AI 工作台**。核心 5 步闭环（比赛交付范围）：

```
   教师上传讲义 / 课件 / 视频 / 图片
                ↓
        多模态解析（PDF / DOCX / PPTX / OCR / 视频帧 / 音频字幕）
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

> 本项目采用 **Docker Compose** 一键部署，包含前端、后端、数据库、缓存、向量库等全部依赖。

```
┌──────────────────────────────────────────────────────────────┐
│                         Docker Compose                         │
│                                                               │
│   ┌──────────────┐         ┌──────────────────────────────┐ │
│   │  frontend     │  HTTPS  │   backend                    │ │
│   │  Nginx         │ ◄────►  │   FastAPI + Uvicorn + Gunicorn│ │
│   │  :80/:443     │  REST   │   :8000                      │ │
│   │  (静态托管)    │  + SSE  │   + Celery Worker            │ │
│   └──────┬───────�  + WT    └──────────┬───────────────────┘ │
│          │                              │                     │
│          ▼                              ▼                     │
│   ┌─────────────────────────────────────────────────────────┐ │
│   │              HTTP/3 / QUIC 实时网关                     │ │
│   │        (WebTransport 主通道 + WS / SSE 降级)            │ │
│   └─────────────────────────────────────────────────────────┘ │
│                              │                                │
│              ┌───────────────┼────────────────┐              │
│              ▼               ▼                ▼              │
│   ┌────────────────┐  ┌──────────┐  ┌───────────────┐     │
│   │  PostgreSQL    │  │  Redis    │  │  MinIO         │     │
│   │  + pgvector    │  │  缓存/队列│  │  对象存储       │     │
│   │  + HNSW 索引   │  │  :6379    │  │  :9000/:9001   │     │
│   │  + 全文检索     │  │           │  │  资料/帧/成果   │     │
│   │  :5432         │  │           │  │                │     │
│   └────────────────┘  └──────────┘  └───────────────┘     │
└──────────────────────────────────────────────────────────────┘
```

**说明**：

- **前端**：Nginx 托管静态页面（React 构建产物），同时做反向代理负载均衡
- **后端**：Gunicorn + Uvicorn 部署 FastAPI 异步应用，支持高并发；Celery Worker 处理 OCR / 视频转写 / 生成 / 渲染等异步任务
- **PostgreSQL + pgvector**：存储教师/课程/素材等关系数据，启用 pgvector 扩展 + HNSW 索引做向量检索，启用中文全文检索做关键词召回
- **Redis**：缓存对话状态、任务进度、对话历史，支持 Celery 异步任务队列
- **MinIO**：对象存储，保存原始资料、页面图像、视频帧、生成成果和导出文件
- **实时网关**：HTTP/3 + WebTransport 主通道承载 AI 流式回复与实时协作事件，向下兼容 WebSocket / SSE
- **通信**：REST API + WebTransport 主通道 + WebSocket 兼容 + SSE 进度推送

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
| `services/` | API / SSE 进度推送 | Axios + TanStack Query |
| `stores/` | 全局状态 | Zustand |
| `state/` | 业务流程状态机 | **XState**（澄清 → 解析 → 蓝图 → 生成 → 质检 → 修改 → 导出） |
| `preview/` | PDF 预览 | PDF.js |
| `quality/` | 本地预检：布局、碰撞、文字密度 | Web Worker |
| `ppt-export/` | PptxGenJS 浏览器侧生成 .pptx | PptxGenJS |

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
│   │   ├── parsers/            # 多模态解析（PyMuPDF/pptx/docx/PaddleOCR/FFmpeg/faster-whisper）
│   │   └── generators/         # python-docx（教案）+ Jinja2（模板）
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

> **工程风险提示**：PPTX ↔ HTML 双向保真是本项目最大的技术风险。文档采用 PptxGenJS 浏览器侧直出策略，避免来回转换：
>
> - **生成路径**：PPT 结构数据 → PptxGenJS → .pptx 文件（浏览器侧，无 Node 服务）
> - **保真边界**：字体依赖系统字体库；动画/母版支持有限；如有复杂版式需求降级为静态图片占位
> - **兜底方案**：若 PPT 生成失败，自动降级为"网页幻灯片预览 + Markdown 讲稿"导出，保证总有产出
> - **编辑路径**：生成后允许教师在浏览器内直接修改文字/图片，保存后重新导出
> - **PDF 渲染**：需要将 PPT/DOCX 转换为 PDF 预览时，使用 LibreOffice Headless 转换

### 3.4 模块依赖与初始化顺序

> 占位小节，避免章节跳号。说明前后端模块的启动依赖：MinIO → PostgreSQL → Redis → 后端 FastAPI → Celery Worker → 前端 Nginx。在 Docker Compose 中通过 `depends_on` + healthcheck 保证启动顺序。

---

### 3.5 参考资料解析与指代绑定

> 比赛要求"参考资料与教师输入的意图需有对应关系，比如参照这个 PDF 的哪个知识点的内容，或者内容格式"。本节说明解析 + 指代如何落到 Lesson IR。

### 3.5.1 解析能力清单

| 文件类型 | 处理方式 | 产出 |
|---|---|---|
| PDF | PyMuPDF 提取文本 + 页码 + bbox | `chunks` (页级 + 段级 + bbox) |
| Word (docx) | python-docx 解析段落 + 标题层级 | `chunks` (标题锚段) |
| PPT (pptx) | python-pptx 提取幻灯片文本 + slide_idx | `chunks` (slide 级) |
| 图片 (png/jpg) | PaddleOCR + OpenCV 预处理 + 图像特征 | `chunks` (caption + bbox + 图像向量) |
| 视频 (mp4) | FFmpeg 抽关键帧 → OpenCV 帧处理 → faster-whisper 音频转写 + Qwen2-VL 描述 | `chunks` (帧级 + 时间戳 + 字幕) |

### 3.5.1.1 解析流水线

上传不是只保存文件，而是进入统一解析任务：

```
POST /api/v1/materials/upload
        ↓
materials.status = uploaded
        ↓
Celery parse_material_job(material_id)
        ↓
parser dispatch by mime
        ↓
chunks + metadata + storage_path 写入 PostgreSQL / MinIO
        ↓
BGE-M3 embedding + pgvector upsert
        ↓
materials.status = parsed / failed
        ↓
SSE 推送解析进度给前端
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
      "media_ref": "minio://materials/xxx/page-3.png",
      "modality": "text"
    }
  ],
  "warnings": []
}
```

前端在上传页展示 `uploaded / parsing / parsed / failed`，并允许教师打开解析结果预览后再做指代绑定。

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
| 视频只有 mp4，无内置字幕 | 仅靠关键帧 caption，文字检索能力弱，前端 UI 给出明确提示 |
| 图片 OCR 失败 | 降级为视觉向量检索 (BGE-M3 图像向量 / ColPali)，仅做相似度匹配，不绑到具体页 |
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
  3. 浏览器侧 PptxGenJS 执行指令 + self-correction（最多 2 轮）
        ↓
PPTEVAL 质检（Content / Design / Coherence）
        ↓
合格 → 导出 .pptx / .docx
```

### 5.3 核心范式：浏览器侧 PptxGenJS

**比赛版不走 PPTX ↔ HTML 双向转换**，直接用 PptxGenJS 在浏览器侧根据 LLM 输出的 JSON 结构化指令生成 .pptx 文件。

理由：
- PPTX XML 平均 1006 行/页，LLM 难以稳定操作
- HTML ↔ PPTX 双向保真实现成本高，比赛时间不允许
- PptxGenJS API 简洁（addSlide / addText / addImage），LLM 输出结构化 JSON 即可执行
- 避免任何服务端代码执行风险

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
| 基础图形（矩形、圆形） | 支持 | — |
| 动画、母版、母版动画 | 有限支持 | 降级为静态占位 |
| 字体依赖 | 依赖系统字体 | 预设 3 种安全字体兜底 |
| 复杂排版（如参考 PPT） | 部分支持 | 近似布局 + 图片占位符 |
| 生成失败 | — | 自动降级为"网页幻灯片 + Markdown 讲稿" |

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

### 5.5 PPTAgent LangGraph 节点

```python
graph.add_node("ppt_analyzer", ppt_analyzer_node)        # Stage I：分析参考
graph.add_node("ppt_outliner", ppt_outliner_node)        # Outline 生成
graph.add_node("ppt_slide_gen", ppt_slide_gen_node)       # 循环生成每张
graph.add_node("ppt_executor", ppt_executor_node)        # PptxGenJS 执行 + self-correction
graph.add_node("ppt_quality", ppt_quality_node)          # PPTEVAL 质检
```

### 5.6 Self-correction 闭环

> 在浏览器侧执行，无服务端代码执行风险。

```
for 轮次 in [1, 2]:
    1. LLM 生成结构化 JSON（slides + metadata）
    2. PptxGenJS 浏览器侧执行 JSON
    3. 捕获错误（5 类）：SYNTAX / LAYOUT / IMAGE / TEXT / OVERFLOW
    4. 错误信息回传 LLM
    5. LLM 生成修正后的 JSON
end
```

错误分类：SYNTAX（JSON 格式错误）/ LAYOUT（布局超出边界）/ IMAGE（图片 URL 失效）/ TEXT（文字溢出）/ OVERFLOW（内容超出页面）。

### 5.6.1 教师修改意见 → 再生成闭环

比赛要求的迭代优化不只依赖自动 self-correction，还需要教师反馈闭环：

```
教师在预览页提交修改意见
        ↓
edit_requests 记录原文、目标页、目标元素、当前 artifact 版本
        ↓
LLM 将自然语言改写为结构化 edit action
        ↓
PPTAgent Editor 应用到 Lesson IR / slide JSON
        ↓
PptxGenJS 重新渲染受影响页面
        ↓
PPTEVAL 局部复检
        ↓
生成新 artifact version，教师确认或继续修改
```

支持的首批修改意图：

| 教师说法 | 结构化动作 | 处理范围 |
|---|---|---|
| "调整顺序" | `reorder_sections` / `reorder_slides` | outline + slide JSON |
| "简化某页" | `compress_text` | 单页文本 |
| "增加一个案例" | `insert_example` | RAG 检索 + 单页或章节 |
| "换成更活泼的风格" | `restyle_slide` | 单页或整套主题 token |
| "加一个互动题" | `insert_interactive` | 互动模板 + PPT 占位 |

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

> 支持 .pptx / .docx / .html5 / .gif / .mp4，覆盖比赛全部要求。

### 5.9.1 导出矩阵

| 产物 | 格式 | 导出方式 | 适用场景 |
|---|---|---|---|
| 课件 PPT | `.pptx` | 浏览器侧 PptxGenJS → 文件流下载 | 主交付物 |
| 教案 Word | `.docx` | 服务端 python-docx 生成 → 文件下载 | 配套教学设计 |
| 互动内容 | `.html` | 浏览器侧模板渲染 + Blob 下载 | 浏览器打开即用 |
| | `.zip`（打包 PPT + HTML） | 服务端 zip 多个文件 | 整体交付 |
| 动画动图 | `.gif` | 浏览器侧 canvas + gif.js 录制 | 嵌入 PPT 的静态演示 |
| 短视频 | `.mp4` | 浏览器侧 MediaRecorder 录制动画 + WebM 转 MP4 | 用于课堂播放 |

### 5.9.2 关键库

- **PPT**：`PptxGenJS`（浏览器侧）
- **Word**：`python-docx`（服务端）
- **HTML5 互动**：自研模板引擎，无依赖
- **GIF**：`gif.js`（浏览器侧，Web Worker）
- **MP4**：`MediaRecorder API`（浏览器侧，录制 → 自动转码/或导出 WebM）

### 5.9.3 集成路径

- **互动内容嵌入 PPT**：导出时先用 puppeteer-style 截图插件（如 `html2pptx`）把 HTML 渲染为图片，再嵌入 .pptx。降级方案：用 PptxGenJS 占位框标注"+HTML 入口"。
- **批量导出**：支持"一键导出 .zip"，含 PPT / 教案 / 所有互动 HTML / 所有 GIF。

### 5.9.4 边界与保真

| 风险 | 兜底 |
|---|---|
| gif.js 录制超过 30s 性能下降 | 单动画最长 30s，超出提示拆分 |
| MP4 转码兼容性差 | 同时提供 .webm，浏览器直接播放 |
| 互动 HTML 嵌入 PPT 失真 | 降级为占位框 + 单独 HTML 文件附在 zip |

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
| UI 组件库 | Ant Design + **shadcn/ui** | 完整设计语言 + 可复用高质量组件 |
| 图表可视化 | **ECharts**（质检雷达图、数据概览） | 丰富图表，支持响应式 |
| DAG / 流程图 | **React Flow**（GPS DAG 可视化） | 专业节点图库 |
| PDF 预览 | **PDF.js** | 浏览器内交互式 PDF 阅读器 |
| 状态管理 | Zustand + TanStack Query + **XState** | XState 管业务流程状态机（澄清→生成→质检→修改→导出） |
| 表单 | React Hook Form + Zod | 性能 + 类型化校验 |
| 语音输入 | Web Speech API + MediaRecorder + faster-whisper fallback | 满足文字/语音双输入，兼容浏览器能力差异 |
| 前端测试 | **Vitest** | 单元测试、覆盖测试 |
| 后端框架 | **FastAPI** + Gunicorn + Uvicorn | 高性能异步，OpenAPI 自文档 |
| ORM | SQLAlchemy 2.x | 支持多种数据库，async 支持 |
| 数据库迁移 | **Alembic** | 版本化管理 schema 演进 |
| 数据库 | **PostgreSQL** + pgvector | 关系数据 + 向量检索一体，ACID 支持 |
| 向量索引 | pgvector HNSW + **NVIDIA GPU 加速索引** | 提升向量检索性能 |
| 全文检索 | PostgreSQL 全文搜索 | 内置，无需额外服务 |
| 缓存 / 任务队列 | **Redis** + **Celery** | 缓存对话状态 + 异步任务调度 |
| 部署 | **Docker Compose** + **Nginx** | 一键部署，负载均衡，静态托管 |
| 后端测试 | **Pytest** | 单元测试 + 集成测试 |
| Embedding | **BGE-M3**（中文 dense / sparse / multi-vector 三路召回） | 多语言，文本检索主力 |
| 视觉检索 | **ColPali**（PDF / PPT 页面图像细粒度视觉检索） | 图像型资料的语义定位 |
| 重排 | **bge-reranker-v2-m3** | 检索后重排序，提升相关性 |
| 检索策略 | 混合全双工搜索（全文 + 向量 + rerank） | 双层答案匹配，兼顾精确与语义 |
| LLM 框架 | **LangChain** + provider 抽象层 | 构建复杂 Agent、工作流、工具调用 |
| LLM 调用 | DeepSeek 主模型 + OpenAI-compatible fallback + **Structured Output** | 结构化输出，确保 JSON Schema 合规 |
| 可观测性 | **Langfuse** | 监控、追踪 LLM 应用，评估输出 |
| 视觉质检 | **Qwen2-VL**（多模态 judge） | PPTEVAL Content/Design/Coherence 评分 |
| PPT 操作 | **浏览器侧 PptxGenJS** | 避免 PPTX↔HTML 双向转换工程风险 |
| PDF 转换 | **LibreOffice Headless** | PPT/DOCX → PDF 渲染预览 |
| 文档生成 | **python-docx**（教案）+ **Jinja2**（模板引擎） | 动态 Word 文档，HTML/文本合并到结构化文档 |
| 信息图表 | **ECharts / Mermaid** | 动态生成信息图表，实时渲染可视化数据 |
| Word 文档 | **OOXML 文档规范** | 生成含表格、流程、方法、代码的文档 |
| 实时通信 | **WebSocket + SSE** | 双向实时推送 + 进度流推送 |
| **需求澄清** | **固定槽位 + 动态追问 + DAG 可视化** | 可演示，无训练成本 |
| **PPT 生成** | **LLM JSON → PptxGenJS → .pptx** | 浏览器侧，无服务端代码执行风险 |
| Word 生成 | **python-docx**（服务端） | 标准库，够用 |
| 互动内容 | **HTML5 模板 + LLM JSON 填充** | 4 种模板（动画/选择题/拖拽/卡片），浏览器侧渲染 |
| GIF 导出 | **gif.js**（浏览器侧 Web Worker） | 动画 → 静态动图 |
| MP4 导出 | **MediaRecorder API** | 动画 → 短视频 |
| **视觉质检** | **PPTEVAL + self-correction 最多 2 轮** | 与人类评估一致 |
| **数据流采集** | **MockRecorder.js**（开发调试） | 记录虚拟操作序列，调试 LLM 输入用，**不进生产** |
| **开发辅助** | **Cursor / Claude-Code**（开发期 IDE） | 通用多模态对话 AI 平台，仅开发阶段使用，**非运行时依赖** |
| 鉴权 | JWT + **RBAC** | 身份认证 + 细粒度权限管理 |

---

## 8. 暂未确定项

| 项 | 决策 | 说明 |
|---|---|---|
| LLM 后端 | **DeepSeek 主用，OpenAI-compatible provider 兜底** | `services/llm/` 统一配置、重试、schema 校验、fallback |
| 多租户 | 单租户起步 | 后续按需扩展 |

---

## 9. 安全与合规

### 9.1 常规安全

- 所有 API 走 HTTPS
- JWT 鉴权 + RBAC
- 文件上传校验：mime + 大小上限（默认 50MB）+ 后缀白名单（pdf/docx/doc/pptx/ppt/jpg/png/mp4）
- 上传文件存 PostgreSQL（Large Object 或文件系统），不直接执行
- Redis 存会话 token，设 TTL 自动过期
- 用户密码 bcrypt 哈希
- 敏感配置走环境变量，不入仓
- Docker Compose 隔离网络，最小化容器权限

### 9.2 LLM 调用安全

- **API 白名单**：LLM 调用仅限内部服务发起，不暴露客户端；后端对 LLM 返回内容做 JSON Schema 校验
- **超时限制**：LLM 调用超时 60s，生成任务超时 300s，超时自动取消
- **资源限制**：图片 URL 必须属于白名单域名；文件上传大小受限
- **内容过滤**：Prompt 层面防御提示词注入
- **PptxGenJS 执行边界**：JSON Schema 限定 slides 数组最大长度（50 页）和单页最大文字量（2000 字符）
- **无服务端代码执行**：生成闭环在浏览器侧完成，服务端仅返回 LLM 文本

---

## 10. 后续文档

- `docs/GPS_INTEGRATION.md` — GPS 接入详细设计
- `docs/PPTAGENT_INTEGRATION.md` — PPTAgent 接入详细设计
- `docs/INTERACTIVE_CONTENT.md` — 动画 / 小游戏模板与导出设计
- `docs/REFERENCE_BINDING.md` — 参考资料指代绑定详细设计
- `docs/DATA_MODEL.md` — 数据库详细 schema
- `docs/API.md` — REST API 文档
- `docs/DEPLOY.md` — 部署运维手册
