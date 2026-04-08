"""HTTP route handlers for the web GUI."""

from pathlib import Path
from tempfile import TemporaryDirectory
from shutil import copy2, rmtree

from starlette.responses import HTMLResponse, JSONResponse, Response

from .helpers import STATIC_DIR, asset_url, is_path_safe
from .filesystem import sandbox_root, build_file_tree
from .structure import read_structure, write_structure, resolve_ase_io_format
from .todo import serialize_todo_flow
from .agent_session import session_service, runner
from . import session_store
from agent_team.context import get_context


_EXPORT_FORMATS = {
    "cif": {"ase": "cif", "suffix": ".cif", "content_type": "chemical/x-cif"},
    "xyz": {"ase": "xyz", "suffix": ".xyz", "content_type": "chemical/x-xyz"},
    "extxyz": {"ase": "extxyz", "suffix": ".extxyz", "content_type": "chemical/x-extxyz"},
    "pdb": {"ase": "pdb", "suffix": ".pdb", "content_type": "chemical/x-pdb"},
    "poscar": {"ase": "vasp", "suffix": ".vasp", "content_type": "text/plain"},
}

_PROTECTED_PARTS = {"toolbox", "instructions"}


def _normalize_rel(path_value: str) -> str:
    return str(path_value or "").strip().replace("\\", "/").lstrip("/")


def _is_protected_rel(rel: str) -> bool:
    parts = [part for part in Path(_normalize_rel(rel)).parts if part not in ("", ".")]
    return any(part in _PROTECTED_PARTS for part in parts)


def _copy_target_for(source: Path, target_dir: Path) -> Path:
    base = source.stem
    suffix = source.suffix
    candidate = target_dir / f"{base}_copy{suffix}"
    counter = 1
    while candidate.exists():
        candidate = target_dir / f"{base}_copy_{counter}{suffix}"
        counter += 1
    return candidate


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


async def api_structure_add_molecule(request):
    """POST /api/structure/add-molecule — convert SMILES to 3D atom positions."""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid JSON"}, status_code=400)

    smiles = str(body.get("smiles", "")).strip()
    if not smiles:
        return JSONResponse({"error": "SMILES string required"}, status_code=400)

    try:
        from rdkit import Chem
        from rdkit.Chem import AllChem

        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            return JSONResponse({"error": "Invalid SMILES string"}, status_code=400)

        mol = Chem.AddHs(mol)
        result = AllChem.EmbedMolecule(mol, AllChem.ETKDG())
        if result != 0:
            return JSONResponse({"error": "Could not generate 3D coordinates"}, status_code=400)

        AllChem.MMFFOptimizeMolecule(mol)

        conf = mol.GetConformer()
        atoms = []
        for i in range(mol.GetNumAtoms()):
            atom = mol.GetAtomWithIdx(i)
            pos = conf.GetAtomPosition(i)
            atoms.append({
                "symbol": atom.GetSymbol(),
                "x": round(pos.x, 4),
                "y": round(pos.y, 4),
                "z": round(pos.z, 4),
            })

        return JSONResponse({
            "atoms": atoms,
            "smiles": Chem.MolToSmiles(Chem.RemoveHs(mol)),
        })
    except ImportError:
        return JSONResponse({"error": "RDKit is not installed"}, status_code=500)
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


async def api_file_delete(request):
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid JSON"}, status_code=400)

    rel = _normalize_rel(body.get("path", ""))
    if not rel:
        return JSONResponse({"error": "path required"}, status_code=400)
    if _is_protected_rel(rel):
        return JSONResponse({"error": "modifying toolbox/instructions files is not allowed"}, status_code=403)

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


