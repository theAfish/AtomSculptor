---
name: sandwich-structure-creation
description: Recipe for sandwich and multi-layer vdW heterostructures (e.g. metal | molecule | oxide, graphene/MoS2/GaAs).
when_to_use: Use when stacking three or more layers, inserting a molecule between two substrates, or building vdW heterostructures.
---

# Sandwich Structure Creation Instructions

## Common Workflow

1. **Design sandwich architecture**
   - Identify substrate materials (top and bottom layers)
   - Identify molecule/layer to be sandwiched in the middle
   - Example: Fe | Ibuprofen | SiO2 sandwich structure

2. **Create individual components**
   - Generate or obtain bottom substrate surface (e.g., Fe (100))
   - Generate or obtain top substrate surface (e.g., hexagonal SiO2 (001))
   - Create molecule using SMILES or other method with geometry optimization

3. **Build lattice-matched interface**
   - Use build_interface tool with ZSL algorithm
   - Set gap parameter to accommodate molecule plus margins
   - Example: 15 Å gap for 4.5 Å thick molecule

4. **Check supercell dimensions**
   - Verify molecule fits within lateral cell dimensions
   - Ensure 10-15 Å margin in all lateral directions
   - Expand supercell if necessary

5. **Insert molecule into gap**
   - Place molecule at center of gap region
   - Verify no overlaps with substrate atoms
   - Check molecular orientation is appropriate

## Multi-Layer vdW Heterostructure Workflow

For creating multi-layer van der Waals heterostructures (e.g., graphene/MoS2/GaAs):

1. **Identify layer types**
   - 2D materials: graphene, MoS2, WS2, h-BN, etc.
   - 3D materials: thin surface slabs (not bulk)
   - Determine correct layer ordering

2. **Build 2D material layers correctly**
   - **Graphene**: Use `ase.build.graphene()` function for perfect hexagonal rings
     - C-C bond length: 1.42 Å
     - Creates proper 2D layer with correct PBC
   - **MoS2 and TMDs**: Use `ase.build.mx2()` function for 2H phase
     - Creates proper S-Mo-S trilayer structure
     - S-Mo distance: 2.42 Å
   - **Do NOT use build_surface on bulk TMDs** - may cut through multiple layers

3. **Build 3D material layers**
   - Use `ase.build.surface()` for thin surface slabs
   - Specify number of atomic layers (e.g., 4 layers for GaAs)
   - Example: GaAs (001) with 4 layers gives ~10.8 Å thickness

4. **Stack layers with proper vdW gaps**
   - Typical vdW gap: 3.5 Å between layers
   - Manually stack layers in correct order
   - Center each layer in xy-plane
   - Adjust z-positions for proper gaps

5. **Validate heterostructure**
   - Check minimum interatomic distances (> 1.4 Å)
   - Verify no broken structural motifs
   - Confirm correct layer ordering

### ASE Functions for 2D Materials
```python
from ase.build import graphene, mx2, surface

# Graphene - perfect hexagonal rings
gr = graphene(vacuum=10.0)  # Add vacuum for 2D

# MoS2 2H phase - proper S-Mo-S trilayer
mos2 = mx2('MoS2', vacuum=10.0)

# Thin surface slab
gaas = surface('GaAs', (0,0,1), 4, vacuum=10.0)
```

## Key Considerations

### Gap Sizing
- Gap must accommodate molecule with room for flexibility
- Measure optimized molecule dimensions
- Add margins for molecule movement during simulation
- Example: 15 Å gap for 4.5 Å thick ibuprofen provides ~10 Å total margin

### vdW Gap Distances
- Between 2D materials: 3.5 Å typical
- Between metal and 2D material: 2.5-3.0 Å
- Between oxide and 2D material: 3.0-3.5 Å

### Lattice Matching
- Critical for creating defect-free interface
- Use ZSL algorithm in build_interface tool
- Different crystal structures can be matched
- Some lattice strain may be unavoidable
- For dissimilar structures, manual stacking may be necessary

### Molecule Generation
- Use appropriate method
- SMILES strings can generate initial 3D structure
- Geometry optimization (e.g., MMFF with RDKit) provides realistic dimensions
- Final structure: 391 atoms, ~17×16 Å lateral dimensions

### 2D Material Structural Integrity
- **Critical**: Use specialized ASE functions for 2D materials
- build_surface on bulk TMDs may cut through layers incorrectly
- build_interface may not preserve 2D material structure properly
- Always verify hexagonal rings in graphene, trilayer structure in TMDs

## Common Pitfalls and Fixes

| Pitfall | Symptom | Fix |
|---------|---------|-----|
| PBC gaps from manual stacking | Gaps across periodic boundaries | Use build_interface tool for lattice matching |
| Cell too small for molecule | Molecule dimension exceeds cell dimension | Build supercell expansion before molecule insertion |
| Molecule overlaps with substrate | Atom positions overlap after insertion | Increase gap parameter and re-insert molecule |
| Broken graphene rings | Non-hexagonal ring structure | Use ase.build.graphene() instead of build_interface |
| Wrong MoS2 structure | Missing S-Mo-S trilayer | Use ase.build.mx2() for 2H phase |
| Bulk instead of thin slab | Excessive thickness for 3D layer | Use surface() with few layers, not bulk structure |
| Wrong layer ordering | Layers in incorrect sequence | Flip interface structure or manually stack |
| Close contacts | Atoms too close (< 1.5 Å) | Use ASE supercell with proper wrapping |

## Additional Tips

### Manual Stacking Approach
When build_interface struggles with dissimilar structures:
1. Create each layer with correct PBC from the start
2. Center each layer in xy-plane
3. Position in z-direction with proper vdW gaps
4. This maintains structural integrity while achieving correct ordering

### Lattice Matching Challenges
- build_interface tool uses ZSL algorithm
- May struggle with very dissimilar structures (e.g., 3D surface slab vs 2D material)
- Manual stacking avoids forced lattice matching that breaks structure

### Validation for Heterostructures
- Minimum interatomic distance check: should be > 1.4 Å
- Verify graphene hexagonal rings intact
- Verify MoS2 S-Mo-S trilayer structure correct
- Check vdW gaps are as specified

### Layer Order Verification
- Verify correct bottom-to-top ordering
- May need to flip interface structure from build_interface
- Example: GaAs (bottom) → MoS2 (middle) → Graphene (top)

### Supercell Sizing for Heterostructures
- Use large enough cell to avoid artifacts (e.g., 20×20 Å xy-dimensions)
- Total z-dimension = sum of layer thicknesses + vdW gaps
- Add sufficient vacuum for 2D materials

### Documentation Requirements
- Document all Materials Project IDs for reproducibility
- Record layer ordering, vdW gaps, cell dimensions
- Note construction method (build_interface vs manual stacking)
- Verify molecule is properly centered in the gap region
- Check final atom count matches expectation (substrate + molecule atoms)
- Consider molecule orientation relative to substrate surfaces
- For multiple molecules, ensure sufficient spacing between them
