"""Build supercells from an existing structure file."""
from pathlib import Path
from typing import Optional

import numpy as np
from ase.build import make_supercell
from ase.io import read, write

from sandbox.cli_support import build_cli_parser, run_cli
from sandbox.runtime_paths import display_path, resolve_output_path, sandbox_root

_LARGE_CIF_SIZE_BYTES = 1_000_000
DEFAULT_SAVE_TYPE = "extxyz"


def _normalize_file_name(file_name: str) -> str:
    path = Path(file_name)
    if path.suffix == "":
        return str(path.with_suffix(f".{DEFAULT_SAVE_TYPE}"))
    return str(path)


def _iter_path_candidates(path_str: str) -> list[Path]:
    p = Path(path_str)
    candidates: list[Path] = [p]
    if not p.is_absolute():
        candidates.append(sandbox_root() / p)
        if p.parent == Path("."):
            candidates.append(sandbox_root() / p.name)
    seen: set[str] = set()
    unique: list[Path] = []
    for item in candidates:
        key = str(item)
        if key not in seen:
            seen.add(key)
            unique.append(item)
    return unique


def _resolve_existing_file(path_str: str) -> Path | None:
    for candidate in _iter_path_candidates(path_str):
        if candidate.exists() and candidate.is_file():
            return candidate
    return None


def _load_atoms(folder: str, file_name: str):
    path_str = file_name if folder in ("", ".") else str(Path(folder) / file_name)
    resolved = _resolve_existing_file(path_str)
    if resolved is None:
        return {"error": f"File not found: {path_str}"}
    try:
        if resolved.suffix.lower() == ".cif" and resolved.stat().st_size >= _LARGE_CIF_SIZE_BYTES:
            from pymatgen.io.ase import AseAtomsAdaptor
            from pymatgen.io.cif import CifParser
            parser = CifParser(str(resolved))
            structures = parser.parse_structures(primitive=False)
            if not structures:
                return {"error": f"No structures found in CIF file: {path_str}"}
            return AseAtomsAdaptor.get_atoms(structures[0])
        return read(resolved)
    except Exception as exc:
        return {"error": str(exc)}


def build_supercell(
    folder: str,
    file_name: str,
    repetitions: list[int] | list[list[int]],
    output_name: Optional[str] = None,
) -> dict:
    """Generate a supercell.

    `repetitions` may be either a 3-list `[n1, n2, n3]` or a 3x3 matrix.
    Default output format is extxyz.
    """
    if output_name:
        output_name = _normalize_file_name(output_name)
    atoms = _load_atoms(folder, file_name)
    if isinstance(atoms, dict) and "error" in atoms:
        return atoms
    if len(repetitions) != 3:
        return {"error": "Repetitions must be a list of three integers, or a 3x3 matrix."}

    if all(isinstance(x, int) for x in repetitions):
        repetitions = np.diag(repetitions)

    supercell_atoms = make_supercell(atoms, repetitions)
    output_file_name = output_name or f"supercell_{Path(file_name).name}"
    output_file_path = resolve_output_path(output_file_name)
    write(output_file_path, supercell_atoms)
    return {
        "original_file": file_name,
        "output_supercell_file": display_path(output_file_path),
    }


_TOOLS = {"build_supercell": build_supercell}


if __name__ == "__main__":
    parser = build_cli_parser(
        prog="supercell_builder.py",
        description_lines=[
            "Build supercells from an existing structure file.",
            f"Working directory: {sandbox_root()}",
            "",
        ],
        tool_functions=_TOOLS,
    )
    raise SystemExit(run_cli(argv=None, parser=parser, tool_functions=_TOOLS))
