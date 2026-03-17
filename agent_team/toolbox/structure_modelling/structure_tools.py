"""
Tools for working with ASE (Atomic Simulation Environment).
"""
import argparse
import inspect
import json
from pathlib import Path
from types import NoneType, UnionType
from typing import Any, Optional, Union, get_args, get_origin

from ase import Atoms
from ase.build import surface, make_supercell
from ase.data import covalent_radii
from ase.io import read, write
from ase.neighborlist import neighbor_list
from ase.visualize.plot import plot_atoms
import matplotlib.pyplot as plt
import numpy as np

from pymatgen.analysis.interfaces.substrate_analyzer import SubstrateAnalyzer
from pymatgen.analysis.interfaces.coherent_interfaces import CoherentInterfaceBuilder
from pymatgen.io.ase import AseAtomsAdaptor
from pymatgen.io.cif import CifParser


_LARGE_CIF_SIZE_BYTES = 1_000_000
DEFAULT_SAVE_TYPE = "extxyz"

def _normalize_file_name(file_name: str) -> str:
    """Normalize file names to make sure the suffix is set"""
    path = Path(file_name)
    if path.suffix == "":
        return str(path.with_suffix(f".{DEFAULT_SAVE_TYPE}"))
    return str(path)



TOOL_FUNCTION_NAMES = [
    "read_structure",
    "read_structures_in_text",
    "calculate_distance",
    "build_supercell",
    "build_surface",
    "generate_structure_image",
    "check_close_atoms",
    "build_interface",
]


def _sandbox_root() -> Path:
    return Path(".").resolve()


def _sandbox_output_dir() -> Path:
    output_dir = _sandbox_root()
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def _display_path(path: Path) -> str:
    """Return sandbox-relative path when possible for cleaner tool output."""
    resolved = path.expanduser().resolve()
    root = _sandbox_root()
    try:
        return str(resolved.relative_to(root))
    except ValueError:
        return str(resolved)


def _iter_path_candidates(path_str: str) -> list[Path]:
    p = Path(path_str)
    candidates: list[Path] = [p]

    if not p.is_absolute():
        candidates.append(_sandbox_root() / p)
        if p.parent == Path("."):
            candidates.append(_sandbox_root() / p.name)

    # Preserve order while de-duplicating.
    unique: list[Path] = []
    seen: set[str] = set()
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


def _resolve_output_path(output_name: str) -> Path:
    output_path = Path(output_name)
    if not output_path.is_absolute():
        output_path = _sandbox_output_dir() / output_path
    output_path.parent.mkdir(parents=True, exist_ok=True)
    return output_path


def _parse_json_or_raw(value: str) -> Any:
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


def _parse_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "t", "yes", "y", "on"}:
            return True
        if normalized in {"0", "false", "f", "no", "n", "off"}:
            return False
    raise ValueError(f"Expected a boolean value, got: {value!r}")


def _annotation_to_cli_type(annotation: Any) -> str:
    origin = get_origin(annotation)

    if annotation in (inspect._empty, Any, str):
        return "string"
    if annotation is int:
        return "integer"
    if annotation is float:
        return "number"
    if annotation is bool:
        return "boolean"
    if annotation in (list, tuple, dict):
        return "JSON"
    if origin in (list, tuple, dict):
        return "JSON"
    if origin in (UnionType, Union):
        args = [arg for arg in get_args(annotation) if arg is not NoneType]
        if len(args) == 1:
            return _annotation_to_cli_type(args[0])
        cli_types = {_annotation_to_cli_type(arg) for arg in args}
        if len(cli_types) == 1:
            return cli_types.pop()
    return "string"


