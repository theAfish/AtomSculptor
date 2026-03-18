from pathlib import Path
import socket
import time
import subprocess
import shutil

from loguru import logger
import mgclient

from code_graph_rag.codebase_rag.graph_updater import MemgraphIngestor
from code_graph_rag.codebase_rag.graph_updater import GraphUpdater
from code_graph_rag.codebase_rag.parser_loader import load_parsers
from code_graph_rag.codebase_rag.tool_api import initialize_rag_agent
from code_graph_rag.codebase_rag.config import settings as rag_settings
from settings import settings as app_settings

_INDEXED_REPO_PATH: str | None = None


def _get_config_value(name: str):
    value = getattr(app_settings, name, None)
    if value not in (None, ""):
        return value
    return getattr(rag_settings, name, None)


def _resolve_repo_path() -> str:
    # 1. Try to use user-defined path from settings
    configured_repo_path = _get_config_value("TARGET_REPO_PATH")
    if configured_repo_path:
        target_path = Path(configured_repo_path).resolve()
        # Check if the path exists and is a directory
        if target_path.exists() and target_path.is_dir():
            # If it's the default placeholder path and looks like it wasn't created/intended,
            # we might want to skip. But usually if it exists, we respect it.
            # Assuming if user sets path or creates default path, they want to use it.
            logger.info(f"Using user-defined repo path: {target_path}")
            return str(target_path)
        else:
            # Only warn if it's NOT the default hardcoded in config (likely user intent)
            logger.warning(
                f"User-defined TARGET_REPO_PATH '{configured_repo_path}' does not exist. "
                "Falling back to pymatgen detection."
            )

    # 2. Fallback to pymatgen detection
    try:
        import importlib.util
        import pymatgen

        if getattr(pymatgen, "__file__", None):
            return str(Path(pymatgen.__file__).resolve().parents[1])

        pkg_paths = list(getattr(pymatgen, "__path__", []))
        if pkg_paths:
            return str(Path(pkg_paths[0]).resolve())

        spec = importlib.util.find_spec("pymatgen")
        if spec and spec.origin:
            return str(Path(spec.origin).resolve().parents[1])

        raise ValueError("Could not resolve pymatgen installation path.")
    except Exception as e:
        raise ValueError(
            "repo_path is required when pymatgen is not available in the environment."
        ) from e


