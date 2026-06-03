import json

from kafka import KafkaConsumer


TOPIC_NAME = "orders"


def create_consumer():

    consumer = KafkaConsumer(
        TOPIC_NAME,
        bootstrap_servers="localhost:9092",
        group_id="order-processing-group",
        auto_offset_reset="earliest",
        value_deserializer=lambda x: json.loads(
            x.decode("utf-8")
        )
    )

    return consumer


def process_order(order):

    print("\n📦 Nueva orden recibida")
    print("-" * 40)

    print(f"Order ID   : {order['order_id']}")
    print(f"Cliente    : {order['customer_id']}")
    print(f"Producto   : {order['product']}")
    print(f"Cantidad   : {order['quantity']}")
    print(f"Total      : ${order['total']}")

    print("-" * 40)


def main():

    consumer = create_consumer()

    print("Consumer iniciado...")
    print("Esperando eventos...\n")

    try:

        for message in consumer:

            process_order(message.value)

            print(
                f"Partition={message.partition} "
                f"Offset={message.offset}"
            )

    except KeyboardInterrupt:

        print("\nConsumer detenido")

    finally:

        consumer.close()


if __name__ == "__main__":
    main()