---
name: molecular-structure-creation
description: Methods for building isolated molecules (ASE database, SMILES via RDKit, organometallics, endohedral cages, NEB pathways).
when_to_use: Use when constructing a single molecule, an organometallic compound, or a molecule-in-cage system.
---

# Molecular Structure Creation Instructions

## Common Workflow

1. **Search for existing structure data**
   - Check Materials Project for crystalline molecular compounds
   - Note: MP mainly stores crystalline materials, not isolated molecules
   - For simple molecules, use ASE's built-in molecule database

2. **Determine construction method**
   - **Option A: ASE molecule database** - for common molecules (H2O, CO2, C60, etc.)
   - **Option B: SMILES strings** - for organic molecules with RDKit
   - **Option C: Manual construction** - for complex organometallics
   - **Option D: Endohedral/encapsulated structures** - for molecules inside cages

3. **Build molecular structure**
   - For ASE database: Use `ase.build.molecule()` function
   - For SMILES: Use RDKit to generate 3D coordinates
   - For manual: Define atomic positions based on literature/experimental data
   - For endohedral: Build cage, then insert guest at center

4. **Validate molecular geometry**
   - Check bond lengths match expected values
   - Verify coordination and geometry
   - For organometallics: check metal-ligand distances
   - For endohedral: verify guest fits within cage (consider vdW radii)

5. **NEB pathway generation (if needed)**
   - Identify insertion/extraction pathways
   - Generate intermediate images between initial and final states
   - Consider ring/cage openings and steric constraints

6. **Geometry optimization (if needed)**
   - Use force fields (MMFF, UFF) for initial optimization
   - Note: EMT calculator does not support all elements (e.g., Fe)
   - For unsupported calculators, use experimental parameters directly

7. **Save and document**
   - Export in XYZ, CIF, or POSCAR formats
   - Document construction method and parameters
   - Record reference if using literature values

## Key Considerations

### Molecular Geometry Parameters
- Use experimental or literature values when available
- Common bond lengths (Å):
  - C-C: 1.43 (aromatic), 1.54 (aliphatic)
  - C-H: 1.08-1.10
  - O-H (water): 0.97
  - H-O-H angle: 104°
  - Metal-C (organometallics): varies by metal
  - Fe-C (ferrocene): ~2.05

### Endohedral Fullerene Construction
- C60 cage radius: ~3.51 Å
- Effective cavity radius: ~1.81 Å (accounting for C vdW radius 1.70 Å)
- Guest vdW radius must be considered for steric fit
- Example: Xe (vdW 2.16 Å) slightly larger than cavity → steric interaction

### Encapsulated Molecules (Molecule-in-Cage)
**Cage Size Calculation:**
1. Determine guest molecule maximum extent (use RDKit 3D conformer)
2. Add clearance: cage radius ≥ molecule extent + 1.5-2.0 Å buffer
3. Example: Caffeine (8.4 Å diameter) requires cage radius ≥ 6.0 Å (diameter 12 Å)

**Cage Construction Methods:**
- **C60 and small fullerenes**: Use `ase.build.molecule('C60')`
- **Larger carbon cages**: Use Fibonacci sphere algorithm for uniform point distribution
- Fibonacci sphere provides isotropic, uniform distribution of cage atoms

**Fibonacci Sphere Algorithm:**
```python
def fibonacci_sphere(radius, n_points):
    points = []
    phi = np.pi * (3.0 - np.sqrt(5.0))  # golden angle
    for i in range(n_points):
        y = 1.0 - (i / (n_points - 1)) * 2.0
        r = np.sqrt(1.0 - y * y)
        theta = phi * i
        x = np.cos(theta) * r
        z = np.sin(theta) * r
        points.append([x * radius, y * radius, z * radius])
    return points
```

**RDKit SMILES to 3D:**
```python
from rdkit import Chem
from rdkit.Chem import AllChem
mol = Chem.MolFromSmiles("CN1C=NC2=C1C(=O)N(C(=O)N2C)C")  # Caffeine
mol = Chem.AddHs(mol)
AllChem.EmbedMolecule(mol)
AllChem.MMFFOptimizeMolecule(mol)
```

### NEB Pathway Generation
- Identify possible insertion/extraction routes
- C60 ring openings: hexagonal (12 rings, 1.41 Å radius), pentagonal (20 rings, 1.22 Å radius)
- Generate intermediate images (typically 7-12 images)
- Consider cage deformation for larger guests

### ASE Molecule Database Examples
- `molecule('H2O')` - Water with O-H=0.97Å, H-O-H=104°
- `molecule('C60')` - Buckminsterfullerene
- `molecule('C6H6')` - Benzene
- Random orientations are normal for liquid simulations
- **Note**: ASE only has C60, not larger fullerenes

### Organometallic Compound Construction
- Build metal-ligand framework manually
- Example: Ferrocene Fe(C5H5)2
  - Staggered conformation common
  - Fe-C distance: 2.05 Å
  - Ring separation: 3.30 Å

## Common Pitfalls and Fixes

| Pitfall | Symptom | Fix |
|---------|---------|-----|
| MP doesn't have molecule | Search returns no results | Build manually using experimental parameters |
| EMT calculator unsupported | Optimization fails for transition metals | Use experimental parameters directly |
| Wrong coordination geometry | Metal center has wrong coordination | Verify against known structures (CSD, literature) |
| Unrealistic bond lengths | Bonds too short or too long | Check experimental values from databases |
| Wrong molecular conformation | Unexpected shape/stereochemistry | Choose appropriate conformer (staggered vs. eclipsed) |
| Guest too large for cage | Severe steric clash | Use larger cage; calculate needed radius from molecule extent |
| Cage too small for molecule | Cannot encapsulate | Fibonacci sphere for custom cage size |

## Additional Tips

### Construction Strategy for Complex Molecules
1. Break down into sub-units (e.g., rings, ligands)
2. Build each sub-unit separately
3. Position sub-units relative to each other
4. Check all bond lengths and angles
5. Verify overall geometry and symmetry

### Encapsulation Workflow
1. Build guest molecule (SMILES → RDKit 3D)
2. Calculate maximum molecular extent
3. Determine cage radius: extent/2 + 1.5-2.0 Å buffer
4. Generate cage using Fibonacci sphere algorithm
5. Place guest at cage center
6. Verify no overlaps (check all guest-cage distances)
7. Optimize if needed

### NEB Pathway Considerations
- Hexagonal ring pathways typically have lower barriers than pentagonal
- High barriers (150-300 kcal/mol) explain why endohedral fullerenes are formed during synthesis, not by post-synthesis insertion
- Save NEB structures as ASE trajectory files for direct use in calculations

### Useful Tools and Databases
- **ASE molecule database**: Common small molecules (H2O, CO2, CH4, C60, etc.)
- **RDKit with SMILES**: Organic molecules with automatic 3D generation
- **Cambridge Structural Database (CSD)**: Experimental crystal structures
- **Literature values**: Always cite sources for experimental parameters

### File Formats for Molecules
- XYZ: Most common for isolated molecules
- .extxyz: Preserves cell/PBC info if needed
- CIF: If structure has crystallographic information
- POSCAR: For VASP calculations

### Validation Checklist
- [ ] All bond lengths within expected ranges
- [ ] Coordination numbers correct
- [ ] Molecular symmetry as expected
- [ ] No steric clashes
- [ ] Correct conformation chosen
- [ ] Documentation includes parameter sources
- [ ] For encapsulated: guest fits with buffer space
