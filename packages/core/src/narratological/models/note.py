"""Pydantic models for the Zettelkasten note subsystem.

Implements the "German note-taking method" (독일식 메모법) — Niklas Luhmann's
Zettelkasten — as atomic, uniquely-identified notes ("Zettel") woven together
by bidirectional links and tags into a navigable index.

Three note types follow Luhmann's classic workflow:
- PERMANENT (영구노트): fully-formed, atomic ideas in your own words.
- LITERATURE (문헌노트): notes taken while reading a source.
- FLEETING (임시노트): quick, temporary captures to be processed later.

Notes can additionally carry a ``study_ref`` linking them back into the
narratological compendium (a study id or ``study_id/axiom_id``), tying the
personal note web into the formalized knowledge base.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class NoteType(StrEnum):
    """Luhmann's three-tier note classification (노트 유형)."""

    PERMANENT = "permanent"  # 영구노트
    LITERATURE = "literature"  # 문헌노트
    FLEETING = "fleeting"  # 임시노트


class LinkType(StrEnum):
    """The semantic relationship expressed by an outgoing link."""

    REFERENCE = "reference"
    FOLLOWS = "follows"
    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"
    ELABORATES = "elaborates"


class NoteLink(BaseModel):
    """A directed link from one note to another.

    Backlinks are never stored; they are computed by scanning the index
    (see :meth:`Zettelkasten.backlinks`), so link state is never duplicated.
    """

    target_id: str = Field(description="ID of the note being linked to")
    link_type: LinkType = Field(
        default=LinkType.REFERENCE,
        description="The kind of relationship this link expresses",
    )
    context: str | None = Field(
        default=None,
        description="Optional note on why this link exists",
    )


class Note(BaseModel):
    """A single atomic note (Zettel).

    Each note should capture exactly one idea, identified by a unique,
    collision-free ID and connected to other notes via :attr:`links`.
    """

    id: str = Field(description="Unique identifier (timestamp-based, e.g. '20260618T1230')")
    title: str = Field(description="Short, declarative title for the idea")
    body: str = Field(default="", description="Note content (markdown)")
    note_type: NoteType = Field(
        default=NoteType.FLEETING,
        description="Luhmann note classification (영구/문헌/임시)",
    )
    tags: list[str] = Field(default_factory=list, description="Free-form topic tags")
    links: list[NoteLink] = Field(
        default_factory=list,
        description="Outgoing links to other notes",
    )
    source: str | None = Field(
        default=None,
        description="Optional provenance/citation (free text)",
    )
    study_ref: str | None = Field(
        default=None,
        description="Narrative connection: 'study_id' or 'study_id/axiom_id'",
    )
    created: str = Field(description="Creation timestamp (ISO format)")
    updated: str = Field(description="Last-update timestamp (ISO format)")

    def link_ids(self) -> list[str]:
        """Return the IDs of all notes this note links to."""
        return [link.target_id for link in self.links]

    def has_link(self, target_id: str) -> bool:
        """Return True if this note already links to ``target_id``."""
        return any(link.target_id == target_id for link in self.links)


class Zettelkasten(BaseModel):
    """The in-memory note index (the "slip box").

    Holds every note keyed by ID and provides the traversal/query surface
    over them, analogous to :class:`narratological.models.study.Compendium`.
    """

    notes: dict[str, Note] = Field(
        default_factory=dict,
        description="Notes keyed by their ID",
    )

    def add(self, note: Note) -> None:
        """Add or replace a note in the index."""
        self.notes[note.id] = note

    def get(self, note_id: str) -> Note | None:
        """Get a note by ID, or None if it does not exist."""
        return self.notes.get(note_id)

    def remove(self, note_id: str) -> bool:
        """Remove a note and any links pointing to it.

        Returns True if the note existed and was removed.
        """
        if note_id not in self.notes:
            return False
        del self.notes[note_id]
        # Clean up dangling links from the remaining notes.
        for other in self.notes.values():
            other.links = [link for link in other.links if link.target_id != note_id]
        return True

    def list_notes(self) -> list[Note]:
        """Return all notes."""
        return list(self.notes.values())

    def backlinks(self, note_id: str) -> list[Note]:
        """Return all notes that link *to* ``note_id``."""
        return [n for n in self.notes.values() if n.has_link(note_id)]

    def search(self, query: str) -> list[Note]:
        """Substring search across title, body, and tags (case-insensitive)."""
        q = query.lower()
        results = []
        for note in self.notes.values():
            if (
                q in note.title.lower()
                or q in note.body.lower()
                or any(q in tag.lower() for tag in note.tags)
            ):
                results.append(note)
        return results

    def by_tag(self, tag: str) -> list[Note]:
        """Return all notes carrying ``tag`` (case-insensitive)."""
        t = tag.lower()
        return [n for n in self.notes.values() if any(t == nt.lower() for nt in n.tags)]

    def by_type(self, note_type: NoteType) -> list[Note]:
        """Return all notes of a given :class:`NoteType`."""
        return [n for n in self.notes.values() if n.note_type == note_type]

    def all_tags(self) -> list[str]:
        """Return the sorted set of all tags used across notes."""
        tags: set[str] = set()
        for note in self.notes.values():
            tags.update(note.tags)
        return sorted(tags)

    def orphans(self) -> list[Note]:
        """Return notes with no outgoing and no incoming links."""
        linked_to: set[str] = set()
        for note in self.notes.values():
            linked_to.update(note.link_ids())
        return [
            n
            for n in self.notes.values()
            if not n.links and n.id not in linked_to
        ]

    def graph(self) -> dict[str, list[dict[str, str]]]:
        """Return a node/edge representation for export or visualization."""
        nodes = [
            {"id": n.id, "title": n.title, "note_type": n.note_type.value}
            for n in self.notes.values()
        ]
        edges = [
            {
                "source": n.id,
                "target": link.target_id,
                "link_type": link.link_type.value,
            }
            for n in self.notes.values()
            for link in n.links
        ]
        return {"nodes": nodes, "edges": edges}
