"""Anthropic-style Agent Skills for AtomSculptor.

A *skill* is a self-contained folder containing a ``SKILL.md`` file with YAML
frontmatter and (optionally) ``scripts/``, ``references/``, ``assets/`` and a
``requirements.txt``.  Skills live in two locations:

- Built-in library:  ``<repo>/skills/<name>/``        (read-only, ships with code)
- Sandbox library:   ``<SANDBOX_DIR>/skills/<name>/`` (writable; agent-created or
  copied-on-demand from the built-in library)

Public surface is exposed via :mod:`agent_team.skills.tools`.
"""

from agent_team.skills.tools import (
    create_skill,
    delete_skill,
    install_skill_deps,
    list_skills,
    promote_skill,
    read_skill,
    run_skill,
    update_skill,
)

__all__ = [
    "create_skill",
    "delete_skill",
    "install_skill_deps",
    "list_skills",
    "promote_skill",
    "read_skill",
    "run_skill",
    "update_skill",
]
