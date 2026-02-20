"""
Skill loader and registry (v0.8).
Skills are filesystem-based instruction modules: YAML frontmatter (metadata)
+ markdown body (instructions) + optional resource files.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, List

import yaml

from .types import RoutingTarget, SkillMetadata

# Default skill directory; ORE_SKILLS_ROOT env var overrides for dev/bundled skills
DEFAULT_SKILLS_ROOT = (
    Path(os.environ["ORE_SKILLS_ROOT"])
    if "ORE_SKILLS_ROOT" in os.environ
    else Path.home() / ".ore" / "skills"
)

SKILL_FILENAME = "SKILL.md"


def load_skill_metadata(skill_dir: Path) -> SkillMetadata:
    """
    Parse YAML frontmatter from SKILL.md and return Level 1 metadata.

    Frontmatter must be delimited by --- on its own line at the start of the
    file and closed by a second ---. Required keys: name, description.
    Optional: hints (list of strings).
    """
    skill_file = skill_dir / SKILL_FILENAME
    if not skill_file.is_file():
        raise FileNotFoundError(f"No {SKILL_FILENAME} in {skill_dir}")

    text = skill_file.read_text(encoding="utf-8")
    frontmatter = _parse_frontmatter(text, skill_file)

    name = frontmatter.get("name")
    if not name or not isinstance(name, str):
        raise ValueError(f"Missing or invalid 'name' in {skill_file}")
    description = frontmatter.get("description")
    if not description or not isinstance(description, str):
        raise ValueError(f"Missing or invalid 'description' in {skill_file}")

    raw_hints = frontmatter.get("hints", [])
    if isinstance(raw_hints, list):
        hints = [str(h) for h in raw_hints]
    else:
        hints = []

    return SkillMetadata(
        name=name,
        description=description,
        hints=hints,
        path=skill_dir.resolve(),
    )


def load_skill_instructions(skill_dir: Path) -> str:
    """
    Return the Level 2 instruction body from SKILL.md (everything after the
    closing --- of the YAML frontmatter). Strips leading/trailing whitespace.
    """
    skill_file = skill_dir / SKILL_FILENAME
    if not skill_file.is_file():
        raise FileNotFoundError(f"No {SKILL_FILENAME} in {skill_dir}")

    text = skill_file.read_text(encoding="utf-8")
    body = _extract_body(text, skill_file)
    return body.strip()


def load_skill_resource(skill_dir: Path, resource_ref: str) -> str:
    """
    Read a Level 3 resource file from skill_dir/resources/resource_ref.

    Security constraint: the resolved path must fall inside
    skill_dir/resources/. Any path traversal attempt (e.g. ../../etc/passwd)
    is rejected with a ValueError.
    """
    resources_root = (skill_dir / "resources").resolve()
    target = (resources_root / resource_ref).resolve()

    # Reject traversal: target must be inside resources_root
    try:
        target.relative_to(resources_root)
    except ValueError:
        raise ValueError(
            f"Path traversal blocked: '{resource_ref}' resolves outside "
            f"{resources_root}"
        )

    if not target.is_file():
        raise FileNotFoundError(f"Resource not found: {target}")

    return target.read_text(encoding="utf-8")


def build_skill_registry(root: Path | None = None) -> Dict[str, SkillMetadata]:
    """
    Scan root for subdirectories containing SKILL.md, parse each, return
    {name: metadata}. Skips malformed skills with a warning on stderr.
    """
    import sys

    skills_root = root or DEFAULT_SKILLS_ROOT
    registry: Dict[str, SkillMetadata] = {}
    if not skills_root.is_dir():
        return registry

    for child in sorted(skills_root.iterdir()):
        if not child.is_dir():
            continue
        skill_file = child / SKILL_FILENAME
        if not skill_file.is_file():
            continue
        try:
            meta = load_skill_metadata(child)
            registry[meta.name] = meta
        except (ValueError, FileNotFoundError) as exc:
            print(f"Skipping skill in {child}: {exc}", file=sys.stderr)

    return registry


def build_targets_from_skill_registry(
    registry: Dict[str, SkillMetadata],
) -> List[RoutingTarget]:
    """
    Convert skill metadata into RoutingTarget objects with target_type="skill".
    Mirrors build_targets_from_registry in ore/router.py.
    """
    targets: List[RoutingTarget] = []
    for name, meta in sorted(registry.items()):
        targets.append(
            RoutingTarget(
                name=name,
                target_type="skill",
                description=meta.description,
                hints=list(meta.hints),
            )
        )
    return targets


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _parse_frontmatter(text: str, source: Path) -> dict:
    """Extract and parse YAML frontmatter between --- delimiters."""
    stripped = text.lstrip("\n")
    if not stripped.startswith("---"):
        raise ValueError(f"No YAML frontmatter found in {source}")

    # Find closing ---
    after_open = stripped[3:].lstrip("\n")
    close_idx = after_open.find("\n---")
    if close_idx == -1:
        raise ValueError(f"Unclosed YAML frontmatter in {source}")

    yaml_text = after_open[:close_idx]
    parsed = yaml.safe_load(yaml_text)
    if not isinstance(parsed, dict):
        raise ValueError(f"YAML frontmatter is not a mapping in {source}")
    return parsed


def _extract_body(text: str, source: Path) -> str:
    """Return everything after the closing --- of the YAML frontmatter."""
    stripped = text.lstrip("\n")
    if not stripped.startswith("---"):
        raise ValueError(f"No YAML frontmatter found in {source}")

    after_open = stripped[3:].lstrip("\n")
    close_idx = after_open.find("\n---")
    if close_idx == -1:
        raise ValueError(f"Unclosed YAML frontmatter in {source}")

    # Body starts after the closing --- line
    body_start = close_idx + 4  # len("\n---")
    return after_open[body_start:]
