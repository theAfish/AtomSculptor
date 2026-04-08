import inspect
import json
import os
import subprocess
import shutil
from pathlib import Path
from typing import Any, Iterable


class SandboxRuntimeError(RuntimeError):
    pass


class Sandbox:
    def __init__(
        self,
        root_dir: str | Path = "sandbox_runtime",
        create: bool = True,
        clear_existing: bool = False,
        settings_path: str | Path | None = None,
        config: dict[str, Any] | None = None,
        auto_install_srt: bool = False,
    ) -> None:
        self.root_dir = Path(root_dir).expanduser().resolve()
        self.control_dir = self.root_dir.parent / ".sandbox_control"
        self.agents_dir = self.control_dir / "agents"
        self.settings_path = (
            Path(settings_path).expanduser().resolve()
            if settings_path is not None
            else self.control_dir / "srt-settings.json"
        )
        self._config_override = config
        self._auto_install_srt = auto_install_srt

        if clear_existing and self.root_dir.exists():
            shutil.rmtree(self.root_dir)

        if create:
            self.initialize()

    def initialize(self) -> None:
        self.root_dir.mkdir(parents=True, exist_ok=True)
        self._migrate_legacy_runtime_layout()
        self.agents_dir.mkdir(parents=True, exist_ok=True)
        self._write_settings_file()

    def ensure_runtime(self) -> None:
        if self._has_srt():
            return

        if not self._auto_install_srt:
            raise SandboxRuntimeError(
                "Sandbox Runtime CLI not found. Install with: npm install -g @anthropic-ai/sandbox-runtime"
            )

        self._install_srt()

        if not self._has_srt():
            raise SandboxRuntimeError(
                "Failed to install sandbox runtime CLI. Try manually: npm install -g @anthropic-ai/sandbox-runtime"
            )

    def add_agent(self, agents: Any | Iterable[Any]) -> list[Path]:
        if isinstance(agents, (list, tuple, set)):
            items = list(agents)
        else:
            items = [agents]

        created_dirs: list[Path] = []
        for agent in items:
            created_dirs.append(self._materialize_agent(agent))
        return created_dirs

    def add(self, agents: Any | Iterable[Any]) -> list[Path]:
        return self.add_agent(agents)

    def run(
        self,
        command: str,
        cwd: str | Path | None = None,
        capture_output: bool = True,
        check: bool = True,
        env: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        self.ensure_runtime()

        merged_env = os.environ.copy()
        if env:
            merged_env.update(env)

        run_cwd = Path(cwd).expanduser().resolve() if cwd is not None else self.root_dir
        shell_cmd = f'srt --settings "{self.settings_path}" {command}'

        result = subprocess.run(
            shell_cmd,
            shell=True,
            cwd=str(run_cwd),
            env=merged_env,
            text=True,
            capture_output=capture_output,
            check=False,
        )

        if check and result.returncode != 0:
            message = result.stderr.strip() if result.stderr else "unknown error"
            raise SandboxRuntimeError(
                f"Sandboxed command failed (exit={result.returncode}): {message}"
            )

        return result

    def list_agents(self) -> list[str]:
        if not self.agents_dir.exists():
            return []
        return sorted(
            child.name for child in self.agents_dir.iterdir() if child.is_dir()
        )

    def get_settings(self) -> dict[str, Any]:
        return self._default_config()

    def _materialize_agent(self, agent: Any) -> Path:
        agent_name = self._resolve_agent_name(agent)
        target_dir = self.agents_dir / agent_name
        target_dir.mkdir(parents=True, exist_ok=True)

        metadata = {
            "name": agent_name,
            "type": type(agent).__name__,
            "module": getattr(type(agent), "__module__", "unknown"),
            "repr": repr(agent),
        }
        (target_dir / "agent.json").write_text(
            json.dumps(metadata, indent=2), encoding="utf-8"
        )

        source_path = self._resolve_agent_source_file(agent)
        if source_path and source_path.exists() and source_path.is_file():
            shutil.copy2(source_path, target_dir / source_path.name)

        return target_dir

    def _default_config(self) -> dict[str, Any]:
        if self._config_override is not None:
            return self._config_override

        return {
            "network": {
                "allowedDomains": [
                    "api.materialsproject.org",
                    "*.materialsproject.org",
                    
                ],
                "deniedDomains": [],
            },
            "filesystem": {
                "denyRead": [str(self.control_dir)],
                "allowWrite": [str(self.root_dir)],
                "denyWrite": [],
            },
        }

    def _migrate_legacy_runtime_layout(self) -> None:
        legacy_agents_dir = self.root_dir / "agents"
        legacy_settings_path = self.root_dir / "srt-settings.json"

        if legacy_agents_dir.exists() and legacy_agents_dir.is_dir():
            self.agents_dir.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(legacy_agents_dir, self.agents_dir, dirs_exist_ok=True)
            shutil.rmtree(legacy_agents_dir)

        if legacy_settings_path.exists() and legacy_settings_path != self.settings_path:
            self.settings_path.parent.mkdir(parents=True, exist_ok=True)
            if not self.settings_path.exists():
                shutil.move(str(legacy_settings_path), str(self.settings_path))
            else:
                legacy_settings_path.unlink()

    def _write_settings_file(self) -> None:
        self.settings_path.parent.mkdir(parents=True, exist_ok=True)
        self.settings_path.write_text(
            json.dumps(self._default_config(), indent=2), encoding="utf-8"
        )

    @staticmethod
    def _has_srt() -> bool:
        probe = subprocess.run(
            ["bash", "-lc", "command -v srt"],
            text=True,
            capture_output=True,
            check=False,
        )
        return probe.returncode == 0 and bool(probe.stdout.strip())

    @staticmethod
    def _install_srt() -> None:
        subprocess.run(
            ["bash", "-lc", "npm install -g @anthropic-ai/sandbox-runtime"],
            text=True,
            capture_output=True,
            check=False,
        )

    @staticmethod
    def _resolve_agent_name(agent: Any) -> str:
        for attr in ("name", "id"):
            value = getattr(agent, attr, None)
            if isinstance(value, str) and value.strip():
                return value.strip().replace("/", "_")
        return type(agent).__name__.lower()

    @staticmethod
    def _resolve_agent_source_file(agent: Any) -> Path | None:
        try:
            source_file = inspect.getsourcefile(agent)
        except TypeError:
            source_file = None

        if source_file:
            return Path(source_file)

        module_name = getattr(agent, "__module__", None)
        if module_name:
            import importlib

            module = importlib.import_module(module_name)
            module_file = getattr(module, "__file__", None)
            if module_file:
                return Path(module_file)

        class_module_name = getattr(type(agent), "__module__", None)
        if class_module_name:
            import importlib

            module = importlib.import_module(class_module_name)
            module_file = getattr(module, "__file__", None)
            if module_file:
                return Path(module_file)

        return None


class AgentSandbox(Sandbox):
    pass
