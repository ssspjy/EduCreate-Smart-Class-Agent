"""GPS 教学意图澄清 API。

文档 §3.2 API/v1/gps.py：
- POST /clarify        — 首次 / 继续澄清（多轮对话）
- GET  /slots          — 获取固定槽位定义（前端展示用）
- GET  /session/{id}/dag    — 获取会话 DAG 可视化数据
- POST /session/{id}/reset  — 重置会话（清空对话历史，保留 lesson_id）
- DELETE /session/{id}      — 删除会话
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy.orm import Session

from app.schemas.gps import (
    ChatMessage,
    ClarifyResponse,
    GpsClarifyResult,
    MissingSlot,
)
from app.services.gps import (
    ClarifierSession,
    build_dag,
)
from app.db import get_db
from app.rag.retriever import retrieve
from app.core.security import require_user
from app.services.gps.session_store import (
    delete_session as delete_persisted_session,
    load_or_create_session,
    load_session,
    save_session,
)

logger = logging.getLogger(__name__)
router = APIRouter(dependencies=[Depends(require_user)])


# ── 请求体 ─────────────────────────────────────────────────────────────────────

class ClarifyRequestBody(BaseModel):
    """GPS 澄清请求（支持首次 + 多轮）。"""
    query: Optional[str] = None  # 本轮用户输入（首次必填）
    messages: Optional[list[ChatMessage]] = None  # 对话历史（多轮场景）
    materials: list[str] = []  # 参考材料 ID 列表
    lesson_id: Optional[str] = None
    session_id: Optional[str] = None  # 不传则自动创建新会话


# ── GET /slots — 固定槽位定义 ──────────────────────────────────────────────────

SLOT_DEFINITIONS: dict[str, str] = {
    "subject": "科目，如：物理、化学、数学",
    "grade": "年级，如：初中一年级、高中二年级",
    "topic": "课题/主题，如：浮力、光合作用",
    "objectives": "学习目标（最多3条），如：理解阿基米德原理",
    "key_points": "教学重点（最多3条），如：浮力公式 F=ρgV",
}


@router.get("/slots", summary="获取 GPS 固定槽位定义")
def get_slots() -> dict[str, str]:
    """返回固定槽位定义，供前端渲染槽位列表和状态。"""
    return SLOT_DEFINITIONS


# ── POST /clarify — GPS 澄清 ──────────────────────────────────────────────────

@router.post("/clarify", response_model=ClarifyResponse, summary="GPS 意图澄清（首次/多轮）")
async def clarify(body: ClarifyRequestBody, db: Session = Depends(get_db)) -> ClarifyResponse:
    """GPS 澄清核心接口。

    流程：
    1. 获取或创建 ClarifierSession
    2. 注入对话历史（多轮场景）
    3. LLM 提取意图
    4. 比对缺失槽位，生成追问话术
    5. 返回 ClarifyResponse（前端直接消费）
    """
    # 首次调用必须传 query
    if not body.query and not body.messages:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="首次调用必须传入 query 字段，多轮调用可只传 messages",
        )

    session = load_or_create_session(db, body.session_id, body.lesson_id or "")

    # 多轮场景：重放历史消息（用于前端恢复上下文）
    # 仅当 session 历史为空时才追加（避免页面刷新后重复）
    if body.messages and body.session_id:
        existing = get_session(body.session_id)
        if existing and len(existing.history) == 0:
            _restore_history(session, body.messages)

    # 处理本轮用户输入
    if body.query:
        context_hits = await retrieve(db, body.query, top_k=5, material_ids=body.materials or None)
        materials_context = "\n".join(
            f"[{hit.source}{f' 第{hit.page_ref}页' if hit.page_ref else ''}] {hit.content}"
            for hit in context_hits
        )
        result = await session.process_turn(
            user_message=body.query,
            materials_context=materials_context or None,
        )
        save_session(db, session)
        return ClarifyResponse(
            result=GpsClarifyResult.model_validate(result["result"]),
            missing_slots=[MissingSlot(**m) for m in result["missing_slots"]],
            needs_more_info=result["needs_more_info"],
            suggestion=result["suggestion"],
            session_id=session.session_id,
        )

    # 仅传 messages（重放模式，不处理新输入）
    save_session(db, session)
    current_missing = session.get_missing_slots()
    return ClarifyResponse(
        result=GpsClarifyResult.model_validate(session.intent.to_gps_result()),
        missing_slots=[MissingSlot(**m) for m in current_missing],
        needs_more_info=len(current_missing) > 0,
        suggestion=None,
        session_id=session.session_id,
    )


def _restore_history(session: ClarifierSession, messages: list[ChatMessage]) -> None:
    """从前端消息历史恢复 ClarifierSession 状态（不重调 LLM，仅重建内存结构）。"""
    from app.services.gps.clarifier import DialogueEntry
    from datetime import datetime

    for msg in messages:
        session.history.append(
            DialogueEntry(
                role=msg.role,
                content=msg.content,
                timestamp=datetime.utcnow(),
                filled_slots=[],
            )
        )


# ── GET /session/{session_id}/dag — DAG 可视化数据 ──────────────────────────────

@router.get("/session/{session_id}/dag", summary="获取会话 DAG 可视化数据")
def get_session_dag(session_id: str, db: Session = Depends(get_db)) -> dict:
    """返回前端 React Flow 格式的 DAG 数据。

    Response 格式与 frontend/src/flow/GpsDag.tsx DagGraph 接口对齐。
    """
    session = load_session(db, session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"会话 {session_id} 不存在",
        )
    return build_dag(session)


# ── POST /session/{session_id}/reset — 重置会话 ────────────────────────────────

class ResetResponse(BaseModel):
    status: str
    session_id: str


@router.post("/session/{session_id}/reset", response_model=ResetResponse, summary="重置澄清会话")
def reset_session(session_id: str, db: Session = Depends(get_db)) -> ResetResponse:
    """清空对话历史，保留 lesson_id，重新开始澄清。"""
    session = load_session(db, session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"会话 {session_id} 不存在",
        )
    lesson_id = session.lesson_id
    delete_persisted_session(db, session_id)
    new_session = load_or_create_session(db, None, lesson_id)
    save_session(db, new_session)
    return ResetResponse(status="reset", session_id=new_session.session_id)


# ── DELETE /session/{session_id} — 删除会话 ──────────────────────────────────

@router.delete("/session/{session_id}", response_model=ResetResponse, summary="删除澄清会话")
def delete_session(session_id: str, db: Session = Depends(get_db)) -> ResetResponse:
    """永久删除会话。"""
    ok = delete_persisted_session(db, session_id)
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"会话 {session_id} 不存在",
        )
    return ResetResponse(status="deleted", session_id=session_id)


# ── GET /session/{session_id} — 获取会话状态 ───────────────────────────────────

@router.get("/session/{session_id}", summary="获取会话当前状态")
def get_session_status(session_id: str, db: Session = Depends(get_db)) -> dict:
    """返回会话的意图摘要、缺失槽位、完成度（不含 DAG 数据）。"""
    session = load_session(db, session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"会话 {session_id} 不存在",
        )
    missing = session.get_missing_slots()
    return {
        "session_id": session.session_id,
        "lesson_id": session.lesson_id,
        "intent": session.intent.to_gps_result(),
        "missing_slots": missing,
        "needs_more_info": len(missing) > 0,
        "completion": session.get_completion_ratio(),
        "dialogue_count": session.dialogue_count,
        "created_at": session.created_at.isoformat(),
    }
