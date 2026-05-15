# LPSCl and α-SiO2 — Worked Examples

Load via `read_skill("surface-creation", "references/lpscl_and_sio2.md")` only
when working with these specific materials.

## LPSCl (Li6PS5Cl)
- Contains PS4 tetrahedra and S–S dimers.
- P–S bond distance: 2.057 Å.
- Surface generation must keep PS4 units intact — test every termination and
  pick one that preserves them.

## α-Quartz SiO2
- Source: `mp-6930` (trigonal P3_221).
- Common orientations: (001), (100), (101), (110).
- Layer optimization: 5 layers usually sufficient for DFT (down from 8).
- Maintain > 10 Å periodic image distance for adsorbates.

| Surface     | Typical supercell | Dimensions (Å) | Layers | Atoms (5 layers) |
|-------------|-------------------|----------------|--------|------------------|
| SiO2 (001)  | 4×4×1             | 19.7 × 19.7    | 5      | 405              |
| SiO2 (100)  | 4×3×1             | 19.7 × 16.3    | 5      | 417              |
| SiO2 (101)  | 3×4×1             | 22.0 × 19.7    | 5      | 270              |
| SiO2 (110)  | 2×3×1             | 17.0 × 16.3    | 5      | 282              |

## Lattice parameters for common reference materials

| Material        | Structure | Lattice constant (Å) | Space group  |
|-----------------|-----------|----------------------|--------------|
| Fe              | BCC       | 2.866                | Im-3m (229)  |
| Cu              | FCC       | 3.615                | Fm-3m (225)  |
| Pt              | FCC       | 3.924                | Fm-3m (225)  |
| SiO2 (α-quartz) | Trigonal  | a=4.91, c=5.40       | P3_221 (154) |
