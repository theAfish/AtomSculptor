"""HTTP route handlers for the web GUI."""

from pathlib import Path
from tempfile import TemporaryDirectory

from starlette.responses import HTMLResponse, JSONResponse, Response

from .helpers import STATIC_DIR, asset_url, is_path_safe
from .filesystem import sandbox_root, build_file_tree
from .structure import read_structure, write_structure, resolve_ase_io_format
from .todo import serialize_todo_flow


_EXPORT_FORMATS = {
    "cif": {"ase": "cif", "suffix": ".cif", "content_type": "chemical/x-cif"},
    "xyz": {"ase": "xyz", "suffix": ".xyz", "content_type": "chemical/x-xyz"},
    "extxyz": {"ase": "extxyz", "suffix": ".extxyz", "content_type": "chemical/x-extxyz"},
    "pdb": {"ase": "pdb", "suffix": ".pdb", "content_type": "chemical/x-pdb"},
    "poscar": {"ase": "vasp", "suffix": ".vasp", "content_type": "text/plain"},
}


async def index(request):
    html = (STATIC_DIR / "index.html").read_text("utf-8")
    html = html.replace("__INDEX_CSS__", asset_url("css/index.css"))
    html = html.replace("__APP_JS__", asset_url("js/app.js"))
    return HTMLResponse(html, media_type="text/html", headers={"Cache-Control": "no-store"})


async def api_todo_flow(request):
    return JSONResponse(serialize_todo_flow())


async def api_files(request):
    root = sandbox_root()
    return JSONResponse({"tree": build_file_tree(root, root), "root": str(root)})


async def api_file_content(request):
    rel = request.query_params.get("path", "")
    if not rel:
        return JSONResponse({"error": "path required"}, status_code=400)
    root = sandbox_root()
    fp = (root / rel).resolve()
    if not is_path_safe(fp, root):
        return JSONResponse({"error": "access denied"}, status_code=403)
    if not fp.exists() or not fp.is_file():
        return JSONResponse({"error": "not found"}, status_code=404)
    try:
        return JSONResponse({"content": fp.read_text("utf-8"), "path": rel})
    except UnicodeDecodeError:
        return JSONResponse({"error": "binary file"}, status_code=400)


async def api_structure(request):
    rel = request.query_params.get("path", "")
    if not rel:
        return JSONResponse({"error": "path required"}, status_code=400)
    root = sandbox_root()
    fp = (root / rel).resolve()
    if not is_path_safe(fp, root):
        return JSONResponse({"error": "access denied"}, status_code=403)
    if not fp.exists() or not fp.is_file():
        return JSONResponse({"error": "not found"}, status_code=404)
    try:
        data = read_structure(fp)
    except Exception as exc:
        return JSONResponse({"error": f"Could not parse structure: {exc}"}, status_code=400)
    data["path"] = rel
    return JSONResponse(data)


async def api_structure_save(request):
    """POST /api/structure/save — receive modified atom list, write back via ASE."""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid JSON"}, status_code=400)

    rel = body.get("path", "")
    atoms_data = body.get("atoms", [])
    layers = body.get("layers", None)
    cell = body.get("cell", None)
    pbc = body.get("pbc", [False, False, False])

    if not rel:
        return JSONResponse({"error": "path required"}, status_code=400)
    root = sandbox_root()
    fp = (root / rel).resolve()
    if not is_path_safe(fp, root):
        return JSONResponse({"error": "access denied"}, status_code=403)

    try:
        natoms = write_structure(fp, atoms_data, cell, pbc, layers)
        return JSONResponse({"ok": True, "path": rel, "natoms": natoms})
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


