---
name: structure-perturbation
description: Apply random/Gaussian/scaled-random displacements to atomic structures, single or batch.
when_to_use: Use when generating perturbed structures for MLIP training data, NEB starts, finite-temperature initial configurations, or to stress-test a relaxed structure.
entry: scripts/structure_perturbation.py
---

# Structure Perturbation

Two CLI sub-commands:

- `perturb_structure` — produce one perturbed copy with stats.
- `batch_perturb`     — produce many (different seeds) for dataset generation.

```bash
python3 scripts/structure_perturbation.py perturb_structure \
  --input-file Fe_bcc.extxyz --displacement-magnitude 0.1 --perturbation-mode gaussian --seed 42

python3 scripts/structure_perturbation.py batch_perturb \
  --input-file Fe_bcc.extxyz --num-structures 50 --displacement-magnitude 0.05
```

Modes: `random` (uniform), `gaussian` (std = magnitude), `scaled_random`
(scaled by per-element covalent radius).
