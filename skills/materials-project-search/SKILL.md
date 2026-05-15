---
name: materials-project-search
description: Strategies for searching, filtering, and downloading structures from the Materials Project (MP) database.
when_to_use: Use when the user asks to fetch a real material from MP, pick a polymorph, or fall back to manual creation when the MP API is unavailable.
---

# Materials Project Search Instructions

## Common Workflow

1. **Identify target material properties**
   - Determine chemical composition (e.g., SiO2, Fe, Cu-Zn alloy)
   - Specify crystal structure or polymorph if known
   - Define stability requirements (energy above hull threshold)
   - Note any specific requirements (space group, band gap, etc.)

2. **Search Materials Project database**
   - Use composition-based search
   - Filter by thermodynamic stability (energy_above_hull)
   - Apply additional filters as needed (space group, formation energy)
   - Review candidate structures

3. **Select appropriate structure**
   - Check Materials Project ID (mp-XXXXX format)
   - Verify crystal structure matches requirements
   - Note space group and lattice parameters
   - Confirm stability (energy_above_hull close to 0)

4. **Download and verify structure**
   - Use appropriate tools to fetch structure
   - Verify imported structure integrity
   - Check atom count and positions
   - Save in desired format (CIF, XYZ, POSCAR)

5. **Handle API failures (if applicable)**
   - If MP API unavailable, use manual creation with known parameters
   - Document source of alternative parameters

## Key Considerations

### Stability Criteria
- **energy_above_hull = 0**: Most thermodynamically stable structure
- **energy_above_hull > 0**: Metastable or unstable structures
- For production calculations: prefer energy_above_hull = 0
- For exploratory work: small values (e.g., < 0.1 eV) may be acceptable

### Common Materials and IDs
| Material | MP ID | Structure | Space Group | Notes |
|----------|-------|-----------|-------------|-------|
| BCC Fe | mp-13 | BCC | Im-3m (229) | Most stable Fe |
| SiO2 (α-quartz) | mp-6930 | α-quartz | P3_221 | Most stable SiO2 |
| Cu-Zn (beta brass) | mp-987 | B2 (CsCl-type) | Pm-3m (221) | Stable alloy |

### Polymorph Selection
- Many materials have multiple polymorphs
- Example: SiO2 has quartz, cristobalite, tridymite, coesite, stishovite
- Use stability (energy_above_hull) and space group to identify desired polymorph
- β-quartz (mp-6922) with space group P6222 is common hexagonal SiO2 form

### Lattice Matching for Interfaces
- Consider lattice parameters relative to other materials
- For interfaces: check lattice mismatch before selection
- May need to try multiple polymorphs for best match

## Common Pitfalls and Fixes

1. **API connection failure**
   - Symptom: Cannot connect to Materials Project
   - Cause: Network issues, proxy errors, API downtime
   - Fix: Create structure manually with known parameters
   - Example: BCC Fe with a=2.866 Å, space group Im-3m

2. **Non-existent crystal structure**
   - Symptom: Search returns no results
   - Cause: Searching for structure that doesn't exist in nature
   - Fix: Use closest polymorph or build manually
   - Example: "hcp SiO2" doesn't exist; use hexagonal β-quartz

3. **Multiple candidates match search**
   - Symptom: Many structures returned for composition
   - Cause: Multiple polymorphs or similar compositions
   - Fix: Apply additional filters (space group, formation energy, band gap)
   - Check energy_above_hull to identify most stable

4. **Wrong polymorph selected**
   - Symptom: Crystal structure doesn't match expected form
   - Cause: Multiple polymorphs with similar stability
   - Fix: Check space group and structure carefully
   - Cross-reference with literature for commonly used forms

5. **Primitive vs. conventional cell confusion**
   - Symptom: Unexpected atom count in downloaded structure
   - Cause: Materials Project often provides primitive cell
   - Fix: Convert to conventional cell if needed
   - Use crystal_builder with --cubic true

## Additional Tips

### Efficient Searching
- Always note the MP ID for reproducibility
- Use energy_above_hull = 0 filter for most stable structures
- Space group can quickly identify polymorphs
- Formation energy can indicate stability trends

### Structure Validation After Download
- Check atom count matches expectation
- Verify space group is correct
- Confirm lattice parameters are reasonable
- Check for any unusual atomic positions

### Manual Structure Creation Parameters
When MP API is unavailable, use known parameters:
- **BCC Fe**: a=2.866 Å, space group Im-3m (229), 2 atoms in conventional cell
- **FCC Cu**: a=3.615 Å, space group Fm-3m (225), 4 atoms in conventional cell
- **FCC Pt**: a=3.924 Å, space group Fm-3m (225), 4 atoms in conventional cell

### Documentation Requirements
- Record MP ID for all structures from MP
- If using manual creation, document parameter source
- Note any filters applied during search
- For interfaces, document MP IDs of all components

### Cross-Referencing
- Use ICSD IDs when available for additional validation
- Check common literature for frequently used structures
- Some structures may have multiple MP IDs (different settings)
- Verify structure visualization matches expectations
