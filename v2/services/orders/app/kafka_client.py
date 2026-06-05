import json
import logging
import os
import time

from kafka import KafkaProducer
from kafka.errors import NoBrokersAvailable

logger = logging.getLogger(__name__)

KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
KAFKA_TOPIC = os.getenv("KAFKA_TOPIC", "store-events")

_producer: KafkaProducer | None = None


def get_producer() -> KafkaProducer:
    global _producer
    if _producer is not None:
        return _producer

    for attempt in range(1, 11):
        try:
            _producer = KafkaProducer(
                bootstrap_servers=KAFKA_BOOTSTRAP,
                value_serializer=lambda v: json.dumps(v).encode("utf-8"),
            )
            logger.info("Kafka producer conectado a %s", KAFKA_BOOTSTRAP)
            return _producer
        except NoBrokersAvailable:
            logger.warning("Kafka no disponible, reintento %s/10", attempt)
            time.sleep(3)

    raise RuntimeError(f"No se pudo conectar a Kafka en {KAFKA_BOOTSTRAP}")


def publish_event(event: dict) -> None:
    producer = get_producer()
    producer.send(KAFKA_TOPIC, value=event)
    producer.flush()
    logger.info("evento publicado: %s order_id=%s", event.get("event_type"), event.get("order_id"))
