# OCR 使用与运维说明

## 能力范围

材料上传接口会对 PNG、JPG、JPEG 图片执行 OCR。PDF 先通过 `pypdf` 提取文本，只对没有文本层的页面执行 OCR，识别出的 chunk 保留 `page_ref`，并标记 `modality=ocr`。

OCR 采用 `pypdfium2` 渲染 PDF 页面、Pillow 预处理图片、Tesseract 识别中英文。Docker 镜像已包含 `tesseract-ocr-chi-sim` 和 `tesseract-ocr-eng`，因此比赛环境推荐使用 Docker Compose。

OCR 失败、超时或没有识别到文本时，上传接口仍保存材料，并通过 `error_message` 返回中文警告；已有文本页不受影响。

## 配置

| 环境变量 | 默认值 | 约束与作用 |
|---|---:|---|
| `OCR_ENABLED` | `true` | 是否启用图片和扫描 PDF OCR |
| `OCR_LANGUAGE` | `chi_sim` | 中文优先模型也能识别常见英文；纯英文材料可设为 `eng` |
| `OCR_DPI` | `200` | PDF 渲染 DPI，允许 72–400 |
| `OCR_TIMEOUT_SECONDS` | `30` | 每页/图片识别超时，允许 1–120 秒 |
| `OCR_MAX_PAGES` | `30` | 单个 PDF 最多 OCR 页数，允许 1–100 |
| `OCR_MAX_PIXELS` | `20000000` | 单页或图片进入 OCR 前的最大像素数 |

最多两个 Tesseract 识别进程并行运行。解析工作会移入线程，避免阻塞 FastAPI 事件循环；当前上传请求仍会等待解析结束。需要任务进度、取消或更高并发时，再接入 Redis、Celery 和 SSE。

## 本地开发

Python 依赖由 `backend/requirements.txt` 安装。本机还需自行安装 Tesseract，并安装 `chi_sim`、`eng` 语言数据；如果未安装，接口会返回“OCR 运行时不可用”的警告。不要默认使用 `chi_sim+eng` 处理短中文标题，因为 Tesseract 可能错误偏向拉丁字符；混合材料应先使用默认 `chi_sim`，确有需要再覆盖。无需 OCR 的本地开发可设置：

```env
OCR_ENABLED=false
```

## 冒烟检查

启动 Compose 后，上传一份只有扫描图片、没有文本层的 PDF：

```powershell
curl.exe -F "file=@D:\资料\scan.pdf" http://localhost:8000/api/v1/materials/upload
```

成功时返回 `status=parsed` 和非零 `chunk_count`。随后调用：

```powershell
curl.exe http://localhost:8000/api/v1/materials/<file_id>/chunks
```

OCR 片段应包含正确的 `page_ref` 和 `"modality":"ocr"`。排障时执行 `docker compose logs --tail=100 backend`，重点检查语言包缺失、单页超时和像素限制相关警告。
