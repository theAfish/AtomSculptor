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

_INDEXED = False


def _resolve_repo_path() -> str:
    # 1. Try to use user-defined path from settings
    if rag_settings.TARGET_REPO_PATH:
        target_path = Path(rag_settings.TARGET_REPO_PATH).resolve()
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
                f"User-defined TARGET_REPO_PATH '{rag_settings.TARGET_REPO_PATH}' does not exist. "
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
    if _memgraph_reachable(rag_settings.MEMGRAPH_HOST, rag_settings.MEMGRAPH_PORT):
        return

    repo_root = Path(__file__).resolve().parents[2]
    compose_path = repo_root / "code-graph-rag" / "docker-compose.yaml"
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
        if _memgraph_reachable(rag_settings.MEMGRAPH_HOST, rag_settings.MEMGRAPH_PORT):
            logger.info("[code_graph_tool] Memgraph is now reachable.")
            return
        time.sleep(1)

    logger.error("[code_graph_tool] Memgraph did not become reachable in time.")


def _ensure_graph_indexed_with_ingestor(
    ingestor: MemgraphIngestor, repo_path: str
) -> None:
    global _INDEXED
    if _INDEXED:
        return
    try:
        result = ingestor.fetch_all("MATCH (n) RETURN count(n) AS count")
        count = int(result[0]["count"]) if result else 0
        if count > 0:
            logger.info(f"[code_graph_tool] Graph already indexed: {count} nodes.")
            _INDEXED = True
            return

        logger.info("[code_graph_tool] Graph is empty. Building index...")
        parsers, queries = load_parsers()
        updater = GraphUpdater(ingestor, Path(repo_path), parsers, queries)
        updater.run()
        _INDEXED = True
        logger.info("[code_graph_tool] Graph indexing complete.")
    except Exception as e:
        logger.error(f"[code_graph_tool] Graph indexing failed: {e}")
        raise


async def ask_code_graph_local(question: str) -> str:
    """Query code-graph-rag locally without MCP."""
    _ensure_memgraph_running()
    repo_path = _resolve_repo_path()
    logger.info(f"[code_graph_tool] question: {question[:200]}")
    logger.info(f"[code_graph_tool] repo_path: {repo_path}")
    last_error: Exception | None = None
    for _ in range(10):
        try:
            with MemgraphIngestor(
                host=rag_settings.MEMGRAPH_HOST, port=rag_settings.MEMGRAPH_PORT
            ) as ingestor:
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
