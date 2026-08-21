"""PPTAgent 参考课件分析与安全编辑动作 API。"""

from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.security import require_user
from app.db import get_db
from app.models import Material
from app.schemas.pptagent import (
    PptAgentApplyRequest,
    PptAgentApplyResponse,
    PptAgentRewriteRequest,
    PptAgentRewriteResponse,
    PptReferenceAnalyzeRequest,
)
from app.services.pptagent.analyzer import analyze_reference
from app.services.pptagent.editor import apply_actions
from app.services.pptagent.rewrite import rewrite_instruction

router = APIRouter(dependencies=[Depends(require_user)])


@router.post("/rewrite-instruction", response_model=PptAgentRewriteResponse, summary="将教师修改意见改写为 PPT 动作")
async def rewrite_ppt_instruction(request: PptAgentRewriteRequest) -> PptAgentRewriteResponse:
    actions, warnings, confidence, explanation = rewrite_instruction(request.outline, request.instruction)
    return PptAgentRewriteResponse(actions=actions, warnings=warnings, confidence=confidence, explanation=explanation)


@router.post("/analyze-reference", summary="分析参考 PPTX 结构")
async def analyze_reference_ppt(request: PptReferenceAnalyzeRequest, db: Session = Depends(get_db)) -> dict:
    material = db.get(Material, request.material_id)
    if material is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="参考资料不存在")
    return analyze_reference(material.storage_path, material.id, material.filename)


@router.post("/apply-actions", response_model=PptAgentApplyResponse, summary="应用结构化 PPT 编辑动作")
async def apply_ppt_actions(request: PptAgentApplyRequest, db: Session = Depends(get_db)) -> PptAgentApplyResponse:
    outline, applied, warnings = apply_actions(request.outline, request.actions)
    edit_request_id = None
    if request.lesson_id and applied:
        from app.models import EditRequest, Lesson
        lesson = db.get(Lesson, request.lesson_id)
        if lesson is not None:
            edit_request = EditRequest(
                lesson_id=lesson.id,
                instruction=request.instruction or "PPTAgent 结构化编辑",
                status="applied",
                action_json=applied,
                resolved_at=datetime.utcnow(),
            )
            db.add(edit_request)
            db.commit()
            db.refresh(edit_request)
            edit_request_id = edit_request.id
        else:
            warnings.append("lesson_id 不存在，未记录编辑请求")
    return PptAgentApplyResponse(outline=outline, applied=applied, warnings=warnings, edit_request_id=edit_request_id)
