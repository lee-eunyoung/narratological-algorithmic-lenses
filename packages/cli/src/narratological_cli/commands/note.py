"""CLI commands for the Zettelkasten note subsystem (독일식 메모법)."""

from typing import Annotated

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.tree import Tree

app = typer.Typer(help="Take and link atomic notes (Zettelkasten)")
console = Console()


@app.command("new")
def new_note(
    title: Annotated[str, typer.Option("--title", help="Note title")],
    body: Annotated[str, typer.Option("--body", "-b", help="Note body")] = "",
    note_type: Annotated[
        str,
        typer.Option("--type", help="Note type: permanent, literature, fleeting"),
    ] = "fleeting",
    tag: Annotated[
        list[str] | None,
        typer.Option("--tag", "-t", help="Tag (repeatable)"),
    ] = None,
    source: Annotated[
        str | None,
        typer.Option("--source", help="Provenance/citation"),
    ] = None,
    study_ref: Annotated[
        str | None,
        typer.Option("--study-ref", help="Link to study: 'study_id' or 'study_id/axiom_id'"),
    ] = None,
) -> None:
    """Create a new note."""
    from narratological.models.note import NoteType
    from narratological.zettelkasten import create_note

    try:
        ntype = NoteType(note_type)
    except ValueError:
        console.print(f"[red]Invalid note type: {note_type}[/red]")
        console.print(f"Valid types: {', '.join(t.value for t in NoteType)}")
        raise typer.Exit(1) from None

    note = create_note(
        title=title,
        body=body,
        note_type=ntype,
        tags=tag or [],
        source=source,
        study_ref=study_ref,
    )
    console.print(f"[green]Created note[/green] [cyan]{note.id}[/cyan]: {note.title}")


@app.command("list")
def list_notes(
    tag: Annotated[
        str | None,
        typer.Option("--tag", "-t", help="Filter by tag"),
    ] = None,
    note_type: Annotated[
        str | None,
        typer.Option("--type", help="Filter by type"),
    ] = None,
) -> None:
    """List all notes."""
    from narratological.models.note import NoteType
    from narratological.zettelkasten import load_zettelkasten

    zk = load_zettelkasten()
    notes = zk.list_notes()

    if tag:
        notes = [n for n in notes if n in zk.by_tag(tag)]
    if note_type:
        try:
            ntype = NoteType(note_type)
        except ValueError:
            console.print(f"[red]Invalid note type: {note_type}[/red]")
            raise typer.Exit(1) from None
        notes = [n for n in notes if n.note_type == ntype]

    if not notes:
        console.print("[dim]No notes found.[/dim]")
        return

    table = Table(title="Zettelkasten Notes")
    table.add_column("ID", style="cyan")
    table.add_column("Title", style="green")
    table.add_column("Type", style="yellow")
    table.add_column("Tags", justify="right")
    table.add_column("Links", justify="right")

    for n in notes:
        table.add_row(
            n.id,
            n.title[:50] + "..." if len(n.title) > 50 else n.title,
            n.note_type.value,
            str(len(n.tags)),
            str(len(n.links)),
        )

    console.print(table)


@app.command("show")
def show_note(
    note_id: Annotated[str, typer.Argument(help="Note ID to show")],
) -> None:
    """Show a note with its links, backlinks, and study connection."""
    from narratological.zettelkasten import load_zettelkasten, resolve_study_ref

    zk = load_zettelkasten()
    note = zk.get(note_id)
    if note is None:
        console.print(f"[red]Note '{note_id}' not found[/red]")
        raise typer.Exit(1)

    subtitle = f"{note.note_type.value}"
    if note.tags:
        subtitle += f"  |  tags: {', '.join(note.tags)}"
    console.print(Panel(
        f"[bold]{note.title}[/bold]\n\n{note.body}",
        title=f"Note: {note.id}",
        subtitle=subtitle,
    ))

    if note.source:
        console.print(f"\n[dim]Source:[/dim] {note.source}")

    if note.study_ref:
        console.print(f"\n[bold]Study connection:[/bold] [magenta]{note.study_ref}[/magenta]")
        resolved = resolve_study_ref(note.study_ref)
        if resolved:
            console.print(f"  {resolved['creator']} — {resolved['work']}")
            if "axiom_name" in resolved:
                console.print(f"  [cyan]{resolved['axiom_id']}[/cyan] {resolved['axiom_name']}")
                console.print(f"  [dim]{resolved['axiom_statement']}[/dim]")
        else:
            console.print("  [yellow](could not resolve reference)[/yellow]")

    if note.links:
        console.print("\n[bold]Links →[/bold]")
        for link in note.links:
            target = zk.get(link.target_id)
            label = target.title if target else "[red](missing)[/red]"
            ctx = f" — {link.context}" if link.context else ""
            console.print(f"  ({link.link_type.value}) [cyan]{link.target_id}[/cyan]: {label}{ctx}")

    backlinks = zk.backlinks(note.id)
    if backlinks:
        console.print("\n[bold]← Backlinks[/bold]")
        for b in backlinks:
            console.print(f"  [cyan]{b.id}[/cyan]: {b.title}")


