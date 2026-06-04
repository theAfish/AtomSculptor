---
name: nanostructure-creation
description: Workflows for nanoparticles, carbon nanotubes, nanoshells, confined/filled systems, and atomic text patterns.
when_to_use: Use when building a nanoparticle, CNT, nanoshell, filled-tube system, or other finite nanostructure. Pairs with the `nanotube-builder` skill.
---

# Nanostructure Creation Instructions

## Common Workflow

1. **Determine nanostructure type and geometry**
   - Nanoparticle: faceted shapes (icosahedron, decahedron, octahedron, etc.)
   - Nanotube: specify chirality (n,m) for CNTs
   - Nanoshell: hollow or solid spherical shells
   - Confined systems: structures filled with molecules/elements
   - Atomic text/patterns: custom arrangements spelling text

2. **Select construction method based on structure type**

   **For metallic nanoparticles:**
   - Use ASE's cluster tools or manual construction
   - Specify number of shells or total atoms
   - Common shapes: icosahedron, cuboctahedron, decahedron
   
   **For carbon nanotubes (CNTs):**
   - Use ASE's `nanotube()` function with chirality (n,m)
   - Diameter formula: d = 0.783 × √(n² + nm + m²) Å (or d = a/π × √(n² + nm + m²), a = 2.46 Å)
   - Armchair (n,n): metallic; Zigzag (n,0): semiconducting
   - Example: (15,15) → ~2.03 nm diameter; (7,7) → ~0.95 nm diameter (~1 nm)

   **For crystalline nano-shells:**
   - Start from real crystal structure (e.g., from Materials Project)
   - Build large supercell to provide sufficient material
   - Cut desired geometry maintaining crystalline order

   **For filled nanotubes/confined systems:**
   - Build CNT first, then fill interior
   - Use cylinder_filler for elements (Ga, Cu, Au, etc.)
   - Use molecule_filler for molecules (H2O, O2, CO2, etc.)

   **For atomic text/patterns:**
   - Use dot-matrix approach with 5×7 character grid
   - Calculate positions for each character
   - Support customizable spacing and atom types

3. **Build structure**
   - For nanoparticles: Define shape, element, and size
   - For CNTs: Define chirality (n,m), length, bond length
   - For filled systems: Use spatial hashing for O(N) overlap detection
   - Ensure sufficient atoms for meaningful statistics

4. **Handle periodic boundary conditions (PBC)**
   - CNTs: Set PBC=[False, False, True] for z-direction only
   - Cell dimensions must accommodate all atoms plus margin
   - Use z-margin (typically 3 Å) to prevent PBC overlaps

5. **Validate nanostructure**
   - Check atomic coordination (especially for surface atoms)
   - Verify bond lengths are realistic
   - For shells: ensure proper thickness and geometry
   - For filled systems: verify minimum interatomic distances
   - **Critical**: Check periodic image distances using minimum image convention

6. **Apply perturbations (if needed)**
   - Gaussian perturbation for thermal displacement simulation
   - Typical magnitude: 0.15 Å for mean displacement ~0.23 Å
   - Useful for testing structural stability or initial conditions

7. **Save and document**
   - Export in .extxyz format (preserves cell/PBC info)
   - Document construction parameters
   - Record Materials Project ID if applicable

## Key Considerations

### CNT Chirality and Dimensions
| Chirality | Type | Diameter Formula | Example |
|-----------|------|------------------|---------|
| (n,n) armchair | Metallic | d = 0.783 × n Å | (7,7) → ~0.95 nm (~1 nm) |
| (n,0) zigzag | Semiconducting | d = 0.783 × n Å | (13,0) → ~1.02 nm |
| (n,m) chiral | Varies | d = 0.783 × √(n²+nm+m²) Å | Depends on n,m |

- Inner radius for filling: R_inner = R_CNT - 2.0 Å (C wall thickness + vdW buffer)
- C-C bond length: 1.42 Å
- **Important**: ASE nanotube() creates finite tubes NOT PBC-consistent - C atoms at z=0 don't match z=length

### Quick Reference for CNT Diameter
- (7,7) armchair: outer diameter ~0.95 nm → good for ~1 nm CNT
- (10,10) armchair: outer diameter ~1.36 nm
- (15,15) armchair: outer diameter ~2.03 nm
- (22,22) armchair: outer diameter ~3.0 nm

### Filling Confined Systems

