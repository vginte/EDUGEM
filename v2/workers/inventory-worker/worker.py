"""
Consumer EDA: lee eventos de Kafka y llama inventory-service por HTTP.

Patron educativo del curso:
  API publica mensaje -> consumer hace llamado a la siguiente API
"""

import json
import logging
import os
import time

import httpx
from kafka import KafkaConsumer
from kafka.errors import NoBrokersAvailable

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("inventory-worker")

KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
KAFKA_TOPIC = os.getenv("KAFKA_TOPIC", "store-events")
KAFKA_GROUP = os.getenv("KAFKA_GROUP_ID", "inventory-worker-group")
INVENTORY_URL = os.getenv("INVENTORY_BASE_URL", "http://localhost:8002")
ORDERS_URL = os.getenv("ORDERS_BASE_URL", "http://localhost:8004")


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


def patch_order_status(client: httpx.Client, order_id: str, status: str, inventory_status: str) -> None:
    client.patch(
        f"{ORDERS_URL}/orders/{order_id}/status",
        json={"status": status, "inventory_status": inventory_status},
    )


def handle_order_created(client: httpx.Client, event: dict) -> None:
    order_id = event["order_id"]
    logger.info("order.created -> reservar stock order_id=%s", order_id)

    try:
        for item in event["items"]:
            resp = client.post(
                f"{INVENTORY_URL}/stock/reserve",
                json={"product_id": item["product_id"], "quantity": item["quantity"]},
            )
            resp.raise_for_status()
            logger.info("  POST /stock/reserve %s x%s OK", item["product_id"], item["quantity"])

        patch_order_status(client, order_id, "pending", "reserved")
        logger.info("order.created completado order_id=%s", order_id)

    except httpx.HTTPError as exc:
        logger.error("Fallo al reservar order_id=%s: %s", order_id, exc)
        patch_order_status(client, order_id, "failed", "reserve_failed")


def handle_order_confirm(client: httpx.Client, event: dict) -> None:
    order_id = event["order_id"]
    logger.info("order.confirm -> commit stock order_id=%s", order_id)

    try:
        for item in event["items"]:
            resp = client.post(
                f"{INVENTORY_URL}/stock/commit",
                json={"product_id": item["product_id"], "quantity": item["quantity"]},
            )
            resp.raise_for_status()
            logger.info("  POST /stock/commit %s x%s OK", item["product_id"], item["quantity"])

        patch_order_status(client, order_id, "confirmed", "committed")
        logger.info("order.confirm completado order_id=%s", order_id)

    except httpx.HTTPError as exc:
        logger.error("Fallo al confirmar order_id=%s: %s", order_id, exc)
        patch_order_status(client, order_id, "failed", "commit_failed")


def handle_order_cancel(client: httpx.Client, event: dict) -> None:
    order_id = event["order_id"]
    logger.info("order.cancel -> liberar stock order_id=%s", order_id)

    for item in event["items"]:
        try:
            client.post(
                f"{INVENTORY_URL}/stock/release",
                json={"product_id": item["product_id"], "quantity": item["quantity"]},
            )
            logger.info("  POST /stock/release %s x%s OK", item["product_id"], item["quantity"])
        except httpx.HTTPError as exc:
            logger.error("Fallo release %s: %s", item["product_id"], exc)

    patch_order_status(client, order_id, "cancelled", "released")
    logger.info("order.cancel completado order_id=%s", order_id)


def process_event(client: httpx.Client, event: dict) -> None:
    handlers = {
        "order.created": handle_order_created,
        "order.confirm": handle_order_confirm,
        "order.cancel": handle_order_cancel,
    }
    event_type = event.get("event_type")
    handler = handlers.get(event_type)
    if handler:
        handler(client, event)
    else:
        logger.warning("Evento desconocido: %s", event_type)


def main() -> None:
    consumer = wait_for_kafka()
    logger.info("inventory-worker iniciado (consumer -> inventory API)")

    with httpx.Client(timeout=10.0) as client:
        for message in consumer:
            event = message.value
            logger.info(
                "Mensaje recibido partition=%s offset=%s type=%s",
                message.partition,
                message.offset,
                event.get("event_type"),
            )
            process_event(client, event)


if __name__ == "__main__":
    main()
