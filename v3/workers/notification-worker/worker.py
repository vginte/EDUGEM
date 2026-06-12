"""
Consumer paralelo (otro group_id): demuestra multiples consumidores en el mismo topic.

Como EDA/consumer_notifications.py pero integrado a la tienda v2.
"""

import json
import logging
import os
import time

from kafka import KafkaConsumer
from kafka.errors import NoBrokersAvailable

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("notification-worker")

KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
KAFKA_TOPIC = os.getenv("KAFKA_TOPIC", "store-events")
KAFKA_GROUP = os.getenv("KAFKA_GROUP_ID", "notification-worker-group")


def wait_for_kafka() -> KafkaConsumer:
    while True:
        try:
            consumer = KafkaConsumer(
                KAFKA_TOPIC,
                bootstrap_servers=KAFKA_BOOTSTRAP,
                group_id=KAFKA_GROUP,
                auto_offset_reset="earliest",
                value_deserializer=lambda x: json.loads(x.decode("utf-8")),
            )
            logger.info("Conectado a Kafka %s topic=%s", KAFKA_BOOTSTRAP, KAFKA_TOPIC)
            return consumer
        except NoBrokersAvailable:
            logger.warning("Esperando Kafka...")
            time.sleep(3)


def notify(event: dict) -> None:
    event_type = event.get("event_type", "unknown")
    order_id = event.get("order_id", "n/a")
    customer = event.get("customer_name", event.get("customer_id", "cliente"))

    request_id = event.get("request_id", "-")
    if event_type == "order.created":
        logger.info(
            "request_id=%s EMAIL -> Hola %s, pedido %s (total: %s)",
            request_id,
            customer,
            order_id,
            event.get("total"),
        )
    elif event_type == "order.confirm":
        logger.info("EMAIL -> Pedido %s confirmado y en preparacion", order_id)
    elif event_type == "order.cancel":
        logger.info("EMAIL -> Pedido %s cancelado", order_id)
    else:
        logger.info("EMAIL -> Evento %s para pedido %s", event_type, order_id)


def main() -> None:
    consumer = wait_for_kafka()
    logger.info("notification-worker iniciado (solo simula notificaciones)")

    for message in consumer:
        notify(message.value)


if __name__ == "__main__":
    main()
