from __future__ import annotations


class RequestGate:
    def __init__(self) -> None:
        self._sequence = 0
        self._active: dict[str, int] = {}

    def begin(self, channel: str) -> int:
        self._sequence += 1
        request_id = self._sequence
        self._active[channel] = request_id
        return request_id

    def is_current(self, channel: str, request_id: int) -> bool:
        return self._active.get(channel) == request_id

    def current(self, channel: str) -> int:
        return self._active.get(channel, 0)
