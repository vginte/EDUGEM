"""
Bus de eventos in-process (monolito).

En microservicios esto se sustituye por cola (RabbitMQ, Redis Streams, etc.).
Registra eventos en JSONL para observar flujos asíncronos durante el aprendizaje.
"""

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from app.core.config import settings

logger = logging.getLogger(__name__)

EventHandler = Callable[["DomainEvent"], None]


@dataclass
class DomainEvent:
    event_type: str
    aggregate_id: str
    payload: dict = field(default_factory=dict)
    occurred_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class EventBus:
    def __init__(self) -> None:
        self._handlers: dict[str, list[EventHandler]] = {}
        self._log_path = settings.data_dir / settings.events_log_file

    def subscribe(self, event_type: str, handler: EventHandler) -> None:
        self._handlers.setdefault(event_type, []).append(handler)

    def publish(self, event: DomainEvent) -> None:
        self._append_log(event)
        logger.info("event published: %s aggregate=%s", event.event_type, event.aggregate_id)
        for handler in self._handlers.get(event.event_type, []):
            try:
                handler(event)
            except Exception:
                logger.exception("handler failed for %s", event.event_type)

    def _append_log(self, event: DomainEvent) -> None:
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        with self._log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(event), ensure_ascii=False) + "\n")


event_bus = EventBus()
