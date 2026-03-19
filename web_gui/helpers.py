"""General-purpose helpers for the web GUI server."""

from datetime import datetime, timezone
from pathlib import Path

_HERE = Path(__file__).resolve().parent
STATIC_DIR = _HERE / "static"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def asset_url(relative_path: str) -> str:
    asset_path = STATIC_DIR / relative_path
    try:
        version = asset_path.stat().st_mtime_ns
    except FileNotFoundError:
        version = 0
    return f"/static/{relative_path}?v={version}"


def is_path_safe(requested: Path, root: Path) -> bool:
    try:
        requested.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def safe_value(obj):
    """Recursively convert protobuf / special objects to plain JSON-safe types."""
    if obj is None:
        return None
    if isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, dict):
        return {str(k): safe_value(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [safe_value(v) for v in obj]
    try:
        return {str(k): safe_value(v) for k, v in dict(obj).items()}
    except (TypeError, ValueError):
        return str(obj)
