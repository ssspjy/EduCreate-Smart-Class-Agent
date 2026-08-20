"""教案 / 课件生成 API。

文档 §3.2 API/v1/lessons.py：
- Lesson workspace CRUD
- LessonIR 创建 / 查询 / 版本管理
- 参考资料绑定（materials <-> lesson）
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Lesson, LessonIR, Material
from app.schemas import GpsClarifyResult, LessonIRCreate, LessonIRListResponse, LessonIRResponse
from app.schemas.lesson_ir import (
    DagSnapshot,
    MaterialBinding,
    TeachingSlots,
)

router = APIRouter(tags=["lessons"])


# ── helpers ───────────────────────────────────────────────────────────────────

def _lesson_or_404(db: Session, lesson_id: str) -> Lesson:
    lesson = db.get(Lesson, lesson_id)
    if lesson is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lesson not found")
    return lesson


def _lesson_ir_model_to_response(ir: LessonIR) -> LessonIRResponse:
    raw_refs = ir.reference_materials or []
    bindings = []
    for r in raw_refs:
        if isinstance(r, dict):
            bindings.append(MaterialBinding(**r))
        else:
            bindings.append(MaterialBinding(material_id=str(r)))
    return LessonIRResponse(
        id=ir.id,
        lesson_id=ir.lesson_id,
        version=ir.version,
        slots=TeachingSlots.model_validate(ir.slots or {}),
        dag_snapshot=DagSnapshot.model_validate(ir.dag_snapshot or {}),
        reference_materials=bindings,
        created_at=ir.created_at,
    )


# ── Lesson CRUD ────────────────────────────────────────────────────────────────

class LessonCreate(BaseModel):
    """创建 lesson workspace 的请求体。"""
    title: str
    subject: str = ""
    grade: str = ""
    topic: str = ""


class LessonResponse(BaseModel):
    id: str
    title: str
    subject: str
    grade: str
    topic: str
    status: str

    model_config = {"from_attributes": True}


@router.post("", response_model=LessonResponse, summary="创建 lesson workspace")
async def create_lesson(
    req: LessonCreate,
    db: Session = Depends(get_db),
) -> LessonResponse:
    """创建一个 lesson workspace，后续 GPS + PPTAgent 都挂在该 lesson 下。"""
    lesson = Lesson(
        title=req.title,
        subject=req.subject,
        grade=req.grade,
        topic=req.topic,
        status="draft",
    )
    db.add(lesson)
    db.commit()
    db.refresh(lesson)
    return LessonResponse.model_validate(lesson)


@router.get("", summary="列出 lesson workspaces")
async def list_lessons(db: Session = Depends(get_db)) -> list[LessonResponse]:
    """列出当前教师的所有 lesson workspaces。"""
    lessons = db.query(Lesson).order_by(Lesson.created_at.desc()).all()
    return [LessonResponse.model_validate(l) for l in lessons]


@router.get("/{lesson_id}", summary="获取 lesson 详情")
async def get_lesson(
    lesson_id: str,
    db: Session = Depends(get_db),
) -> LessonResponse:
    """获取指定 lesson 的元信息。"""
    lesson = _lesson_or_404(db, lesson_id)
    return LessonResponse.model_validate(lesson)


# ── LessonIR ──────────────────────────────────────────────────────────────────

@router.post(
    "/{lesson_id}/ir",
    response_model=LessonIRResponse,
    summary="创建或更新 LessonIR（生成新版本）",
)
async def upsert_lesson_ir(
    lesson_id: str,
    req: LessonIRCreate,
    db: Session = Depends(get_db),
) -> LessonIRResponse:
    """基于 GPS 澄清结果创建 LessonIR，每次调用生成新版本（version++）。

    不会覆盖旧版本，旧版本保留在数据库中。
    """
    lesson = _lesson_or_404(db, lesson_id)  # 验证存在

    if req.lesson_id != lesson_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="lesson_id in body must match path",
        )

    existing = (
        db.query(LessonIR)
        .filter(LessonIR.lesson_id == lesson_id)
        .order_by(LessonIR.version.desc())
        .first()
    )
    next_version = (existing.version + 1) if existing else 1

    ir = LessonIR(
        lesson_id=lesson_id,
        version=next_version,
        slots=req.slots.model_dump(),
        dag_snapshot=req.dag_snapshot.model_dump(),
        reference_materials=[m.model_dump() for m in req.reference_materials],
    )
    db.add(ir)
    lesson.status = "ir_ready"
    db.commit()
    db.refresh(ir)
    return _lesson_ir_model_to_response(ir)


@router.get(
    "/{lesson_id}/ir",
    response_model=LessonIRResponse,
    summary="获取当前最新版 LessonIR",
)
async def get_current_lesson_ir(
    lesson_id: str,
    db: Session = Depends(get_db),
) -> LessonIRResponse:
    """获取某 lesson 下版本号最大的 LessonIR。"""
    _lesson_or_404(db, lesson_id)

    ir = (
        db.query(LessonIR)
        .filter(LessonIR.lesson_id == lesson_id)
        .order_by(LessonIR.version.desc())
        .first()
    )
    if ir is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No LessonIR found for this lesson",
        )
    return _lesson_ir_model_to_response(ir)


@router.get(
    "/{lesson_id}/ir/versions",
    response_model=LessonIRListResponse,
    summary="列出 LessonIR 所有版本",
)
async def list_lesson_ir_versions(
    lesson_id: str,
    db: Session = Depends(get_db),
) -> LessonIRListResponse:
    """返回某 lesson 下所有 LessonIR 版本（按 version 降序）。"""
    _lesson_or_404(db, lesson_id)

    irs = (
        db.query(LessonIR)
        .filter(LessonIR.lesson_id == lesson_id)
        .order_by(LessonIR.version.desc())
        .all()
    )
    return LessonIRListResponse(
        lesson_id=lesson_id,
        versions=[_lesson_ir_model_to_response(ir) for ir in irs],
    )


# ── 参考资料绑定 ───────────────────────────────────────────────────────────────

@router.post(
    "/{lesson_id}/materials/{material_id}/bind",
    summary="绑定参考资料到 lesson",
)
async def bind_material(
    lesson_id: str,
    material_id: str,
    db: Session = Depends(get_db),
) -> dict[str, str]:
    """将已上传的参考资料绑定到某个 lesson（不自动填充 RagEvidence）。"""
    material = db.get(Material, material_id)
    if material is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Material not found")

    existing = (
        db.query(LessonIR)
        .filter(LessonIR.lesson_id == lesson_id)
        .order_by(LessonIR.version.desc())
        .first()
    )
    if existing:
        ref_mats: list[dict] = list(existing.reference_materials)
        if material_id not in [m.get("material_id") for m in ref_mats]:
            ref_mats.append({"material_id": material_id, "chunk_ids": [], "bound_slot": "", "excerpt": "", "page_ref": None})
            existing.reference_materials = ref_mats
    else:
        lesson = _lesson_or_404(db, lesson_id)
        ir = LessonIR(
            lesson_id=lesson_id,
            version=1,
            slots={"subject": lesson.subject or "", "grade": lesson.grade or "", "topic": lesson.topic or ""},
            dag_snapshot={"turns": []},
            reference_materials=[{"material_id": material_id, "chunk_ids": [], "bound_slot": "", "excerpt": "", "page_ref": None}],
        )
        db.add(ir)

    db.commit()
    return {"status": "bound", "lesson_id": lesson_id, "material_id": material_id}


@router.get(
    "/{lesson_id}/materials",
    summary="列出 lesson 绑定的参考资料",
)
async def list_bound_materials(
    lesson_id: str,
    db: Session = Depends(get_db),
) -> list[dict]:
    """返回某 lesson 绑定的所有参考材料（从最新 LessonIR 中读取）。"""
    _lesson_or_404(db, lesson_id)

    ir = (
        db.query(LessonIR)
        .filter(LessonIR.lesson_id == lesson_id)
        .order_by(LessonIR.version.desc())
        .first()
    )
    if ir is None:
        return []

    results: list[dict] = []
    for binding in ir.reference_materials:
        mat_id = binding.get("material_id") if isinstance(binding, dict) else ""
        if not mat_id:
            continue
        mat = db.get(Material, mat_id)
        if mat:
            results.append({
                "material_id": mat.id,
                "filename": mat.filename,
                "status": mat.status,
                "chunk_count": len(mat.chunks),
            })
    return results


# ── 大纲生成（GPS -> Outline）──────────────────────────────────────────────────

class OutlineSection(BaseModel):
    id: str
    title: str
    bullets: list[str]
    duration_minutes: int
    slide_count: int


class OutlineResponse(BaseModel):
    title: str
    subject: str
    grade: str
    sections: list[OutlineSection]
    total_slides: int
    total_duration_minutes: int


@router.post("/outline", response_model=OutlineResponse, summary="生成 PPT 大纲")
async def generate_outline(
    req: GpsClarifyResult,
    db: Session = Depends(get_db),
) -> OutlineResponse:
    """基于 GPS 澄清结果动态生成章节大纲。

    根据 GPS 字段动态构建章节（不再硬编码"浮力"模板）。
    """
    subject = (req.subject or "通用").strip()
    grade = (req.grade or "未指定年级").strip()
    topic = (req.topic or "未命名课题").strip()
    objectives = req.objectives or []
    key_points = req.key_points or []
    difficulty = req.difficulty or "medium"
    style = req.style or "interactive"

    # ── 章节结构：根据 GPS 字段动态生成 ─────────────────────────────────────
    sections: list[OutlineSection] = []

    # 1. 引入（始终存在）
    sections.append(OutlineSection(
        id="1",
        title=f"引入：{topic}",
        bullets=[
            f"从生活实例切入{topic}的话题",
            f"提问：什么是{topic}的核心问题？",
            "引出本节课的思考方向",
        ],
        duration_minutes=5,
        slide_count=3,
    ))

    # 2. 目标与重难点（仅在 GPS 提取到时展示）
    if objectives or key_points:
        bullets: list[str] = []
        if objectives:
            bullets.append("学习目标：" + "；".join(objectives[:3]))
        if key_points:
            bullets.append("教学重点：" + "；".join(key_points[:3]))
        sections.append(OutlineSection(
            id=str(len(sections) + 1),
            title="学习目标与重难点",
            bullets=bullets,
            duration_minutes=5,
            slide_count=2,
        ))

    # 3. 核心内容讲解（核心章节，按难度自适应页数与时长）
    style_hint = {
        "theory": "概念讲解 + 公式推导",
        "interactive": "互动探究 + 小组讨论",
        "experiment": "实验演示 + 现象分析",
    }.get(style, "互动讲解")

    difficulty_slides = {"easy": 4, "medium": 6, "hard": 8}.get(difficulty, 6)
    difficulty_minutes = {"easy": 10, "medium": 14, "hard": 18}.get(difficulty, 14)

    sections.append(OutlineSection(
        id=str(len(sections) + 1),
        title=f"{topic}：核心内容（{style_hint}）",
        bullets=[
            f"围绕『{topic}』的核心概念展开",
            f"采用「{style_hint}」形式呈现",
            f"难度定位：{difficulty}",
            "结合学生已有知识递进讲解",
        ],
        duration_minutes=difficulty_minutes,
        slide_count=difficulty_slides,
    ))

    # 4. 重点剖析（仅在 GPS 提取到 key_points 时展开）
    if key_points:
        sections.append(OutlineSection(
            id=str(len(sections) + 1),
            title=f"{topic}：重点剖析",
            bullets=[f"重点 {i+1}：{kp}" for i, kp in enumerate(key_points[:3])],
            duration_minutes=8,
            slide_count=4,
        ))

    # 5. 课堂练习（始终存在）
    sections.append(OutlineSection(
        id=str(len(sections) + 1),
        title="课堂练习与即时反馈",
        bullets=[
            f"2–3 道与{topic}相关的典型例题",
            "学生独立思考 + 同伴互评",
            "教师巡视，针对性答疑",
        ],
        duration_minutes=8,
        slide_count=4,
    ))

    # 6. 小结与作业（始终存在）
    sections.append(OutlineSection(
        id=str(len(sections) + 1),
        title="课堂小结与作业",
        bullets=[
            f"回顾{topic}的核心要点",
            "梳理本节课的知识脉络",
            "布置分层作业（基础 + 拓展）",
        ],
        duration_minutes=4,
        slide_count=2,
    ))

    return OutlineResponse(
        title=f"{grade} {subject}：{topic}",
        subject=subject,
        grade=grade,
        sections=sections,
        total_slides=sum(s.slide_count for s in sections),
        total_duration_minutes=sum(s.duration_minutes for s in sections),
    )
