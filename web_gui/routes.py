"""HTTP route handlers for the web GUI."""

from pathlib import Path

from starlette.responses import HTMLResponse, JSONResponse

from .helpers import STATIC_DIR, asset_url, is_path_safe
from .filesystem import sandbox_root, build_file_tree
from .structure import read_structure, write_structure
from .todo import serialize_todo_flow


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
    cell = body.get("cell", None)
    pbc = body.get("pbc", [False, False, False])

    if not rel:
        return JSONResponse({"error": "path required"}, status_code=400)
    root = sandbox_root()
    fp = (root / rel).resolve()
    if not is_path_safe(fp, root):
        return JSONResponse({"error": "access denied"}, status_code=403)

    try:
        natoms = write_structure(fp, atoms_data, cell, pbc)
        return JSONResponse({"ok": True, "path": rel, "natoms": natoms})
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)
