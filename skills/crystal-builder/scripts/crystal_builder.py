"""
CLI tool for generating common crystal structures using ASE.
Supports BCC, FCC, HCP, and other crystal structure types.
"""
import argparse
import inspect
from pathlib import Path
from typing import Optional

from ase import Atoms
from ase.build import bulk
from ase.io import write
import numpy as np

from sandbox.cli_support import (
    annotation_to_cli_type,
    build_cli_parser,
    run_cli,
)
from sandbox.runtime_paths import (
    display_path,
    resolve_output_path,
    sandbox_output_dir,
    sandbox_root,
)


DEFAULT_SAVE_TYPE = "extxyz"


def _normalize_file_name(file_name: str) -> str:
    """Normalize file names to make sure the suffix is set"""
    path = Path(file_name)
    if path.suffix == "":
        return str(path.with_suffix(f".{DEFAULT_SAVE_TYPE}"))
    return str(path)


def _sandbox_root() -> Path:
    return sandbox_root()


def _sandbox_output_dir() -> Path:
    return sandbox_output_dir()


def _display_path(path: Path) -> str:
    """Return sandbox-relative path when possible for cleaner tool output."""
    return display_path(path)


def _resolve_output_path(output_name: str) -> Path:
    return resolve_output_path(output_name)


TOOL_FUNCTION_NAMES = [
    "build_bulk_crystal",
    "list_crystal_structures",
]


def build_bulk_crystal(
    element: str,
    crystalstructure: str,
    a=None,
    b=None,
    c=None,
    alpha=None,
    covera=None,
    u=None,
    orthorhombic=False,
    cubic=False,
    output_name=None,
):
    """
    Build a bulk crystal structure.
    
    Parameters:
    - element: Chemical symbol(s) as in 'MgO' or 'NaCl' (for compound structures).
    - crystalstructure: Must be one of: sc, fcc, bcc, tetragonal, bct, hcp, rhombohedral,
                        orthorhombic, mcl, diamond, zincblende, rocksalt, cesiumchloride,
                        fluorite, wurtzite.
    - a: Lattice constant in Angstroms.
    - b: Lattice constant in Angstroms (for certain structures).
    - c: Lattice constant in Angstroms (for certain structures).
    - alpha: Angle in degrees for rhombohedral lattice.
    - covera: c/a ratio used for hcp. Default is ideal ratio: sqrt(8/3).
    - u: Internal coordinate for Wurtzite structure.
    - orthorhombic: Construct orthorhombic unit cell instead of primitive cell.
    - cubic: Construct cubic unit cell if possible.
    - output_name: Output file name. Default format is extxyz.
    
    Returns:
    - Dictionary with file path and structure info.
    """
    try:
        # Build kwargs for ASE bulk function
        kwargs = {
            "name": element,
            "crystalstructure": crystalstructure,
        }
        
        if a is not None:
            kwargs["a"] = float(a)
        if b is not None:
            kwargs["b"] = float(b)
        if c is not None:
            kwargs["c"] = float(c)
        if alpha is not None:
            kwargs["alpha"] = float(alpha)
        if covera is not None:
            kwargs["covera"] = float(covera)
        if u is not None:
            kwargs["u"] = float(u)
        if orthorhombic:
            kwargs["orthorhombic"] = bool(orthorhombic)
        if cubic:
            kwargs["cubic"] = bool(cubic)
        
        # Create the structure
        atoms = bulk(**kwargs)
        
        # Extract lattice parameters from cell
        cell = atoms.cell
        if cell is not None:
            # Calculate lattice lengths (magnitudes of cell vectors)
            lattice_a = float(np.linalg.norm(cell[0]))
            lattice_b = float(np.linalg.norm(cell[1]))
            lattice_c = float(np.linalg.norm(cell[2]))
        else:
            lattice_a = lattice_b = lattice_c = None
        
        # Determine output file name
        if output_name:
            output_name = _normalize_file_name(output_name)
        else:
            output_name = f"{element}_{crystalstructure}.{DEFAULT_SAVE_TYPE}"
        
        output_path = _resolve_output_path(output_name)
        write(output_path, atoms)
        
        return {
            "element": element,
            "crystalstructure": crystalstructure,
            "num_atoms": len(atoms),
            "chemical_formula": atoms.get_chemical_formula(),
            "lattice_constants": {
                "a": lattice_a,
                "b": lattice_b,
                "c": lattice_c,
            },
            "output_file": _display_path(output_path),
        }
    except Exception as e:
        return {"error": f"Failed to build crystal structure: {str(e)}"}