async def api_file_delete_many(request):
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid JSON"}, status_code=400)

    paths = body.get("paths")
    if not isinstance(paths, list) or not paths:
        return JSONResponse({"error": "paths must be a non-empty list"}, status_code=400)

    normalized = [_normalize_rel(p) for p in paths]
    if any(not p for p in normalized):
        return JSONResponse({"error": "all paths must be non-empty"}, status_code=400)
    if any(_is_protected_rel(p) for p in normalized):
        return JSONResponse({"error": "modifying toolbox/instructions files is not allowed"}, status_code=403)

    root = sandbox_root()
    items_to_delete = []
    for rel in normalized:
        fp = (root / rel).resolve()
        if not is_path_safe(fp, root):
            return JSONResponse({"error": f"access denied: {rel}"}, status_code=403)
        if not fp.exists():
            return JSONResponse({"error": f"not found: {rel}"}, status_code=404)
        items_to_delete.append((rel, fp))

    try:
        for _, fp in items_to_delete:
            if fp.is_dir():
                rmtree(fp)
            else:
                fp.unlink()
        return JSONResponse({"ok": True, "deleted": [rel for rel, _ in items_to_delete]})
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


async def api_file_rename(request):
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid JSON"}, status_code=400)

    rel = _normalize_rel(body.get("path", ""))
    new_name = body.get("new_name", "")
    if not rel or not new_name:
        return JSONResponse({"error": "path and new_name required"}, status_code=400)
    if _is_protected_rel(rel):
        return JSONResponse({"error": "modifying toolbox/instructions files is not allowed"}, status_code=403)

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
    if _is_protected_rel(str(target.relative_to(root))):
        return JSONResponse({"error": "modifying toolbox/instructions files is not allowed"}, status_code=403)
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

    rel = _normalize_rel(body.get("path", ""))
    if not rel:
        return JSONResponse({"error": "path required"}, status_code=400)
    if _is_protected_rel(rel):
        return JSONResponse({"error": "modifying toolbox/instructions files is not allowed"}, status_code=403)

    root = sandbox_root()
    fp = (root / rel).resolve()
    if not is_path_safe(fp, root):
        return JSONResponse({"error": "access denied"}, status_code=403)
    if not fp.exists() or not fp.is_file():
        return JSONResponse({"error": "not found"}, status_code=404)

    candidate = _copy_target_for(fp, fp.parent)

    try:
        copy2(fp, candidate)
        return JSONResponse({"ok": True, "path": str(candidate.relative_to(root))})
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


async def api_file_paste(request):
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid JSON"}, status_code=400)

    paths = body.get("paths")
    target_rel = _normalize_rel(body.get("target_dir", ""))
    if not isinstance(paths, list) or not paths:
        return JSONResponse({"error": "paths must be a non-empty list"}, status_code=400)

    normalized = [_normalize_rel(p) for p in paths]
    if any(not p for p in normalized):
        return JSONResponse({"error": "all paths must be non-empty"}, status_code=400)
    if any(_is_protected_rel(p) for p in normalized):
        return JSONResponse({"error": "modifying toolbox/instructions files is not allowed"}, status_code=403)

    root = sandbox_root()
    target_dir = (root / target_rel).resolve() if target_rel else root
    if not is_path_safe(target_dir, root):
        return JSONResponse({"error": "invalid target_dir"}, status_code=400)
    if not target_dir.exists() or not target_dir.is_dir():
        return JSONResponse({"error": "target_dir not found"}, status_code=404)
    if _is_protected_rel(str(target_dir.relative_to(root))):
        return JSONResponse({"error": "modifying toolbox/instructions files is not allowed"}, status_code=403)

    sources = []
    for rel in normalized:
        fp = (root / rel).resolve()
        if not is_path_safe(fp, root):
            return JSONResponse({"error": f"access denied: {rel}"}, status_code=403)
        if not fp.exists() or not fp.is_file():
            return JSONResponse({"error": f"not found: {rel}"}, status_code=404)
        sources.append((rel, fp))

    pasted = []
    try:
        for _, src in sources:
            dest = _copy_target_for(src, target_dir)
            copy2(src, dest)
            pasted.append(str(dest.relative_to(root)))
        return JSONResponse({"ok": True, "paths": pasted})
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


