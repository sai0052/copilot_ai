from fastapi.testclient import TestClient


def test_import_endpoint_preserves_tree(client: TestClient):
    response = client.post(
        "/api/projects/import",
        json={
            "name": "demo",
            "files": [
                {"path": "app/main.py", "content": "from fastapi import FastAPI\napp=FastAPI()\n"},
                {"path": "requirements.txt", "content": "fastapi\n"},
            ],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["project_type"] == "fastapi"
    scanned = client.post(f"/api/projects/{body['id']}/scan")
    assert scanned.status_code == 200
    paths = [item["path"] for item in scanned.json()["files"]]
    assert "app/main.py" in paths
    assert "app" in scanned.json()["tree"]
    assert "main.py" in scanned.json()["tree"]


def test_import_rejects_traversal_via_api(client: TestClient):
    response = client.post(
        "/api/projects/import",
        json={"name": "bad", "files": [{"path": "../../etc/passwd", "content": "x"}]},
    )
    assert response.status_code == 400
    assert "LLM_API_KEY" not in response.text


def test_health_never_includes_api_key(client: TestClient):
    response = client.get("/health")
    assert "LLM_API_KEY" not in response.text
    assert "llm_api_key" not in response.text.lower()
    assert "api_key" not in response.json()
