"""GPS 教学意图澄清 API。

文档 §3.2 API/v1/gps.py：
- 多轮对话澄清 + 结构化提取
- 支持传入已上传的 materials chunks 作为上下文
- 调用 GPS reasoner + clarifier 服务层
"""

from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas import ChatMessage, ClarifyRequest, ClarifyResponse
from app.services.gps.clarifier import SLOT_HINTS, create_session, get_session
from app.services.gps.reasoner import extract_intent
from app.services.material_service import list_material_chunks

router = APIRouter()


def _build_materials_context(
    db: Session,
    material_ids: list[str],
    max_tokens: int = 3500,
) -> str:
    """从 materials IDs 提取 chunks 内容，拼成上下文文本。

    按 token 估算截断（每个汉字约 ~1.5 token，英文约 ~0.25 token，
    用 len(text) / 2 作为保守估算）。
    优先取每份材料的前面 chunks（通常包含目录、摘要、重点章节）。
    """
    if not material_ids:
        return ""

    ESTIMATED_TOKENS_PER_CHAR = 2.0  # 保守估算：每个字符约 0.5 token，反向用 2 倍字符数估算 token

    chunks_texts: list[tuple[int, str]] = []  # (estimated_tokens, text)
    total_chars = 0

    for mid in material_ids:
        try:
            chunks = list_material_chunks(db, mid)
            for chunk in chunks:
                text = chunk.content.strip()
                if not text:
                    continue
                prefix = f"[材料 {mid[:8]}... 第{chunk.chunk_index + 1}段]"
                labeled = f"{prefix}\n{text}"
                estimated = int(len(labeled) / ESTIMATED_TOKENS_PER_CHAR)
                chunks_texts.append((estimated, labeled))
                total_chars += len(labeled)
        except Exception:
            continue

    # 先累加到 max_tokens 限制
    result_parts: list[str] = []
    used_tokens = 0
    for est, text in chunks_texts:
        if used_tokens + est > max_tokens:
            # 不再拆 chunk，直接截断当前累加结果
            break
        result_parts.append(text)
        used_tokens += est

    result = "\n\n".join(result_parts)
    if result_parts and total_chars > sum(len(p) for _, p in chunks_texts[:len(result_parts)]):
        skipped = total_chars - sum(len(p) for _, p in chunks_texts[:len(result_parts)])
        result += f"\n\n...（省略约 {skipped} 字）"
    return result


@router.post("/clarify", response_model=ClarifyResponse, summary="GPS 教学意图澄清")
async def clarify(
    req: ClarifyRequest,
    db: Session = Depends(get_db),
) -> ClarifyResponse:
    """GPS 多轮澄清入口。

    流程：
    1. 从数据库加载已上传 materials 的 chunks 作为上下文
    2. 调用 GPS reasoner（LLM）提取结构化意图
    3. 检测缺失槽位，判断是否需要追问
    4. 将会话状态存储在内存中
    """
    session_id = req.session_id or str(uuid4())
    messages = req.messages or []
    if req.query:
        messages.append(ChatMessage(role="user", content=req.query))

    prev_result = None
    if session_id:
        session = get_session(session_id)
        if session:
            prev_result = session.current_result

    materials_context = _build_materials_context(db, req.materials)

    response = await extract_intent(
        messages=messages,
        materials_context=materials_context,
        prev_result=prev_result,
    )

    if session_id:
        session = create_session(session_id, initial_result=response.result)
        session.update(response.result)

    return ClarifyResponse(
        result=response.result,
        missing_slots=response.missing_slots,
        needs_more_info=response.needs_more_info,
        suggestion=response.suggestion,
        session_id=session_id,
    )


@router.get("/slots", summary="GPS 固定槽位定义")
async def list_slots() -> dict[str, str]:
    """返回 GPS 固定槽位及其描述（供前端渲染追问表单）。"""
    return SLOT_HINTS
