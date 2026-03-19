"""Filesystem operations: sandbox root, file-tree building, file content serving."""

from pathlib import Path

from settings import settings

from .helpers import is_path_safe


def sandbox_root() -> Path:
    return Path(settings.SANDBOX_DIR).expanduser().resolve()


def build_file_tree(root: Path, base: Path) -> list:
    if not root.exists():
        return []
    entries = []
    try:
        for item in sorted(
            root.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())
        ):
            if item.name.startswith(".") or item.name == "__pycache__":
                continue
            rel = str(item.relative_to(base))
            if item.is_dir():
                entries.append({
                    "name": item.name,
                    "path": rel,
                    "type": "directory",
                    "children": build_file_tree(item, base),
                })
            else:
                from .structure import is_structure_filename
                entries.append({
                    "name": item.name,
                    "path": rel,
                    "type": "file",
                    "size": item.stat().st_size,
                    "is_structure": is_structure_filename(item.name),
                })
    except PermissionError:
        pass
    return entries
