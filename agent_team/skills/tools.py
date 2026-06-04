"""Agent-facing skill tools (list / read / run / create / promote / install_deps)."""
from __future__ import annotations

import shutil
from pathlib import Path

import yaml

from agent_team.skills.loader import (
    BUILTIN_SKILLS_DIR,
    discover_skills,
    find_skill,
    resolve_inside_skill,
    sandbox_skills_dir,
    validate_skill_name,
)
from agent_team.skills.runner import (
    ensure_runnable,
    execute_skill,
    install_dependencies,
)


def list_skills() -> dict:
    """List every available skill with its description and `when_to_use` hint.

    Skills are the primary mechanism for accomplishing domain tasks. Always call
    this before reaching for ad-hoc code: a skill may already exist for the job.

    Returns a dict with a ``skills`` list. Each entry has:
        name, description, when_to_use, runnable (bool), source ("builtin" or "sandbox")
    """
    skills = discover_skills()
    return {
        "skills": [
            {
                "name": s.name,
                "description": s.description,
                "when_to_use": s.when_to_use,
                "runnable": s.entry is not None,
                "source": s.source,
            }
            for s in skills.values()
        ]
    }


def read_skill(name: str, path: str | None = None) -> dict:
    """Read a skill's SKILL.md (default) or a referenced file inside the skill folder.

    Use this for *progressive disclosure*: start with SKILL.md, then drill into
    ``references/<file>.md`` or ``scripts/<file>.py`` only when you need the detail.

    Parameters:
    - name: skill name as returned by `list_skills`.
    - path: optional path *relative to the skill folder* (e.g. "references/notes.md").
            If omitted, returns SKILL.md.
    """
    skill = find_skill(name)
    if skill is None:
        return {"error": f"Skill not found: {name!r}"}

    target = (skill.path / "SKILL.md") if path is None else resolve_inside_skill(skill, path)
    if target is None or not target.is_file():
        return {"error": f"File not found inside skill {name!r}: {path}"}

    return {
        "name": skill.name,
        "source": skill.source,
        "path": str(target.relative_to(skill.path)),
        "content": target.read_text(encoding="utf-8"),
    }


def run_skill(name: str, args: str = "") -> dict:
    """Execute a runnable skill inside the sandbox.

    On first invocation the skill is copied from the built-in library into the
    sandbox and its ``requirements.txt`` (if any) is installed. The entry script
    declared in the skill's frontmatter is then run via the sandbox runtime.

    Parameters:
    - name: skill name (must have ``entry:`` in its SKILL.md frontmatter).
    - args: command-line arguments string passed verbatim after the entry script,
            e.g. ``"build_bulk_crystal --element Fe --crystalstructure bcc --a 2.87"``.
    """
    skill, error = ensure_runnable(name)
    if error is not None:
        return error
    return execute_skill(skill, args)


def install_skill_deps(name: str, force: bool = False) -> dict:
    """Explicitly install a skill's ``requirements.txt`` (normally automatic on run_skill).

    Parameters:
    - name: skill name.
    - force: re-install even if the deps were already installed.
    """
    skill = find_skill(name)
    if skill is None:
        return {"error": f"Skill not found: {name!r}"}
    return install_dependencies(skill, force=force)


