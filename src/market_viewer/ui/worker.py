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


class Worker(QRunnable):
    def __init__(self, fn, task_name: str) -> None:
        super().__init__()
        self.fn = fn
        self.task_name = task_name
        self.signals = WorkerSignals()

    def run(self) -> None:
        try:
            result = self.fn()
            self.signals.finished.emit(WorkerTask(self.task_name, result))
        except Exception as exc:
            self.signals.failed.emit(str(exc))
