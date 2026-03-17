"""
CLI tool for generating common crystal structures using ASE.
Supports BCC, FCC, HCP, and other crystal structure types.
"""
import argparse
import inspect
import json
from pathlib import Path
from types import NoneType, UnionType
from typing import Any, Optional, Union, get_args, get_origin

from ase import Atoms
from ase.build import bulk
from ase.io import write
import numpy as np


DEFAULT_SAVE_TYPE = "extxyz"


def _normalize_file_name(file_name: str) -> str:
    """Normalize file names to make sure the suffix is set"""
    path = Path(file_name)
    if path.suffix == "":
        return str(path.with_suffix(f".{DEFAULT_SAVE_TYPE}"))
    return str(path)


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


def _resolve_output_path(output_name: str) -> Path:
    output_path = Path(output_name)
    if not output_path.is_absolute():
        output_path = _sandbox_output_dir() / output_path
    output_path.parent.mkdir(parents=True, exist_ok=True)
    return output_path


def _parse_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "t", "yes", "y", "on"}:
            return True
        if normalized in {"0", "false", "f", "no", "n", "off"}:
            return False
    raise ValueError(f"Expected a boolean value, got: {repr(value)}")


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
        parsed = json.loads(raw_value)
        if not isinstance(parsed, list):
            raise ValueError(f"Expected a JSON list, got: {raw_value}")
        return parsed
    if annotation is tuple:
        parsed = json.loads(raw_value)
        if not isinstance(parsed, list):
            raise ValueError(f"Expected a JSON list for tuple input, got: {raw_value}")
        return tuple(parsed)
    if annotation is dict:
        parsed = json.loads(raw_value)
        if not isinstance(parsed, dict):
            raise ValueError(f"Expected a JSON object, got: {raw_value}")
        return parsed
    if origin is list:
        parsed = json.loads(raw_value)
        if not isinstance(parsed, list):
            raise ValueError(f"Expected a JSON list, got: {raw_value}")
        return parsed
    if origin is tuple:
        parsed = json.loads(raw_value)
        if not isinstance(parsed, list):
            raise ValueError(f"Expected a JSON list for tuple input, got: {raw_value}")
        return tuple(parsed)
    if origin is dict:
        parsed = json.loads(raw_value)
        if not isinstance(parsed, dict):
            raise ValueError(f"Expected a JSON object, got: {raw_value}")
        return parsed
    if origin in (UnionType, Union):
        args = [arg for arg in get_args(annotation) if arg is not NoneType]
        last_error = None
        for arg in args:
            try:
                return _coerce_cli_value(raw_value, arg)
            except Exception as exc:
                last_error = exc
        if last_error is not None:
            raise ValueError(str(last_error)) from last_error
    return json.loads(raw_value)


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
        cli_type = _annotation_to_cli_type(parameter.annotation)
        if parameter.default is inspect._empty:
            parts.append(f"{cli_name} <{cli_type}>")
        else:
            parts.append(f"[{cli_name} <{cli_type}>]")
    usage = " ".join(parts)
    return f"{function_name}: {summary}\n  python crystal_builder.py {function_name} {usage}".rstrip()


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
    description_lines.append("Use 'python crystal_builder.py <tool_name> --help' for detailed help.")

    parser = argparse.ArgumentParser(
        prog="crystal_builder.py",
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
                help_text += f". Default: {repr(parameter.default)}"
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
            f"  python crystal_builder.py {tool_name} --help\n"
            f"  python crystal_builder.py {tool_name} "
            + " ".join(
                f"--{parameter.name.replace('_', '-')} <{_annotation_to_cli_type(parameter.annotation)}>"
                for parameter in inspect.signature(function).parameters.values()
            )
        )

    return parser


def _run_cli(argv=None):
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


if __name__ == "__main__":
    raise SystemExit(_run_cli())
