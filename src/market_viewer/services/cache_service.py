from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd


class CacheService:
    def __init__(self, root: str = ".cache/market_viewer") -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def load_dataframe(self, namespace: str, key: str, max_age: timedelta) -> pd.DataFrame | None:
        path = self._path(namespace, key)
        if not path.exists():
            return None
        modified = datetime.fromtimestamp(path.stat().st_mtime)
        if datetime.now() - modified > max_age:
            return None
        try:
            frame = pd.read_pickle(path)
        except Exception:
            return None
        return frame.copy()

    def store_dataframe(self, namespace: str, key: str, frame: pd.DataFrame) -> None:
        path = self._path(namespace, key)
        path.parent.mkdir(parents=True, exist_ok=True)
        frame.to_pickle(path)

    def _path(self, namespace: str, key: str) -> Path:
        safe_namespace = namespace.replace("/", "_")
        safe_key = key.replace("/", "_").replace(":", "_")
        return self.root / safe_namespace / f"{safe_key}.pkl"
