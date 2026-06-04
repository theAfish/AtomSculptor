"""Skill discovery, frontmatter parsing, and path resolution."""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import yaml

from settings import settings

_REPO_ROOT = Path(__file__).resolve().parents[2]
BUILTIN_SKILLS_DIR = _REPO_ROOT / "skills"

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", re.DOTALL)
_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*$")


@dataclass(frozen=True)
class Skill:
    name: str
    source: str  # "builtin" | "sandbox"
    path: Path
    description: str
    when_to_use: str
    entry: str | None  # script path relative to skill folder; None => not runnable
    body: str          # SKILL.md body (without frontmatter)


def sandbox_skills_dir() -> Path:
    root = Path(settings.SANDBOX_DIR).expanduser()
    if not root.is_absolute():
        root = (_REPO_ROOT / root).resolve()
    return root / "skills"


def _parse_skill_md(skill_md: Path) -> tuple[dict, str]:
    text = skill_md.read_text(encoding="utf-8")
    match = _FRONTMATTER_RE.match(text)
    if not match:
        raise ValueError(f"SKILL.md is missing YAML frontmatter: {skill_md}")
    meta = yaml.safe_load(match.group(1)) or {}
    if not isinstance(meta, dict):
        raise ValueError(f"SKILL.md frontmatter must be a mapping: {skill_md}")
    return meta, match.group(2)


def _load_skill(skill_dir: Path, source: str) -> Skill:
    skill_md = skill_dir / "SKILL.md"
    meta, body = _parse_skill_md(skill_md)
    name = str(meta.get("name") or skill_dir.name)
    return Skill(
        name=name,
        source=source,
        path=skill_dir,
        description=str(meta.get("description", "")).strip(),
        when_to_use=str(meta.get("when_to_use", "")).strip(),
        entry=(str(meta["entry"]) if meta.get("entry") else None),
        body=body,
    )


def _iter_skill_dirs(root: Path) -> Iterable[Path]:
    if not root.is_dir():
        return
    for child in sorted(root.iterdir()):
        if not child.is_dir() or child.name.startswith((".", "_")):
            continue
        if (child / "SKILL.md").is_file():
            yield child


def discover_skills() -> dict[str, Skill]:
    """Return ``{name: Skill}``.  Sandbox skills shadow built-in ones with the same name."""
    skills: dict[str, Skill] = {}
    for skill_dir in _iter_skill_dirs(BUILTIN_SKILLS_DIR):
        skill = _load_skill(skill_dir, "builtin")
        skills[skill.name] = skill
    for skill_dir in _iter_skill_dirs(sandbox_skills_dir()):
        skill = _load_skill(skill_dir, "sandbox")
        skills[skill.name] = skill
    return skills


def find_skill(name: str) -> Skill | None:
    return discover_skills().get(name)


def validate_skill_name(name: str) -> str | None:
    if not name or not _NAME_RE.match(name):
        return (
            f"Invalid skill name: {name!r}. "
            "Use lowercase letters, digits, hyphens, or underscores; must start "
            "with a letter or digit."
        )
    return None


def resolve_inside_skill(skill: Skill, relative_path: str) -> Path | None:
    """Return ``skill.path / relative_path`` only if it stays within the skill folder."""
    candidate = (skill.path / relative_path).resolve()
    try:
        candidate.relative_to(skill.path.resolve())
    except ValueError:
        return None
    return candidate
