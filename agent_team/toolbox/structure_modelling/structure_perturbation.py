"""Tool for perturbing atomic structures with random or systematic displacements."""
from sandbox.cli_support import build_cli_parser, run_cli
from sandbox.runtime_paths import (
    display_path,
    resolve_output_path,
    sandbox_root,
)

import numpy as np
from pathlib import Path
from typing import Optional
from ase.io import read, write
from ase.data import covalent_radii


def perturb_structure(
    input_file: str,
    displacement_magnitude: float = 0.1,
    perturbation_mode: str = "random",
    atom_indices: Optional[str] = None,
    seed: Optional[int] = None,
    output_name: Optional[str] = None
) -> dict:
    """
    Perturbs atomic positions by applying random or systematic displacements.
    
    Parameters:
    - input_file: Path to the input structure file (supports any ASE format)
    - displacement_magnitude: Maximum displacement in Å (default: 0.1)
    - perturbation_mode: Type of perturbation - "random", "gaussian", or "scaled_random"
                         (default: "random")
                         - "random": uniform random displacement in [-magnitude, +magnitude]
                         - "gaussian": Gaussian distributed displacement with std=magnitude
                         - "scaled_random": random displacement scaled by covalent radii
    - atom_indices: JSON string list of atom indices to perturb (e.g., '[0, 1, 2]'). 
                    If None, perturbs all atoms.
    - seed: Random seed for reproducibility (optional)
    - output_name: Optional output file name. Default is perturbed_{input_name}.extxyz
    
    Returns:
    - Dictionary with perturbed structure file path and displacement statistics
    """
    # Resolve input path
    input_path = Path(input_file)
    if not input_path.is_absolute():
        input_path = sandbox_root() / input_path
    
    if not input_path.exists():
        return {"error": f"Input file not found: {input_file}"}
    
    # Load structure
    try:
        atoms = read(input_path)
    except Exception as e:
        return {"error": f"Failed to read structure: {str(e)}"}
    
    # Parse atom indices
    indices = None
    if atom_indices is not None:
        import json
        try:
            indices = json.loads(atom_indices)
        except json.JSONDecodeError:
            return {"error": f"Invalid atom_indices JSON: {atom_indices}"}
    
    # Set random seed if provided
    if seed is not None:
        np.random.seed(seed)
    
    # Determine which atoms to perturb
    num_atoms = len(atoms)
    if indices is None:
        indices = list(range(num_atoms))
    else:
        # Validate atom indices
        for idx in indices:
            if idx < 0 or idx >= num_atoms:
                return {"error": f"Atom index {idx} is out of bounds for {num_atoms} atoms"}
    
    # Store original positions for statistics
    original_positions = atoms.positions.copy()
    
    # Generate displacements based on mode
    displacements = np.zeros((num_atoms, 3))
    
    if perturbation_mode == "random":
        # Uniform random displacement in [-magnitude, +magnitude] for each component
        displacements[indices] = np.random.uniform(
            -displacement_magnitude, 
            displacement_magnitude, 
            (len(indices), 3)
        )
    
    elif perturbation_mode == "gaussian":
        # Gaussian distributed displacement with std = magnitude
        displacements[indices] = np.random.normal(
            0, 
            displacement_magnitude, 
            (len(indices), 3)
        )
    
    elif perturbation_mode == "scaled_random":
        # Random displacement scaled by covalent radius
        for idx in indices:
            radius = covalent_radii[atoms[idx].number]
            scale = radius if radius > 0 else 1.0
            displacements[idx] = np.random.uniform(
                -displacement_magnitude * scale,
                displacement_magnitude * scale,
                3
            )
    
    else:
        return {"error": f"Unknown perturbation mode: {perturbation_mode}. Use 'random', 'gaussian', or 'scaled_random'"}
    
    # Apply displacements
    atoms.positions += displacements
    
    # Calculate statistics
    displacement_vectors = atoms.positions - original_positions
    displacement_magnitudes = np.linalg.norm(displacement_vectors, axis=1)
    
    # Prepare output
    if output_name:
        output_file_path = resolve_output_path(output_name)
    else:
        input_stem = Path(input_file).stem
        output_file_path = resolve_output_path(f"perturbed_{input_stem}.extxyz")
    
    write(output_file_path, atoms)
    
    # Statistics for perturbed atoms
    perturbed_displacements = displacement_magnitudes[indices]
    
    return {
        "input_file": display_path(input_path),
        "output_file": display_path(output_file_path),
        "perturbation_mode": perturbation_mode,
        "displacement_magnitude_setting": displacement_magnitude,
        "number_of_perturbed_atoms": len(indices),
        "total_atoms": num_atoms,
        "statistics": {
            "mean_displacement_angstrom": round(float(np.mean(perturbed_displacements)), 6),
            "max_displacement_angstrom": round(float(np.max(perturbed_displacements)), 6),
            "min_displacement_angstrom": round(float(np.min(perturbed_displacements)), 6),
            "std_displacement_angstrom": round(float(np.std(perturbed_displacements)), 6),
        }
    }