def _coerce_cli_value(raw_value: str, annotation: Any) -> Any:
    origin = get_origin(annotation)

    if annotation in (inspect._empty, Any, str):
        return raw_value
    if annotation is int:
        return int(raw_value)
    if annotation is float:
        return float(raw_value)
    if annotation is bool:
        return _parse_bool(raw_value)
    if annotation is list:
        parsed = _parse_json_or_raw(raw_value)
        if not isinstance(parsed, list):
            raise ValueError(f"Expected a JSON list, got: {raw_value}")
        return parsed
    if annotation is tuple:
        parsed = _parse_json_or_raw(raw_value)
        if not isinstance(parsed, list):
            raise ValueError(f"Expected a JSON list for tuple input, got: {raw_value}")
        return tuple(parsed)
    if annotation is dict:
        parsed = _parse_json_or_raw(raw_value)
        if not isinstance(parsed, dict):
            raise ValueError(f"Expected a JSON object, got: {raw_value}")
        return parsed
    if origin is list:
        parsed = _parse_json_or_raw(raw_value)
        if not isinstance(parsed, list):
            raise ValueError(f"Expected a JSON list, got: {raw_value}")
        return parsed
    if origin is tuple:
        parsed = _parse_json_or_raw(raw_value)
        if not isinstance(parsed, list):
            raise ValueError(f"Expected a JSON list for tuple input, got: {raw_value}")
        return tuple(parsed)
    if origin is dict:
        parsed = _parse_json_or_raw(raw_value)
        if not isinstance(parsed, dict):
            raise ValueError(f"Expected a JSON object, got: {raw_value}")
        return parsed
    if origin in (UnionType, Union):
        args = [arg for arg in get_args(annotation) if arg is not NoneType]
        last_error: Exception | None = None
        for arg in args:
            try:
                return _coerce_cli_value(raw_value, arg)
            except Exception as exc:
                last_error = exc
        if last_error is not None:
            raise ValueError(str(last_error)) from last_error
    return _parse_json_or_raw(raw_value)


def _tool_functions() -> dict[str, Any]:
    return {name: globals()[name] for name in TOOL_FUNCTION_NAMES}


def _build_tool_summary(function_name: str, function: Any) -> str:
    doc_lines = (inspect.getdoc(function) or "").splitlines()
    summary = doc_lines[0].strip() if doc_lines else function_name
    signature = inspect.signature(function)
    parts = []
    for parameter in signature.parameters.values():
        cli_name = f"--{parameter.name.replace('_', '-')}"
        cli_type = _annotation_to_cli_type(parameter.annotation)
        if parameter.default is inspect._empty:
            parts.append(f"{cli_name} <{cli_type}>")
        else:
            parts.append(f"[{cli_name} <{cli_type}>]")
    usage = " ".join(parts)
    return f"{function_name}: {summary}\n  python structure_tools.py {function_name} {usage}".rstrip()


def _build_cli_parser() -> argparse.ArgumentParser:
    description_lines = [
        "CLI wrapper for runtime sandbox structure tools.",
        f"Working directory: {_sandbox_root()}",
        "",
    ]

    parser = argparse.ArgumentParser(
        prog="structure_tools.py",
        description="\n".join(description_lines),
        formatter_class=argparse.RawTextHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="tool_name", metavar="tool_name")

    for tool_name, function in _tool_functions().items():
        tool_doc = inspect.getdoc(function) or ""
        tool_parser = subparsers.add_parser(
            tool_name,
            help=tool_doc.splitlines()[0] if tool_doc else tool_name,
            description=tool_doc,
            formatter_class=argparse.RawTextHelpFormatter,
        )

        for parameter in inspect.signature(function).parameters.values():
            cli_flag = f"--{parameter.name.replace('_', '-')}"
            cli_type = _annotation_to_cli_type(parameter.annotation)
            help_text = f"{parameter.name} ({cli_type})"
            if parameter.default is not inspect._empty:
                help_text += f". Default: {parameter.default!r}"
            if cli_type == "JSON":
                help_text += ". Pass JSON, for example '[1, 0, 0]'"

            tool_parser.add_argument(
                cli_flag,
                dest=parameter.name,
                required=parameter.default is inspect._empty,
                help=help_text,
            )

        tool_parser.epilog = (
            "Examples:\n"
            f"  python structure_tools.py {tool_name} --help\n"
            f"  python structure_tools.py {tool_name} "
            + " ".join(
                f"--{parameter.name.replace('_', '-')} <{_annotation_to_cli_type(parameter.annotation)}>"
                for parameter in inspect.signature(function).parameters.values()
            )
        )

    return parser


def _run_cli(argv: list[str] | None = None) -> int:
    parser = _build_cli_parser()
    args = parser.parse_args(argv)

    if not getattr(args, "tool_name", None):
        parser.print_help()
        return 0

    function = _tool_functions()[args.tool_name]
    signature = inspect.signature(function)

    try:
        kwargs = {}
        for parameter in signature.parameters.values():
            raw_value = getattr(args, parameter.name)
            if raw_value is None:
                continue
            kwargs[parameter.name] = _coerce_cli_value(raw_value, parameter.annotation)
    except Exception as exc:
        parser.error(str(exc))

    result = function(**kwargs)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if not isinstance(result, dict) or "error" not in result else 1


