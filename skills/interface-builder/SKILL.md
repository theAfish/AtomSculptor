---
name: interface-builder
description: Build a coherent lattice-matched interface between two bulk structures using the pymatgen ZSL algorithm.
when_to_use: Use to create a strain-matched film/substrate interface from two bulk crystals. Read the `interface-building` skill first for tolerance tuning, gap sizing, and termination considerations.
entry: scripts/interface_builder.py
---

# Interface Builder

```bash
python3 scripts/interface_builder.py build_interface \
  --structure-1 Fe.extxyz --structure-2 SiO2.extxyz \
  --miller-1 '[1,0,0]' --miller-2 '[0,0,1]' \
  --gap 2.5 --thickness-1 4 --thickness-2 4 \
  --max-area 400 --max-length-tol 0.03 --max-angle-tol 0.01 \
  --output-file-name Fe-SiO2_interface.extxyz
```

For dissimilar lattices try relaxed tolerances: `--max-length-tol 0.15
--max-angle-tol 0.1`. If the lowest-strain match still breaks structural
units (PS4 tetrahedra, dimers, …), build the slab manually with
`surface-builder` and stack — see the `interface-building` skill.
