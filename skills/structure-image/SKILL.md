---
name: structure-image
description: Render a PNG image of an atomic structure (rotation, DPI controllable) using ASE + matplotlib.
when_to_use: Use to produce a quick visual of a structure for the user or for the vision-examiner agent. Output is a PNG file.
entry: scripts/structure_image.py
---

# Structure Image

```bash
python3 scripts/structure_image.py generate_structure_image \
  --folder . --file-name slab.extxyz \
  --output-image-name slab.png \
  --rotation '10x,20y,30z' --dpi 150
```
