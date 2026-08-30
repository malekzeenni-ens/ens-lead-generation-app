from __future__ import annotations

import logging
import threading
from collections.abc import Callable, Iterable

import psutil

logger = logging.getLogger(__name__)

ProcessSupplier = Callable[[], Iterable[str]]
StateCallback = Callable[[set[str]], None]


def running_process_names() -> Iterable[str]:
    for process in psutil.process_iter(["name"]):
        try:
            name = process.info.get("name")
        except (psutil.AccessDenied, psutil.NoSuchProcess, psutil.ZombieProcess):
            continue
        if isinstance(name, str) and name:
            yield name


class ProtectedApplicationMonitor:
    def __init__(
        self,
        process_names: tuple[str, ...],
        poll_seconds: float,
        callback: StateCallback,
        process_supplier: ProcessSupplier = running_process_names,
    ) -> None:
        self._configured = {name.casefold(): self._label(name) for name in process_names}
        self._poll_seconds = poll_seconds
        self._callback = callback
        self._process_supplier = process_supplier
        self._active: set[str] = set()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    @staticmethod
    def _label(name: str) -> str:
        lowered = name.casefold()
        if "lightburn" in lowered:
            return "LightBurn"
        return "xTool Creative Space"

    @property
    def active(self) -> set[str]:
        return set(self._active)

    def check_now(self) -> set[str]:
        running = {name.casefold() for name in self._process_supplier()}
        detected = {label for name, label in self._configured.items() if name in running}
        if detected != self._active:
            self._active = detected
            self._callback(set(detected))
        return set(detected)

    def start(self) -> None:
        if self._thread is not None:
            return
        self._stop.clear()
        self.check_now()
        self._thread = threading.Thread(
            target=self._run,
            name="campaign-assistant-app-monitor",
            daemon=True,
        )
        self._thread.start()

    def _run(self) -> None:
        while not self._stop.wait(self._poll_seconds):
            try:
                self.check_now()
            except Exception:
                logger.exception("Protected application process check failed")

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=max(self._poll_seconds * 2, 5.0))
            self._thread = None
