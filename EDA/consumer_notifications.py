import json
from kafka import KafkaConsumer

consumer = KafkaConsumer(
    "orders",
    bootstrap_servers="localhost:9092",
    group_id="notification-group",
    auto_offset_reset="earliest",
    value_deserializer=lambda x: json.loads(x.decode("utf-8"))
)

print("📧 Servicio Notificaciones iniciado")

for message in consumer:
    order = message.value

    print(
        f"Enviando correo para la orden "
        f"{order['order_id']}"
    )