"""ASE structure detection, parsing, and serialisation."""

from pathlib import Path

STRUCTURE_EXTS = {"cif", "xyz", "vasp", "poscar", "extxyz", "pdb", "sdf", "mol2"}
VASP_STRUCTURE_PREFIXES = ("poscar", "contcar")


def detect_ase_format(path_or_name: str | Path) -> str | None:
    name = Path(path_or_name).name.lower()
    suffix = Path(name).suffix.lower().lstrip(".")
    if suffix in STRUCTURE_EXTS:
        return "vasp" if suffix == "poscar" else suffix
    if any(
        name == prefix
        or name.startswith(f"{prefix}_")
        or name.startswith(f"{prefix}-")
        or name.startswith(f"{prefix}.")
        for prefix in VASP_STRUCTURE_PREFIXES
    ):
        return "vasp"
    return None


def resolve_ase_io_format(path: Path) -> str | None:
    """Resolve ASE format, including extxyz payload in .xyz files."""
    ase_format = detect_ase_format(path)
    if ase_format != "xyz":
        return ase_format

    try:
        with path.open("r", encoding="utf-8") as fh:
            _ = fh.readline()
            comment = fh.readline()
    except OSError:
        return ase_format

    lowered = comment.lower()
    if "lattice=" in lowered or "properties=" in lowered or "pbc=" in lowered:
        return "extxyz"
    return ase_format


def is_structure_filename(path_or_name: str | Path) -> bool:
    return detect_ase_format(path_or_name) is not None


def cell_to_json(atoms) -> list[list[float]] | None:
    """Return 3x3 cell matrix when structure defines a non-zero cell."""
    cell_obj = atoms.get_cell()
    if getattr(cell_obj, "rank", 0) <= 0:
        return None
    return cell_obj.tolist()


def read_structure(fp: Path) -> dict:
    """Read a structure file and return serialised atom/cell/pbc data."""
    from ase.io import read as ase_read

    ase_format = resolve_ase_io_format(fp)
    atoms = ase_read(str(fp), format=ase_format)

    cell = cell_to_json(atoms)
    pbc = [bool(v) for v in atoms.get_pbc()]

    atom_list = []
    for i, atom in enumerate(atoms):
        atom_list.append({
            "id": i,
            "symbol": atom.symbol,
            "x": float(atom.position[0]),
            "y": float(atom.position[1]),
            "z": float(atom.position[2]),
        })

    return {"atoms": atom_list, "cell": cell, "pbc": pbc}


def write_structure(fp: Path, atoms_data: list, cell, pbc) -> int:
    """Write atom data back to a structure file via ASE.  Returns atom count."""
    from ase import Atoms as AseAtoms
    from ase.io import write as ase_write

    symbols = [a["symbol"] for a in atoms_data]
    positions = [[a["x"], a["y"], a["z"]] for a in atoms_data]
    kwargs = {"symbols": symbols, "positions": positions, "pbc": pbc}
    if cell is not None:
        kwargs["cell"] = cell
    new_atoms = AseAtoms(**kwargs)
    ase_format = resolve_ase_io_format(fp)
    if ase_format is None:
        ase_write(str(fp), new_atoms)
    else:
        ase_write(str(fp), new_atoms, format=ase_format)
    return len(atoms_data)
