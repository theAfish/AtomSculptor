---
name: surface-defect-creation
description: Workflow for vacancies, substitutions, doping, interstitials, antisites, and complex defects in bulk/surface/CNT structures.
when_to_use: Use when introducing defects (e.g. CNT N-doping, vacancies, dopants) into an existing structure.
---

# Defect Creation Instructions

## Common Workflow

1. **Prepare base structure**
   - Start with pristine crystal, surface, or nanostructure
   - For surfaces, create using surface creation workflow (see surface_creation.md)
   - For nanostructures (CNTs), build using nanotube tools first
   - Ensure structure has sufficient size for defect concentration desired
   - Convert to CIF format if using defect_builder (extxyz not directly supported)

2. **Select defect type and parameters**
   - **Vacancy**: Remove atom(s) from lattice sites
   - **Substitution**: Replace atom(s) with different element(s)
   - **Doping**: Replace specific element with dopant (e.g., N-doping in CNT)
   - **Interstitial**: Insert atom(s) at non-lattice sites
   - **Antisite**: Swap positions of two different atom types
   - **Defect complex**: Multiple defects in combination

3. **Choose targeting method**
   - **Element-specific**: Target all atoms of a specific element
   - **Coordinate-based**: Target specific positions (for interstitials)
   - **Random**: Statistical distribution across structure
   - **Manual**: Specify exact atom indices

4. **Execute defect creation**
   - Use defect_builder tool with appropriate parameters
   - For reproducibility, set random seed (--seed parameter)
   - Validate concentration matches expectation
   - For nanostructures: specify percentage (e.g., 5% N-doping, 2% vacancies)

5. **Validate defective structure**
   - Check correct number of atoms removed/added
   - Verify atomic distances (no overlapping atoms)
   - Check coordination of atoms near defect sites
   - Ensure minimum distances between defects for multiple defects
   - For CNTs: verify structural integrity maintained

6. **Save and document**
   - Use .extxyz format for ASE compatibility
   - Document defect type, concentration, and seed
   - For CNTs: note chirality and doping percentage

## Key Considerations

### Defect Concentration and Supercell Size
- Need sufficient atoms to achieve desired concentration
- Example: 25% vacancy requires at least 16 atoms to get exactly 4 vacancies
- Use supercell expansion to increase atom count if needed
- Balance between defect concentration and computational cost

### CNT Doping and Vacancies
- **N-doping**: Substitutes C with N, adds extra electrons (n-type doping)
- **Vacancies**: Creates under-coordinated sites
- **Typical concentrations**: 1-5% for realistic doping levels
- **Example**: (22,22) armchair CNT with 5% N-doping, 2% vacancies

### Defect Types and Parameters

| Defect Type | Required Parameters | Optional Parameters |
|-------------|---------------------|---------------------|
| Vacancy | Element to remove | Concentration, seed |
| Substitution | Host element, substitution element | Concentration, seed |
| Interstitial | Element to insert, position | Position type (Voronoi), distance constraints |
| Antisite | Two elements to swap | Concentration, seed |
| Complex | JSON file with defect specification | - |

### Interstitial Site Selection
- **Voronoi method**: Automatically finds interstitial sites using Voronoi analysis
- **Coordinate-based**: Specify fractional or Cartesian coordinates manually
- **Distance constraints**:
  - Minimum distance to existing atoms (default 2.0 Å)
  - Minimum distance between interstitials (default 2.5 Å)
- **Important**: Without constraints, interstitials may cluster unrealistically

### File Format Compatibility
- defect_builder.py works with CIF format
- Use ASE to convert between formats (XYZ, POSCAR, CIF)
- For CNTs: use .extxyz format to preserve structure
- Example: `ase build --change-format cif input.xyz output.cif`

## Common Pitfalls and Fixes

| Pitfall | Symptom | Fix |
|---------|---------|-----|
| Interstitial clustering | Interstitials < 2 Å apart | Use --min-dist-to-atoms and --min-dist-between parameters |
| Wrong file format | defect_builder fails | Convert to CIF before running defect_builder |
| Insufficient atoms | Cannot achieve exact defect number | Build supercell first, then introduce defects |
| Overlapping atoms | Atoms too close after insertion | Increase --min-dist-to-atoms parameter |
| Non-reproducible results | Different distributions each run | Use --seed parameter for reproducibility |
| CIF PBC artifacts | Short inter-atomic distances | Use .extxyz format and process directly with ASE |
| 4-fold coordinated PBC atoms | Atoms at PBC boundaries | These are artifacts from periodic images - expected |

### CNT-Specific Considerations
- Use .extxyz format for CNT structures (CIF can cause PBC artifacts)
- ASE nanotube() creates finite tubes - boundary atoms may show 4-fold coordination
- Vacancies in CNTs create under-coordinated C atoms (expected behavior)
- N-doping changes electronic properties (n-type doping)

## Additional Tips

### Reproducibility
- Always set random seed for reproducible defect distributions
- Example: `--seed 42`

### Validation
- Check interatomic distances after defect creation
  - Vacancies: Check coordination of neighboring atoms
  - Interstitials: Verify > 2 Å from nearest atoms
  - Substitutions: Check if substitution radius is compatible with site
- For CNTs: verify C-C bond lengths remain ~1.42 Å

### Concentration Calculation
- For X% vacancies, need at least 100/X atoms for statistical validity
- Example: 5% doping needs at least 20 atoms for 1 dopant

### Documentation
- Record all defect parameters (type, concentration, seed) for reproducibility
- For CNTs: document chirality, diameter, defect percentage

### Complex Defects
- Use JSON specification file for defect complexes
- Multiple defect types can be introduced sequentially by running defect_builder multiple times

### Validation Checklist
- [ ] Correct number of defects created
- [ ] No overlapping atoms (min distance > threshold)
- [ ] Coordination of neighboring atoms reasonable
- [ ] Structure format compatible with downstream tools
- [ ] Seed recorded for reproducibility
