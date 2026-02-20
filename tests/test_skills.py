"""Tests for ore/skills.py — skill loader and registry (v0.8)."""

from __future__ import annotations

from pathlib import Path

import pytest

from ore.skills import (
    build_skill_registry,
    build_targets_from_skill_registry,
    load_skill_instructions,
    load_skill_metadata,
    load_skill_resource,
)

# ---------------------------------------------------------------------------
# Fixtures: create well-formed and malformed skill dirs in tmp_path
# ---------------------------------------------------------------------------

VALID_SKILL_MD = """\
---
name: test-skill
description: A test skill for unit tests
hints:
  - test keyword
  - another hint
---

These are the skill instructions.
They span multiple lines.
"""

VALID_SKILL_MD_NO_HINTS = """\
---
name: no-hints
description: Skill without hints
---

Instructions for a skill with no hints.
"""

MISSING_NAME_SKILL_MD = """\
---
description: Missing name
---

Body.
"""

NO_FRONTMATTER_SKILL_MD = """\
Just a body with no frontmatter.
"""

UNCLOSED_FRONTMATTER_SKILL_MD = """\
---
name: broken
description: Unclosed frontmatter
"""


@pytest.fixture
def valid_skill_dir(tmp_path: Path) -> Path:
    skill_dir = tmp_path / "test-skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(VALID_SKILL_MD, encoding="utf-8")
    resources = skill_dir / "resources"
    resources.mkdir()
    (resources / "template.md").write_text("Template content here.", encoding="utf-8")
    return skill_dir


@pytest.fixture
def skills_root(tmp_path: Path) -> Path:
    """Root dir with two valid skills and one malformed."""
    root = tmp_path / "skills"
    root.mkdir()

    s1 = root / "alpha"
    s1.mkdir()
    (s1 / "SKILL.md").write_text(VALID_SKILL_MD, encoding="utf-8")

    s2 = root / "beta"
    s2.mkdir()
    (s2 / "SKILL.md").write_text(VALID_SKILL_MD_NO_HINTS, encoding="utf-8")

    bad = root / "broken"
    bad.mkdir()
    (bad / "SKILL.md").write_text(MISSING_NAME_SKILL_MD, encoding="utf-8")

    return root


# ---------------------------------------------------------------------------
# load_skill_metadata
# ---------------------------------------------------------------------------


class TestLoadSkillMetadata:
    def test_valid_skill(self, valid_skill_dir: Path) -> None:
        meta = load_skill_metadata(valid_skill_dir)
        assert meta.name == "test-skill"
        assert meta.description == "A test skill for unit tests"
        assert meta.hints == ["test keyword", "another hint"]
        assert meta.path == valid_skill_dir.resolve()

    def test_no_hints_defaults_to_empty(self, tmp_path: Path) -> None:
        skill_dir = tmp_path / "no-hints"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(VALID_SKILL_MD_NO_HINTS, encoding="utf-8")
        meta = load_skill_metadata(skill_dir)
        assert meta.name == "no-hints"
        assert meta.hints == []

    def test_missing_skill_file(self, tmp_path: Path) -> None:
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()
        with pytest.raises(FileNotFoundError, match="No SKILL.md"):
            load_skill_metadata(empty_dir)

    def test_missing_frontmatter(self, tmp_path: Path) -> None:
        skill_dir = tmp_path / "no-fm"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(NO_FRONTMATTER_SKILL_MD, encoding="utf-8")
        with pytest.raises(ValueError, match="No YAML frontmatter"):
            load_skill_metadata(skill_dir)

    def test_unclosed_frontmatter(self, tmp_path: Path) -> None:
        skill_dir = tmp_path / "unclosed"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(
            UNCLOSED_FRONTMATTER_SKILL_MD, encoding="utf-8"
        )
        with pytest.raises(ValueError, match="Unclosed YAML frontmatter"):
            load_skill_metadata(skill_dir)

    def test_missing_name(self, tmp_path: Path) -> None:
        skill_dir = tmp_path / "bad"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(MISSING_NAME_SKILL_MD, encoding="utf-8")
        with pytest.raises(ValueError, match="Missing or invalid 'name'"):
            load_skill_metadata(skill_dir)