async def api_reset(request):
    """POST /api/reset — clear in-memory sessions and reset the TodoFlow."""
    try:
        ss = session_service

        # Preserve the app key to avoid "app_name ... not in sessions" warnings
        app_name = getattr(runner, "app_name", "atom_sculptor")

        if hasattr(ss, "sessions"):
            try:
                # Reset sessions map but keep the app_name present with an empty dict
                ss.sessions.clear()
                ss.sessions[app_name] = {}
            except Exception:
                ss.sessions = {app_name: {}}

        if hasattr(ss, "user_state"):
            try:
                ss.user_state.clear()
            except Exception:
                ss.user_state = {}

        if hasattr(ss, "app_state"):
            try:
                ss.app_state.clear()
            except Exception:
                ss.app_state = {}

        # Reset the shared todo flow
        try:
            get_context().reset()
        except Exception:
            pass

        # Clear the in-memory session store
        session_store.clear()

        return JSONResponse({"ok": True})
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


async def api_sessions_list(request):
    """GET /api/sessions — list all in-memory sessions."""
    return JSONResponse({"sessions": session_store.list_sessions()})


async def api_session_rename(request):
    """PATCH /api/sessions/rename — rename a session."""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid JSON"}, status_code=400)

    sid = str(body.get("session_id", "")).strip()
    name = str(body.get("name", "")).strip()
    if not sid or not name:
        return JSONResponse({"error": "session_id and name required"}, status_code=400)

    if session_store.rename(sid, name):
        return JSONResponse({"ok": True})
    return JSONResponse({"error": "session not found"}, status_code=404)


async def api_session_delete(request):
    """DELETE /api/sessions/delete — delete a session."""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid JSON"}, status_code=400)

    sid = str(body.get("session_id", "")).strip()
    if not sid:
        return JSONResponse({"error": "session_id required"}, status_code=400)

    if session_store.delete(sid):
        return JSONResponse({"ok": True})
    return JSONResponse({"error": "session not found"}, status_code=404)


