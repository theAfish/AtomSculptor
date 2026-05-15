---
name: interface-building
description: Workflow, lattice-matching strategies, and pitfalls for building interfaces between two crystals/surfaces.
when_to_use: Read BEFORE running the `interface-builder` skill (or any custom interface stacking). Use when constructing an interface, heterostructure, or coherent slab between two materials.
---

# Interface Building Instructions

## Common Workflow

1. **Prepare individual surfaces**
   - Create or obtain both surface structures separately
   - Ensure surface orientations are appropriate for interface
   - Verify both structures have adequate vacuum layers
   - **Critical**: Set PBC=(True, True, False) for surface calculations

2. **Use build_interface tool for lattice matching**
   - Apply ZSL (Zur super Lattice) algorithm for automatic lattice matching
   - Specify both surface structures and their orientations
   - Set appropriate gap distance for interface region

3. **Configure interface parameters**
   - Set gap distance based on intended use:
     - For simple interfaces: typical gap ~2-3 Å
     - For molecular insertion: gap should accommodate molecule plus margins
     - Example: 15 Å gap for 4.5 Å thick ibuprofen molecule
   - Specify maximum strain tolerance for lattice matching
   - For hetero-interfaces, relax tolerances: `--max-length-tol 0.15, --max-angle-tol 0.1`

4. **Verify interface quality**
   - Check for gaps across periodic boundaries
   - Verify lattice strain is acceptable
   - Ensure interface atoms have reasonable coordination
   - **For complex structures with molecular units**: Verify structural integrity (e.g., PS4 tetrahedra)

5. **Validate structural units (if applicable)**
   - Check molecular unit integrity (tetrahedra, dimers, etc.)
   - Use appropriate bond distance cutoffs (e.g., P-S = 2.057 Å, cutoff ~2.2 Å)
   - Ensure proper PBC handling when checking bonds

## Key Considerations

### Lattice Matching Algorithm
- ZSL automatically finds matching supercells
- Example: Fe (100) surface matched with hexagonal SiO2 (001) surface
- Resulted in 8.77 × 17.71 Å interface cell
- For dissimilar structures, lattice matching may struggle - consider manual stacking

### Gap Sizing
- Critical for molecular simulations
- Must accommodate molecule dimensions
- Consider molecule orientation and flexibility

### PBC Consistency
- **Critical**: Set PBC=(True, True, False) for surfaces with vacuum
- Vacuum layer in z-direction should NOT have periodic boundary conditions
- Interface tool handles periodic boundary conditions automatically

### Termination Selection
- Complex structures may have multiple surface terminations
- build_interface tool may not expose termination selection
- **For best results**: Use pymatgen SlabGenerator directly to test all terminations
- Select termination that preserves structural integrity

### LPSCl (Li6PS5Cl) Specific Notes
- Structure: 4 PS4 tetrahedra + 2 S-S dimers per unit cell
- P-S bond distance: 2.057 Å (use cutoff ~2.2 Å for neighbor detection)
- PS4 tetrahedra locations in fractional coordinates:
  - 2 tetrahedra centered at z=0 with S atoms spanning PBC (z=0.116 and z=0.884)
  - 2 tetrahedra centered at z=0.5 with S contained (z=0.384 and z=0.616)
- Safe cut position for (100) surface: frac_x≈0.12 (just after S at 0.116)
- Use termination that preserves 100% PS4 units

## Common Pitfalls and Fixes

| Pitfall | Symptom | Fix |
|---------|---------|-----|
| PBC gaps from manual stacking | Gaps across periodic boundaries | Use build_interface tool with ZSL algorithm |
| Insufficient gap for molecules | Molecule overlaps with substrate | Increase gap parameter |
| Excessive lattice strain | Matched lattices have high strain | Adjust strain tolerance or try different orientations |
| Broken structural units | Tetrahedra/dimers broken at surface | Test all terminations, select one preserving units |
| Wrong PBC settings | Incorrect bond analysis across vacuum | Set PBC=(True, True, False) for surfaces |
| build_interface breaks units | Tool doesn't preserve molecular units | Use SlabGenerator directly to select termination |
| No lattice matches found | Tool returns empty | Relax tolerances: max-length-tol=0.15, max-angle-tol=0.1 |
| Primitive cell issues | Wrong surface terminations | Convert to conventional cell before surface generation |

## Additional Tips

### For Complex Structures with Molecular Units
1. Identify molecular units (tetrahedra, dimers, etc.) and their bond distances
2. Check all surface terminations for unit preservation
3. Calculate safe cut positions based on bond extents
4. Use termination that preserves 100% of structural units

### Surface Generation from Materials Project
- FCC structures often come in primitive cell (60° angles, rhombohedral)
- **Must convert to conventional cell BEFORE surface generation**
- Use `need_conventional=True` flag in structure_tools.py
- Manual cell transformations can easily corrupt atomic positions

### Import Paths
```python
from pymatgen.core.surface import SlabGenerator
```

### Lattice Matching for Dissimilar Structures
- When build_interface struggles with lattice matching between dissimilar structures
- Consider manual stacking approach with proper centering
- Maintain structural integrity of each layer
- Use appropriate vdW gaps (typically 3.5 Å) between layers

### Documentation Requirements
- Record all termination selections with reasoning
- Note any structural units preserved/broken
- Document lattice matching parameters used
- Save intermediate surface structures for verification

### Validation Checklist
- [ ] PBC correctly set (T, T, F) for surfaces
- [ ] Structural units intact (tetrahedra, dimers, etc.)
- [ ] Gap size appropriate for intended use
- [ ] Lattice strain within tolerance
- [ ] No gaps across periodic boundaries
- [ ] Interface atoms have reasonable coordination
