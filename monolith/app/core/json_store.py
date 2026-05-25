"""Persistencia en archivos JSON (simula BD por dominio — base para 'database per service')."""

import json
import threading
from pathlib import Path
from typing import Any, Generic, TypeVar

T = TypeVar("T")


class JsonStore(Generic[T]):
    """Lectura/escritura atómica simple sobre un archivo JSON."""

    def __init__(self, path: Path, default: T):
        self._path = path
        self._default = default
        self._lock = threading.Lock()

    def _ensure_file(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        if not self._path.exists():
            self._path.write_text(
                json.dumps(self._default, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )

    def _load(self) -> T:
        self._ensure_file()
        return json.loads(self._path.read_text(encoding="utf-8"))

    def _save(self, data: T) -> None:
        self._path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def read(self) -> T:
        with self._lock:
            return self._load()

    def write(self, data: T) -> None:
        with self._lock:
            self._save(data)

    def update(self, mutator: Any) -> T:
        with self._lock:
            data = self._load()
            mutator(data)
            self._save(data)
            return data