def batch_perturb(
    input_file: str,
    num_structures: int = 10,
    displacement_magnitude: float = 0.1,
    perturbation_mode: str = "random",
    seed: Optional[int] = None,
    output_prefix: Optional[str] = None
) -> dict:
    """
    Generates multiple perturbed structures from a single input structure.
    
    Useful for creating training datasets or diverse starting configurations.
    
    Parameters:
    - input_file: Path to the input structure file
    - num_structures: Number of perturbed structures to generate (default: 10)
    - displacement_magnitude: Maximum displacement in Å (default: 0.1)
    - perturbation_mode: Type of perturbation - "random", "gaussian", or "scaled_random"
    - seed: Base random seed (each structure uses seed + i, optional)
    - output_prefix: Prefix for output file names. Default is perturbed_{input_name}_batch_
    
    Returns:
    - Dictionary with list of output files and statistics
    """
    # Resolve input path
    input_path = Path(input_file)
    if not input_path.is_absolute():
        input_path = sandbox_root() / input_path
    
    if not input_path.exists():
        return {"error": f"Input file not found: {input_file}"}
    
    # Load structure
    try:
        atoms = read(input_path)
    except Exception as e:
        return {"error": f"Failed to read structure: {str(e)}"}
    
    num_atoms = len(atoms)
    
    # Set output prefix
    if output_prefix is None:
        input_stem = Path(input_file).stem
        output_prefix = f"perturbed_{input_stem}_batch_"
    
    output_files = []
    all_stats = []
    
    for i in range(num_structures):
        # Set seed for this structure
        if seed is not None:
            np.random.seed(seed + i)
        
        # Copy atoms
        perturbed_atoms = atoms.copy()
        original_positions = perturbed_atoms.positions.copy()
        
        # Generate displacements
        if perturbation_mode == "random":
            displacements = np.random.uniform(
                -displacement_magnitude, 
                displacement_magnitude, 
                (num_atoms, 3)
            )
        elif perturbation_mode == "gaussian":
            displacements = np.random.normal(
                0, 
                displacement_magnitude, 
                (num_atoms, 3)
            )
        elif perturbation_mode == "scaled_random":
            displacements = np.zeros((num_atoms, 3))
            for j in range(num_atoms):
                radius = covalent_radii[perturbed_atoms[j].number]
                scale = radius if radius > 0 else 1.0
                displacements[j] = np.random.uniform(
                    -displacement_magnitude * scale,
                    displacement_magnitude * scale,
                    3
                )
        else:
            return {"error": f"Unknown perturbation mode: {perturbation_mode}"}
        
        # Apply displacements
        perturbed_atoms.positions += displacements
        
        # Calculate statistics
        disp_magnitudes = np.linalg.norm(perturbed_atoms.positions - original_positions, axis=1)
        
        # Save structure
        output_file = resolve_output_path(f"{output_prefix}{i:04d}.extxyz")
        write(output_file, perturbed_atoms)
        
        output_files.append(display_path(output_file))
        all_stats.append({
            "structure_index": i,
            "mean_displacement": round(float(np.mean(disp_magnitudes)), 6),
            "max_displacement": round(float(np.max(disp_magnitudes)), 6),
        })
    
    return {
        "input_file": display_path(input_path),
        "num_structures_generated": num_structures,
        "perturbation_mode": perturbation_mode,
        "displacement_magnitude": displacement_magnitude,
        "output_files": output_files,
        "statistics_per_structure": all_stats,
    }


TOOL_FUNCTION_NAMES = ['perturb_structure', 'batch_perturb']


def _tool_functions():
    return {name: globals()[name] for name in TOOL_FUNCTION_NAMES}


def _build_cli_parser():
    return build_cli_parser(
        prog="structure_perturbation.py",
        description_lines=[
            "Tool for perturbing atomic structures with random or systematic displacements.",
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
