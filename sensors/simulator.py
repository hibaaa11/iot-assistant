import json
import random
import time
from datetime import datetime, timezone

import paho.mqtt.client as mqtt

# --- Configuration (must match the README) ---
GROUPE = "groupe_XX"          # <-- put your real group name here
PREFIX = f"tdia2/{GROUPE}"
BROKER = "localhost"
PORT = 1883
MACHINES = ["machine_1", "machine_2", "machine_3"]

# Normal behaviour of each sensor: (average, noise)
NORMAL = {
    "temperature": (65.0, 2.0),    # degrees C
    "vibration":   (2.0, 0.3),     # mm/s
    "courant":     (12.0, 0.8),    # amperes
}

# Probability per reading of an anomaly, and how it changes the value
ANOMALY_PROB = 0.01
ANOMALY_BOOST = {
    "temperature": 25.0,
    "vibration":   4.0,
    "courant":     6.0,
}


def read_sensor(sensor):
    mean, noise = NORMAL[sensor]
    value = random.gauss(mean, noise)
    if random.random() < ANOMALY_PROB:
        value += ANOMALY_BOOST[sensor]
    return round(value, 2)


def main():
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.connect(BROKER, PORT)
    client.loop_start()
    print(f"Publishing on {PREFIX}/... (Ctrl+C to stop)")

    try:
        while True:
            now = datetime.now(timezone.utc).isoformat()
            for machine in MACHINES:
                for sensor in NORMAL:
                    topic = f"{PREFIX}/{machine}/{sensor}"
                    payload = json.dumps({"temps": now, "valeur": read_sensor(sensor)})
                    client.publish(topic, payload)
            time.sleep(1)
    except KeyboardInterrupt:
        print("Stopped.")
    finally:
        client.loop_stop()
        client.disconnect()


if __name__ == "__main__":
    main()
    