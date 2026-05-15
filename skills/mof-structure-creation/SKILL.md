---
name: mof-structure-creation
description: Workflow for building Metal-Organic Framework (MOF) structures (MOF-5, Cu-BTC, IRMOF series, custom).
when_to_use: Use when the user asks to construct a MOF or any metal-node + organic-linker porous framework.
---

# MOF Structure Creation Instructions

## Common Workflow

1. **Select MOF type**
   - MOF-5 (IRMOF-1): Zn4O(BDC)3, highly porous (~2900 m²/g)
   - Cu-BTC (HKUST-1): Cu3(BTC)2, Cu paddlewheel nodes
   - IRMOF series: Isoreticular MOFs with varying linkers
   - Custom MOFs: Define metal nodes and organic linkers

2. **Build MOF structure**
   - Use MOF builder tools with predefined templates
   - Specify lattice parameter (MOF-5: a=25.9 Å)
   - For custom MOFs: define metal, linker, and connectivity

3. **Validate MOF structure**
   - Check metal coordination (Zn4O clusters, Cu paddlewheels)
   - Verify pore sizes match expected values
   - Check linker geometry and connectivity
   - Ensure no overlapping atoms

4. **Save and document**
   - Export in .extxyz and .vasp formats
   - Document MOF type, lattice parameter, atom count
   - Record surface area and pore size if available

## Key Considerations

### Common MOF Parameters

| MOF Type | Formula | Space Group | Lattice (Å) | Pore Size | Surface Area |
|----------|---------|-------------|-------------|-----------|--------------|
| MOF-5 | Zn4O(BDC)3 | Fm-3m (225) | 25.9 | ~12 Å | ~2900 m²/g |
| Cu-BTC | Cu3(BTC)2 | Fm-3m | 26.34 | ~9 Å | ~1500 m²/g |
| IRMOF-1 | Zn4O(BDC)3 | Fm-3m | 25.9 | ~12 Å | ~2900 m²/g |

### MOF Building Blocks
- **Metal nodes**: Zn4O clusters, Cu paddlewheels, Zr6 clusters
- **Linkers**: BDC (benzenedicarboxylate), BTC (benzenetricarboxylate)
- **Connectivity**: 3-connected, 4-connected, 6-connected nodes

### Structure Validation
- Metal-metal distances: Check cluster geometry
- Metal-linker bonds: Typically 1.9-2.2 Å for Zn-O, 1.9-2.0 Å for Cu-O
- Linker bond lengths: C-C aromatic ~1.40 Å, C-O ~1.27 Å
- Pore accessibility: Ensure channels are not blocked

## Common Pitfalls and Fixes

| Pitfall | Symptom | Fix |
|---------|---------|-----|
| Missing metal nodes | Wrong stoichiometry | Use proper builder function with correct cluster type |
| Incorrect lattice | Wrong pore size | Verify lattice parameter against literature |
| Linker disorder | Multiple orientations | Check symmetry and use ordered positions |
| Under-coordinated metals | Dangling bonds | Verify metal coordination environment |

## Additional Tips

### Available MOF Builder Functions
1. **build_mof5(a=25.9)** - Build MOF-5 (IRMOF-1) structure
2. **build_cu_btc()** - Build Cu-BTC (HKUST-1) MOF
3. **build_simple_mof(a=20.0, metal="Zn")** - Customizable simple MOF
4. **build_irmof_1()** - IRMOF-1 with accurate coordinates
5. **list_mof_types()** - List all available MOF types

### Usage Example
```bash
python3 toolbox/structure_modelling/mof_builder.py build_mof5
python3 toolbox/structure_modelling/mof_builder.py build_cu_btc
```

### File Formats
- Output: .extxyz (preserves all structural info) and .vasp (for VASP)
- MOF-5 example: 99 atoms, a=25.9 Å
- Cu-BTC example: 22 atoms (unit cell), a=26.34 Å

### Post-Processing Notes
- MOF structures from builder are ideal/uncollapsed
- For simulations, consider geometry optimization (DFT/force field)
- Check for framework flexibility in molecular simulations
- Porosity calculations may require specialized tools (ZeO++, PoreBlazer)
