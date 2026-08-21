# PPTAgent 参考分析与结构化编辑

比赛版 PPTAgent 采用后端固定 `python-pptx` 生成器。参考课件只用于提取结构统计；编辑请求必须是经过 Pydantic 校验的 JSON 动作，服务端不会执行模型返回的代码、路径或任意主题参数。

## 参考 PPTX 分析

先按普通材料上传 PPTX，Compose 异步解析完成后调用：

```powershell
$body = @{ material_id = "<file_id>" } | ConvertTo-Json
Invoke-RestMethod -Method Post `
  -Uri http://localhost:8000/api/v1/pptagent/analyze-reference `
  -ContentType "application/json" -Body $body
```

返回页数、每页文本块/字符数、文本密度和固定主题建议。当前只支持 `.pptx`，损坏文件或不存在的受控文件路径返回 4xx。

## 自然语言意见改写

教师可以先调用 `POST /api/v1/pptagent/rewrite-instruction`：请求携带同一份 `outline` 和不超过 500 字的 `instruction`，返回 `actions`、置信度、解释和 warning。该接口只改写不执行，前端展示动作后再调用 `apply-actions`，避免自然语言或模型输出直接改变课件。

## 应用编辑动作

```json
{
  "outline": {
    "title": "光的折射",
    "subject": "物理",
    "grade": "八年级",
    "sections": [
      {"id": "1", "title": "引入", "bullets": ["生活实例"], "duration_minutes": 5, "slide_count": 2}
    ],
    "total_slides": 4,
    "total_duration_minutes": 5
  },
  "actions": [
    {"type": "rename_section", "section_id": "1", "title": "生活中的折射"},
    {"type": "set_style", "style": "modern"}
  ]
}
```

请求 `POST /api/v1/pptagent/apply-actions` 返回更新后的大纲、已应用动作和 warning。支持动作：`move_section`、`rename_section`、`replace_bullet`、`append_bullet`、`remove_bullet`、`set_style`。章节/要点索引越界只返回 warning；未知动作、缺少必填字段或超长文本直接返回 422。

## 导出与版本

`POST /api/v1/exports/pptx` 保留为同步兼容接口。预览页使用 `POST /api/v1/exports/pptx/jobs` 创建持久化任务，Compose 交给 Celery 执行，并通过 SSE 展示进度；动作先由白名单执行器应用，再由固定生成器写入 PPTX。成功后在 `generated_artifacts` 记录递增的 `version` 和受控存储路径。任务 API 与排障见 [`GENERATION_TASKS.md`](./GENERATION_TASKS.md)。

## 排障

```powershell
docker compose ps
curl.exe http://localhost:8000/health
docker compose logs --tail=100 backend
```

如果参考分析返回 404，先确认材料记录仍存在且文件没有被清理；如果返回 422，确认扩展名为 PPTX 且文件可被 PowerPoint/python-pptx 打开。