async def api_structure_export(request):
    """POST /api/structure/export — convert and download a structure file."""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid JSON"}, status_code=400)

    rel = body.get("path", "")
    export_format = str(body.get("format", "")).strip().lower()

    if not rel:
        return JSONResponse({"error": "path required"}, status_code=400)
    if export_format not in _EXPORT_FORMATS:
        return JSONResponse({"error": f"Unsupported export format: {export_format}"}, status_code=400)

    root = sandbox_root()
    fp = (root / rel).resolve()
    if not is_path_safe(fp, root):
        return JSONResponse({"error": "access denied"}, status_code=403)
    if not fp.exists() or not fp.is_file():
        return JSONResponse({"error": "not found"}, status_code=404)

    try:
        from ase.io import write as ase_write

        atoms = _read_atoms_safe(fp)
        spec = _EXPORT_FORMATS[export_format]
        base_name = Path(rel).stem

        with TemporaryDirectory(prefix="atomsculptor-export-") as tmp_dir:
            tmp_path = Path(tmp_dir) / f"{base_name}{spec['suffix']}"
            ase_write(str(tmp_path), atoms, format=spec["ase"])
            payload = tmp_path.read_bytes()

        filename = f"{base_name}{spec['suffix']}"
        headers = {
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-store",
        }
        return Response(payload, media_type=spec["content_type"], headers=headers)
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


def _read_atoms_safe(fp: Path):
    """Read an ASE Atoms object from *fp* with format auto-detection."""
    from ase.io import read as ase_read

    ase_format = resolve_ase_io_format(fp)
    return ase_read(str(fp), format=ase_format)


def _output_path_for(root: Path, prefix: str, source: Path) -> Path:
    """Generate a non-colliding output path inside *root*."""
    stem = source.stem
    candidate = root / f"{prefix}_{stem}.extxyz"
    counter = 1
    while candidate.exists():
        candidate = root / f"{prefix}_{stem}_{counter}.extxyz"
        counter += 1
    return candidate


async def api_structure_build_surface(request):
    """POST /api/structure/build-surface — create a surface slab from a bulk structure."""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid JSON"}, status_code=400)

    rel = body.get("path", "")
    miller = body.get("miller_indices", [1, 0, 0])
    layers = body.get("layers", 3)
    vacuum = body.get("vacuum", 10.0)

    if not rel:
        return JSONResponse({"error": "path required"}, status_code=400)

    root = sandbox_root()
    fp = (root / rel).resolve()
    if not is_path_safe(fp, root):
        return JSONResponse({"error": "access denied"}, status_code=403)
    if not fp.exists() or not fp.is_file():
        return JSONResponse({"error": "not found"}, status_code=404)

    try:
        from ase.build import surface
        from ase.io import write as ase_write

        atoms = _read_atoms_safe(fp)

        if not isinstance(miller, list) or len(miller) != 3:
            return JSONResponse({"error": "Miller indices must be a list of 3 integers."}, status_code=400)
        miller_tuple = tuple(int(m) for m in miller)
        layers = int(layers)
        vacuum = float(vacuum)

        if layers < 1:
            return JSONResponse({"error": "Layers must be at least 1."}, status_code=400)
        if vacuum < 0:
            return JSONResponse({"error": "Vacuum must be non-negative."}, status_code=400)

        slab = surface(atoms, miller_tuple, layers, vacuum=vacuum)

        output_path = _output_path_for(root, "slab", fp)
        ase_write(str(output_path), slab, format="extxyz")

        data = read_structure(output_path)
        data["path"] = str(output_path.relative_to(root))
        return JSONResponse(data)
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


async def api_structure_build_supercell(request):
    """POST /api/structure/build-supercell — create a supercell from current structure."""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid JSON"}, status_code=400)

    rel = body.get("path", "")
    matrix = body.get("matrix")

    if not rel:
        return JSONResponse({"error": "path required"}, status_code=400)

    root = sandbox_root()
    fp = (root / rel).resolve()
    if not is_path_safe(fp, root):
        return JSONResponse({"error": "access denied"}, status_code=403)
    if not fp.exists() or not fp.is_file():
        return JSONResponse({"error": "not found"}, status_code=404)

    try:
        from ase.build import make_supercell
        from ase.io import write as ase_write
        import numpy as np

        atoms = _read_atoms_safe(fp)

        if (
            not isinstance(matrix, list)
            or len(matrix) != 3
            or any(not isinstance(row, list) or len(row) != 3 for row in matrix)
        ):
            return JSONResponse({"error": "matrix must be a 3×3 array of integers."}, status_code=400)
        mat = np.array([[int(v) for v in row] for row in matrix])
        if int(round(abs(np.linalg.det(mat)))) < 1:
            return JSONResponse({"error": "Supercell matrix must have a non-zero determinant."}, status_code=400)

        supercell = make_supercell(atoms, mat)

        output_path = _output_path_for(root, "supercell", fp)
        ase_write(str(output_path), supercell, format="extxyz")

        data = read_structure(output_path)
        data["path"] = str(output_path.relative_to(root))
        return JSONResponse(data)
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


