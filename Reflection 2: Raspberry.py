import json
import paho.mqtt.client as mqtt

MQTT_SERVER = "192.168.51.183"    # Your Raspberry Pi's IP
MQTT_PORT   = 1883
MQTT_SUB    = "thanos/clap_data"   # ESP32 → RPi
MQTT_PUB    = "thanos/led_cmd"     # RPi → ESP32


#MAP AVERAGE CLAP PERIOD TO BRIGHTNESS

def map_period_to_brightness(avg_period):
    # Define expected clap-speed window (seconds)
    MIN_T = 0.05     # Fastest human clap interval
    MAX_T = 0.80     # Slowest 3–4 clap pattern

    # Clap value
    avg_period = max(MIN_T, min(avg_period, MAX_T))

    # Map inverse: fast claps → brighter LED
    brightness = int(255 * (1 - ((avg_period - MIN_T) / (MAX_T - MIN_T))))
    return max(0, min(brightness, 255))

# MQTT HANDLERS
def on_connect(client, userdata, flags, rc):
    print("Connected to MQTT with code", rc)
    client.subscribe(MQTT_SUB)
    print(f"Subscribed to: {MQTT_SUB}")


def on_message(client, userdata, msg):
    print(f"\nReceived from ESP32: {msg.payload.decode()}")

    try:
        data = json.loads(msg.payload.decode())
        pattern = data.get("pattern")
        avg_period = data.get("average_period", 0)

    except Exception as e:
        print("❌ ERROR decoding JSON:", e)
        return


    # LED CONTROL LOGIC

    command = {}

    if pattern == 1:
        print("→ 1 clap → LED OFF")
        command = {"action": "OFF"}

    elif pattern == 2:
        print("→ 2 claps → LED ON")
        command = {"action": "ON"}

    elif pattern == 3:
        brightness = map_period_to_brightness(avg_period)
        print(f"→ 3 claps → Set brightness = {brightness}")
        command = {"action": "BRIGHTNESS", "value": brightness}

    elif pattern == 4:
        brightness = map_period_to_brightness(avg_period)
        print(f"→ 4 claps → Alternate brightness = {brightness}")
        command = {"action": "BRIGHTNESS", "value": brightness}

    else:
        print("Unknown pattern — ignoring")
        return


    # Publish LED command to ESP32

    client.publish(MQTT_PUB, json.dumps(command))
    print(f"Sent → {command}")



# MAIN PROGRAM

client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message

print("Connecting to MQTT…")
client.connect(MQTT_SERVER, MQTT_PORT, 60)

print("Running Raspberry Pi controller...")
client.loop_forever()
