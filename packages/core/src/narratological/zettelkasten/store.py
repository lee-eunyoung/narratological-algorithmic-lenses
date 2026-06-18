"""Persistence and operations for the Zettelkasten note subsystem.

The store is a single JSON file whose location is resolved exactly like the
study compendium (see :mod:`narratological.loader`):

1. ``NARRATOLOGICAL_NOTES`` environment variable, if set.
2. Default user path ``~/.narratological/zettelkasten.json`` (created on demand).

High-level operations follow a load -> mutate -> save pattern and return the
affected note, keeping each call self-contained and crash-safe.
"""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

from narratological.models.note import LinkType, Note, NoteLink, NoteType, Zettelkasten

if TYPE_CHECKING:
    from collections.abc import Iterable
    from os import PathLike

DEFAULT_STORE = Path.home() / ".narratological" / "zettelkasten.json"


def _now() -> str:
    """Return the current UTC time as an ISO-8601 string."""
    return datetime.now(UTC).isoformat()


def _get_store_path() -> Path:
    """Resolve the path to the notes store.

    Priority:
    1. NARRATOLOGICAL_NOTES env var.
    2. Default user path (~/.narratological/zettelkasten.json).
    """
    env_path = os.environ.get("NARRATOLOGICAL_NOTES")
    if env_path:
        return Path(env_path)
    return DEFAULT_STORE


def load_zettelkasten(path: str | PathLike[str] | None = None) -> Zettelkasten:
    """Load the note index from disk.

    Returns an empty :class:`Zettelkasten` if the store file does not yet
    exist, so first-time use needs no setup.
    """
    file_path = Path(path) if path else _get_store_path()

    if not file_path.exists():
        return Zettelkasten()

    with open(file_path, encoding="utf-8") as f:
        data = json.load(f)

    return Zettelkasten.model_validate(data)


def save_zettelkasten(
    zk: Zettelkasten,
    path: str | PathLike[str] | None = None,
) -> None:
    """Write the note index to disk, creating parent directories as needed.

    The write is atomic: data is written to a temporary file in the same
    directory and then moved into place.
    """
    file_path = Path(path) if path else _get_store_path()
    file_path.parent.mkdir(parents=True, exist_ok=True)

    tmp_path = file_path.with_suffix(file_path.suffix + ".tmp")
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(zk.model_dump(mode="json"), f, ensure_ascii=False, indent=2)
    tmp_path.replace(file_path)


def generate_id(existing: Iterable[str]) -> str:
    """Generate a unique, timestamp-based note ID.

    Uses a ``YYYYMMDDTHHMMSS`` base (Luhmann's modern, collision-free scheme).
    If that ID is already taken, a lowercase-letter suffix is appended
    (``...a``, ``...b``, ...) until a free ID is found.
    """
    existing_set = set(existing)
    base = datetime.now(UTC).strftime("%Y%m%dT%H%M%S")
    if base not in existing_set:
        return base

    for i in range(26):
        candidate = f"{base}{chr(ord('a') + i)}"
        if candidate not in existing_set:
            return candidate

    # Extremely unlikely fallback: append microseconds.
    return f"{base}{datetime.now(UTC).strftime('%f')}"


def create_note(
    title: str,
    body: str = "",
    note_type: NoteType = NoteType.FLEETING,
    tags: Iterable[str] = (),
    source: str | None = None,
    study_ref: str | None = None,
    path: str | PathLike[str] | None = None,
) -> Note:
    """Create and persist a new note, returning it."""
    zk = load_zettelkasten(path)
    now = _now()
    note = Note(
        id=generate_id(zk.notes.keys()),
        title=title,
        body=body,
        note_type=note_type,
        tags=list(tags),
        source=source,
        study_ref=study_ref,
        created=now,
        updated=now,
    )
    zk.add(note)
    save_zettelkasten(zk, path)
    return note


def update_note(
    note_id: str,
    *,
    title: str | None = None,
    body: str | None = None,
    note_type: NoteType | None = None,
    tags: Iterable[str] | None = None,
    source: str | None = None,
    study_ref: str | None = None,
    path: str | PathLike[str] | None = None,
) -> Note:
    """Update fields on an existing note and persist it.

    Only the provided (non-None) fields are changed.

    Raises:
        KeyError: If the note does not exist.
    """
    zk = load_zettelkasten(path)
    note = zk.get(note_id)
    if note is None:
        raise KeyError(f"Note '{note_id}' not found")

    if title is not None:
        note.title = title
    if body is not None:
        note.body = body
    if note_type is not None:
        note.note_type = note_type
    if tags is not None:
        note.tags = list(tags)
    if source is not None:
        note.source = source
    if study_ref is not None:
        note.study_ref = study_ref
    note.updated = _now()

    zk.add(note)
    save_zettelkasten(zk, path)
    return note


def delete_note(
    note_id: str,
    path: str | PathLike[str] | None = None,
) -> bool:
    """Delete a note (and any links pointing to it). Returns True if removed."""
    zk = load_zettelkasten(path)
    removed = zk.remove(note_id)
    if removed:
        save_zettelkasten(zk, path)
    return removed


def link_notes(
    source_id: str,
    target_id: str,
    link_type: LinkType = LinkType.REFERENCE,
    context: str | None = None,
    path: str | PathLike[str] | None = None,
) -> Note:
    """Add an outgoing link from ``source_id`` to ``target_id``.

    If the link already exists, its type and context are updated.

    Raises:
        KeyError: If either note does not exist.
    """
    zk = load_zettelkasten(path)
    source = zk.get(source_id)
    if source is None:
        raise KeyError(f"Note '{source_id}' not found")
    if zk.get(target_id) is None:
        raise KeyError(f"Note '{target_id}' not found")

    existing = next((link for link in source.links if link.target_id == target_id), None)
    if existing is not None:
        existing.link_type = link_type
        existing.context = context
    else:
        source.links.append(
            NoteLink(target_id=target_id, link_type=link_type, context=context)
        )
    source.updated = _now()

    zk.add(source)
    save_zettelkasten(zk, path)
    return source


def unlink_notes(
    source_id: str,
    target_id: str,
    path: str | PathLike[str] | None = None,
) -> Note:
    """Remove the link from ``source_id`` to ``target_id``.

    Raises:
        KeyError: If the source note does not exist.
    """
    zk = load_zettelkasten(path)
    source = zk.get(source_id)
    if source is None:
        raise KeyError(f"Note '{source_id}' not found")

    source.links = [link for link in source.links if link.target_id != target_id]
    source.updated = _now()

    zk.add(source)
    save_zettelkasten(zk, path)
    return source


def resolve_study_ref(study_ref: str) -> dict[str, str] | None:
    """Resolve a note's ``study_ref`` into a compendium summary.

    Accepts ``study_id`` or ``study_id/axiom_id`` and uses the existing
    study loader to fetch details (the narrative connection). Returns a small
    summary dict, or None if the reference cannot be resolved.
    """
    from narratological.loader import load_study

    ref = study_ref.strip()
    if "/" in ref:
        study_id, axiom_id = ref.split("/", 1)
    else:
        study_id, axiom_id = ref, None

    try:
        study = load_study(study_id)
    except (KeyError, FileNotFoundError):
        return None

    summary: dict[str, str] = {
        "study_id": study.id,
        "creator": study.creator,
        "work": study.work,
    }

    if axiom_id:
        axiom = study.get_axiom(axiom_id)
        if axiom is None:
            return None
        summary["axiom_id"] = axiom.id
        summary["axiom_name"] = axiom.name
        summary["axiom_statement"] = axiom.statement

    return summary
