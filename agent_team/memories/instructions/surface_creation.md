## Common Workflow
 
 1. **Identify crystal structure and surface orientation**
  - Determine bulk crystal structure (e.g., bcc, fcc, hcp, perovskite)
  - Choose surface Miller indices (e.g., (100), (111), (001))
  - Obtain lattice constant for the material
 
2. **Create bulk structure**
  - **For standard crystal structures**: Use `bulk()` function with crystalstructure parameter (bcc, fcc, hcp, diamond, etc.)
  - **For unsupported structures** (e.g., perovskites): Build manually using `Atoms()` with `scaled_positions` (see "Unsupported Crystal Structures" below)

3. **Create surface using appropriate tool**
  - Use surface creation tool with bulk parameters
  - Specify number of layers (typically 4-8 layers for adequate thickness)
  - Set vacuum layer (typically 10-15 Å for surface studies)
 
4. **Validate surface structure**
  - Check that surface atoms have proper coordination
  - Verify cell dimensions and periodicity
  - Ensure surface is not interacting with its periodic images

## Key Parameters

 - **Lattice constants**: Use experimentally verified values when possible
   - Example: bcc Fe lattice constant = 2.87 Å
   - Example: SrTiO3 perovskite lattice constant ≈ 3.905 Å
 - **Layer count**: Balance between computational cost and surface model accuracy
   - Too few layers: bulk-like behavior not captured
   - Too many layers: unnecessary computational expense
 - **Vacuum thickness**: Must be sufficient to prevent periodic image interactions (typically >10 Å)
 - **Surface termination**: Some materials have multiple possible terminations; choose based on stability
   - Example: SrTiO3 (001) surface typically has TiO2 termination

## Unsupported Crystal Structures

Some crystal structures are not supported by ASE's `bulk()` function (e.g., perovskites). Build these manually:

### Perovskite Structure (ABO3)
- Space group: Pm-3m (221), cubic
- Atomic positions in fractional coordinates:
  - A atom (e.g., Sr): (0, 0, 0) - corners
  - B atom (e.g., Ti): (0.5, 0.5, 0.5) - body center
  - O atoms: (0.5, 0.5, 0), (0.5, 0, 0.5), (0, 0.5, 0.5) - face centers
- Build using `Atoms()` with `scaled_positions` and `cell` parameters

### Manual Structure Building Example (SrTiO3)
```python
from ase import Atoms
lattice = 3.905  # Å
cell = [[lattice, 0, 0], [0, lattice, 0], [0, 0, lattice]]
atoms = Atoms(
    symbols='SrTiO3',
    scaled_positions=[
        [0, 0, 0],        # Sr at corner
        [0.5, 0.5, 0.5],  # Ti at body center
        [0.5, 0.5, 0],    # O at face centers
        [0.5, 0, 0.5],
        [0, 0.5, 0.5]
    ],
    cell=cell,
    pbc=True
)
```

## Common Pitfalls and Fixes

1. **PBC gaps across boundaries**: When combining with other surfaces or substrates
   - Fix: Ensure lattice matching before combining surfaces (see interface_building.md)

2. **Incorrect surface orientation**: Miller indices don't match desired surface
   - Fix: Double-check surface normal vector and Miller index convention

3. **Unsupported crystalstructure parameter**: ASE bulk() doesn't recognize structure type
   - Symptom: Error when using crystalstructure='perovskite' or similar
   - Fix: Build structure manually using Atoms() with scaled_positions (see example above)

## Additional Tips

 - For bcc structures, (100) surfaces are often stable and commonly used
 - Surface reconstruction may occur in real systems but typically requires relaxation calculations
 - When creating surfaces for interface studies, consider the matching requirements with the second material
 - For surface defect studies, see `surface_defect_creation.md`
 - Always verify the crystal structure by checking atomic positions and coordination before creating surfaces