def _memgraph_reachable(host: str, port: int, timeout: float = 1.5) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _ensure_memgraph_running() -> None:
    memgraph_host = _get_config_value("MEMGRAPH_HOST")
    memgraph_port = int(_get_config_value("MEMGRAPH_PORT"))

    if _memgraph_reachable(memgraph_host, memgraph_port):
        return

    repo_root = Path(__file__).resolve().parents[2]
    compose_path = repo_root / "docker-compose.yaml"
    if not compose_path.exists():
        logger.error(f"[code_graph_tool] docker-compose.yaml not found: {compose_path}")
        return

    docker_cmd = "docker"
    if not shutil.which(docker_cmd):
        logger.error("[code_graph_tool] docker not found in PATH.")
        return

    logger.info("[code_graph_tool] Memgraph not reachable. Starting via docker compose...")
    try:
        subprocess.run(
            [docker_cmd, "compose", "-f", str(compose_path), "up", "-d"],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except subprocess.CalledProcessError as e:
        logger.error(
            f"[code_graph_tool] docker compose failed: {e.stderr or e.stdout}"
        )
        return

    for _ in range(60):
        if _memgraph_reachable(memgraph_host, memgraph_port):
            logger.info("[code_graph_tool] Memgraph is now reachable.")
            return
        time.sleep(1)

    logger.error("[code_graph_tool] Memgraph did not become reachable in time.")


def _get_indexed_projects(ingestor: MemgraphIngestor) -> list[str]:
    rows = ingestor.fetch_all("MATCH (p:Project) RETURN p.name AS name ORDER BY p.name")
    return [str(row["name"]) for row in rows if row.get("name")]


def _ensure_graph_indexed_with_ingestor(
    ingestor: MemgraphIngestor,
    repo_path: str,
    *,
    clear_existing: bool = False,
) -> None:
    global _INDEXED_REPO_PATH
    resolved_repo_path = str(Path(repo_path).resolve())
    desired_project_name = Path(resolved_repo_path).name

    if not clear_existing and _INDEXED_REPO_PATH == resolved_repo_path:
        return

    try:
        result = ingestor.fetch_all("MATCH (n) RETURN count(n) AS count")
        count = int(result[0]["count"]) if result else 0

        indexed_projects = _get_indexed_projects(ingestor)
        graph_matches_repo = indexed_projects == [desired_project_name]

        if clear_existing:
            logger.info("[code_graph_tool] Clearing existing graph before rebuild.")
            ingestor.clean_database()
            count = 0
            indexed_projects = []
        elif count > 0 and graph_matches_repo:
            logger.info(
                f"[code_graph_tool] Graph already indexed for {desired_project_name}: {count} nodes."
            )
            _INDEXED_REPO_PATH = resolved_repo_path
            return
        elif count > 0:
            logger.info(
                "[code_graph_tool] Existing graph does not match requested repo. "
                f"Found projects={indexed_projects}, expected={[desired_project_name]}. Rebuilding."
            )
            ingestor.clean_database()

        logger.info("[code_graph_tool] Graph is empty. Building index...")
        ingestor.ensure_constraints()
        parsers, queries = load_parsers()
        updater = GraphUpdater(ingestor, Path(resolved_repo_path), parsers, queries)
        updater.run()
        _INDEXED_REPO_PATH = resolved_repo_path
        logger.info("[code_graph_tool] Graph indexing complete.")
    except Exception as e:
        logger.error(f"[code_graph_tool] Graph indexing failed: {e}")
        raise


def ingest_codebase(repo_path: str | None = None, clear_existing: bool = False) -> str:
    """Index the configured codebase into Memgraph, optionally clearing stale data first."""
    _ensure_memgraph_running()
    resolved_repo_path = str(Path(repo_path).resolve()) if repo_path else _resolve_repo_path()
    memgraph_host = _get_config_value("MEMGRAPH_HOST")
    memgraph_port = int(_get_config_value("MEMGRAPH_PORT"))

    with MemgraphIngestor(host=memgraph_host, port=memgraph_port) as ingestor:
        _ensure_graph_indexed_with_ingestor(
            ingestor,
            resolved_repo_path,
            clear_existing=clear_existing,
        )
        counts = ingestor.fetch_all(
            "MATCH (n) RETURN count(n) AS node_count"
        )
        indexed_projects = _get_indexed_projects(ingestor)

    node_count = int(counts[0]["node_count"]) if counts else 0
    return (
        f"Indexed repo '{resolved_repo_path}' into Memgraph. "
        f"Projects={indexed_projects}, node_count={node_count}."
    )


async def ask_code_graph_local(question: str) -> str:
    """Query code-graph-rag locally without MCP."""
    _ensure_memgraph_running()
    repo_path = _resolve_repo_path()
    memgraph_host = _get_config_value("MEMGRAPH_HOST")
    memgraph_port = int(_get_config_value("MEMGRAPH_PORT"))
    logger.info(f"[code_graph_tool] question: {question[:200]}")
    logger.info(f"[code_graph_tool] repo_path: {repo_path}")
    last_error: Exception | None = None
    for _ in range(10):
        try:
            with MemgraphIngestor(host=memgraph_host, port=memgraph_port) as ingestor:
                _ensure_graph_indexed_with_ingestor(ingestor, repo_path)
                rag_agent = initialize_rag_agent(repo_path, ingestor)
                result = await rag_agent.run(question, message_history=[])
                return str(result.output)
        except mgclient.OperationalError as e:
            last_error = e
            logger.warning(
                f"[code_graph_tool] Memgraph handshake failed, retrying... {e}"
            )
            time.sleep(2)
    # raise last_error or RuntimeError("Memgraph connection failed.")
    return f"Error: Unable to connect to code graph database after multiple attempts. Last error: {last_error}"
