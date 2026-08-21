"""课堂互动模板生成测试。"""

from fastapi.testclient import TestClient


OUTLINE = {
    "title": "光的折射",
    "sections": [
        {"id": "1", "title": "导入", "bullets": ["光从一种介质进入另一种介质会发生偏折", "入射光线、折射光线和法线在同一平面内"], "duration_minutes": 8, "slide_count": 2},
    ],
}


def test_generate_choice_uses_fixed_escaped_template(client: TestClient) -> None:
    response = client.post("/api/v1/interactive/generate", json={"outline": OUTLINE, "interaction_type": "choice", "count": 2})
    assert response.status_code == 200
    payload = response.json()
    assert len(payload["items"]) == 2
    assert payload["items"][0]["options"]
    assert "<script>" not in payload["html"]
    assert "光从一种介质" in payload["html"]


def test_generate_true_false_can_target_section(client: TestClient) -> None:
    response = client.post("/api/v1/interactive/generate", json={
        "outline": OUTLINE,
        "interaction_type": "true_false",
        "count": 3,
        "section_id": "1",
    })
    assert response.status_code == 200
    assert response.json()["items"][0]["answer"] == "正确"
    assert "可用要点只有 2 条" in response.json()["warnings"][0]


def test_generate_without_bullets_degrades_with_warning(client: TestClient) -> None:
    response = client.post("/api/v1/interactive/generate", json={
        "outline": {"title": "空课件", "sections": [{"id": "1", "title": "空章节", "bullets": []}]},
        "interaction_type": "fill_blank",
        "count": 2,
    })
    assert response.status_code == 200
    assert response.json()["items"] == []
    assert response.json()["warnings"]


def test_unknown_interaction_type_is_rejected(client: TestClient) -> None:
    response = client.post("/api/v1/interactive/generate", json={"outline": OUTLINE, "interaction_type": "run_code"})
    assert response.status_code == 422
