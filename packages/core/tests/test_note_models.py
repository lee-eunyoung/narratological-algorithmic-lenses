"""Tests for the Zettelkasten note models."""

from narratological.models.note import (
    LinkType,
    Note,
    NoteLink,
    NoteType,
    Zettelkasten,
)


def _note(note_id: str, title: str, **kwargs) -> Note:
    """Build a Note with sensible timestamp defaults for tests."""
    return Note(
        id=note_id,
        title=title,
        created="2026-06-18T00:00:00+00:00",
        updated="2026-06-18T00:00:00+00:00",
        **kwargs,
    )


class TestNoteModel:
    """Tests for the Note model."""

    def test_defaults(self):
        """A minimal note defaults to a fleeting type with empty collections."""
        note = _note("20260618T0001", "미메시스는 선택적이다")
        assert note.note_type == NoteType.FLEETING
        assert note.tags == []
        assert note.links == []
        assert note.source is None
        assert note.study_ref is None

    def test_link_helpers(self):
        """link_ids and has_link reflect the note's outgoing links."""
        note = _note(
            "a",
            "원자성",
            links=[NoteLink(target_id="b"), NoteLink(target_id="c")],
        )
        assert note.link_ids() == ["b", "c"]
        assert note.has_link("b")
        assert not note.has_link("z")

    def test_note_type_enum(self):
        """Note types accept the Luhmann classification values."""
        note = _note("a", "영구노트", note_type=NoteType.PERMANENT)
        assert note.note_type == NoteType.PERMANENT
        assert note.model_dump(mode="json")["note_type"] == "permanent"


class TestZettelkasten:
    """Tests for the Zettelkasten index."""

    def _build(self) -> Zettelkasten:
        zk = Zettelkasten()
        zk.add(_note(
            "1",
            "미메시스는 선택적이다",
            body="예술은 본질을 모방한다.",
            note_type=NoteType.PERMANENT,
            tags=["미학"],
            study_ref="aristotle/A0",
            links=[NoteLink(target_id="2", link_type=LinkType.ELABORATES)],
        ))
        zk.add(_note(
            "2",
            "카타르시스는 사전 설정이 필요하다",
            body="감정 해방에는 긴장 축적이 선행된다.",
            note_type=NoteType.LITERATURE,
            tags=["감정"],
        ))
        zk.add(_note("3", "고립된 임시 메모", note_type=NoteType.FLEETING))
        return zk

    def test_get_and_list(self):
        zk = self._build()
        assert zk.get("1").title == "미메시스는 선택적이다"
        assert zk.get("missing") is None
        assert len(zk.list_notes()) == 3

    def test_backlinks(self):
        zk = self._build()
        backs = zk.backlinks("2")
        assert [n.id for n in backs] == ["1"]
        assert zk.backlinks("1") == []

    def test_search(self):
        zk = self._build()
        # Body match
        assert {n.id for n in zk.search("긴장")} == {"2"}
        # Tag match (case-insensitive path)
        assert {n.id for n in zk.search("미학")} == {"1"}

    def test_by_tag(self):
        zk = self._build()
        assert [n.id for n in zk.by_tag("감정")] == ["2"]
        assert zk.by_tag("없음") == []

    def test_by_type(self):
        zk = self._build()
        assert [n.id for n in zk.by_type(NoteType.PERMANENT)] == ["1"]
        assert [n.id for n in zk.by_type(NoteType.FLEETING)] == ["3"]

    def test_all_tags(self):
        zk = self._build()
        assert zk.all_tags() == ["감정", "미학"]

    def test_orphans(self):
        zk = self._build()
        # Note 3 has no incoming or outgoing links.
        assert [n.id for n in zk.orphans()] == ["3"]

    def test_graph(self):
        zk = self._build()
        g = zk.graph()
        assert len(g["nodes"]) == 3
        assert g["edges"] == [
            {"source": "1", "target": "2", "link_type": "elaborates"}
        ]

    def test_remove_cleans_dangling_links(self):
        zk = self._build()
        assert zk.remove("2") is True
        # Note 1's link to 2 should be gone.
        assert zk.get("1").links == []
        assert zk.remove("missing") is False
