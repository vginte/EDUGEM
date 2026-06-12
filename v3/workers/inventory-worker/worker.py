"""
inventory-worker v3: retry + DLQ + X-Request-ID en logs.
"""

import json
import logging
import os
import time

import httpx
from kafka import KafkaConsumer, KafkaProducer
from kafka.errors import NoBrokersAvailable

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("inventory-worker")

KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
KAFKA_TOPIC = os.getenv("KAFKA_TOPIC", "store-events")
KAFKA_DLQ_TOPIC = os.getenv("KAFKA_DLQ_TOPIC", "store-events-dlq")
KAFKA_GROUP = os.getenv("KAFKA_GROUP_ID", "inventory-worker-group")
INVENTORY_URL = os.getenv("INVENTORY_BASE_URL", "http://localhost:8002")
ORDERS_URL = os.getenv("ORDERS_BASE_URL", "http://localhost:8004")
HTTP_RETRIES = int(os.getenv("HTTP_RETRIES", "3"))
HTTP_TIMEOUT = float(os.getenv("HTTP_TIMEOUT", "10"))


def wait_for_kafka_consumer() -> KafkaConsumer:
    while True:
        try:
            return KafkaConsumer(
                KAFKA_TOPIC,
                bootstrap_servers=KAFKA_BOOTSTRAP,
                group_id=KAFKA_GROUP,
                auto_offset_reset="earliest",
                value_deserializer=lambda x: json.loads(x.decode("utf-8")),
            )
        except NoBrokersAvailable:
            logger.warning("Esperando Kafka...")
            time.sleep(3)


def create_dlq_producer() -> KafkaProducer:
    while True:
        try:
            return KafkaProducer(
                bootstrap_servers=KAFKA_BOOTSTRAP,
                value_serializer=lambda v: json.dumps(v).encode("utf-8"),
            )
        except NoBrokersAvailable:
            time.sleep(3)


def publish_dlq(producer: KafkaProducer, event: dict, error: str) -> None:
    payload = {**event, "dlq_reason": error, "dlq_at": time.time()}
    producer.send(KAFKA_DLQ_TOPIC, value=payload)
    producer.flush()
    logger.error("Evento enviado a DLQ topic=%s order_id=%s", KAFKA_DLQ_TOPIC, event.get("order_id"))


def http_post_with_retry(client: httpx.Client, url: str, payload: dict, request_id: str) -> None:
    headers = {"X-Request-ID": request_id}
    last_error: Exception | None = None
    for attempt in range(1, HTTP_RETRIES + 1):
        try:
            resp = client.post(url, json=payload, headers=headers, timeout=HTTP_TIMEOUT)
            resp.raise_for_status()
            return
        except httpx.HTTPError as exc:
            last_error = exc
            logger.warning("request_id=%s retry %s/%s %s", request_id, attempt, HTTP_RETRIES, exc)
            time.sleep(0.5 * attempt)
    raise last_error  # type: ignore[misc]


def patch_order_status(client: httpx.Client, order_id: str, status: str, inventory_status: str, request_id: str) -> None:
    client.patch(
        f"{ORDERS_URL}/orders/{order_id}/status",
        json={"status": status, "inventory_status": inventory_status},
        headers={"X-Request-ID": request_id},
        timeout=HTTP_TIMEOUT,
    )


def handle_order_created(client: httpx.Client, producer: KafkaProducer, event: dict) -> None:
    order_id = event["order_id"]
    request_id = event.get("request_id", order_id)
    logger.info("request_id=%s order.created -> reserve order_id=%s", request_id, order_id)

    try:
        for item in event["items"]:
            http_post_with_retry(
                client,
                f"{INVENTORY_URL}/stock/reserve",
                {"product_id": item["product_id"], "quantity": item["quantity"]},
                request_id,
            )
        patch_order_status(client, order_id, "pending", "reserved", request_id)
    except httpx.HTTPError as exc:
        patch_order_status(client, order_id, "failed", "reserve_failed", request_id)
        publish_dlq(producer, event, str(exc))


def handle_order_confirm(client: httpx.Client, producer: KafkaProducer, event: dict) -> None:
    order_id = event["order_id"]
    request_id = event.get("request_id", order_id)
    logger.info("request_id=%s order.confirm -> commit order_id=%s", request_id, order_id)

    try:
        for item in event["items"]:
            http_post_with_retry(
                client,
                f"{INVENTORY_URL}/stock/commit",
                {"product_id": item["product_id"], "quantity": item["quantity"]},
                request_id,
            )
        patch_order_status(client, order_id, "confirmed", "committed", request_id)
    except httpx.HTTPError as exc:
        patch_order_status(client, order_id, "failed", "commit_failed", request_id)
        publish_dlq(producer, event, str(exc))


def handle_order_cancel(client: httpx.Client, event: dict) -> None:
    order_id = event["order_id"]
    request_id = event.get("request_id", order_id)
    for item in event["items"]:
        try:
            http_post_with_retry(
                client,
                f"{INVENTORY_URL}/stock/release",
                {"product_id": item["product_id"], "quantity": item["quantity"]},
                request_id,
            )
        except httpx.HTTPError as exc:
            logger.error("request_id=%s release failed: %s", request_id, exc)
    patch_order_status(client, order_id, "cancelled", "released", request_id)


def process_event(client: httpx.Client, producer: KafkaProducer, event: dict) -> None:
    handlers = {
        "order.created": lambda: handle_order_created(client, producer, event),
        "order.confirm": lambda: handle_order_confirm(client, producer, event),
        "order.cancel": lambda: handle_order_cancel(client, event),
    }
    handler = handlers.get(event.get("event_type", ""))
    if handler:
        handler()
    else:
        logger.warning("Evento desconocido: %s", event.get("event_type"))


def main() -> None:
    consumer = wait_for_kafka_consumer()
    dlq_producer = create_dlq_producer()
    logger.info("inventory-worker v3 (retry + DLQ) iniciado")

    with httpx.Client(timeout=HTTP_TIMEOUT) as client:
        for message in consumer:
            event = message.value
            logger.info(
                "request_id=%s event=%s partition=%s offset=%s",
                event.get("request_id", "-"),
                event.get("event_type"),
                message.partition,
                message.offset,
            )
            process_event(client, dlq_producer, event)


if __name__ == "__main__":
    main()
