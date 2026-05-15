---
name: supercell-dimension-check
description: "How to size supercells correctly: primitive vs. conventional cell, periodic-image clearance for adsorbates/molecules."
when_to_use: Read BEFORE building a supercell that must host a molecule, defect, or adsorbate. Pairs with the `supercell-builder` skill.
---

# Supercell Creation and Dimension Check Instructions

## Common Workflow

### Part 1: Supercell Creation

1. **Obtain base structure**
   - Download from Materials Project (preferred for real materials)
   - Or create manually with known lattice parameters
   - Note: Distinguish between primitive and conventional cells

2. **Determine cell type and expansion needs**
   - Primitive cell: Smallest possible unit cell (e.g., BCC = 1 atom)
   - Conventional cell: Standard unit cell (e.g., BCC = 2 atoms)
   - Choose based on intended application

3. **Build supercell**
   - Use structure_tools.py build_supercell command
   - Specify expansion factors (e.g., 4×4×4)
   - Consider final atom count and computational cost

4. **Validate supercell**
   - Check atom count matches expectation
   - Verify lattice parameters scaled correctly
   - Ensure structure integrity maintained

### Part 2: Dimension Checking for Molecular Systems

5. **Measure molecule dimensions**
   - Calculate maximum extent in all directions
   - For flexible molecules, use optimized geometry
   - Example: Ibuprofen dimensions ~11.43 × 4.5 Å

6. **Check supercell lateral dimensions**
   - Compare with supercell a, b parameters
   - Calculate available margin: (cell_dimension - molecule_dimension) / 2

7. **Verify minimum margin requirements**
   - For molecular simulations: require 10-15 Å minimum margin
   - This prevents periodic image interactions
   - Example: For 11.43 Å molecule, need cell > 21 Å

8. **Expand supercell if necessary**
   - If margins insufficient, build larger supercell
   - May need asymmetric expansion (e.g., 4×2)
   - Re-verify margins after expansion

## Key Considerations

### Primitive vs. Conventional Cells

| Cell Type | BCC Example | FCC Example | Use Case |
|-----------|-------------|-------------|----------|
| Primitive | 1 atom | 1 atom | Smallest representation |
| Conventional | 2 atoms | 4 atoms | Standard visualization, surface creation |

- Use `crystal_builder.py --cubic true` for conventional cells
- Primitive cells from Materials Project may need conversion

### Supercell Expansion Strategy
- Balance atom count vs. computational cost
- Consider defect concentration needs (e.g., 25% vacancy needs ≥16 atoms)
- For molecules: must exceed dimension requirements
- Expansion factors multiply atom count (e.g., 4×4×4 conventional BCC = 128 atoms)

### Common Supercell Sizes
- BCC Fe: 4×4×4 primitive = 64 atoms; 4×4×4 conventional = 128 atoms
- Lattice parameter scaling: a_4×4×4 = 4 × a_primitive

### Periodic Image Requirements for Molecules
- **Critical**: Molecules must have 10-15 Å clearance from periodic images
- This means 10-15 Å margin from molecule edge to cell boundary
- Not just molecule center to cell center
- Total cell dimension = molecule size + 2 × margin

## Common Pitfalls and Fixes

### Supercell Creation

1. **Using primitive cell when conventional needed**
   - Symptom: Unexpected atom count (e.g., 1 atom for BCC)
   - Cause: Downloaded primitive cell from Materials Project
   - Fix: Use crystal_builder with --cubic true for conventional cell

2. **File format incompatibility**
   - Symptom: Tool doesn't recognize file format
   - Cause: Using extxyz when tool expects CIF
   - Fix: Use ASE for format conversion between steps

3. **Incorrect expansion factor**
   - Symptom: Final atom count doesn't match expectation
   - Cause: Wrong multiplication (e.g., forgot cell has multiple atoms)
   - Fix: Calculate expected atoms: n_atoms = primitive_atoms × nx × ny × nz

### Dimension Checking

4. **Molecule exceeds cell dimension**
   - Symptom: Molecule dimension > cell dimension
   - Cause: Supercell too small before molecule insertion
   - Fix: Build supercell expansion first
   - Example: 8.77 Å cell too small for 11.43 Å ibuprofen

5. **Insufficient margin for periodic images**
   - Symptom: Margins < 10 Å
   - Cause: Cell barely larger than molecule
   - Fix: Expand supercell to provide 10-15 Å buffer

6. **Not checking all dimensions**
   - Symptom: One direction has insufficient margin
   - Cause: Only checked largest dimension
   - Fix: Verify all lateral dimensions (x, y) have adequate margin

## Additional Tips

### Supercell Creation Workflow
1. Download structure from MP or create manually
2. Convert to conventional cell if needed (crystal_builder --cubic true)
3. Determine expansion factors based on needs:
   - Defect concentration requirements
   - Molecular dimension requirements
   - Computational budget
4. Build supercell (structure_tools.py build_supercell)
5. Verify final structure and atom count

### Dimension Calculation Example
- Molecule: 11.43 × 4.5 Å (ibuprofen)
- Minimum cell: 11.43 + 2×10 = 31.43 Å (x), 4.5 + 2×10 = 24.5 Å (y)
- Actual 4×2 supercell: 35.06 × 36.50 Å
- Margins: x = (35.06-11.43)/2 = 11.8 Å ✓, y = (36.50-4.5)/2 = 16.0 Å ✓

### Format Conversion
- Use ASE for conversion: `ase build --change-format <format> input output`
- CIF preferred for many tools
- XYZ for quick inspection
- POSCAR for VASP

### Validation Checklist
- [ ] Correct atom count for expansion factor
- [ ] Lattice parameters scaled appropriately
- [ ] Structure integrity maintained (bond lengths, coordination)
- [ ] For molecules: all dimensions have 10-15 Å margins
- [ ] PBC set appropriately for application
