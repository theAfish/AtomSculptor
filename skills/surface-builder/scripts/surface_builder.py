"""Build (hkl) surface slabs from a bulk crystal."""
from pathlib import Path
from typing import Optional

from ase.build import surface
from ase.io import read, write
from pymatgen.core import Structure
from pymatgen.symmetry.analyzer import SpacegroupAnalyzer

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


def build_surface(
    folder: str,
    file_name: str,
    miller_indices: list,
    layers: int,
    vacuum: float,
    output_name: Optional[str] = None,
    need_conventional: bool = True,
) -> dict:
    """Create a surface slab from a bulk structure.

    Parameters:
    - miller_indices: 3-list of integers (the surface Miller indices).
    - layers: number of atomic layers in the slab.
    - vacuum: vacuum thickness in Å added above the slab.
    - need_conventional: if True, convert to the conventional standard cell first.
    """
    try:
        if output_name:
            output_name = _normalize_file_name(output_name)
        atoms = _load_atoms(folder, file_name)
        if isinstance(atoms, dict) and "error" in atoms:
            return atoms
        if len(miller_indices) != 3:
            return {"error": "Miller indices must be a list of three integers."}

        if need_conventional:
            struct = Structure.from_ase_atoms(atoms)
            analyzer = SpacegroupAnalyzer(struct, symprec=0.1)
            conventional_struct = analyzer.get_conventional_standard_structure()
            atoms = conventional_struct.to_ase_atoms()

        slab = surface(atoms, miller_indices, layers, vacuum=vacuum)
        output_file_name = output_name or f"slab_{Path(file_name).name}"
        output_file_path = resolve_output_path(output_file_name)
        write(output_file_path, slab)
        return {
            "original_file": file_name,
            "output_surface_file": display_path(output_file_path),
        }
    except Exception as exc:
        return {"error": str(exc)}


_TOOLS = {"build_surface": build_surface}


if __name__ == "__main__":
    parser = build_cli_parser(
        prog="surface_builder.py",
        description_lines=[
            "Build (hkl) surface slabs from a bulk crystal.",
            f"Working directory: {sandbox_root()}",
            "",
        ],
        tool_functions=_TOOLS,
    )
    raise SystemExit(run_cli(argv=None, parser=parser, tool_functions=_TOOLS))