@app.command("link")
def link(
    source_id: Annotated[str, typer.Argument(help="Source note ID")],
    target_id: Annotated[str, typer.Argument(help="Target note ID")],
    link_type: Annotated[
        str,
        typer.Option("--type", help="reference, follows, supports, contradicts, elaborates"),
    ] = "reference",
    context: Annotated[
        str | None,
        typer.Option("--context", help="Why this link exists"),
    ] = None,
) -> None:
    """Link one note to another."""
    from narratological.models.note import LinkType
    from narratological.zettelkasten import link_notes

    try:
        ltype = LinkType(link_type)
    except ValueError:
        console.print(f"[red]Invalid link type: {link_type}[/red]")
        console.print(f"Valid types: {', '.join(t.value for t in LinkType)}")
        raise typer.Exit(1) from None

    try:
        link_notes(source_id, target_id, ltype, context)
    except KeyError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1) from e

    console.print(f"[green]Linked[/green] [cyan]{source_id}[/cyan] → [cyan]{target_id}[/cyan] ({ltype.value})")


@app.command("unlink")
def unlink(
    source_id: Annotated[str, typer.Argument(help="Source note ID")],
    target_id: Annotated[str, typer.Argument(help="Target note ID")],
) -> None:
    """Remove a link between two notes."""
    from narratological.zettelkasten import unlink_notes

    try:
        unlink_notes(source_id, target_id)
    except KeyError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1) from e

    console.print(f"[green]Unlinked[/green] [cyan]{source_id}[/cyan] → [cyan]{target_id}[/cyan]")


@app.command("backlinks")
def backlinks(
    note_id: Annotated[str, typer.Argument(help="Note ID")],
) -> None:
    """Show all notes that link to a note."""
    from narratological.zettelkasten import load_zettelkasten

    zk = load_zettelkasten()
    if zk.get(note_id) is None:
        console.print(f"[red]Note '{note_id}' not found[/red]")
        raise typer.Exit(1)

    results = zk.backlinks(note_id)
    if not results:
        console.print("[dim]No backlinks.[/dim]")
        return

    console.print(f"[bold]Backlinks to {note_id} ({len(results)}):[/bold]")
    for b in results:
        console.print(f"  [cyan]{b.id}[/cyan]: {b.title}")


@app.command("search")
def search(
    query: Annotated[str, typer.Argument(help="Search query")],
) -> None:
    """Search notes by title, body, or tag."""
    from narratological.zettelkasten import load_zettelkasten

    zk = load_zettelkasten()
    results = zk.search(query)

    if not results:
        console.print("[dim]No matches.[/dim]")
        return

    console.print(f"[bold]Matches ({len(results)}):[/bold]")
    for n in results:
        console.print(f"  [cyan]{n.id}[/cyan] ({n.note_type.value}): {n.title}")


@app.command("graph")
def graph() -> None:
    """Show the note graph: node/edge counts, link tree, and orphans."""
    from narratological.zettelkasten import load_zettelkasten

    zk = load_zettelkasten()
    g = zk.graph()
    console.print(f"[bold]Nodes:[/bold] {len(g['nodes'])}  [bold]Edges:[/bold] {len(g['edges'])}")

    if zk.notes:
        tree = Tree("[bold]Links[/bold]")
        for note in zk.list_notes():
            if note.links:
                branch = tree.add(f"[cyan]{note.id}[/cyan]: {note.title}")
                for link in note.links:
                    target = zk.get(link.target_id)
                    label = target.title if target else "(missing)"
                    branch.add(f"({link.link_type.value}) → [cyan]{link.target_id}[/cyan]: {label}")
        console.print(tree)

    orphans = zk.orphans()
    if orphans:
        console.print(f"\n[yellow]Orphans ({len(orphans)}):[/yellow]")
        for o in orphans:
            console.print(f"  [cyan]{o.id}[/cyan]: {o.title}")


@app.command("delete")
def delete(
    note_id: Annotated[str, typer.Argument(help="Note ID to delete")],
) -> None:
    """Delete a note and any links pointing to it."""
    from narratological.zettelkasten import delete_note

    if delete_note(note_id):
        console.print(f"[green]Deleted note[/green] [cyan]{note_id}[/cyan]")
    else:
        console.print(f"[red]Note '{note_id}' not found[/red]")
        raise typer.Exit(1)
