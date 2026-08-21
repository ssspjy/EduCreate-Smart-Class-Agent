"""材料解析 SSE 事件流测试。"""

import json

from fastapi.testclient import TestClient


def test_material_events_emits_terminal_snapshot(client: TestClient) -> None:
    upload = client.post("/api/v1/materials/upload", files={"file": ("lesson.txt", "第一条要点".encode("utf-8"), "text/plain")})
    assert upload.status_code == 200
    material_id = upload.json()["file_id"]

    response = client.get(f"/api/v1/materials/{material_id}/events")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert "event: material" in response.text
    data_line = next(line for line in response.text.splitlines() if line.startswith("data: "))
    payload = json.loads(data_line.removeprefix("data: "))
    assert payload["file_id"] == material_id
    assert payload["status"] == "parsed"


def test_material_events_returns_404_for_unknown_material(client: TestClient) -> None:
    response = client.get("/api/v1/materials/not-found/events")
    assert response.status_code == 404