def _load_atoms(folder: str, file_name: str) -> Atoms:
    """Loads an ASE Atoms object from disk."""
    path_str = file_name if folder in ("", ".") else str(Path(folder) / file_name)
    return _load_atoms_from_path(path_str)


def _load_atoms_from_path(path_str: str) -> Atoms:
    """Load an ASE Atoms object from a path string.

    This helper accepts either an absolute or relative filesystem path, or
    a workspace-relative path/filename. It returns the Atoms object on
    success or a dict with an "error" key on failure (to match
    _load_atoms behavior).
    """
    resolved = _resolve_existing_file(path_str)
    if resolved is None:
        return {"error": f"File not found: {path_str}"}

    try:
        # ASE's CIF reader can become extremely slow on very large CIFs due
        # to symmetry-equivalent site handling. Use pymatgen for large CIFs.
        if resolved.suffix.lower() == ".cif" and resolved.stat().st_size >= _LARGE_CIF_SIZE_BYTES:
            parser = CifParser(str(resolved))
            structures = parser.parse_structures(primitive=False)
            if not structures:
                return {"error": f"No structures found in CIF file: {path_str}"}
            return AseAtomsAdaptor.get_atoms(structures[0])

        return read(resolved)
    except Exception as e:
        return {"error": str(e)}


def read_structure(folder: str, file_name: str) -> dict:
    """Summarizes the structure in a way that downstream agents can consume."""
    atoms = _load_atoms(folder, file_name)
    if isinstance(atoms, dict) and "error" in atoms:
        return {"error": atoms["error"]}
    
    num_atoms = len(atoms)
    result = {
        "file": file_name,
        "chemical_formula": atoms.get_chemical_formula(),
        "num_atoms": num_atoms,
        "cell_vectors_angstrom": atoms.cell.array.tolist()
        if atoms.cell is not None
        else None,
        "periodic_boundary_conditions": atoms.pbc.tolist(),
    }
    
    # For structures with <= 10 atoms, provide full atom details
    if num_atoms <= 10:
        result["atoms"] = [
            {
                "index": index,
                "symbol": atom.symbol,
                "position_angstrom": atoms.positions[index].tolist(),
            }
            for index, atom in enumerate(atoms)
        ]
    # else:
    #     # Later potential implementation of robocrystallographer
    #     result["note"] = f""
    
    return result

def read_structures_in_text(folder: str, file_name: str) -> dict:
    """Read the raw structure file in text format as a string, if agents want to see and check."""
    path_str = file_name if folder in ("", ".") else str(Path(folder) / file_name)
    file_path = _resolve_existing_file(path_str)
    if file_path is None:
        return {"error": f"File not found: {path_str}"}

    try:
        return {"raw_file_text": file_path.read_text(encoding="utf-8")}
    except Exception as e:
        return {"error": str(e)}


def calculate_distance(folder: str, file_name: str, index1: int, index2: int) -> dict:
    """Calculates the distance between two atoms within the referenced structure."""
    atoms = _load_atoms(folder, file_name)
    if isinstance(atoms, dict) and "error" in atoms:
        return atoms
        
    num_atoms = len(atoms)
    for requested_index in (index1, index2):
        if requested_index < 0 or requested_index >= num_atoms:
            return {"error": f"Atom index {requested_index} is out of bounds for {num_atoms} atoms"}

    pos1 = atoms.positions[index1]
    pos2 = atoms.positions[index2]
    distance = float(np.linalg.norm(pos1 - pos2))
    return {
        "file": file_name,
        "atom1": {
            "index": index1,
            "symbol": atoms[index1].symbol,
            "position_angstrom": pos1.tolist(),
        },
        "atom2": {
            "index": index2,
            "symbol": atoms[index2].symbol,
            "position_angstrom": pos2.tolist(),
        },
        "distance_angstrom": distance,
    }

def build_supercell(folder: str, file_name: str, repetitions: list[int] | list[list[int]], output_name: Optional[str] = None) -> dict:
    f"""
    Generates a supercell from the given structure by repeating it along each axis.
     - repetitions can be either a list of three integers [n1, n2, n3] or a 3x3 matrix for general supercells.
     - output_name is optional; if not provided, the output file will be named based on the input file. Default output format is {DEFAULT_SAVE_TYPE}.
    """
    if output_name:
        output_name = _normalize_file_name(output_name)
    atoms = _load_atoms(folder, file_name)
    if isinstance(atoms, dict) and "error" in atoms:
        return atoms
    if len(repetitions) != 3:
        return {"error": "Repetitions must be a list of three integers, or a 3x3 matrix."}
    
    # if repetitions is a list of three integers, convert to a diagonal matrix
    if all(isinstance(x, int) for x in repetitions):
        repetitions = np.diag(repetitions)

    supercell_atoms = make_supercell(atoms, repetitions)
    if output_name:
        output_file_name = output_name
    else:
        output_file_name = f"supercell_{Path(file_name).name}"
    output_file_path = _resolve_output_path(output_file_name)
    write(output_file_path, supercell_atoms)
    return {
        "original_file": file_name,
        "output_supercell_file": _display_path(output_file_path),
    }

