"""Contract tests for the Zettelkasten note API routes."""

import pytest


@pytest.fixture(autouse=True)
def temp_store(tmp_path, monkeypatch):
    """Point the note store at a throwaway file for every test.

    The note routes resolve the store path per request via the
    NARRATOLOGICAL_NOTES env var, so setting it here isolates each test.
    """
    monkeypatch.setenv("NARRATOLOGICAL_NOTES", str(tmp_path / "zk.json"))


def _create(client, title="미메시스는 선택적이다", **fields) -> dict:
    payload = {"title": title, **fields}
    resp = client.post("/notes/", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


class TestNoteCrud:
    """CRUD endpoint contracts."""

    def test_create_and_get(self, client):
        note = _create(client, body="예술은 본질을 모방한다.", note_type="permanent", tags=["미학"])
        assert note["note_type"] == "permanent"

        resp = client.get(f"/notes/{note['id']}")
        assert resp.status_code == 200
        assert resp.json()["title"] == "미메시스는 선택적이다"

    def test_list_with_filters(self, client):
        _create(client, title="영구", note_type="permanent", tags=["미학"])
        _create(client, title="임시", note_type="fleeting")

        resp = client.get("/notes/", params={"note_type": "permanent"})
        assert resp.status_code == 200
        titles = [n["title"] for n in resp.json()]
        assert titles == ["영구"]

        resp = client.get("/notes/", params={"tag": "미학"})
        assert [n["title"] for n in resp.json()] == ["영구"]

    def test_update(self, client):
        note = _create(client, title="원래")
        resp = client.put(f"/notes/{note['id']}", json={"title": "수정됨"})
        assert resp.status_code == 200
        assert resp.json()["title"] == "수정됨"

    def test_get_missing_returns_404(self, client):
        resp = client.get("/notes/nonexistent")
        assert resp.status_code == 404

    def test_delete(self, client):
        note = _create(client)
        resp = client.delete(f"/notes/{note['id']}")
        assert resp.status_code == 200
        assert client.get(f"/notes/{note['id']}").status_code == 404


class TestNoteLinks:
    """Link and backlink endpoint contracts."""

    def test_link_and_backlinks(self, client):
        a = _create(client, title="A")
        b = _create(client, title="B")
        resp = client.post(f"/notes/{a['id']}/links", json={"target_id": b["id"], "link_type": "elaborates"})
        assert resp.status_code == 201

        resp = client.get(f"/notes/{b['id']}/backlinks")
        assert resp.status_code == 200
        assert [n["id"] for n in resp.json()] == [a["id"]]

    def test_link_missing_target_404(self, client):
        a = _create(client, title="A")
        resp = client.post(f"/notes/{a['id']}/links", json={"target_id": "missing"})
        assert resp.status_code == 404

    def test_unlink(self, client):
        a = _create(client, title="A")
        b = _create(client, title="B")
        client.post(f"/notes/{a['id']}/links", json={"target_id": b["id"]})
        resp = client.delete(f"/notes/{a['id']}/links/{b['id']}")
        assert resp.status_code == 200
        assert resp.json()["links"] == []


class TestNoteQueries:
    """Search, graph, tags, and study-ref endpoints."""

    def test_search(self, client):
        _create(client, title="감정의 카타르시스", body="긴장 축적")
        resp = client.get("/notes/search", params={"q": "카타르시스"})
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_graph(self, client):
        a = _create(client, title="A")
        b = _create(client, title="B")
        client.post(f"/notes/{a['id']}/links", json={"target_id": b["id"]})
        resp = client.get("/notes/graph")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["nodes"]) == 2
        assert len(body["edges"]) == 1
        assert "orphans" in body

    def test_tags(self, client):
        _create(client, tags=["미학", "감정"])
        resp = client.get("/notes/tags")
        assert resp.status_code == 200
        assert set(resp.json()) == {"미학", "감정"}

    def test_study_ref_resolution(self, client):
        note = _create(client, title="아리스토텔레스", study_ref="aristotle/A0")
        resp = client.get(f"/notes/{note['id']}/study-ref")
        assert resp.status_code == 200
        body = resp.json()
        assert body["study_id"] == "aristotle"
        assert body["axiom_id"] == "A0"

    def test_study_ref_absent_404(self, client):
        note = _create(client, title="연결 없음")
        resp = client.get(f"/notes/{note['id']}/study-ref")
        assert resp.status_code == 404
