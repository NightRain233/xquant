from pathlib import Path

import pytest

from xquant.project import find_repo_root


def make_repository(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    (root / ".git").mkdir(parents=True)
    (root / "pyproject.toml").write_text("[project]\nname = \"example\"\n")
    return root


def test_find_repo_root_walks_up_from_nested_directory(tmp_path):
    root = make_repository(tmp_path)
    nested = root / "research" / "notebooks"
    nested.mkdir(parents=True)

    assert find_repo_root(nested) == root


def test_find_repo_root_accepts_file_as_starting_point(tmp_path):
    root = make_repository(tmp_path)
    notebook = root / "research" / "example.ipynb"
    notebook.parent.mkdir()
    notebook.write_text("{}")

    assert find_repo_root(notebook) == root


def test_find_repo_root_raises_clear_error_when_markers_are_missing(tmp_path):
    with pytest.raises(FileNotFoundError, match="pyproject.toml"):
        find_repo_root(tmp_path)
