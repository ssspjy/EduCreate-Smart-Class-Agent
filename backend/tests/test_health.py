"""后端存活与 API 占位测试。"""

from fastapi.testclient import TestClient


def test_health_ok(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert "version" in payload


def test_lessons_list_ok(client: TestClient) -> None:
    response = client.get("/api/v1/lessons")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_knowledge_search_ok(client: TestClient) -> None:
    response = client.post(
        "/api/v1/knowledge/search",
        json={"query": "光的折射", "top_k": 3},
    )
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_openapi_docs_ok(client: TestClient) -> None:
    """确保所有路由注册成功（无路由加载错误）。"""
    response = client.get("/openapi.json")
    assert response.status_code == 200
    paths = response.json()["paths"]
    assert "/health" in paths
    assert "/api/v1/auth/login" in paths
    assert "/api/v1/lessons/generate" in paths
    assert "/api/v1/knowledge/search" in paths
