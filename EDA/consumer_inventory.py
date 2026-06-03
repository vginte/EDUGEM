import json
from kafka import KafkaConsumer

consumer = KafkaConsumer(
    "orders",
    bootstrap_servers="localhost:9092",
    group_id="inventory-group",
    auto_offset_reset="earliest",
    value_deserializer=lambda x: json.loads(x.decode("utf-8"))
)

print("📦 Servicio Inventario iniciado")

for message in consumer:
    order = message.value

    print(
        f"Actualizando inventario para "
        f"{order['product']}"
    )