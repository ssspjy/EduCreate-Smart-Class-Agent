"""Courseware generation job, persistence and SSE tests."""

from pathlib import Path

from fastapi.testclient import TestClient

from app.db import SessionLocal
from app.models import GeneratedArtifact, GenerationJob
from app.services.generation_service import run_generation_job


def _outline(lesson_id: str) -> dict:
    return {
        "title": "异步浮力课件",
        "subject": "物理",
        "grade": "八年级",
        "sections": [
            {
                "id": "intro",
                "title": "浮力导入",
                "bullets": ["观察物体在水中的受力"],
                "duration_minutes": 5,
                "slide_count": 2,
            }
        ],
        "total_slides": 2,
        "total_duration_minutes": 5,
        "lesson_id": lesson_id,
    }


def test_generation_job_completes_and_streams_terminal_event(client: TestClient) -> None:
    lesson = client.post("/api/v1/lessons", json={"title": "异步生成测试"})
    assert lesson.status_code == 200
    lesson_id = lesson.json()["id"]

    created = client.post("/api/v1/exports/pptx/jobs", json=_outline(lesson_id))
    assert created.status_code == 202
    payload = created.json()
    assert payload["status"] == "completed"
    assert payload["progress"] == 100
    assert payload["output"]["url"].endswith(".pptx")

    status_response = client.get(f"/api/v1/exports/jobs/{payload['job_id']}")
    assert status_response.status_code == 200
    assert status_response.json()["output"] == payload["output"]

    events = client.get(f"/api/v1/exports/jobs/{payload['job_id']}/events")
    assert events.status_code == 200
    assert events.headers["content-type"].startswith("text/event-stream")
    assert "event: generation" in events.text
    assert '"status": "completed"' in events.text

    downloaded = client.get(payload["output"]["url"])
    assert downloaded.status_code == 200
    assert downloaded.content.startswith(b"PK")

    cannot_cancel = client.post(f"/api/v1/exports/jobs/{payload['job_id']}/cancel")
    assert cannot_cancel.status_code == 409

    with SessionLocal() as db:
        job = db.get(GenerationJob, payload["job_id"])
        artifact = db.query(GeneratedArtifact).filter(GeneratedArtifact.job_id == payload["job_id"]).one()
        assert job is not None
        assert job.status == "completed"
        assert Path(artifact.storage_path).is_file()


def test_generation_job_rejects_unknown_lesson(client: TestClient) -> None:
    response = client.post("/api/v1/exports/pptx/jobs", json=_outline("missing-lesson"))

    assert response.status_code == 404
    assert response.json()["detail"] == "lesson_id 不存在"


def test_generation_job_rejects_more_than_fifty_slides(client: TestClient) -> None:
    lesson = client.post("/api/v1/lessons", json={"title": "页数边界测试"})
    body = _outline(lesson.json()["id"])
    body["total_slides"] = 51

    response = client.post("/api/v1/exports/pptx/jobs", json=body)

    assert response.status_code == 422


def test_generation_job_events_return_404(client: TestClient) -> None:
    response = client.get("/api/v1/exports/jobs/missing/events")

    assert response.status_code == 404


def test_queued_generation_can_be_cancelled_and_retried(client: TestClient) -> None:
    lesson = client.post("/api/v1/lessons", json={"title": "取消重试测试"})
    lesson_id = lesson.json()["id"]
    with SessionLocal() as db:
        job = GenerationJob(
            lesson_id=lesson_id,
            job_type="pptx",
            status="queued",
            request_json=_outline(lesson_id),
        )
        db.add(job)
        db.commit()
        db.refresh(job)
        job_id = job.id

    cancelled = client.post(f"/api/v1/exports/jobs/{job_id}/cancel")
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"
    assert cancelled.json()["cancel_requested"] is True

    retried = client.post(f"/api/v1/exports/jobs/{job_id}/retry")
    assert retried.status_code == 200
    assert retried.json()["status"] == "completed"
    assert retried.json()["progress"] == 100
    assert retried.json()["output"]["artifact_id"]


def test_generation_worker_skips_stale_task_and_marks_cancelled(client: TestClient) -> None:
    lesson = client.post("/api/v1/lessons", json={"title": "安全停止测试"})
    lesson_id = lesson.json()["id"]
    with SessionLocal() as db:
        job = GenerationJob(
            lesson_id=lesson_id,
            job_type="pptx",
            status="cancelling",
            cancel_requested=True,
            task_id="new-task",
            request_json=_outline(lesson_id),
        )
        db.add(job)
        db.commit()
        db.refresh(job)
        job_id = job.id

        stale_result = run_generation_job(db, job_id, task_id="old-task")
        assert stale_result.status == "cancelling"

        result = run_generation_job(db, job_id, task_id="new-task")
        assert result.status == "cancelled"
        assert result.cancel_requested is True
