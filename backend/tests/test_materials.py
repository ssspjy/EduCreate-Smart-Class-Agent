"""Material upload and persistence tests."""

from io import BytesIO
from pathlib import Path

from fastapi.testclient import TestClient
from docx import Document


def test_upload_image_is_persisted_without_fake_chunks(client: TestClient) -> None:
    response = client.post(
        "/api/v1/materials/upload",
        files={"file": ("diagram.png", b"not-a-real-image-but-stored", "image/png")},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["filename"] == "diagram.png"
    assert payload["status"] == "uploaded"
    assert payload["chunk_count"] == 0
    assert "OCR" in payload["error_message"]

    detail = client.get(f"/api/v1/materials/{payload['file_id']}")
    assert detail.status_code == 200
    assert detail.json()["chunks"] == []


def test_upload_docx_extracts_text_chunks(client: TestClient) -> None:
    document = Document()
    document.add_paragraph("光的折射发生在两种介质的交界面。")
    document.add_paragraph("入射光线、折射光线和法线在同一平面内。")
    buffer = BytesIO()
    document.save(buffer)
    buffer.seek(0)

    response = client.post(
        "/api/v1/materials/upload",
        files={
            "file": (
                "refraction.docx",
                buffer.getvalue(),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "parsed"
    assert payload["chunk_count"] >= 1

    chunks = client.get(f"/api/v1/materials/{payload['file_id']}/chunks")
    assert chunks.status_code == 200
    joined = "\n".join(chunk["content"] for chunk in chunks.json())
    assert "光的折射" in joined
    assert "同一平面" in joined


def test_upload_filename_path_is_sanitized(client: TestClient) -> None:
    response = client.post(
        "/api/v1/materials/upload",
        files={"file": ("..\\..\\escape.png", b"image-placeholder", "image/png")},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["filename"] == "escape.png"


def test_corrupt_supported_file_is_recorded_as_failed(client: TestClient) -> None:
    response = client.post(
        "/api/v1/materials/upload",
        files={"file": ("broken.pdf", b"not a pdf", "application/pdf")},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "failed"
    assert payload["chunk_count"] == 0
    assert payload["error_message"]

    detail = client.get(f"/api/v1/materials/{payload['file_id']}")
    assert detail.status_code == 200
    assert detail.json()["status"] == "failed"


def test_rejects_unsupported_upload_extension(client: TestClient) -> None:
    response = client.post(
        "/api/v1/materials/upload",
        files={"file": ("unsafe.exe", b"binary", "application/octet-stream")},
    )

    assert response.status_code == 400
    assert "unsupported file extension" in response.json()["detail"]


def test_generate_lesson_persists_workspace(client: TestClient) -> None:
    response = client.post(
        "/api/v1/lessons",
        json={"title": "教案-测试", "subject": "物理", "grade": "初中三年级", "topic": "浮力"},
    )

    assert response.status_code == 200
    lesson = response.json()
    assert lesson["id"]
    assert lesson["status"] == "draft"

    lessons = client.get("/api/v1/lessons")
    assert lessons.status_code == 200
    assert any(item["id"] == lesson["id"] for item in lessons.json())


def test_upload_file_is_stored_inside_test_runtime(client: TestClient) -> None:
    response = client.post(
        "/api/v1/materials/upload",
        files={"file": ("diagram.png", b"stored", "image/png")},
    )

    assert response.status_code == 200
    payload = response.json()
    stored_files = list((Path(__file__).resolve().parent / "_tmp" / "uploads").glob("**/*.png"))
    assert len(stored_files) == 1
    assert payload["file_id"] in str(stored_files[0])
