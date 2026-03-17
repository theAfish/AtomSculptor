# Structure Tools CLI

This module provides CLI tools for working with atomic structures directly inside the runtime sandbox.

The CLI tools have two help layers:

- General help: `python path/to/tools.py -h`
- Tool-specific help: `python path/to/tools.py <tool_name> -h`

## 1. How To Use

```bash
python path/to/tools.py -h
python path/to/tools.py <tool_name> -h
```

Notes:

- Relative input paths are resolved against the current working directory.
- Output files are written into the current working directory unless you pass an absolute path.
- List and tuple parameters must be passed as JSON strings, for example `'[2, 2, 1]'` or `'[1, 0, 0]'`.
- Boolean parameters should be passed explicitly, for example `--in-layers true`.
- CLI results are printed as JSON. If the tool returns an `error` field, the CLI exits with a non-zero status.

---

## 2. structure_tools.py

Tools for reading, manipulating, and analyzing existing structure files.

### Included Tools:

- `read_structure`: Read a structure file and return a compact summary.
- `read_structures_in_text`: Read the raw text of a structure file.
- `calculate_distance`: Measure the straight-line distance between two atom indices.
- `build_supercell`: Repeat a structure using a 3-vector or 3x3 transformation matrix.
- `build_surface`: Build a slab from a bulk structure with Miller indices, layers, and vacuum.
- `generate_structure_image`: Save a PNG image rendered from the structure.
- `check_close_atoms`: Detect atom pairs that are closer than a covalent-radius-based threshold.
- `build_interface`: Build a coherent interface between two structures using pymatgen.

---

## 3. crystal_builder.py

Tool for generating common bulk crystal structures from scratch.

### Included Tools:

- `build_bulk_crystal`: Build a bulk crystal structure from element and crystal type.
- `list_crystal_structures`: List all supported crystal structure types with descriptions.
