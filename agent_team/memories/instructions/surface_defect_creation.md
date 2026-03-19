# Surface Defect Creation Instructions

## Common Workflow

1. **Create pristine surface**
   - Generate the bulk crystal structure (see surface_creation.md)
   - Create surface with appropriate Miller indices
   - Verify structure integrity before introducing defects

2. **Identify defect type and location**
   - Determine defect type: vacancy, substitution, interstitial
   - Identify target atom(s) for removal or replacement
   - Consider surface layer vs. subsurface layer defects

3. **Introduce defects**
   - **Vacancy**: Remove atom(s) from specific positions
   - **Substitution**: Replace atom(s) with different element(s)
   - **Interstitial**: Add atom(s) at non-lattice positions
   - Document defect positions and types

4. **Validate defective structure**
   - Verify correct number of atoms removed/added
   - Check coordination of atoms near defect site
   - Ensure no unintended structural changes

5. **Save and document**
   - Save defective structure with descriptive filename
   - Document defect type, location, and concentration

## Key Considerations

### Defect Types

| Defect Type | Description | Example |
|-------------|-------------|---------|
| Vacancy | Missing atom at lattice site | Oxygen vacancy in SrTiO3 |
| Substitution | Atom replaced by different element | Sr substituted by Ca |
| Interstitial | Extra atom at non-lattice site | H in interstitial position |
| Frenkel pair | Vacancy + interstitial of same atom | Mobile ion defects |

### Defect Location
- **Surface defects**: Atoms in top layer(s) - most relevant for surface chemistry
- **Subsurface defects**: Atoms below surface - affect electronic structure
- **Bulk-like defects**: Deep within slab - for studying bulk-defect-surface interactions

### Common Defect Sites in Perovskite Oxides (ABO3)
- Oxygen vacancies: Most common defect in perovskite oxides
- Often form at surface or near interfaces
- Affect catalytic activity and electronic properties

## Common Pitfalls and Fixes

1. **Removing wrong atom**: Index-based removal errors
   - Symptom: Defect at unexpected location
   - Fix: Verify atom positions and indices before removal; use visualization tools

2. **Incorrect defect concentration**: Wrong number of defects
   - Symptom: Unexpected stoichiometry
   - Fix: Calculate expected stoichiometry after defect introduction

3. **Unstable defect configuration**: Defect causes structural collapse
   - Symptom: Atoms too close together or unrealistic geometries
   - Fix: Consider relaxation calculations; verify initial defect placement

## Additional Tips

- Oxygen vacancies are particularly important in oxide surfaces for catalysis
- Defect formation energy calculations require reference states
- Consider charge compensation when creating charged defects
- For high-throughput studies, automate defect creation at multiple symmetrically equivalent sites
- Always compare defective structure with pristine reference for validation
