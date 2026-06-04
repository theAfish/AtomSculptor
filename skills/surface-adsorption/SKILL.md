---
name: surface-adsorption
description: "Recipe for placing adsorbates on surfaces: site selection, height, orientation, periodic-image clearance."
when_to_use: Use when placing a molecule on a slab. Combine with `surface-builder` (for the slab) and `supercell-dimension-check` (for sizing).
---

# Surface Adsorption Instructions

## Common Workflow

1. **Create substrate surface**
   - Generate appropriate surface (see surface_creation.md)
   - Determine supercell size based on adsorbate and periodic image requirements
   - Ensure sufficient vacuum (> 10 Å, more for large adsorbates)
   - Optimize layer count for DFT cost (5 layers often sufficient)

2. **Generate adsorbate molecule**
   - Use ASE `molecule()` function for pre-optimized molecular geometries
   - Alternatively, read from database or construct manually
   - Verify molecular geometry is reasonable

3. **Place adsorbate on surface**
   - Choose adsorption site (top, bridge, hollow, or element-specific)
   - Set adsorption height (typical distances: 2.2-2.7 Å for O-metal bonds)
   - Orient molecule appropriately for desired adsorption mode
   - Consider multiple configurations (parallel, perpendicular orientations)

4. **Verify structure integrity**
   - Check all interatomic distances, especially between adsorbate and surface
   - Ensure minimum distance > 2.0 Å to avoid steric clashes
   - Calculate periodic image distances
   - Verify supercell size maintains > 10 Å between periodic images

5. **Save and document**
   - Save structure in appropriate format (.extxyz, POSCAR)
   - Document adsorption site, height, and orientation parameters
   - Record supercell size and layer count

## Key Considerations

### Supercell Sizing for Adsorbates
- **Critical**: Periodic images of adsorbates must be > 10 Å apart
- Calculate required supercell: account for both adsorbate size and surface unit cell
- Progressively test supercell sizes: 2x2, 3x3, 4x4, 5x5, 6x6
- Verify actual periodic image distances after construction

### Supercell Sizing Examples
| Surface | Supercell | Dimensions (Å) | Atoms | Use Case |
|---------|-----------|----------------|-------|----------|
| SiO2 (001) | 4×4×1 | 19.7×19.7 | 1152 | Large adsorbates |
| SiO2 (100) | 4×3×1 | 19.7×16.3 | 864 | Medium adsorbates |
| SiO2 (101) | 3×4×1 | 22.0×19.7 | 864 | Medium adsorbates |
| SiO2 (110) | 2×3×1 | 17.0×16.3 | 432 | Small adsorbates |

### Layer Optimization for DFT
- Initial structures may use 8 layers for surface stability
- For DFT, reduce to 5 layers to minimize computational cost
- 5-layer structures typically reduce atoms by 40-60%
- Verify surface properties maintained with fewer layers

### Adsorption Parameters
- **Adsorption height**: Depends on adsorbate and surface
  - O-metal: typically 2.2-2.7 Å
  - C-metal: typically 2.0-2.5 Å
  - N-metal: typically 2.0-2.5 Å
  - H-metal: typically 1.5-2.0 Å
  - Benzene on oxide: ~3.5 Å (π-stacking distance)
- **Orientation**: Match molecular symmetry to surface site symmetry
- **Site selection**: Consider coordination and reactivity

### Adsorption Site Types
| Site Type | Description | Typical Use |
|-----------|-------------|-------------|
| top_X | Above specific element | Element-specific binding |
| bridge | Between two surface atoms | Bidentate adsorption |
| hollow | Center of surface ring | Maximum coordination |
| fcc/hcp | 3-fold sites on FCC | Common for close-packed |

### Periodic Image Distance Checking
- For each atom in adsorbate, find distance to nearest periodic image
- Minimum distance across all atoms should be > 10 Å
- Use ASE or similar tools to calculate these distances
- Larger molecules require larger supercells

## Common Pitfalls and Fixes

| Pitfall | Symptom | Fix |
|---------|---------|-----|
| Steric clashes | Adsorbate-surface distances < 2.0 Å | Increase adsorption height; reorient molecule |
| Periodic image interactions | Adsorbate images < 10 Å apart | Increase supercell size (e.g., 2x2 → 3x3 or larger) |
| Incorrect adsorption geometry | Unexpected binding mode | Adjust molecule orientation; check adsorption site |
| Too large supercell | Excessive computational cost | Balance accuracy vs. cost; 10 Å is minimum threshold |
| Wrong surface termination | Unexpected surface chemistry | Check termination for polar surfaces |

### Supercell Sizing Guidelines
- **2x2 supercell**: Small adsorbates only
- **3x3 supercell**: May still have < 10 Å for medium adsorbates
- **4x4 supercell**: Often sufficient for medium adsorbates
- **5x5 to 6x6 supercell**: Required for larger molecules (e.g., benzene)
- **Always verify**: Calculate actual distances, don't assume

## Additional Tips

### Benzene Adsorption Example (SiO2)
- Benzene diameter: ~5 Å
- Recommended starting surfaces: (110) and (101) - smaller atom counts
- Site types: top_Si, top_O, bridge, hollow
- Orientations: parallel (expected most stable), perpendicular
- Adsorption height: 3.5 Å
- Recommended: parallel orientation at bridge/hollow sites

### General Workflow for Adsorption Studies
1. Build bulk structure from Materials Project
2. Create multiple surface orientations
3. Optimize layer count for DFT
4. Build supercells with > 10 Å periodic image distance
5. Place adsorbate at multiple sites/orientations
6. Validate all configurations
7. Generate batch of structures for systematic study

### Validation Checklist
- [ ] Minimum adsorbate-surface distance > 2.0 Å
- [ ] Periodic image distances > 10 Å
- [ ] Molecular geometry not severely distorted
- [ ] Correct surface termination
- [ ] Sufficient layers (5+ for DFT)
- [ ] Sufficient vacuum (> 10 Å)
- [ ] Documentation includes supercell size, site, orientation, height
