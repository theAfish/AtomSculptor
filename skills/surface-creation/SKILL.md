---
name: surface-creation
description: Workflow and pitfalls for generating crystal surfaces (slabs) from bulk structures.
when_to_use: Use when the user asks for a surface, slab, Miller-indexed face, or surface termination. Read this BEFORE invoking any surface-building tool.
---

# Surface Creation

Instruction-only skill (no entry script). Use it as a checklist when planning a
surface-generation task. For deeper material-specific notes, drill down via:

- [references/lpscl_and_sio2.md](references/lpscl_and_sio2.md) — worked examples
  for LPSCl (Li6PS5Cl) and α-SiO2 surfaces.
- [references/checklist.md](references/checklist.md) — validation checklist and
  PBC / vacuum / layer-count rules of thumb.

## Common Workflow

1. **Obtain bulk crystal structure**
   - Materials Project search (preferred for real materials), or
   - Manual creation via `crystal-builder` skill / pymatgen / ASE.

2. **Convert to conventional cell (CRITICAL for FCC)**
   - MP often returns primitive cells (60° angles for FCC).
   - For surfaces, use the conventional cell. The structure tools accept
     `need_conventional=True`.
   - Never hand-roll cell transformations — use proper tools.

3. **Generate surface using SlabGenerator**
   - Specify Miller indices.
   - Layers: 4–8 (5 is a good default for DFT).
   - Vacuum: ≥ 10–15 Å.

4. **Build supercell for desired adsorbate coverage**
   - Periodic images of any adsorbate must be > 10 Å apart.

5. **Validate** (Miller indices, termination, surface coordination, PBC=(T,T,F),
   structural-unit integrity).

6. **Save and document** (`.extxyz` preferred; record MP ID, orientation,
   layers, vacuum thickness).

## Key Considerations

### Miller indices and stability
- BCC: (100), (110), (111). (110) often most stable.
- FCC: (111) most stable, (100) common.
- Perovskites: (001) common, multiple terminations.
- Oxides: (001), (100), (101), (110).

### Primitive vs. conventional cell

| Cell type    | Angles               | Use case            |
|--------------|----------------------|---------------------|
| Primitive    | 60° (rhombohedral)   | Bulk calculations   |
| Conventional | 90° (cubic)          | Surface generation  |

### Common pitfalls

| Pitfall                              | Fix                                                  |
|--------------------------------------|------------------------------------------------------|
| Primitive vs. conventional cell      | Convert to conventional BEFORE surface generation.   |
| Wrong surface termination            | Check all terminations, pick one preserving units.   |
| Insufficient vacuum                  | Increase to ≥ 10 Å.                                  |
| Too many layers for DFT              | Reduce to 5; verify properties hold.                 |
| Adsorbate periodic images < 10 Å     | Enlarge supercell.                                   |
| Broken structural units (PS4, dimers)| Test all terminations; see lpscl_and_sio2 reference. |