# ---------------------------------------------------------------------------
# load_skill_instructions
# ---------------------------------------------------------------------------


class TestLoadSkillInstructions:
    def test_returns_body_only(self, valid_skill_dir: Path) -> None:
        body = load_skill_instructions(valid_skill_dir)
        assert "These are the skill instructions." in body
        assert "They span multiple lines." in body
        # Frontmatter keys should not appear in body
        assert "name:" not in body
        assert "description:" not in body

    def test_missing_skill_file(self, tmp_path: Path) -> None:
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()
        with pytest.raises(FileNotFoundError):
            load_skill_instructions(empty_dir)


# ---------------------------------------------------------------------------
# load_skill_resource
# ---------------------------------------------------------------------------


class TestLoadSkillResource:
    def test_reads_valid_resource(self, valid_skill_dir: Path) -> None:
        content = load_skill_resource(valid_skill_dir, "template.md")
        assert content == "Template content here."

    def test_resource_not_found(self, valid_skill_dir: Path) -> None:
        with pytest.raises(FileNotFoundError, match="Resource not found"):
            load_skill_resource(valid_skill_dir, "nonexistent.md")

    def test_path_traversal_blocked(self, valid_skill_dir: Path) -> None:
        with pytest.raises(ValueError, match="Path traversal blocked"):
            load_skill_resource(valid_skill_dir, "../../../etc/passwd")

    def test_path_traversal_blocked_sibling(self, valid_skill_dir: Path) -> None:
        # Attempt to escape into the skill dir itself (above resources/)
        with pytest.raises(ValueError, match="Path traversal blocked"):
            load_skill_resource(valid_skill_dir, "../SKILL.md")


# ---------------------------------------------------------------------------
# build_skill_registry
# ---------------------------------------------------------------------------


class TestBuildSkillRegistry:
    def test_scans_valid_skills(self, skills_root: Path) -> None:
        registry = build_skill_registry(skills_root)
        # alpha uses VALID_SKILL_MD → name "test-skill"; beta → "no-hints"
        # broken is skipped (missing name)
        assert "test-skill" in registry
        assert "no-hints" in registry
        assert len(registry) == 2

    def test_empty_dir(self, tmp_path: Path) -> None:
        empty = tmp_path / "empty-skills"
        empty.mkdir()
        registry = build_skill_registry(empty)
        assert registry == {}

    def test_nonexistent_dir(self, tmp_path: Path) -> None:
        registry = build_skill_registry(tmp_path / "does-not-exist")
        assert registry == {}

    def test_skips_malformed_skill(self, skills_root: Path, capsys) -> None:
        build_skill_registry(skills_root)
        captured = capsys.readouterr()
        assert "Skipping skill" in captured.err


# ---------------------------------------------------------------------------
# build_targets_from_skill_registry
# ---------------------------------------------------------------------------


class TestBuildTargetsFromSkillRegistry:
    def test_produces_routing_targets(self, skills_root: Path) -> None:
        registry = build_skill_registry(skills_root)
        targets = build_targets_from_skill_registry(registry)
        assert len(targets) == 2
        for t in targets:
            assert t.target_type == "skill"
        names = {t.name for t in targets}
        assert "test-skill" in names
        assert "no-hints" in names

    def test_empty_registry(self) -> None:
        targets = build_targets_from_skill_registry({})
        assert targets == []

    def test_hints_propagated(self, skills_root: Path) -> None:
        registry = build_skill_registry(skills_root)
        targets = build_targets_from_skill_registry(registry)
        test_target = next(t for t in targets if t.name == "test-skill")
        assert "test keyword" in test_target.hints
        assert "another hint" in test_target.hints
