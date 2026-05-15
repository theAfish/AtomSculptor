---
name: crystal-builder
description: Build common bulk crystal structures (FCC/BCC/HCP/diamond/zincblende/...) using ASE.
when_to_use: Use when the user asks to construct a bulk crystal from scratch given an element (or compound such as NaCl) and a crystal structure type. Not for surfaces, slabs, or molecules.
entry: scripts/crystal_builder.py
---

# Crystal Builder

Generates bulk crystal structures via `ase.build.bulk` and writes them to the
sandbox output directory. Two CLI sub-commands:

- `build_bulk_crystal` — create a structure for one element + crystalstructure.
- `list_crystal_structures` — list every supported `crystalstructure` value.

## Quick examples

```bash
python3 scripts/crystal_builder.py build_bulk_crystal --element Fe --crystalstructure bcc --a 2.87
python3 scripts/crystal_builder.py build_bulk_crystal --element NaCl --crystalstructure rocksalt --a 5.64
python3 scripts/crystal_builder.py list_crystal_structures
```

For full per-tool help, run with `-h`. For deeper guidance on choosing
`crystalstructure` and lattice constants, read
[references/notes.md](references/notes.md).
