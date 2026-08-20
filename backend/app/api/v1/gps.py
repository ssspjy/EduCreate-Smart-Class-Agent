"""GPS 教学意图澄清 API。

文档 §3.2 API/v1/gps.py：
- 多轮对话澄清 + 结构化提取
- 支持传入已上传的 materials chunks 作为上下文
- 调用 GPS reasoner + clarifier 服务层
- 集成 DAG builder 生成可视化数据
"""

from __future__ import annotations

import logging
import time
from uuid import uuid4

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas import GpsClarifyResult
from app.schemas import ChatMessage, ClarifyRequest, ClarifyResponse
from app.services.gps.clarifier import (
    SLOT_HINTS,
    ClarifierSession,
    DialogueEntry,
    get_or_create_session,
    get_session,
)
from app.services.gps.dag_builder import build_dag
from app.services.gps.reasoner import extract_intent
from app.services.material_service import list_material_chunks

logger = logging.getLogger(__name__)
router = APIRouter()


# ── 辅助函数 ──────────────────────────────────────────────────────────────────

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

    ESTIMATED_TOKENS_PER_CHAR = 2.0

    chunks_texts: list[tuple[int, str]] = []
    total_chars = 0

    for mid in material_ids:
        try:
            chunks = list_material_chunks(db, mid)
            for chunk in chunks:
                text = chunk.content.strip()
                if not text:
                    continue
                # 截断超长 chunk（单个 chunk 超过 500 字则截断）
                if len(text) > 500:
                    text = text[:500] + "……（已截断）"
                prefix = f"[材料 {mid[:8]}... 第{chunk.chunk_index + 1}段]"
                labeled = f"{prefix}\n{text}"
                estimated = int(len(labeled) / ESTIMATED_TOKENS_PER_CHAR)
                chunks_texts.append((estimated, labeled))
                total_chars += len(labeled)
        except Exception:
            continue

    # 按 token 预算累加，截断至 max_tokens
    result_parts: list[str] = []
    used_tokens = 0
    for est, text in chunks_texts:
        if used_tokens + est > max_tokens:
            break
        result_parts.append(text)
        used_tokens += est

    if not result_parts:
        return ""

    result = "\n\n".join(result_parts)
    total_included = sum(len(p) for p in result_parts)
    if total_chars > total_included:
        result += f"\n\n...（共 {total_chars} 字，省略约 {total_chars - total_included} 字）"
    return result


def _serialize_dag_snapshot(session: ClarifierSession) -> dict:
    """将会话状态序列化为前端可渲染的 DAG 数据。"""
    entries = session.get_dialogue_entries()
    # 由 dag_builder 生成标准节点/边结构
    dag_data = build_dag(
        result=session.current_result,
        dialogue_entries=entries,
        filled_slots=session.get_filled_slots(),
        missing_slots=[ms.slot for ms in session.get_missing_slots()],
    )
    return dag_data


# ── API 端点 ─────────────────────────────────────────────────────────────────

@router.post("/clarify", response_model=ClarifyResponse, summary="GPS 教学意图澄清")
async def clarify(
    req: ClarifyRequest,
    db: Session = Depends(get_db),
) -> ClarifyResponse:
    """GPS 多轮澄清入口。

    流程：
    1. 获取或创建澄清会话（不覆盖已有会话的状态）
    2. 从数据库加载已上传 materials 的 chunks 作为上下文
    3. 调用 GPS reasoner（LLM）提取结构化意图
    4. 检测缺失槽位，判断是否需要追问
    5. 更新会话状态（记录对话历史，追踪新填充的槽位）
    6. 生成 DAG 快照数据
    """
    # 1. session 管理
    session_id = req.session_id or str(uuid4())
    session = get_or_create_session(session_id)

    # 2. 构建消息列表（包含历史 + 本轮输入）
    messages = req.messages or []
    if req.query:
        messages.append(ChatMessage(role="user", content=req.query))

    # 3. 构建材料上下文
    materials_context = _build_materials_context(db, req.materials)

    # 4. 调用 LLM 提取意图（传入上一轮结果用于渐进填充）
    try:
        response = await extract_intent(
            messages=messages,
            materials_context=materials_context,
            prev_result=session.current_result,
        )
    except Exception as exc:
        logger.exception("[GPS] LLM intent extraction failed: %s", exc)
        # LLM 不可用时降级：返回空结果 + 追问提示
        fallback_result = GpsClarifyResult(
            subject="",
            grade="",
            topic="",
            objectives=[],
            key_points=[],
            difficulty="medium",
            style="interactive",
            confidence=0.0,
        )
        return ClarifyResponse(
            result=fallback_result,
            missing_slots=[],
            needs_more_info=False,
            suggestion="抱歉，AI 服务暂时不可用（" + str(exc)[:100] + "）。请检查 LLM 配置后重试。",
            session_id=session_id,
        )

    # 5. 更新会话状态（正确增量更新，不覆盖已有状态）
    new_filled_slots = session.update(response.result)

    # 记录对话历史（用于 DAG 可视化）
    last_user_msg = req.query or (messages[-1].content if messages else "")
    if last_user_msg:
        session.add_user_message(last_user_msg)

    response_text = f"已解析：{response.result.subject} · {response.result.grade} · {response.result.topic}"
    if response.needs_more_info and response.suggestion:
        response_text += f"\n\n{response.suggestion}"
    session.add_assistant_message(response_text, new_filled_slots=new_filled_slots)

    # 6. 判断是否强制结束（达到最大追问轮次）
    if session.is_max_reached() and not session.is_complete():
        logger.warning(
            "[GPS] Session %s reached max dialogue rounds (%d) without completing slots",
            session_id, ClarifierSession.MAX_MESSAGE_COUNT,
        )
        response.needs_more_info = False
        response.suggestion = (
            "已达到最大澄清轮次。请根据当前已提取的信息继续，或在后续步骤中手动补充。"
        )

    # 7. 响应构造（不含 DAG 数据，DAG 由 GET /session/{id}/dag 端点单独获取）
    response.session_id = session_id
    return response


@router.get("/slots", summary="GPS 固定槽位定义")
async def list_slots() -> dict[str, str]:
    """返回 GPS 固定槽位及其描述（供前端渲染追问表单）。"""
    return SLOT_HINTS


@router.get("/session/{session_id}/dag", summary="获取会话 DAG 状态")
async def get_session_dag(
    session_id: str,
    db: Session = Depends(get_db),
) -> dict:
    """返回指定会话的当前 DAG 可视化数据。"""
    session = get_session(session_id)
    if session is None:
        return {"nodes": [], "edges": [], "error": "session not found"}

    return _serialize_dag_snapshot(session)


@router.post("/session/{session_id}/reset", summary="重置澄清会话")
async def reset_session(session_id: str) -> dict:
    """重置指定会话，清空对话历史，重新开始澄清。"""
    from app.services.gps.clarifier import create_session
    create_session(session_id)
    return {"status": "reset", "session_id": session_id}


@router.delete("/session/{session_id}", summary="删除澄清会话")
async def delete_session(session_id: str) -> dict:
    """删除指定会话。"""
    from app.services.gps.clarifier import clear_session
    clear_session(session_id)
    return {"status": "deleted", "session_id": session_id}
