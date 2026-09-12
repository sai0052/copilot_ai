from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient


def _repo(tmp_path: Path, name: str, filename: str, content: str) -> Path:
    root = tmp_path / name
    root.mkdir()
    (root / filename).write_text(content, encoding="utf-8")
    return root


def test_register_valid_repository(client: TestClient, tmp_path: Path):
    root = _repo(tmp_path, "alpha", "main.py", "print(1)\n")
    created = client.post("/api/projects", json={"root_path": str(root), "name": "alpha"})
    assert created.status_code == 200
    body = created.json()
    assert body["name"] == "alpha"
    assert body["id"]
    assert body["source"] == "local_path"
    scanned = client.post(f"/api/projects/{body['id']}/scan")
    assert scanned.status_code == 200
    assert scanned.json()["file_count"] >= 1
    assert "main.py" in scanned.json()["tree"]
    listed = client.get("/api/projects")
    assert any(item["id"] == body["id"] for item in listed.json())


def test_register_nonexistent_path(client: TestClient, tmp_path: Path):
    missing = client.post("/api/projects", json={"root_path": str(tmp_path / "nope")})
    assert missing.status_code == 404
    assert missing.json()["detail"] == "Repository path does not exist."


def test_register_file_instead_of_directory(client: TestClient, tmp_path: Path):
    file_path = tmp_path / "readme.txt"
    file_path.write_text("hi\n", encoding="utf-8")
    response = client.post("/api/projects", json={"root_path": str(file_path)})
    assert response.status_code == 400
    assert "not a directory" in response.json()["detail"].lower()


def test_switch_between_two_repositories(client: TestClient, tmp_path: Path):
    one = _repo(tmp_path, "repo_one", "one.py", "x = 1\n")
    two = _repo(tmp_path, "repo_two", "two.py", "y = 2\n")
    a = client.post("/api/projects", json={"root_path": str(one), "name": "repo_one"}).json()
    b = client.post("/api/projects", json={"root_path": str(two), "name": "repo_two"}).json()
    assert a["id"] != b["id"]
    scan_a = client.post(f"/api/projects/{a['id']}/scan").json()
    scan_b = client.post(f"/api/projects/{b['id']}/scan").json()
    assert "one.py" in scan_a["tree"]
    assert "two.py" in scan_b["tree"]
    assert "two.py" not in scan_a["tree"]
    assert "one.py" not in scan_b["tree"]
    listed = client.get("/api/projects").json()
    ids = [item["id"] for item in listed]
    assert a["id"] in ids and b["id"] in ids


def test_scan_newly_registered_repository(client: TestClient, tmp_path: Path):
    root = _repo(tmp_path, "fresh", "app.py", "print('fresh')\n")
    created = client.post("/api/projects", json={"root_path": str(root)}).json()
    scanned = client.post(f"/api/projects/{created['id']}/scan")
    assert scanned.status_code == 200
    paths = [item["path"] for item in scanned.json()["files"]]
    assert "app.py" in paths
    assert scanned.json()["root"].replace("\\", "/").endswith("fresh")


def test_project_list_refresh_after_register(client: TestClient, tmp_path: Path):
    before = client.get("/api/projects").json()
    root = _repo(tmp_path, "listed", "x.py", "x=1\n")
    created = client.post("/api/projects", json={"root_path": str(root), "name": "listed"}).json()
    after = client.get("/api/projects").json()
    assert len(after) == len(before) + 1
    assert after[0]["id"] == created["id"]


def test_invalid_path_empty(client: TestClient):
    response = client.post("/api/projects", json={"root_path": ""})
    assert response.status_code == 422


def test_permission_access_failure(client: TestClient, tmp_path: Path, monkeypatch):
    root = _repo(tmp_path, "locked", "z.py", "z=1\n")

    def boom(_path):
        raise PermissionError("denied")

    monkeypatch.setattr("app.api.routes.projects.scanner.scan", boom)
    response = client.post("/api/projects", json={"root_path": str(root)})
    assert response.status_code == 403
    assert "could not be accessed" in response.json()["detail"].lower()


def test_import_creates_distinct_workspace(client: TestClient):
    first = client.post(
        "/api/projects/import",
        json={"name": "copy", "files": [{"path": "a.py", "content": "a=1\n"}]},
    ).json()
    second = client.post(
        "/api/projects/import",
        json={"name": "copy", "files": [{"path": "b.py", "content": "b=2\n"}]},
    ).json()
    assert first["id"] != second["id"]
    assert first["source"] == "imported"
    assert first["root_path"] != second["root_path"]
    scan = client.post(f"/api/projects/{second['id']}/scan").json()
    assert "b.py" in scan["tree"]
    assert "a.py" not in scan["tree"]