async def api_structure_build_interfaces(request):
    """POST /api/structure/build-interfaces — generate interface candidates between two structures."""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid JSON"}, status_code=400)

    film_rel = body.get("film_path", "")
    substrate_rel = body.get("substrate_path", "")
    film_miller = body.get("film_miller", [1, 0, 0])
    substrate_miller = body.get("substrate_miller", [1, 0, 0])
    gap = float(body.get("gap", 2.0))
    vacuum_over_film = float(body.get("vacuum_over_film", 10.0))
    film_thickness = int(body.get("film_thickness", 3))
    substrate_thickness = int(body.get("substrate_thickness", 3))
    in_layers = bool(body.get("in_layers", True))
    max_interfaces = int(body.get("max_interfaces", 10))

    if not film_rel:
        return JSONResponse({"error": "film_path required"}, status_code=400)
    if not substrate_rel:
        return JSONResponse({"error": "substrate_path required"}, status_code=400)

    root = sandbox_root()
    film_fp = (root / film_rel).resolve()
    substrate_fp = (root / substrate_rel).resolve()

    if not is_path_safe(film_fp, root):
        return JSONResponse({"error": "film_path access denied"}, status_code=403)
    if not is_path_safe(substrate_fp, root):
        return JSONResponse({"error": "substrate_path access denied"}, status_code=403)
    if not film_fp.exists() or not film_fp.is_file():
        return JSONResponse({"error": "film file not found"}, status_code=404)
    if not substrate_fp.exists() or not substrate_fp.is_file():
        return JSONResponse({"error": "substrate file not found"}, status_code=404)

    if not isinstance(film_miller, list) or len(film_miller) != 3:
        return JSONResponse({"error": "film_miller must be a list of 3 integers"}, status_code=400)
    if not isinstance(substrate_miller, list) or len(substrate_miller) != 3:
        return JSONResponse({"error": "substrate_miller must be a list of 3 integers"}, status_code=400)

    try:
        import numpy as np
        from pymatgen.analysis.interfaces.coherent_interfaces import CoherentInterfaceBuilder
        from pymatgen.io.ase import AseAtomsAdaptor

        try:
            from pymatgen.analysis.interfaces.coherent_interfaces import fix_pbc as _fix_pbc
        except ImportError:
            def _fix_pbc(s):
                return s

        def _load_pmg(fp: Path):
            suffix = fp.suffix.lower()
            if suffix in (".cif", ".vasp", ".poscar"):
                from pymatgen.core import Structure
                return Structure.from_file(str(fp))
            else:
                atoms = _read_atoms_safe(fp)
                return AseAtomsAdaptor.get_structure(atoms)

        film_structure = _load_pmg(film_fp).to_conventional()
        substrate_structure = _load_pmg(substrate_fp).to_conventional()

        cib = CoherentInterfaceBuilder(
            substrate_structure=substrate_structure,
            film_structure=film_structure,
            film_miller=tuple(int(x) for x in film_miller),
            substrate_miller=tuple(int(x) for x in substrate_miller),
        )

        results = []
        collected = 0
        for t_idx, termination in enumerate(cib.terminations):
            if collected >= max_interfaces:
                break
            interfaces = list(cib.get_interfaces(
                termination=termination,
                gap=gap,
                vacuum_over_film=(vacuum_over_film if vacuum_over_film != 0 else gap),
                film_thickness=film_thickness,
                substrate_thickness=substrate_thickness,
                in_layers=in_layers,
            ))
            for iface_idx, interface in enumerate(interfaces):
                if collected >= max_interfaces:
                    break
                wrapped = _fix_pbc(interface)
                vec_a = interface.lattice.matrix[0]
                vec_b = interface.lattice.matrix[1]
                area = float(np.linalg.norm(np.cross(vec_a, vec_b)))
                try:
                    poscar_text = wrapped.to(fmt="poscar")
                except Exception:
                    poscar_text = None
                results.append({
                    "id": f"iface_{collected}",
                    "von_mises_strain": interface.interface_properties.get("von_mises_strain"),
                    "termination_index": t_idx,
                    "interface_index": iface_idx,
                    "area": area,
                    "n_atoms": len(interface),
                    "poscar": poscar_text,
                })
                collected += 1

        return JSONResponse({"interfaces": results})
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


async def api_structure_build_interfaces_save(request):
    """POST /api/structure/build-interfaces/save — save a selected interface candidate."""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid JSON"}, status_code=400)

    poscar_text = body.get("poscar", "")
    filename = str(body.get("filename", "")).strip()

    if not poscar_text:
        return JSONResponse({"error": "poscar required"}, status_code=400)

    root = sandbox_root()

    if filename:
        name = Path(filename).name
        if name in ("", ".", ".."):
            return JSONResponse({"error": "invalid filename"}, status_code=400)
        output_path = root / name
        if not is_path_safe(output_path, root):
            return JSONResponse({"error": "access denied"}, status_code=403)
        counter = 1
        while output_path.exists():
            output_path = root / f"{Path(name).stem}_{counter}{Path(name).suffix}"
            counter += 1
    else:
        output_path = _output_path_for(root, "interface", Path("structure.vasp"))

    try:
        import tempfile
        from ase.io import write as ase_write, read as ase_read

        with tempfile.NamedTemporaryFile(suffix=".vasp", mode="w", delete=False) as tmp:
            tmp.write(poscar_text)
            tmp_path = tmp.name

        try:
            atoms = ase_read(tmp_path, format="vasp")
        finally:
            Path(tmp_path).unlink(missing_ok=True)

        ase_write(str(output_path), atoms, format="extxyz")
        data = read_structure(output_path)
        data["path"] = str(output_path.relative_to(root))
        return JSONResponse(data)
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)