def build_surface(folder: str, file_name: str, miller_indices: list, layers: int, vacuum: float, output_name: Optional[str] = None) -> dict:
    f"""
    Creates a surface slab from a bulk structure.
     - miller_indices is a list of three integers representing the Miller indices of the surface.
     - layers is the number of atomic layers to include in the slab.
     - vacuum is the amount of vacuum (in Å) to add above the slab.
     - output_name is optional; if not provided, the output file will be named based on the input file. Default output format is {DEFAULT_SAVE_TYPE}.
    """
    try:
        if output_name:
            output_name = _normalize_file_name(output_name)
        atoms = _load_atoms(folder, file_name)
        if isinstance(atoms, dict) and "error" in atoms:
            return atoms
        if len(miller_indices) != 3:
            return {"error": "Miller indices must be a list of three integers."}
        
        # Pass the vacuum directly to `surface` so the returned slab keeps a valid 3D cell.
        slab = surface(atoms, miller_indices, layers, vacuum=vacuum)
        if output_name:
            output_file_name = output_name
        else:
            output_file_name = f"slab_{Path(file_name).name}"
        output_file_path = _resolve_output_path(output_file_name)
        write(output_file_path, slab)
        return {
			"original_file": file_name,
			"output_surface_file": _display_path(output_file_path),
		}
    except Exception as e:
        return {"error": str(e)}

def generate_structure_image(folder: str, file_name: str, output_image_name: str, rotation: str = '', dpi: int = 100) -> dict:
    """Generates an image of the structure using ASE.
    rotation: string like '10x,20y,30z'
    dpi: resolution in dots per inch for the PNG image
    """
    atoms = _load_atoms(folder, file_name)
    if isinstance(atoms, dict) and "error" in atoms:
        return atoms
    
    output_file_path = _resolve_output_path(output_image_name)
        
    try:
        # Use ASE's plot_atoms and matplotlib to save with custom DPI
        fig, ax = plt.subplots()
        plot_atoms(atoms, ax=ax, rotation=rotation)
        ax.axis('off')  # Remove coordinate axes
        plt.savefig(output_file_path, dpi=dpi, bbox_inches='tight')
        plt.close(fig)
        return {
            "original_file": file_name,
            "output_image_file": _display_path(output_file_path),
        }
    except Exception as e:
        return {"error": str(e)}

