"""Render a PNG image of an atomic structure using ASE + matplotlib."""
import os
from pathlib import Path

from ase.io import read

from sandbox.cli_support import build_cli_parser, run_cli
from sandbox.runtime_paths import display_path, resolve_output_path, sandbox_output_dir, sandbox_root

# Keep matplotlib's cache out of the user's home dir (sandbox-safe).
_MPL_CONFIG_DIR = sandbox_output_dir() / ".mplconfig"
_MPL_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("MPLCONFIGDIR", str(_MPL_CONFIG_DIR))

import matplotlib.pyplot as plt  # noqa: E402
from ase.visualize.plot import plot_atoms  # noqa: E402

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


def generate_structure_image(
    folder: str,
    file_name: str,
    output_image_name: str,
    rotation: str = "",
    dpi: int = 100,
) -> dict:
    """Render an image of the structure using ASE.

    Parameters:
    - rotation: comma string like '10x,20y,30z'.
    - dpi: PNG resolution (default 100).
    """
    atoms = _load_atoms(folder, file_name)
    if isinstance(atoms, dict) and "error" in atoms:
        return atoms

    output_file_path = resolve_output_path(output_image_name)
    try:
        fig, ax = plt.subplots()
        plot_atoms(atoms, ax=ax, rotation=rotation)
        ax.axis("off")
        plt.savefig(output_file_path, dpi=dpi, bbox_inches="tight")
        plt.close(fig)
        return {
            "original_file": file_name,
            "output_image_file": display_path(output_file_path),
        }
    except Exception as exc:
        return {"error": str(exc)}


_TOOLS = {"generate_structure_image": generate_structure_image}


if __name__ == "__main__":
    parser = build_cli_parser(
        prog="structure_image.py",
        description_lines=[
            "Render a PNG image of an atomic structure.",
            f"Working directory: {sandbox_root()}",
            "",
        ],
        tool_functions=_TOOLS,
    )
    raise SystemExit(run_cli(argv=None, parser=parser, tool_functions=_TOOLS))
