import json
import time

from kafka import KafkaProducer


TOPIC_NAME = "orders"


def create_producer():
    """
    Crea conexión con Kafka.
    """

    return KafkaProducer(
        bootstrap_servers="localhost:9092",
        value_serializer=lambda v: json.dumps(v).encode("utf-8")
    )


def create_order(order_id: int):
    """
    Genera una orden de ejemplo.
    """

    return {
        "order_id": order_id,
        "customer_id": f"customer-{order_id % 10}",
        "product": f"product-{order_id % 5}",
        "quantity": (order_id % 3) + 1,
        "total": round(((order_id % 3) + 1) * 10.99, 2),
        "timestamp": time.time()
    }


def send_order(producer, order):
    """
    Envía una orden al topic.
    """

    producer.send(
        TOPIC_NAME,
        key=str(order["order_id"]).encode("utf-8"),
        value=order
    )

    print(
        f"✅ Orden enviada -> "
        f"ID={order['order_id']} "
        f"Producto={order['product']}"
    )


def main():

    producer = create_producer()

    try:

        print("Producer iniciado...\n")

        for order_id in range(1, 11):

            order = create_order(order_id)

            send_order(producer, order)

            time.sleep(1)

    finally:

        producer.flush()
        producer.close()

        print("\nProducer finalizado")


if __name__ == "__main__":
    main()