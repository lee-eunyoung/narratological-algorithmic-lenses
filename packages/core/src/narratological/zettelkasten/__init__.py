"""Zettelkasten note subsystem (독일식 메모법).

Atomic, uniquely-identified notes linked into a navigable index, following
Niklas Luhmann's German note-taking method. See :mod:`.store` for persistence
and operations, and :mod:`narratological.models.note` for the data models.
"""

from narratological.models.note import (
    LinkType,
    Note,
    NoteLink,
    NoteType,
    Zettelkasten,
)
from narratological.zettelkasten.store import (
    create_note,
    delete_note,
    generate_id,
    link_notes,
    load_zettelkasten,
    resolve_study_ref,
    save_zettelkasten,
    unlink_notes,
    update_note,
)

__all__ = [
    # Models
    "Note",
    "NoteLink",
    "NoteType",
    "LinkType",
    "Zettelkasten",
    # Store / operations
    "load_zettelkasten",
    "save_zettelkasten",
    "generate_id",
    "create_note",
    "update_note",
    "delete_note",
    "link_notes",
    "unlink_notes",
    "resolve_study_ref",
]
