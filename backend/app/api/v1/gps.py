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
    max_chars: int = 4000,
) -> str:
    """从 materials IDs 提取 chunks 内容，拼成上下文文本。"""
    if not material_ids:
        return ""

    chunks_texts: list[str] = []
    for mid in material_ids:
        try:
            chunks = list_material_chunks(db, mid)
            for chunk in chunks:
                text = chunk.content.strip()
                if text:
                    chunks_texts.append(f"[材料 {mid} 第{chunk.chunk_index + 1}段] {text}")
        except Exception:
            continue

    full_text = "\n".join(chunks_texts)
    if len(full_text) <= max_chars:
        return full_text
    return full_text[:max_chars] + f"\n...（共 {len(full_text)} 字，已截断）"


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
    )


@router.get("/slots", summary="GPS 固定槽位定义")
async def list_slots() -> dict[str, str]:
    """返回 GPS 固定槽位及其描述（供前端渲染追问表单）。"""
    return SLOT_HINTS
