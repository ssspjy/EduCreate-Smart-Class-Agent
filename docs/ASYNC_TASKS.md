# 材料解析任务与运维说明

## 运行方式

Docker Compose 中，后端只完成文件校验、持久化和任务发布，Redis 保存待消费消息，单并发 Celery worker 执行文档解析、OCR、FFmpeg/Whisper 和 embedding。后端与 worker 共享 `backend_uploads`、`whisper_models` 和 PostgreSQL；业务状态始终以 `materials` 表为准，Redis 结果不能替代数据库记录。

本地开发默认 `MATERIAL_ASYNC_ENABLED=false`，可只启动 FastAPI + SQLite 并同步解析。需要本地调试 worker 时，先启动 Redis，再把该开关设为 `true`。

## 状态与 API

`POST /api/v1/materials/upload` 在 Compose 中通常立即返回：

```json
{
  "file_id": "uuid",
  "status": "queued",
  "parse_progress": 0,
  "can_cancel": true,
  "chunk_count": 0
}
```

前端优先通过 `GET /api/v1/materials/{file_id}/events` 订阅 SSE 事件；每条事件的格式为 `event: material`，`data` 是完整材料状态 JSON。连接失败、超时或浏览器不支持流式读取时，前端保留每 1.5 秒调用 `GET /api/v1/materials` 的轮询降级；也可用 `GET /api/v1/materials/{file_id}` 查询单条记录。状态流转如下：

```text
queued → parsing → parsed
                 → uploaded   （文件保留，但没有可用文本，error_message 给出 warning）
                 → failed
queued → cancelled
parsing → cancelling → cancelled
```

SSE 连接在材料进入 `parsed`、`uploaded`、`failed`、`cancelled` 或 `error` 等终态后自动结束，服务端单次连接最长保持 180 秒。该接口只读数据库状态，不改变任务处理语义；轮询和 SSE 可以安全并存。示例：

```powershell
curl.exe -N "http://localhost:8000/api/v1/materials/<file_id>/events"
```

`POST /api/v1/materials/{file_id}/cancel` 会撤销尚未开始的 Celery 任务并将其标为 `cancelled`。已经运行的 OCR/转写进入 `cancelling`，不会被强杀，而是在解析和 embedding 安全检查点读取 `cancel_requested` 后确认 `cancelled`，避免留下半写入 chunks。活动或 `cancelling` 任务直接删除会返回 HTTP 409，应等待取消完成再删除。

如果 Redis 在发布时不可用，后端记录异常并退回请求内同步解析，保证比赛主流程仍可用。解析实现具有重复执行清理逻辑，Worker 重投不会保留旧 chunks。

## 配置

| 环境变量 | 本地默认值 | Compose 值/作用 |
|---|---:|---|
| `MATERIAL_ASYNC_ENABLED` | `false` | `true`，上传后入队 |
| `CELERY_BROKER_URL` | `redis://localhost:6379/0` | `redis://redis:6379/0` |
| `CELERY_RESULT_BACKEND` | `redis://localhost:6379/1` | `redis://redis:6379/1` |
| `MATERIAL_TASK_SOFT_LIMIT_SECONDS` | `1800` | 软时间上限，异常会写入失败状态 |
| `MATERIAL_TASK_HARD_LIMIT_SECONDS` | `1860` | Worker 硬上限；丢失任务可重新投递 |

OCR、视频、Whisper 和 embedding 参数必须同时传给 backend 与 worker；Compose 已同步这些变量。Worker 使用 `--concurrency=1`，避免比赛机器同时运行多个 OCR/Whisper 任务导致内存和 CPU 抢占。

## 数据库迁移

`materials` 新增 `parse_progress`、`task_id`、`cancel_requested`。后端容器运行 Uvicorn 前自动执行 `python -m app.db.migrate`：

- 空数据库直接执行全部 Alembic 迁移；
- 旧版 `create_all` 数据卷若没有 `alembic_version`，先标记初始基线，再升级到最新 revision；
- 本地 `DATABASE_AUTO_CREATE=true` 保留幂等字段兼容，测试仍同时覆盖 SQLite 与 Alembic 升级。

手动检查：

```powershell
docker compose exec backend alembic current
docker compose exec backend alembic heads
```

## 冒烟与排障

```powershell
docker compose ps
docker compose exec redis redis-cli ping
docker compose exec worker celery -A app.worker:celery_app inspect ping
docker compose logs --tail=100 worker
```

上传一份 TXT/PDF 后，先确认接口快速返回 `queued`，再轮询材料详情直至终态并检查 chunks。常见问题：

- 长期 `queued`：检查 worker 是否在线、是否能连接 Redis，以及任务名 `materials.parse` 是否已注册。
- 长期 `parsing`：检查 OCR/FFmpeg/Whisper 日志和任务时间上限；Worker 异常退出后，`acks_late` 会让未确认任务重新投递。
- `failed`：读取 `error_message` 和 worker traceback；损坏文件不会自动伪造 chunks。
- PDF/OCR 文本中的 NUL 控制字符会在解析和持久化边界自动清理，避免 PostgreSQL 文本列报错；若仍失败，优先查看 worker 的原始 traceback。
- 取消后 CPU 仍短时占用：运行中的外部解析会在下一个安全检查点结束，不使用强制终止，以保护数据库和子进程清理。
