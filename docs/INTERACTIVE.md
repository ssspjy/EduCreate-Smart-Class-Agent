# 课堂互动内容

比赛版互动内容由固定 Jinja2 模板生成，不执行用户提供的模板、JavaScript 或模型代码。题目内容只从当前大纲章节的结构化 bullets 派生。

## API

`POST /api/v1/interactive/generate` 请求示例：

```json
{
  "outline": {
    "title": "光的折射",
    "sections": [
      {"id": "1", "title": "导入", "bullets": ["光线发生偏折"]}
    ]
  },
  "interaction_type": "choice",
  "count": 3,
  "section_id": "1"
}
```

`interaction_type` 支持 `choice`（选择题）、`true_false`（判断题）和 `fill_blank`（填空题）；单次最多生成 5 题。返回 `items`、HTML 预览字符串和 warning。要点不足时返回实际生成数量，不伪造知识点。

前端预览页使用 sandbox iframe 展示 HTML，生成失败或没有可用 bullets 时只提示 warning，不影响 PPT/DOCX 导出主流程。

## 排障

```powershell
curl.exe http://localhost:8000/health
docker compose logs --tail=100 backend
```

如果返回 422，检查题型是否为三个白名单值、`count` 是否在 1~5 之间，以及请求是否包含 `outline.sections`。