**Element filling (Ga, Cu, Au, etc.):**
- Use bulk liquid density for reference (Ga: 0.0527 atoms/Å³)
- Minimum interatomic distance: element-specific (Ga-Ga: ~2.7 Å)
- Achievable density typically 75-85% of bulk due to confinement

**Molecule filling (H2O, etc.):**
- Water density: 0.0334 molecules/Å³ (≈1 g/mL)
- NaCl concentration: 1 mol/L = 6.022e23 / 1e27 molecules per Å³
- Minimum molecule distance: 2.0-2.8 Å to prevent overlaps
- Use collision detection with all-atom distances (O-O, H-H, O-C, H-C)

**Spatial hashing for efficiency:**
- Use spatial grid for O(N) neighbor checking instead of O(N²)
- Essential for large structures (>1000 atoms)

### PBC-Safe Placement
- **Critical**: Cell size must exceed actual atom span
- Add z-margin (typically 3 Å) at boundaries
- Constrain z placement: z = z_margin + random() × (tube_length - 2×z_margin)
- Set cell_z = tube_length + 2×z_margin for proper PBC buffer
- Use minimum image convention: `dz = dz - cell_z × round(dz/cell_z)`

### Nanoparticle Shapes and Sizes
- **Icosahedron**: Common for Pt, Au nanoparticles due to low surface energy
- Magic numbers for closed shells: 13, 55, 147, 309, 561, 923, 1415, ...

### Nanoshell Construction from Crystalline Materials
- **Critical**: Use real crystal structure, not random placement
- Workflow: MP search → supercell → cut spherical shell
- Example: SiO2 alpha-quartz (mp-6930) → 7×7×7 supercell → shell

### Atomic Text/Pattern Construction
- Dot-matrix approach: 5×7 grid per character
- Typical spacing: 2.5 Å between atomic positions
- Character width with 1 Å spacing: ~5 Å
- Total width calculation: n_chars × 5 Å + (n_chars-1) × spacing Å
- Use toolbox/structure_modelling/atomic_text.py for generation

## Common Pitfalls and Fixes

| Pitfall | Symptom | Fix |
|---------|---------|-----|
| PBC overlap | Atoms overlap across z-boundary | Add z-margin (3 Å), check minimum image distances |
| Wrong file format | PBC/cell info lost | Use .extxyz format, not plain XYZ |
| Inefficient overlap check | Slow for large structures | Use spatial hashing for O(N) performance |
| CNT not PBC-consistent | C atoms at z=0 ≠ z=length | Place solvent away from boundaries, or build PBC-consistent CNT manually |
| Overpacking in confined space | Too many atoms, overlaps | Reduce target density to 75-85% of bulk |
| Minimum image formula wrong | Wrong PBC distances | Use `dz - cell_z × round(dz/cell_z)`, NOT `min(abs(dz), cell_z-abs(dz))` |

## Additional Tips

### Tool Architecture (Composable Design)
| Tool | Purpose | Key Parameters |
|------|---------|----------------|
| nanotube_builder | Build any CNT | n, m, length, bond |
| cylinder_filler | Fill with any element | element, density, min distances |
| molecule_filler | Fill with any molecule | molecule_name, density, min distances |
| atomic_text | Generate text patterns | text, spacing, atom_type |

**Workflow Pattern:**
1. Build CNT with nanotube_builder
2. Fill with desired content using cylinder_filler (elements) or molecule_filler (molecules)
3. Apply perturbations if needed

### ASE Calculator Limitations
- EMT: For metals only, not suitable for water/organics
- Simple LJ: Doesn't handle multi-element mixing properly
- For production MD with water: Use GROMACS, LAMMPS, OpenMM with TIP3P/SPC models
- Alternative: Apply thermal displacements (~0.15 Å RMS) to simulate equilibrium while preserving geometry

### File Format Recommendation
- **Use .extxyz format** - preserves cell and PBC information
- Standard XYZ does NOT preserve cell/PBC info
- For PBC-aware structures, always validate with minimum image distance check

### Validation Checklist
- [ ] Bond lengths match expected values
- [ ] Coordination numbers reasonable for surface atoms
- [ ] No overlapping atoms or unrealistic geometries
- [ ] Periodic image distances > minimum threshold (use minimum image convention)
- [ ] PBC correctly set (typically [F,F,T] for CNTs)
- [ ] Cell dimensions accommodate all atoms with margin
- [ ] Perturbation magnitude appropriate (if applied)
