"""Build carbon nanotubes (CNTs) with various chiralities"""
from sandbox.cli_support import build_cli_parser, run_cli
from sandbox.runtime_paths import (
    display_path,
    resolve_output_path,
    sandbox_output_dir,
    sandbox_root,
)


"""Build carbon nanotubes (CNTs) with various chiralities.

This is a general-purpose tool for building CNT structures.
Use cylinder_filler.py to fill the CNT with atoms or molecules.
"""

import numpy as np
from ase import Atoms
from ase.build import nanotube
from ase.io import write


def build_nanotube(
    n: int,
    m: int,
    length: int,
    bond: float = 1.42,
    vacuum: float = 20.0,
    pbc_z: bool = True,
    output_file: str = "nanotube.extxyz"
) -> dict:
    """
    Build a carbon nanotube with specified chirality.
    
    Args:
        n: Chiral index n (determines tube structure)
        m: Chiral index m (determines tube structure)
        length: Length of CNT in unit cells
        bond: C-C bond length in Å (default: 1.42)
        vacuum: Vacuum padding in xy plane in Å (default: 20.0)
        pbc_z: Whether to set periodic boundary in z (default: True)
        output_file: Output file name
    
    Returns:
        Dictionary with CNT parameters and geometry info
    """
    # Build CNT using ASE
    cnt = nanotube(n, m, length=length, bond=bond)
    
    # Get CNT dimensions
    positions = cnt.get_positions()
    x_center = (positions[:, 0].max() + positions[:, 0].min()) / 2
    y_center = (positions[:, 1].max() + positions[:, 1].min()) / 2
    z_min = positions[:, 2].min()
    z_max = positions[:, 2].max()
    tube_length = z_max - z_min
    
    # Calculate radii
    r_values = np.sqrt((positions[:, 0] - x_center)**2 + (positions[:, 1] - y_center)**2)
    outer_radius = r_values.mean()
    inner_radius = outer_radius - 1.7  # Approximate wall thickness
    
    # Set cell
    cell_x = 2 * (outer_radius + vacuum)
    cell_y = 2 * (outer_radius + vacuum)
    cell_z = tube_length
    
    cnt.set_cell([cell_x, cell_y, cell_z])
    cnt.center()
    cnt.set_pbc([False, False, pbc_z])
    
    # Write output
    write(output_file, cnt)
    
    # Determine CNT type
    if n == m:
        cnt_type = "armchair"
    elif m == 0:
        cnt_type = "zigzag"
    else:
        cnt_type = "chiral"
    
    return {
        "output_file": output_file,
        "chirality": f"({n},{m})",
        "cnt_type": cnt_type,
        "length_cells": length,
        "outer_diameter_nm": round(outer_radius * 2 / 10, 3),
        "outer_radius_angstrom": round(outer_radius, 2),
        "inner_radius_angstrom": round(inner_radius, 2),
        "tube_length_angstrom": round(tube_length, 2),
        "cell_dimensions_angstrom": [round(cell_x, 2), round(cell_y, 2), round(cell_z, 2)],
        "n_atoms": len(cnt),
        "center_xy": [round(x_center, 2), round(y_center, 2)],
        "z_range": [round(z_min, 2), round(z_max, 2)]
    }


TOOL_FUNCTION_NAMES = ["build_nanotube"]


TOOL_FUNCTION_NAMES = ['build_nanotube']


def _tool_functions():
    return {name: globals()[name] for name in TOOL_FUNCTION_NAMES}


def _build_cli_parser():
    return build_cli_parser(
        prog="nanotube_builder.py",
        description_lines=[
            "Build carbon nanotubes (CNTs) with various chiralities",
            f"Working directory: {sandbox_root()}",
            "",
        ],
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
