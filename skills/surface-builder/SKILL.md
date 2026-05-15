---
name: surface-builder
description: Build a surface slab (Miller indices, layers, vacuum) from a bulk crystal, optionally first symmetrizing to the conventional cell.
when_to_use: Use to construct an arbitrary (hkl) slab from a bulk structure. Read the `surface-creation` skill for picking Miller indices, layer count, and vacuum thickness; read `surface-defect-creation` / `surface-adsorption` for follow-on steps.
entry: scripts/surface_builder.py
---

# Surface Builder

```bash
python3 scripts/surface_builder.py build_surface \
  --folder . --file-name Fe.extxyz \
  --miller-indices '[1,0,0]' --layers 5 --vacuum 15.0 \
  --need-conventional true \
  --output-name Fe_100.extxyz
```

`need_conventional=true` runs `pymatgen.symmetry.analyzer.SpacegroupAnalyzer`
first to produce the conventional standard cell — strongly recommended for
anything coming out of Materials Project (often primitive).