def create_skill(
    name: str,
    description: str,
    when_to_use: str,
    entry: str | None = None,
    scripts: dict | None = None,
    references: dict | None = None,
    requirements: str | None = None,
    body: str = "",
) -> dict:
    """Scaffold a new skill folder in the sandbox skill library.

    Parameters:
    - name: skill name (lowercase, hyphens/underscores).
    - description: one-line summary shown in `list_skills`.
    - when_to_use: short hint that helps the agent decide when this skill applies.
    - entry: optional path (relative to the skill folder) of the runnable entry
             script, e.g. "scripts/run.py". Omit for instruction-only skills.
    - scripts: optional ``{relative_path: file_content}`` for ``scripts/*`` files.
    - references: optional ``{relative_path: file_content}`` for ``references/*`` files
                  used for progressive disclosure (deeper docs loaded on demand).
    - requirements: optional ``requirements.txt`` content (one ``pip`` requirement
                    per line).  Installed automatically the first time the skill
                    runs.
    - body: optional markdown body appended below the frontmatter in SKILL.md.
    """
    invalid = validate_skill_name(name)
    if invalid:
        return {"error": invalid}
    if not description.strip():
        return {"error": "description must be a non-empty string"}
    if not when_to_use.strip():
        return {"error": "when_to_use must be a non-empty string"}

    skill_dir = sandbox_skills_dir() / name
    if skill_dir.exists():
        return {"error": f"Skill already exists in sandbox: {name!r}"}

    skill_dir.mkdir(parents=True)

    def _write_files(group: dict | None, subdir: str) -> list[str]:
        if not group:
            return []
        target_dir = skill_dir / subdir
        target_dir.mkdir(parents=True, exist_ok=True)
        written: list[str] = []
        for rel, content in group.items():
            rel_path = Path(rel)
            if rel_path.is_absolute() or ".." in rel_path.parts:
                raise ValueError(f"Invalid relative path in {subdir}: {rel}")
            file_path = target_dir / rel_path
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(content, encoding="utf-8")
            written.append(f"{subdir}/{rel_path.as_posix()}")
        return written

    try:
        script_files = _write_files(scripts, "scripts")
        reference_files = _write_files(references, "references")
    except ValueError as exc:
        shutil.rmtree(skill_dir, ignore_errors=True)
        return {"error": str(exc)}

    if requirements is not None:
        (skill_dir / "requirements.txt").write_text(requirements, encoding="utf-8")

    frontmatter: dict = {
        "name": name,
        "description": description.strip(),
        "when_to_use": when_to_use.strip(),
    }
    if entry:
        frontmatter["entry"] = entry

    skill_md = "---\n" + yaml.safe_dump(frontmatter, sort_keys=False) + "---\n"
    if body.strip():
        skill_md += "\n" + body.rstrip() + "\n"
    (skill_dir / "SKILL.md").write_text(skill_md, encoding="utf-8")

    return {
        "name": name,
        "skill_dir": str(skill_dir),
        "files_created": [
            "SKILL.md",
            *script_files,
            *reference_files,
            *(["requirements.txt"] if requirements is not None else []),
        ],
    }


def promote_skill(name: str, overwrite: bool = False) -> dict:
    """Copy a sandbox-resident skill into the built-in library so it ships with the repo.

    Parameters:
    - name: skill name.
    - overwrite: if True, replace an existing built-in skill of the same name.
    """
    sandbox_dir = sandbox_skills_dir() / name
    if not (sandbox_dir / "SKILL.md").is_file():
        return {"error": f"No sandbox skill named {name!r} to promote."}

    target = BUILTIN_SKILLS_DIR / name
    if target.exists() and not overwrite:
        return {"error": f"Built-in skill {name!r} already exists. Pass overwrite=True to replace."}

    if target.exists():
        shutil.rmtree(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(sandbox_dir, target)
    return {"promoted": name, "builtin_path": str(target)}


def update_skill(
    name: str,
    description: str | None = None,
    when_to_use: str | None = None,
    body: str | None = None,
) -> dict:
    """Update a built-in or sandbox skill's SKILL.md frontmatter and/or body.

    Built-in skills are edited in place. Provide only the fields you want to
    change; the rest are kept as-is.
    """
    skill = find_skill(name)
    if skill is None:
        return {"error": f"Skill not found: {name!r}"}

    skill_md = skill.path / "SKILL.md"
    new_desc = (description.strip() if description is not None else skill.description)
    new_when = (when_to_use.strip() if when_to_use is not None else skill.when_to_use)
    new_body = (body if body is not None else skill.body)

    frontmatter: dict = {
        "name": skill.name,
        "description": new_desc,
        "when_to_use": new_when,
    }
    if skill.entry:
        frontmatter["entry"] = skill.entry

    text = "---\n" + yaml.safe_dump(frontmatter, sort_keys=False) + "---\n"
    if new_body and new_body.strip():
        text += "\n" + new_body.lstrip("\n").rstrip() + "\n"
    skill_md.write_text(text, encoding="utf-8")
    return {"updated": skill.name, "source": skill.source, "path": str(skill_md)}


def delete_skill(name: str) -> dict:
    """Delete a skill folder. Sandbox skills are preferred targets; built-in
    skills are also deletable (use with care — they will be removed from the
    repository on disk).
    """
    skill = find_skill(name)
    if skill is None:
        return {"error": f"Skill not found: {name!r}"}
    shutil.rmtree(skill.path)
    return {"deleted": skill.name, "source": skill.source, "path": str(skill.path)}
