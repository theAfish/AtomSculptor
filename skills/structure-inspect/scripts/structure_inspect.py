"""Read and validate atomic structures — inspect a file, measure distances, detect close contacts."""
from pathlib import Path
from typing import Any

import numpy as np
from ase import Atoms
from ase.data import covalent_radii
from ase.io import read
from ase.neighborlist import neighbor_list

from sandbox.cli_support import build_cli_parser, run_cli
from sandbox.runtime_paths import sandbox_root

_LARGE_CIF_SIZE_BYTES = 1_000_000


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


def _load_atoms_from_path(path_str: str):
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


def _load_atoms(folder: str, file_name: str):
    path_str = file_name if folder in ("", ".") else str(Path(folder) / file_name)
    return _load_atoms_from_path(path_str)


def read_structure(folder: str, file_name: str) -> dict:
    """Summarizes the structure (formula, atom count, cell, PBC; full atom list when ≤ 10 atoms)."""
    atoms = _load_atoms(folder, file_name)
    if isinstance(atoms, dict) and "error" in atoms:
        return atoms

    num_atoms = len(atoms)
    result: dict[str, Any] = {
        "file": file_name,
        "chemical_formula": atoms.get_chemical_formula(),
        "num_atoms": num_atoms,
        "cell_vectors_angstrom": atoms.cell.array.tolist() if atoms.cell is not None else None,
        "periodic_boundary_conditions": atoms.pbc.tolist(),
    }
    if num_atoms <= 10:
        result["atoms"] = [
            {
                "index": index,
                "symbol": atom.symbol,
                "position_angstrom": atoms.positions[index].tolist(),
            }
            for index, atom in enumerate(atoms)
        ]
    return result


def read_structures_in_text(folder: str, file_name: str) -> dict:
    """Returns the raw structure file contents as text."""
    path_str = file_name if folder in ("", ".") else str(Path(folder) / file_name)
    file_path = _resolve_existing_file(path_str)
    if file_path is None:
        return {"error": f"File not found: {path_str}"}
    try:
        return {"raw_file_text": file_path.read_text(encoding="utf-8")}
    except Exception as exc:
        return {"error": str(exc)}


def calculate_distance(folder: str, file_name: str, index1: int, index2: int) -> dict:
    """Distance (Å) between two atom indices in the referenced structure."""
    atoms = _load_atoms(folder, file_name)
    if isinstance(atoms, dict) and "error" in atoms:
        return atoms

    num_atoms = len(atoms)
    for requested_index in (index1, index2):
        if requested_index < 0 or requested_index >= num_atoms:
            return {"error": f"Atom index {requested_index} is out of bounds for {num_atoms} atoms"}

    pos1 = atoms.positions[index1]
    pos2 = atoms.positions[index2]
    return {
        "file": file_name,
        "atom1": {"index": index1, "symbol": atoms[index1].symbol, "position_angstrom": pos1.tolist()},
        "atom2": {"index": index2, "symbol": atoms[index2].symbol, "position_angstrom": pos2.tolist()},
        "distance_angstrom": float(np.linalg.norm(pos1 - pos2)),
    }


def check_close_atoms(folder: str, file_name: str, tolerance: float = -0.5) -> dict:
    """Detect pairs whose distance is below covalent_radii_sum + tolerance.

    Useful for validating a freshly built structure for steric clashes.
    """
    atoms = _load_atoms(folder, file_name)
    if isinstance(atoms, dict) and "error" in atoms:
        return atoms

    radii = np.array([covalent_radii[a.number] for a in atoms])
    cutoff = float(radii.max() * 2 + tolerance)
    i, j, d = neighbor_list("ijd", atoms, cutoff)

    pair_mask = i < j
    close_mask = d < (radii[i] + radii[j] + tolerance)
    mask = pair_mask & close_mask

    close_pairs = []
    for idx1, idx2, dist in zip(i[mask], j[mask], d[mask]):
        min_dist = radii[idx1] + radii[idx2] + tolerance
        close_pairs.append({
            "atom1": {"index": int(idx1), "symbol": atoms[int(idx1)].symbol},
            "atom2": {"index": int(idx2), "symbol": atoms[int(idx2)].symbol},
            "distance_angstrom": round(float(dist), 3),
            "min_distance_angstrom": round(float(min_dist), 3),
        })
    num_close = len(close_pairs)
    if num_close > 10:
        close_pairs = close_pairs[:10]
        close_pairs.append({"note": f"{num_close - 10} more pairs not shown"})
    return {
        "file": file_name,
        "number_of_detected_close_pairs": num_close,
        "close_pairs": close_pairs,
    }


_TOOLS = {
    "read_structure": read_structure,
    "read_structures_in_text": read_structures_in_text,
    "calculate_distance": calculate_distance,
    "check_close_atoms": check_close_atoms,
}


if __name__ == "__main__":
    parser = build_cli_parser(
        prog="structure_inspect.py",
        description_lines=[
            "Read and validate atomic structures.",
            f"Working directory: {sandbox_root()}",
            "",
        ],
        tool_functions=_TOOLS,
    )
    raise SystemExit(run_cli(argv=None, parser=parser, tool_functions=_TOOLS))