def check_close_atoms(folder: str, file_name: str, tolerance: float = -0.5) -> dict:
    """
    Checks for atoms that are too close to each other, using covalent radii plus tolerance. 
    This tool is useful for validating structures.
    """
    atoms = _load_atoms(folder, file_name)

    if isinstance(atoms, dict) and "error" in atoms:
        return atoms

    radii = np.array([covalent_radii[a.number] for a in atoms])
    cutoff = float(radii.max() * 2 + tolerance)
    i, j, d = neighbor_list("ijd", atoms, cutoff)

    # Keep each pair once to preserve the original API's i < j behavior.
    pair_mask = i < j
    close_mask = d < (radii[i] + radii[j] + tolerance)
    mask = pair_mask & close_mask

    close_pairs = []
    for idx1, idx2, dist in zip(i[mask], j[mask], d[mask]):
        min_dist = radii[idx1] + radii[idx2] + tolerance
        close_pairs.append({
            "atom1": {
                "index": int(idx1),
                "symbol": atoms[int(idx1)].symbol,
            },
            "atom2": {
                "index": int(idx2),
                "symbol": atoms[int(idx2)].symbol,
            },
            "distance_angstrom": round(float(dist), 3),
            "min_distance_angstrom": round(float(min_dist), 3),
        })
    num_close = len(close_pairs)
    return {
        "file": file_name,
        "number_of_detected_close_pairs": num_close,
        "close_pairs": close_pairs,
    }




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
    in_layers: Optional[bool] = True
) -> dict:
    """
    Builds a coherent interface structure between two bulk structures using pymatgen,
    starting from ASE Atoms objects.

    Parameters:
    - structure_1: File path for the first bulk structure.
    - structure_2: File path for the second bulk structure.
    - miller_1: Miller index for the first structure surface (default: (1, 0, 0)).
    - miller_2: Miller index for the second structure surface (default: (1, 1, 1)).
    - output_file_name: Optional path to save the generated interface structure as a file.
    - max_area: Maximum supercell area for matching (default: 400.0).
    - max_length_tol: Length tolerance for ZSL matching (default: 0.03).
    - max_angle_tol: Angle tolerance for ZSL matching (default: 0.01).
    - gap: Gap between the two structures in Å (default: 2.5).
    - vacuum_between: Vacuum above the first structure in Å (default: 0.0). If set to 0, it will be adjusted to 'gap'.
    - thickness_1: Thickness of the first structure in layers or Å (default: 2).
    - thickness_2: Thickness of the second structure in layers or Å (default: 2).
    - in_layers: If True, thickness is in number of layers (default: True).

    Returns:
    - The generated structure path or error message.
    """
    # Load structures from file paths using safer loader that handles
    # absolute paths and workspace-relative names.
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
    except Exception as e:
        return {"error": f"Failed to load structures: {str(e)}"}
    
    # Ensure numeric parameters are of correct type
    try:
        gap = float(gap)
        if vacuum_between is not None:
            vacuum_between = float(vacuum_between)
        else:
            vacuum_between = 0.0
        
        if max_area is not None:
            max_area = float(max_area)
        if max_length_tol is not None:
            max_length_tol = float(max_length_tol)
        if max_angle_tol is not None:
            max_angle_tol = float(max_angle_tol)
            
        thickness_1 = int(thickness_1)
        thickness_2 = int(thickness_2)


        # Find matches using SubstrateAnalyzer with parameters directly
        analyzer = SubstrateAnalyzer(
            max_area_ratio_tol=0.09,  # Default value; adjust if needed
            max_area=max_area,
            max_length_tol=max_length_tol,
            max_angle_tol=max_angle_tol
        )
        matches = list(analyzer.calculate(
            film=film,
            substrate=substrate,
            film_millers=[miller_1],
            substrate_millers=[miller_2]
        ))
        if not matches:
            return {"error": "No lattice matches found. Try adjusting tolerances or Miller indices."}
        
        # Use the first match (lowest strain preferred)
        match = sorted(matches, key=lambda m: m.von_mises_strain)[0]

        # Initialize CoherentInterfaceBuilder without sl_vectors
        builder = CoherentInterfaceBuilder(
            film_structure=film,
            substrate_structure=substrate,
            film_miller=match.film_miller,
            substrate_miller=match.substrate_miller,
            zslgen=analyzer  # Pass the analyzer as zslgen to use the same matching parameters
        )

        # Get terminations
        terminations = builder.terminations
        if not terminations:
            return {"error": "No terminations available for the selected slabs."}

        # Use the first termination pair
        termination = terminations[0]

        # Adjust vacuum_over_film if 0 to avoid overlap across PBC
        effective_vacuum = vacuum_between
        if vacuum_between == 0:
            effective_vacuum = gap  # Set to gap to symmetrize interfaces and prevent PBC overlap

        # Generate interfaces
        interfaces = list(builder.get_interfaces(
            termination=termination,
            gap=gap,
            vacuum_over_film=effective_vacuum,
            film_thickness=thickness_1,
            substrate_thickness=thickness_2,
            in_layers=in_layers
        ))

        if not interfaces:
            return{"error": "No interfaces generated. Check parameters."}

        # Return the first interface
        interface = interfaces[0]

        # Optional adjustments
        interface.translate_sites(range(len(interface)), [0, 0, 0])  # Translate for better visualization
    except Exception as e:
        return {"error": f"Error during matching: {str(e)}"}
    
    
    if output_file_name:
        output_path = _resolve_output_path(output_file_name)
    else:
        # get the names of the input files without extensions
        film_name = Path(structure_1).stem
        substrate_name = Path(structure_2).stem
        output_path = _resolve_output_path(f"{film_name}-{substrate_name}_interface.extxyz")
    
    try:
        interface = interface.to_ase_atoms()
        write(output_path, interface)
    except Exception as e:
        return {"error": f"Failed to write interface to file: {str(e)}"}

    return {
        "output_interface_file": _display_path(output_path),
    }


if __name__ == "__main__":
    raise SystemExit(_run_cli())