async def api_file_delete(request):
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid JSON"}, status_code=400)

    rel = body.get("path", "")
    if not rel:
        return JSONResponse({"error": "path required"}, status_code=400)

    root = sandbox_root()
    fp = (root / rel).resolve()
    if not is_path_safe(fp, root):
        return JSONResponse({"error": "access denied"}, status_code=403)
    if not fp.exists():
        return JSONResponse({"error": "not found"}, status_code=404)
    if fp.is_dir():
        return JSONResponse({"error": "directory deletion not supported"}, status_code=400)

    try:
        fp.unlink()
        return JSONResponse({"ok": True})
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


async def api_file_rename(request):
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid JSON"}, status_code=400)

    rel = body.get("path", "")
    new_name = body.get("new_name", "")
    if not rel or not new_name:
        return JSONResponse({"error": "path and new_name required"}, status_code=400)

    # prevent path traversal in new name
    if "/" in new_name or ".." in new_name or "\\" in new_name:
        return JSONResponse({"error": "invalid new_name"}, status_code=400)

    root = sandbox_root()
    fp = (root / rel).resolve()
    if not is_path_safe(fp, root):
        return JSONResponse({"error": "access denied"}, status_code=403)
    if not fp.exists():
        return JSONResponse({"error": "not found"}, status_code=404)

    target = fp.parent / new_name
    if not is_path_safe(target, root):
        return JSONResponse({"error": "invalid target"}, status_code=400)
    if target.exists():
        return JSONResponse({"error": "target exists"}, status_code=400)

    try:
        fp.rename(target)
        return JSONResponse({"ok": True, "path": str(target.relative_to(root))})
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


async def api_file_upload(request):
    """POST /api/file/upload — accept dropped files and store them in sandbox root."""
    form = await request.form()
    upload = form.get("file")
    if not upload:
        return JSONResponse({"error": "file required"}, status_code=400)

    filename = getattr(upload, "filename", None) or ""
    if not filename:
        return JSONResponse({"error": "invalid filename"}, status_code=400)

    from pathlib import Path
    root = sandbox_root()
    name = Path(filename).name
    if name in ("", ".", ".."):
        return JSONResponse({"error": "invalid filename"}, status_code=400)

    target = root / name
    counter = 1
    while target.exists():
        target = root / f"{target.stem}_{counter}{target.suffix}"
        counter += 1

    try:
        content = await upload.read()
        target.write_bytes(content)
        return JSONResponse({"ok": True, "path": str(target.relative_to(root))})
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


async def api_file_duplicate(request):
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid JSON"}, status_code=400)

    rel = body.get("path", "")
    if not rel:
        return JSONResponse({"error": "path required"}, status_code=400)

    root = sandbox_root()
    fp = (root / rel).resolve()
    if not is_path_safe(fp, root):
        return JSONResponse({"error": "access denied"}, status_code=403)
    if not fp.exists() or not fp.is_file():
        return JSONResponse({"error": "not found"}, status_code=404)

    from shutil import copy2

    base = fp.stem
    suffix = fp.suffix
    candidate = fp.parent / f"{base}_copy{suffix}"
    counter = 1
    while candidate.exists():
        candidate = fp.parent / f"{base}_copy_{counter}{suffix}"
        counter += 1

    try:
        copy2(fp, candidate)
        return JSONResponse({"ok": True, "path": str(candidate.relative_to(root))})
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)
