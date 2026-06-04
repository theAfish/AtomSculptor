# Surface Creation — Validation Checklist

Load via `read_skill("surface-creation", "references/checklist.md")`.

## Before generating
- [ ] Bulk source confirmed (MP ID recorded, or hand-built parameters noted).
- [ ] Cell converted to conventional if applicable (FCC primitives flagged).

## After generating
- [ ] Correct Miller indices and surface orientation.
- [ ] Proper surface termination (all structural units intact).
- [ ] ≥ 5 layers (for DFT).
- [ ] ≥ 10 Å vacuum.
- [ ] PBC = (True, True, False).
- [ ] Adsorbate periodic images > 10 Å apart in supercell.

## Output
- [ ] Saved as `.extxyz` (preferred). Optionally also CIF / POSCAR.
- [ ] Documented: MP ID, Miller indices, layers, vacuum, supercell expansion.

## Format notes
- `.extxyz` preserves PBC and per-atom info — preferred for surfaces.
- CIF for visualization; POSCAR for VASP.
- ASE handles conversions: `ase build --change-format <format>`.

## Reconstruction & relaxation
- Real surfaces may reconstruct — plan a relaxation step if accuracy matters.
- Multiple stable terminations may exist for clean surfaces — check literature.
