from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_list_items():
    response = client.get("/items")
    assert response.status_code == 200
    assert len(response.json()) >= 1


def test_get_item():
    response = client.get("/items/1")
    assert response.status_code == 200
    assert response.json()["name"] == "Notebook"
