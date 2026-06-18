"""Tests for the Zettelkasten store (persistence and operations)."""

from pathlib import Path

import pytest

from narratological.models.note import LinkType, NoteType
from narratological.zettelkasten import store

# Path to the real compendium for the study-ref resolution test.
SPECS_PATH = Path(__file__).parent.parent.parent.parent / "specs" / "03-structured-data"
UNIFIED_JSON = SPECS_PATH / "narratological-algorithms-unified.json"


@pytest.fixture
def store_path(tmp_path):
    """A throwaway store path inside the test's temp dir."""
    return tmp_path / "zettelkasten.json"


class TestGenerateId:
    """Tests for generate_id."""

    def test_unique_base(self):
        new_id = store.generate_id(set())
        assert new_id
        assert "T" in new_id

    def test_collision_suffix(self):
        base = store.generate_id(set())
        with_suffix = store.generate_id({base})
        assert with_suffix != base
        assert with_suffix.startswith(base)
        assert with_suffix[len(base):].isalpha()


class TestRoundTrip:
    """Tests for save/load persistence."""

    def test_load_missing_returns_empty(self, store_path):
        zk = store.load_zettelkasten(store_path)
        assert zk.notes == {}

    def test_save_and_load_preserves_korean(self, store_path):
        note = store.create_note(
            "미메시스는 선택적이다",
            "예술은 본질을 모방한다.",
            note_type=NoteType.PERMANENT,
            tags=["미학"],
            path=store_path,
        )
        # Reload from disk in a fresh call.
        zk = store.load_zettelkasten(store_path)
        loaded = zk.get(note.id)
        assert loaded.title == "미메시스는 선택적이다"
        assert loaded.body == "예술은 본질을 모방한다."
        assert loaded.note_type == NoteType.PERMANENT
        # UTF-8 should be stored un-escaped.
        assert "미메시스" in store_path.read_text(encoding="utf-8")


class TestOperations:
    """Tests for the high-level CRUD/link operations."""

    def test_create_assigns_unique_ids(self, store_path):
        n1 = store.create_note("첫 노트", path=store_path)
        n2 = store.create_note("둘째 노트", path=store_path)
        assert n1.id != n2.id
        assert len(store.load_zettelkasten(store_path).notes) == 2

    def test_update_changes_only_given_fields(self, store_path):
        note = store.create_note("원래 제목", "원래 본문", tags=["a"], path=store_path)
        updated = store.update_note(
            note.id, title="새 제목", path=store_path
        )
        assert updated.title == "새 제목"
        assert updated.body == "원래 본문"  # unchanged
        assert updated.tags == ["a"]  # unchanged

    def test_update_missing_raises(self, store_path):
        with pytest.raises(KeyError):
            store.update_note("nope", title="x", path=store_path)

    def test_link_and_backlinks(self, store_path):
        a = store.create_note("A", path=store_path)
        b = store.create_note("B", path=store_path)
        store.link_notes(a.id, b.id, LinkType.ELABORATES, "이유", path=store_path)
        zk = store.load_zettelkasten(store_path)
        assert zk.get(a.id).links[0].target_id == b.id
        assert zk.get(a.id).links[0].link_type == LinkType.ELABORATES
        assert [n.id for n in zk.backlinks(b.id)] == [a.id]

    def test_link_is_idempotent(self, store_path):
        a = store.create_note("A", path=store_path)
        b = store.create_note("B", path=store_path)
        store.link_notes(a.id, b.id, path=store_path)
        store.link_notes(a.id, b.id, LinkType.SUPPORTS, path=store_path)
        zk = store.load_zettelkasten(store_path)
        links = zk.get(a.id).links
        assert len(links) == 1
        assert links[0].link_type == LinkType.SUPPORTS

    def test_link_missing_target_raises(self, store_path):
        a = store.create_note("A", path=store_path)
        with pytest.raises(KeyError):
            store.link_notes(a.id, "missing", path=store_path)

    def test_unlink(self, store_path):
        a = store.create_note("A", path=store_path)
        b = store.create_note("B", path=store_path)
        store.link_notes(a.id, b.id, path=store_path)
        store.unlink_notes(a.id, b.id, path=store_path)
        zk = store.load_zettelkasten(store_path)
        assert zk.get(a.id).links == []

    def test_delete_cleans_dangling_links(self, store_path):
        a = store.create_note("A", path=store_path)
        b = store.create_note("B", path=store_path)
        store.link_notes(a.id, b.id, path=store_path)
        assert store.delete_note(b.id, path=store_path) is True
        zk = store.load_zettelkasten(store_path)
        assert b.id not in zk.notes
        assert zk.get(a.id).links == []

    def test_delete_missing_returns_false(self, store_path):
        assert store.delete_note("nope", path=store_path) is False


class TestEnvVarResolution:
    """Tests that the store honors the NARRATOLOGICAL_NOTES env var."""

    def test_env_var_path(self, tmp_path, monkeypatch):
        target = tmp_path / "from_env.json"
        monkeypatch.setenv("NARRATOLOGICAL_NOTES", str(target))
        store.create_note("env 노트")
        assert target.exists()


class TestStudyRefResolution:
    """Tests for the narrative connection (study_ref resolution)."""

    @pytest.fixture(autouse=True)
    def _require_compendium(self):
        if not UNIFIED_JSON.exists():
            pytest.skip("Unified JSON not found - skipping study-ref tests")

    def test_resolve_study_and_axiom(self):
        resolved = store.resolve_study_ref("aristotle/A0")
        assert resolved is not None
        assert resolved["study_id"] == "aristotle"
        assert resolved["axiom_id"] == "A0"
        assert "axiom_statement" in resolved

    def test_resolve_study_only(self):
        resolved = store.resolve_study_ref("aristotle")
        assert resolved is not None
        assert resolved["creator"] == "Aristotle"
        assert "axiom_id" not in resolved

    def test_resolve_unknown_returns_none(self):
        assert store.resolve_study_ref("nonexistent-study") is None
        assert store.resolve_study_ref("aristotle/ZZ-999") is None
