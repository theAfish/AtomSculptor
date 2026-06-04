---
name: nanotube-builder
description: Build carbon nanotubes (CNTs) of any chirality (n,m), length, bond, and PBC.
when_to_use: Use when the user asks to build a CNT, an armchair/zigzag/chiral tube, or a starting tube to be filled later. Pair with `nanostructure-creation` for the design checklist.
entry: scripts/nanotube_builder.py
---

# Nanotube Builder

Single-command CLI built on top of `ase.build.nanotube`. Reports diameter,
chirality type (armchair / zigzag / chiral), tube length, cell, and atom count.

```bash
python3 scripts/nanotube_builder.py build_nanotube --n 7 --m 7 --length 4
python3 scripts/nanotube_builder.py build_nanotube --n 10 --m 0 --length 6 --bond 1.42 --vacuum 20.0
```

For chirality / diameter rules of thumb and post-build steps (filling,
thermal perturbation, PBC consistency), read the
[`nanostructure-creation`](../nanostructure-creation/SKILL.md) skill.
