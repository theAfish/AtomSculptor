"""Build a coherent ZSL-matched interface between two bulk crystals."""
from pathlib import Path
from typing import Optional

from ase.io import read, write
from pymatgen.analysis.interfaces.coherent_interfaces import CoherentInterfaceBuilder
from pymatgen.analysis.interfaces.substrate_analyzer import SubstrateAnalyzer
from pymatgen.io.ase import AseAtomsAdaptor

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


def _load_atoms_from_path(path_str: str):
    resolved = _resolve_existing_file(path_str)
    if resolved is None:
        return {"error": f"File not found: {path_str}"}
    try:
        if resolved.suffix.lower() == ".cif" and resolved.stat().st_size >= _LARGE_CIF_SIZE_BYTES:
            from pymatgen.io.cif import CifParser
            parser = CifParser(str(resolved))
            structures = parser.parse_structures(primitive=False)
            if not structures:
                return {"error": f"No structures found in CIF file: {path_str}"}
            return AseAtomsAdaptor.get_atoms(structures[0])
        return read(resolved)
    except Exception as exc:
        return {"error": str(exc)}


def build_interface(
    structure_1: str,
    structure_2: str,
    miller_1: tuple = (1, 0, 0),
    miller_2: tuple = (1, 1, 1),
    output_file_name: Optional[str] = None,
    max_area: Optional[float] = 400.0,
    max_length_tol: Optional[float] = 0.03,
    max_angle_tol: Optional[float] = 0.01,
    gap: float = 2.5,
    vacuum_between: Optional[float] = 0.0,
    thickness_1: int = 2,
    thickness_2: int = 2,
    in_layers: Optional[bool] = True,
) -> dict:
    """Build a coherent ZSL-matched interface from two bulk structures.

    Parameters:
    - structure_1 / structure_2: paths to the film and substrate bulk files.
    - miller_1 / miller_2: Miller indices of the surfaces to expose.
    - gap: Å between film and substrate.
    - vacuum_between: vacuum above the film (0 → set equal to `gap`).
    - thickness_1 / thickness_2: thickness in layers (or Å if in_layers=False).
    - max_area / max_length_tol / max_angle_tol: ZSL matching tolerances.
    """
    adaptor = AseAtomsAdaptor()
    if output_file_name:
        output_file_name = _normalize_file_name(output_file_name)
    try:
        film_atoms = _load_atoms_from_path(structure_1)
        substrate_atoms = _load_atoms_from_path(structure_2)
        if isinstance(film_atoms, dict) and "error" in film_atoms:
            return film_atoms
        if isinstance(substrate_atoms, dict) and "error" in substrate_atoms:
            return substrate_atoms
        film = adaptor.get_structure(film_atoms)
        substrate = adaptor.get_structure(substrate_atoms)
    except Exception as exc:
        return {"error": f"Failed to load structures: {str(exc)}"}

    try:
        gap = float(gap)
        vacuum_between = float(vacuum_between) if vacuum_between is not None else 0.0
        if max_area is not None:
            max_area = float(max_area)
        if max_length_tol is not None:
            max_length_tol = float(max_length_tol)
        if max_angle_tol is not None:
            max_angle_tol = float(max_angle_tol)
        thickness_1 = int(thickness_1)
        thickness_2 = int(thickness_2)

        analyzer = SubstrateAnalyzer(
            max_area_ratio_tol=0.09,
            max_area=max_area,
            max_length_tol=max_length_tol,
            max_angle_tol=max_angle_tol,
        )
        matches = list(analyzer.calculate(
            film=film,
            substrate=substrate,
            film_millers=[miller_1],
            substrate_millers=[miller_2],
        ))
        if not matches:
            return {"error": "No lattice matches found. Try adjusting tolerances or Miller indices."}

        match = sorted(matches, key=lambda m: m.von_mises_strain)[0]
        builder = CoherentInterfaceBuilder(
            film_structure=film,
            substrate_structure=substrate,
            film_miller=match.film_miller,
            substrate_miller=match.substrate_miller,
            zslgen=analyzer,
        )
        terminations = builder.terminations
        if not terminations:
            return {"error": "No terminations available for the selected slabs."}
        termination = terminations[0]

        effective_vacuum = vacuum_between if vacuum_between != 0 else gap
        interfaces = list(builder.get_interfaces(
            termination=termination,
            gap=gap,
            vacuum_over_film=effective_vacuum,
            film_thickness=thickness_1,
            substrate_thickness=thickness_2,
            in_layers=in_layers,
        ))
        if not interfaces:
            return {"error": "No interfaces generated. Check parameters."}

        interface = interfaces[0]
        interface.translate_sites(range(len(interface)), [0, 0, 0])
    except Exception as exc:
        return {"error": f"Error during matching: {str(exc)}"}

    if output_file_name:
        output_path = resolve_output_path(output_file_name)
    else:
        film_name = Path(structure_1).stem
        substrate_name = Path(structure_2).stem
        output_path = resolve_output_path(f"{film_name}-{substrate_name}_interface.extxyz")

    try:
        interface = interface.to_ase_atoms()
        write(output_path, interface)
    except Exception as exc:
        return {"error": f"Failed to write interface to file: {str(exc)}"}

    return {"output_interface_file": display_path(output_path)}


_TOOLS = {"build_interface": build_interface}


if __name__ == "__main__":
    parser = build_cli_parser(
        prog="interface_builder.py",
        description_lines=[
            "Build a coherent lattice-matched interface between two bulk crystals.",
            f"Working directory: {sandbox_root()}",
            "",
        ],
        tool_functions=_TOOLS,
    )
    raise SystemExit(run_cli(argv=None, parser=parser, tool_functions=_TOOLS))
