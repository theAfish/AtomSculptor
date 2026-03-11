import os
from pathlib import Path
from typing import Any, Dict, Literal

import yaml
from dotenv import load_dotenv


def _load_project_dotenv(dotenv_path: Path) -> None:
    if not dotenv_path.exists() or not dotenv_path.is_file():
        return

    for raw_line in dotenv_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        if line.startswith("export "):
            line = line[len("export ") :].strip()

        if "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()

        if not key:
            continue

        if (value.startswith('"') and value.endswith('"')) or (
            value.startswith("'") and value.endswith("'")
        ):
            value = value[1:-1]

        os.environ.setdefault(key, value)


class Settings:
    """Loads configuration values from a YAML file and/or environment variables.

    Values defined in the environment take precedence over those in the file.
    This keeps secrets out of version control while still allowing a simple
    YAML-based configuration for defaults.
    """

    def __init__(self, config_path: str | Path | None = None) -> None:
        _load_project_dotenv(Path(__file__).resolve().parent / ".env")
        load_dotenv()  # Additional load for code-graph-rag compatibility

        # allow the path to be overridden by environment (useful for tests)
        if config_path is None:
            config_path = os.environ.get("CONFIG_PATH", "config.yaml")
        self._config_path = Path(config_path)
        self._data: Dict[str, Any] = {}

        if self._config_path.exists():
            with open(self._config_path, "r", encoding="utf-8") as f:
                # safe_load will return None for an empty file
                loaded = yaml.safe_load(f)
                if isinstance(loaded, dict):
                    self._data = loaded

        # AtomSculptor settings
        self.PLANNER_MODEL = os.environ.get(
            "PLANNER_MODEL", self._data.get("PLANNER_MODEL", "openai/qwen3-max")
        )
        self.STRUCTURE_BUILDER_MODEL = os.environ.get(
            "STRUCTURE_BUILDER_MODEL", self._data.get("STRUCTURE_BUILDER_MODEL", "openai/qwen3-max")
        )
        self.MP_SEARCHER_MODEL = os.environ.get(
            "MP_SEARCHER_MODEL", self._data.get("MP_SEARCHER_MODEL", "openai/qwen3-max")
        )
        self.CODE_ANALYZER_MODEL = os.environ.get(
            "CODE_ANALYZER_MODEL", self._data.get("CODE_ANALYZER_MODEL", "openai/qwen3-max")
        )
        self.SANDBOX_DIR = os.environ.get(
            "SANDBOX_DIR", self._data.get("SANDBOX_DIR", "sandbox/runtime")
        )

        # Code-graph-rag settings
        self.MEMGRAPH_HOST = os.environ.get(
            "MEMGRAPH_HOST", self._data.get("MEMGRAPH_HOST", "localhost")
        )
        self.MEMGRAPH_PORT = int(os.environ.get(
            "MEMGRAPH_PORT", self._data.get("MEMGRAPH_PORT", 7687)
        ))
        self.MEMGRAPH_HTTP_PORT = int(os.environ.get(
            "MEMGRAPH_HTTP_PORT", self._data.get("MEMGRAPH_HTTP_PORT", 7444)
        ))
        self.LAB_PORT = int(os.environ.get(
            "LAB_PORT", self._data.get("LAB_PORT", 3000)
        ))
        
        self.LLM_PROVIDER: Literal["gemini", "local", "deepseek", "openai"] = os.environ.get(
            "LLM_PROVIDER", self._data.get("LLM_PROVIDER", "openai")
        )
        self.GEMINI_PROVIDER: Literal["gla", "vertex"] = os.environ.get(
            "GEMINI_PROVIDER", self._data.get("GEMINI_PROVIDER", "gla")
        )
        
        self.GEMINI_MODEL_ID = os.environ.get(
            "GEMINI_MODEL_ID", self._data.get("GEMINI_MODEL_ID", "gemini-2.5-pro")
        )
        self.GEMINI_VISION_MODEL_ID = os.environ.get(
            "GEMINI_VISION_MODEL_ID", self._data.get("GEMINI_VISION_MODEL_ID", "gemini-2.5-flash")
        )
        self.MODEL_CYPHER_ID = os.environ.get(
            "MODEL_CYPHER_ID", self._data.get("MODEL_CYPHER_ID", "gemini-2.5-flash-lite-preview-06-17")
        )
        self.GEMINI_API_KEY = os.environ.get(
            "GEMINI_API_KEY", self._data.get("GEMINI_API_KEY")
        )
        self.GEMINI_THINKING_BUDGET = os.environ.get(
            "GEMINI_THINKING_BUDGET", self._data.get("GEMINI_THINKING_BUDGET")
        )
        
        self.GCP_PROJECT_ID = os.environ.get(
            "GCP_PROJECT_ID", self._data.get("GCP_PROJECT_ID")
        )
        self.GCP_REGION = os.environ.get(
            "GCP_REGION", self._data.get("GCP_REGION", "us-central1")
        )
        self.GCP_SERVICE_ACCOUNT_FILE = os.environ.get(
            "GCP_SERVICE_ACCOUNT_FILE", self._data.get("GCP_SERVICE_ACCOUNT_FILE")
        )
        
        self.DEEPSEEK_MODEL_ID = os.environ.get(
            "DEEPSEEK_MODEL_ID", self._data.get("DEEPSEEK_MODEL_ID", "deepseek-chat")
        )
        self.DEEPSEEK_API_KEY = os.environ.get(
            "DEEPSEEK_API_KEY", self._data.get("DEEPSEEK_API_KEY")
        )

        self.OPENAI_ORCHESTRATOR_MODEL_ID = os.environ.get(
            "OPENAI_ORCHESTRATOR_MODEL_ID",
            self._data.get("OPENAI_ORCHESTRATOR_MODEL_ID", "qwen3-max"),
        )
        self.OPENAI_CYPHER_MODEL_ID = os.environ.get(
            "OPENAI_CYPHER_MODEL_ID",
            self._data.get("OPENAI_CYPHER_MODEL_ID", "qwen3-max"),
        )
        
        self.LOCAL_MODEL_ENDPOINT = os.environ.get(
            "LOCAL_MODEL_ENDPOINT", self._data.get("LOCAL_MODEL_ENDPOINT", "http://localhost:11434/v1")
        )
        self.LOCAL_ORCHESTRATOR_MODEL_ID = os.environ.get(
            "LOCAL_ORCHESTRATOR_MODEL_ID", self._data.get("LOCAL_ORCHESTRATOR_MODEL_ID", "llama3")
        )
        self.LOCAL_CYPHER_MODEL_ID = os.environ.get(
            "LOCAL_CYPHER_MODEL_ID", self._data.get("LOCAL_CYPHER_MODEL_ID", "llama3")
        )
        self.LOCAL_MODEL_API_KEY = os.environ.get(
            "LOCAL_MODEL_API_KEY", self._data.get("LOCAL_MODEL_API_KEY", "ollama")
        )
        
        self.TARGET_REPO_PATH = os.environ.get(
            "TARGET_REPO_PATH", self._data.get("TARGET_REPO_PATH")
        )
        self.SHELL_COMMAND_TIMEOUT = int(os.environ.get(
            "SHELL_COMMAND_TIMEOUT", self._data.get("SHELL_COMMAND_TIMEOUT", 30)
        ))
        
        self.MP_API_KEY = os.environ.get(
            "MP_API_KEY", self._data.get("MP_API_KEY")
        )
        self.OPENAI_API_KEY = os.environ.get(
            "OPENAI_API_KEY", self._data.get("OPENAI_API_KEY")
        )
        self.OPENAI_API_BASE = os.environ.get(
            "OPENAI_API_BASE", self._data.get("OPENAI_API_BASE")
        )

    def get_sandbox_client_kwargs(self) -> Dict[str, Any]:
        return {"root_dir": self.SANDBOX_DIR}


# a single, project-wide settings object that can be imported anywhere
settings = Settings()
