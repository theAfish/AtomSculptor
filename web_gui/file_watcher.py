"""Shared, event-driven sandbox file-tree watcher.

A single :class:`FileTreeWatcher` instance is used for **all** connected
WebSocket clients.  When the sandbox directory changes, watchdog fires an
event which is forwarded to the asyncio event loop via
``loop.call_soon_threadsafe()``.  After a short debounce window the tree is
rebuilt once and pushed to every subscribed ``asyncio.Queue``, keeping
CPU/IO usage constant regardless of the number of connected clients.
"""

import asyncio
import logging
import threading
import time
from pathlib import Path

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

logger = logging.getLogger(__name__)

_DEBOUNCE = 1.0  # minimum seconds between consecutive rebuilds


class _FsEventHandler(FileSystemEventHandler):
    """Watchdog event handler that schedules a tree rebuild."""

    def __init__(self, watcher: "FileTreeWatcher") -> None:
        super().__init__()
        self._watcher = watcher

    def on_any_event(self, event) -> None:  # noqa: ANN001
        self._watcher._schedule_rebuild()


class FileTreeWatcher:
    """Shared, event-driven file-tree watcher backed by watchdog.

    A single Observer watches the sandbox directory.  When filesystem events
    occur the tree is rebuilt (with debouncing) and pushed to every
    subscribed ``asyncio.Queue``.

    Typical usage inside a WebSocket handler::

        q = file_watcher.subscribe()
        try:
            while True:
                tree = await q.get()
                await ws.send_json({"type": "files_update", "data": tree})
        finally:
            file_watcher.unsubscribe(q)
    """

    def __init__(self) -> None:
        self._subscribers: set[asyncio.Queue] = set()
        self._sub_lock = threading.Lock()
        self._observer: Observer | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._sandbox: Path | None = None
        self._tree_cache: list = []
        self._last_rebuild: float = 0.0
        self._pending: bool = False
        self._started: bool = False

    # ── public API ───────────────────────────────────────────────────────────

    def start(self, loop: asyncio.AbstractEventLoop, sandbox: Path) -> None:
        """Start the watchdog observer.

        Safe to call multiple times; subsequent calls are no-ops.
        """
        if self._started:
            return
        self._loop = loop
        self._sandbox = sandbox

        # Build initial cache before accepting connections
        try:
            self._tree_cache = self._build(sandbox)
        except Exception:
            logger.warning("FileTreeWatcher: initial file-tree build failed", exc_info=True)

        if sandbox.exists():
            handler = _FsEventHandler(self)
            self._observer = Observer()
            self._observer.schedule(handler, str(sandbox), recursive=True)
            self._observer.start()
        else:
            logger.warning(
                "FileTreeWatcher: sandbox directory %s does not exist; "
                "file-change events will not be delivered until it is created.",
                sandbox,
            )

        self._started = True
        logger.debug("FileTreeWatcher started, watching %s", sandbox)

    def stop(self) -> None:
        """Stop the watchdog observer (call on server shutdown)."""
        if self._observer:
            self._observer.stop()
            self._observer.join()
            self._observer = None
        self._started = False

    def subscribe(self) -> "asyncio.Queue[list]":
        """Return a queue that receives file-tree snapshots on every change."""
        q: asyncio.Queue[list] = asyncio.Queue(maxsize=1)
        with self._sub_lock:
            self._subscribers.add(q)
        return q

    def unsubscribe(self, q: "asyncio.Queue[list]") -> None:
        """Remove *q* from the subscriber set."""
        with self._sub_lock:
            self._subscribers.discard(q)

    @property
    def current_tree(self) -> list:
        """Return the most recently built file-tree snapshot."""
        return self._tree_cache

    # ── internals ────────────────────────────────────────────────────────────

    def _schedule_rebuild(self) -> None:
        """Called from the watchdog thread; hand off to the asyncio event loop."""
        loop = self._loop
        if loop is None or loop.is_closed():
            return
        loop.call_soon_threadsafe(self._on_change_in_loop)

    def _on_change_in_loop(self) -> None:
        """Called in the event-loop thread; apply the debounce window."""
        now = time.monotonic()
        if now - self._last_rebuild < _DEBOUNCE:
            # Another rebuild is recent; schedule one deferred check
            if not self._pending:
                self._pending = True
                assert self._loop is not None
                self._loop.call_later(_DEBOUNCE, self._deferred_rebuild)
            return
        self._do_rebuild()

    def _deferred_rebuild(self) -> None:
        self._pending = False
        self._do_rebuild()

    def _do_rebuild(self) -> None:
        self._last_rebuild = time.monotonic()
        try:
            assert self._sandbox is not None
            self._tree_cache = self._build(self._sandbox)
        except Exception:
            logger.warning("FileTreeWatcher: file-tree rebuild failed", exc_info=True)
            return

        with self._sub_lock:
            subs = list(self._subscribers)
        for q in subs:
            try:
                q.put_nowait(self._tree_cache)
            except asyncio.QueueFull:
                # Slow subscriber; it already has a pending update queued
                pass

    @staticmethod
    def _build(sandbox: Path) -> list:
        from .filesystem import build_file_tree  # local import to avoid circulars

        return build_file_tree(sandbox, sandbox)


# Module-level singleton — shared across all WebSocket connections
file_watcher = FileTreeWatcher()
