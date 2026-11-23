"""Guard internal Markdown links across top-level and evergreen strategy docs."""
from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
LINK_RE = re.compile(r"\[[^\]]+\]\(([^)]+)\)")

GUARDED_DOCS = [
    REPO_ROOT / "README.md",
    REPO_ROOT / "AGENTS.md",
    REPO_ROOT / "AGENTS-CN.md",
    REPO_ROOT / "docs" / "research-ledger.md",
    REPO_ROOT / "docs" / "glossary.md",
    REPO_ROOT / "docs" / "repository-structure.md",
    REPO_ROOT / "docs" / "strategies" / "two-three-asset.md",
    REPO_ROOT / "docs" / "strategies" / "sp500-enhance.md",
    REPO_ROOT / "docs" / "strategies" / "gold-enhance.md",
    REPO_ROOT / "docs" / "strategies" / "pitfalls.md",
    REPO_ROOT / "docs" / "strategies" / "holding-experience.md",
    REPO_ROOT / "docs" / "strategies" / "holding-lump.md",
    REPO_ROOT / "docs" / "strategies" / "holding-dca.md",
    REPO_ROOT / "docs" / "strategies" / "research-index.md",
    REPO_ROOT / "research" / "README.md",
]


def test_guarded_docs_have_no_broken_internal_links():
    broken: list[str] = []
    for doc in GUARDED_DOCS:
        assert doc.exists(), f"Missing guarded doc: {doc}"
        text = doc.read_text(encoding="utf-8")
        for raw in LINK_RE.findall(text):
            target = raw.split("#")[0].strip()
            if not target or target.startswith(("http://", "https://", "mailto:")):
                continue
            if "trading/" in target:
                continue
            resolved = (doc.parent / target).resolve()
            if not resolved.exists():
                broken.append(f"{doc.relative_to(REPO_ROOT)} -> {raw}")
    assert not broken, "Broken internal Markdown links:\n" + "\n".join(broken)
