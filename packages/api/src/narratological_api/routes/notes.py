"""API routes for the Zettelkasten note subsystem (독일식 메모법)."""

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from narratological.models.note import LinkType, NoteType
from narratological.zettelkasten import (
    create_note,
    delete_note,
    link_notes,
    load_zettelkasten,
    resolve_study_ref,
    unlink_notes,
    update_note,
)

router = APIRouter()

TAG_FILTER = Query(None, description="Filter by tag")
TYPE_FILTER = Query(None, description="Filter by note type")
SEARCH_QUERY = Query(..., description="Search query")


class NoteCreate(BaseModel):
    """Request body for creating a note."""

    title: str
    body: str = ""
    note_type: NoteType = NoteType.FLEETING
    tags: list[str] = []
    source: str | None = None
    study_ref: str | None = None


class NoteUpdate(BaseModel):
    """Request body for updating a note (only provided fields change)."""

    title: str | None = None
    body: str | None = None
    note_type: NoteType | None = None
    tags: list[str] | None = None
    source: str | None = None
    study_ref: str | None = None


class LinkCreate(BaseModel):
    """Request body for creating a link between notes."""

    target_id: str
    link_type: LinkType = LinkType.REFERENCE
    context: str | None = None


@router.get("/")
async def list_notes(
    tag: str | None = TAG_FILTER,
    note_type: NoteType | None = TYPE_FILTER,
) -> list[dict[str, Any]]:
    """List all notes, optionally filtered by tag and/or type."""
    zk = load_zettelkasten()
    notes = zk.list_notes()

    if tag:
        tagged = {n.id for n in zk.by_tag(tag)}
        notes = [n for n in notes if n.id in tagged]
    if note_type:
        notes = [n for n in notes if n.note_type == note_type]

    return [n.model_dump() for n in notes]


@router.get("/tags")
async def list_tags() -> list[str]:
    """List all tags used across notes."""
    return load_zettelkasten().all_tags()


@router.get("/graph")
async def get_graph() -> dict[str, Any]:
    """Return the note graph (nodes and edges) plus orphan IDs."""
    zk = load_zettelkasten()
    g = zk.graph()
    g["orphans"] = [n.id for n in zk.orphans()]
    return g


@router.get("/search")
async def search_notes(q: str = SEARCH_QUERY) -> list[dict[str, Any]]:
    """Search notes by title, body, or tag."""
    zk = load_zettelkasten()
    return [n.model_dump() for n in zk.search(q)]


@router.post("/", status_code=201)
async def create(payload: NoteCreate) -> dict[str, Any]:
    """Create a new note."""
    note = create_note(
        title=payload.title,
        body=payload.body,
        note_type=payload.note_type,
        tags=payload.tags,
        source=payload.source,
        study_ref=payload.study_ref,
    )
    return note.model_dump()


@router.get("/{note_id}")
async def get_note(note_id: str) -> dict[str, Any]:
    """Get a note by ID."""
    note = load_zettelkasten().get(note_id)
    if note is None:
        raise HTTPException(status_code=404, detail=f"Note '{note_id}' not found")
    return note.model_dump()


@router.put("/{note_id}")
async def update(note_id: str, payload: NoteUpdate) -> dict[str, Any]:
    """Update a note (only provided fields change)."""
    try:
        note = update_note(
            note_id,
            title=payload.title,
            body=payload.body,
            note_type=payload.note_type,
            tags=payload.tags,
            source=payload.source,
            study_ref=payload.study_ref,
        )
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return note.model_dump()


@router.delete("/{note_id}")
async def remove(note_id: str) -> dict[str, str]:
    """Delete a note and any links pointing to it."""
    if not delete_note(note_id):
        raise HTTPException(status_code=404, detail=f"Note '{note_id}' not found")
    return {"status": "deleted", "id": note_id}


@router.get("/{note_id}/backlinks")
async def get_backlinks(note_id: str) -> list[dict[str, Any]]:
    """Get all notes that link to this note."""
    zk = load_zettelkasten()
    if zk.get(note_id) is None:
        raise HTTPException(status_code=404, detail=f"Note '{note_id}' not found")
    return [n.model_dump() for n in zk.backlinks(note_id)]


@router.get("/{note_id}/study-ref")
async def get_study_ref(note_id: str) -> dict[str, Any]:
    """Resolve the note's narrative connection to a study/axiom."""
    note = load_zettelkasten().get(note_id)
    if note is None:
        raise HTTPException(status_code=404, detail=f"Note '{note_id}' not found")
    if not note.study_ref:
        raise HTTPException(status_code=404, detail="Note has no study_ref")
    resolved = resolve_study_ref(note.study_ref)
    if resolved is None:
        raise HTTPException(
            status_code=404,
            detail=f"Could not resolve study_ref '{note.study_ref}'",
        )
    return resolved


@router.post("/{note_id}/links", status_code=201)
async def add_link(note_id: str, payload: LinkCreate) -> dict[str, Any]:
    """Add an outgoing link from this note to another."""
    try:
        note = link_notes(
            note_id,
            payload.target_id,
            payload.link_type,
            payload.context,
        )
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return note.model_dump()


@router.delete("/{note_id}/links/{target_id}")
async def remove_link(note_id: str, target_id: str) -> dict[str, Any]:
    """Remove the link from this note to ``target_id``."""
    try:
        note = unlink_notes(note_id, target_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return note.model_dump()
