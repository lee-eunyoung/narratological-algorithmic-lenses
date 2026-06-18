"""Tests for the Zettelkasten note CLI commands."""

import re

import pytest
from typer.testing import CliRunner

from narratological_cli.main import app

runner = CliRunner()


@pytest.fixture(autouse=True)
def temp_store(tmp_path, monkeypatch):
    """Point the note store at a throwaway file for every test."""
    monkeypatch.setenv("NARRATOLOGICAL_NOTES", str(tmp_path / "zk.json"))


def _create(title: str, *args: str) -> str:
    """Create a note via the CLI and return its ID."""
    result = runner.invoke(app, ["note", "new", "--title", title, *args])
    assert result.exit_code == 0, result.output
    match = re.search(r"Created note (\S+):", result.output)
    assert match, result.output
    return match.group(1)


class TestNoteCommands:
    """End-to-end tests for the `note` command group."""

    def test_new_and_show(self):
        note_id = _create(
            "미메시스는 선택적이다",
            "-b", "예술은 본질을 모방한다.",
            "--type", "permanent",
            "-t", "미학",
        )
        result = runner.invoke(app, ["note", "show", note_id])
        assert result.exit_code == 0
        assert "미메시스" in result.output
        assert "permanent" in result.output

    def test_new_invalid_type(self):
        result = runner.invoke(app, ["note", "new", "--title", "x", "--type", "bogus"])
        assert result.exit_code == 1
        assert "Invalid note type" in result.output

    def test_list(self):
        _create("첫 노트")
        _create("둘째 노트")
        result = runner.invoke(app, ["note", "list"])
        assert result.exit_code == 0
        assert "첫 노트" in result.output
        assert "둘째 노트" in result.output

    def test_link_and_backlinks(self):
        a = _create("A 노트")
        b = _create("B 노트")
        result = runner.invoke(app, ["note", "link", a, b, "--type", "elaborates"])
        assert result.exit_code == 0

        result = runner.invoke(app, ["note", "backlinks", b])
        assert result.exit_code == 0
        assert a in result.output

    def test_show_with_study_ref(self):
        note_id = _create("아리스토텔레스 메모", "--study-ref", "aristotle/A0")
        result = runner.invoke(app, ["note", "show", note_id])
        assert result.exit_code == 0
        # Either resolves to the study or shows the raw ref.
        assert "aristotle" in result.output.lower()

    def test_search(self):
        _create("감정의 카타르시스", "-b", "긴장 축적이 필요하다")
        result = runner.invoke(app, ["note", "search", "카타르시스"])
        assert result.exit_code == 0
        assert "카타르시스" in result.output

    def test_graph(self):
        a = _create("A")
        b = _create("B")
        runner.invoke(app, ["note", "link", a, b])
        result = runner.invoke(app, ["note", "graph"])
        assert result.exit_code == 0
        assert "Nodes:" in result.output

    def test_delete(self):
        note_id = _create("삭제될 노트")
        result = runner.invoke(app, ["note", "delete", note_id])
        assert result.exit_code == 0
        # Now gone.
        result = runner.invoke(app, ["note", "show", note_id])
        assert result.exit_code == 1

    def test_show_missing(self):
        result = runner.invoke(app, ["note", "show", "nonexistent"])
        assert result.exit_code == 1
        assert "not found" in result.output.lower()
