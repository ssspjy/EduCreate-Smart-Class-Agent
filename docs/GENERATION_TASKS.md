# PPTX 生成任务与实时进度

## 运行边界

Compose 使用现有 Redis + 单并发 Celery worker 执行 PPTX 生成，不新增服务。任务输入先写入 `generation_jobs.request_json`，状态、进度、错误和输出也以 PostgreSQL 为准；Redis 只负责消息投递。生成过程只调用后端固定 `python-pptx` 生成器，不执行 LLM 返回的代码。

本地开发默认 `GENERATION_ASYNC_ENABLED=false`，接口会在请求内完成生成，但仍创建完整任务记录，便于测试同一数据契约。Compose 固定开启异步生成。

## API 与状态

创建任务：

```http
POST /api/v1/exports/pptx/jobs
Content-Type: application/json

{
  "title": "浮力",
  "subject": "物理",
  "grade": "八年级",
  "lesson_id": "<lesson_id>",
  "sections": [
    {
      "id": "intro",
      "title": "课堂导入",
      "bullets": ["观察浮力现象"],
      "duration_minutes": 5,
      "slide_count": 2
    }
  ],
  "total_slides": 2,
  "total_duration_minutes": 5
}
```

接口返回 HTTP 202 和任务快照。Compose 中通常先返回 `queued`，状态流转为：

```text
queued → generating → completed
                    → failed
```

- `GET /api/v1/exports/jobs/{job_id}`：查询任务快照。
- `GET /api/v1/exports/jobs/{job_id}/events`：订阅 SSE；事件名为 `generation`，`data` 是完整任务 JSON。
- `completed` 时 `output.url` 指向现有下载接口，`output.artifact_id` 和 `output.version` 对应持久化产物记录。

预览页优先读取 SSE，并每 1.5 秒查询一次任务作为降级。SSE 断开不会取消任务或丢失结果；任务进入 `completed` 或 `failed` 后事件流自动结束，单次连接最长 330 秒。

## 配置与迁移

| 环境变量 | 本地默认值 | Compose 值/作用 |
|---|---:|---|
| `GENERATION_ASYNC_ENABLED` | `false` | `true`，PPTX 通过 Worker 生成 |
| `GENERATION_TASK_SOFT_LIMIT_SECONDS` | `300` | Celery 软时间上限 |
| `GENERATION_TASK_HARD_LIMIT_SECONDS` | `330` | Celery 硬时间上限 |

Alembic revision `e6251c0c4fb2` 为 `generation_jobs` 增加 `job_type`、`progress`、`task_id`、`request_json` 和 `error_message`。后端容器启动时自动升级；本地旧 SQLite 库由幂等兼容逻辑补齐字段。

## 冒烟与排障

```powershell
docker compose ps
docker compose exec worker celery -A app.worker:celery_app inspect registered
docker compose logs --tail=100 worker
curl.exe -N "http://localhost:8000/api/v1/exports/jobs/<job_id>/events"
```

- 长期 `queued`：确认 Worker 已注册 `generation.pptx`，并检查 Redis 连接。
- 长期 `generating`：检查 Worker 是否被 OCR/Whisper 长任务占用；比赛版单并发按进入队列顺序执行。
- `failed`：读取 `error_message` 和 Worker traceback。失败任务不会创建伪造下载地址。
- SSE 断开：直接查询任务接口；任务状态和结果不会依赖 SSE 连接。
