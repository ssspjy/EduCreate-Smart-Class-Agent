"""PPTAgent 参考分析、结构化编辑和版本记录测试。"""

from io import BytesIO

from pptx import Presentation
from pptx.util import Inches
from fastapi.testclient import TestClient


def _pptx_bytes() -> bytes:
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    box = slide.shapes.add_textbox(Inches(1), Inches(1), Inches(8), Inches(1))
    box.text = "参考课件标题"
    output = BytesIO()
    prs.save(output)
    return output.getvalue()


def test_reference_analysis_and_structured_edit(client: TestClient) -> None:
    upload = client.post(
        "/api/v1/materials/upload",
        files={"file": ("reference.pptx", _pptx_bytes(), "application/vnd.openxmlformats-officedocument.presentationml.presentation")},
    )
    assert upload.status_code == 200
    material_id = upload.json()["file_id"]

    analysis = client.post("/api/v1/pptagent/analyze-reference", json={"material_id": material_id})
    assert analysis.status_code == 200
    assert analysis.json()["slide_count"] == 1
    assert analysis.json()["recommended_style"] in {"classic", "modern", "minimal"}

    outline = {
        "title": "测试课件", "subject": "物理", "grade": "八年级",
        "sections": [
            {"id": "a", "title": "第一节", "bullets": ["旧要点"], "duration_minutes": 5, "slide_count": 2},
            {"id": "b", "title": "第二节", "bullets": ["要点"], "duration_minutes": 6, "slide_count": 2},
        ], "total_slides": 6, "total_duration_minutes": 11,
    }
    edited = client.post("/api/v1/pptagent/apply-actions", json={
        "outline": outline,
        "actions": [
            {"type": "move_section", "section_id": "b", "to_index": 0},
            {"type": "replace_bullet", "section_id": "a", "bullet_index": 0, "text": "新要点"},
        ],
    })
    assert edited.status_code == 200
    assert [section["id"] for section in edited.json()["outline"]["sections"]] == ["b", "a"]
    assert edited.json()["outline"]["sections"][1]["bullets"] == ["新要点"]


def test_invalid_edit_action_is_rejected(client: TestClient) -> None:
    response = client.post("/api/v1/pptagent/apply-actions", json={
        "outline": {"sections": []},
        "actions": [{"type": "run_code", "text": "print(1)"}],
    })
    assert response.status_code == 422


def test_pptx_export_records_lesson_artifact_version(client: TestClient) -> None:
    lesson = client.post("/api/v1/lessons", json={"title": "版本测试"})
    assert lesson.status_code == 200
    lesson_id = lesson.json()["id"]
    outline = {
        "title": "版本课件", "subject": "数学", "grade": "七年级",
        "sections": [{"id": "1", "title": "章节", "bullets": ["要点"], "duration_minutes": 5, "slide_count": 1}],
        "total_slides": 3, "total_duration_minutes": 5,
    }
    first = client.post("/api/v1/exports/pptx", json={**outline, "lesson_id": lesson_id})
    second = client.post("/api/v1/exports/pptx", json={**outline, "lesson_id": lesson_id})
    assert first.status_code == 200 and first.json()["version"] == 1
    assert second.status_code == 200 and second.json()["version"] == 2
    assert first.json()["artifact_id"] != second.json()["artifact_id"]