def list_crystal_structures():
    """
    List all supported crystal structure types with descriptions.
    
    Returns:
    - Dictionary with crystal structure types and their descriptions.
    """
    structures = {
        "sc": "Simple cubic",
        "fcc": "Face-centered cubic",
        "bcc": "Body-centered cubic",
        "tetragonal": "Tetragonal",
        "bct": "Body-centered tetragonal",
        "hcp": "Hexagonal close-packed",
        "rhombohedral": "Rhombohedral",
        "orthorhombic": "Orthorhombic",
        "mcl": "Monoclinic",
        "diamond": "Diamond structure",
        "zincblende": "Zincblende structure (binary compound)",
        "rocksalt": "Rock salt structure (NaCl-type)",
        "cesiumchloride": "Cesium chloride structure (CsCl-type)",
        "fluorite": "Fluorite structure (CaF2-type)",
        "wurtzite": "Wurtzite structure (binary compound)",
    }
    
    return {
        "crystal_structures": structures,
        "usage_note": "Use build_bulk_crystal with crystalstructure parameter to create any of these structures.",
        "examples": [
            "build_bulk_crystal --element Fe --crystalstructure bcc --a 2.87",
            "build_bulk_crystal --element Al --crystalstructure fcc --a 4.05 --cubic true",
            "build_bulk_crystal --element Mg --crystalstructure hcp --a 3.21 --covera 1.633",
            "build_bulk_crystal --element Si --crystalstructure diamond --a 5.43",
            "build_bulk_crystal --element NaCl --crystalstructure rocksalt --a 5.64",
        ]
    }


def _tool_functions():
    return {name: globals()[name] for name in TOOL_FUNCTION_NAMES}


def _build_tool_summary(function_name, function):
    doc_lines = (inspect.getdoc(function) or "").splitlines()
    summary = doc_lines[0].strip() if doc_lines else function_name
    signature = inspect.signature(function)
    parts = []
    for parameter in signature.parameters.values():
        cli_name = f"--{parameter.name.replace('_', '-')}"
        cli_type = annotation_to_cli_type(parameter.annotation)
        if parameter.default is inspect._empty:
            parts.append(f"{cli_name} <{cli_type}>")
        else:
            parts.append(f"[{cli_name} <{cli_type}>]")
    usage = " ".join(parts)
    return f"{function_name}: {summary}\n  python3 crystal_builder.py {function_name} {usage}".rstrip()


def _build_cli_parser():
    description_lines = [
        "CLI tool for generating common crystal structures.",
        f"Working directory: {_sandbox_root()}",
        "",
        "Available tools:",
    ]
    
    for tool_name, function in _tool_functions().items():
        doc_lines = (inspect.getdoc(function) or "").splitlines()
        summary = doc_lines[0].strip() if doc_lines else tool_name
        description_lines.append(f"  - {tool_name}: {summary}")
    
    description_lines.append("")
    description_lines.append("Use 'python3 crystal_builder.py <tool_name> --help' for detailed help.")

    return build_cli_parser(
        prog="crystal_builder.py",
        description_lines=description_lines,
        tool_functions=_tool_functions(),
    )


def _run_cli(argv=None):
    return run_cli(
        argv=argv,
        parser=_build_cli_parser(),
        tool_functions=_tool_functions(),
    )


if __name__ == "__main__":
    raise SystemExit(_run_cli())
