from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QObject, QRunnable, Signal


@dataclass(slots=True)
class WorkerTask:
    name: str
    payload: object


class WorkerSignals(QObject):
    finished = Signal(object)
    failed = Signal(str)
    progress = Signal(object)


class Worker(QRunnable):
    def __init__(self, fn, task_name: str, accepts_progress: bool = False) -> None:
        super().__init__()
        self.setAutoDelete(False)
        self.fn = fn
        self.task_name = task_name
        self.accepts_progress = accepts_progress
        self.signals = WorkerSignals()

    def run(self) -> None:
        try:
            if self.accepts_progress:
                result = self.fn(lambda payload: self._emit("progress", payload))
            else:
                result = self.fn()
            self._emit("finished", WorkerTask(self.task_name, result))
        except Exception as exc:
            self._emit("failed", str(exc))

    def _emit(self, signal_name: str, payload: object) -> None:
        try:
            getattr(self.signals, signal_name).emit(payload)
        except RuntimeError:
            # The app can close while a background task is still returning.
            # In that teardown window Qt may delete the signal QObject first.
            return
