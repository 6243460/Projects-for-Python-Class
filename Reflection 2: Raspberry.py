import paho.mqtt.client as mqtt
import json
import time

print("=== PROJECT THANOS CONTROLLER ===")
print("Starting...")

MQTT_BROKER = "localhost"
CLAP_TOPIC = "thanos/clap"
LED_CONTROL_TOPIC = "thanos/led/control"

def on_connect(client, userdata, flags, rc, properties=None):
    print(f"Connected with result code {rc}")
    client.subscribe(CLAP_TOPIC)
    print("✓ Waiting for claps...")

def on_message(client, userdata, msg, properties=None, reasonCodes=None):
    if msg.topic == CLAP_TOPIC:
        try:
            data = json.loads(msg.payload.decode())
            pattern = data["pattern"]
            print(f"🎯 PATTERN {pattern} DETECTED")
            
            if pattern == 1:
                print("   → Sending: LED OFF")
                client.publish(LED_CONTROL_TOPIC, "OFF")
            elif pattern == 2:
                print("   → Sending: LED ON")  
                client.publish(LED_CONTROL_TOPIC, "ON")
            elif pattern == 3:
                print("   → Sending: -50 brightness")
                client.publish(LED_CONTROL_TOPIC, "BRIGHTNESS:78")
            elif pattern == 4:
                print("   → Sending: +50 brightness")
                client.publish(LED_CONTROL_TOPIC, "BRIGHTNESS:178")
                
        except Exception as e:
            print(f"Error: {e}")

def on_disconnect(client, userdata, rc, properties=None):
    print("Disconnected from broker")

def on_subscribe(client, userdata, mid, reason_codes, properties=None):
    print(f"Subscribed to topic")

def on_publish(client, userdata, mid, reason_code, properties=None):
    print(f"Message published")

# Using VERSION2 with proper callback signatures
client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, "Windows_Controller")
client.on_connect = on_connect
client.on_message = on_message
client.on_disconnect = on_disconnect
client.on_subscribe = on_subscribe
client.on_publish = on_publish

try:
    client.connect(MQTT_BROKER, 1883, 60)
    client.loop_start()
    
    print("Controller RUNNING - Press Ctrl+C to stop")
    
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print("Stopping...")
    client.loop_stop()
    client.disconnect()
except Exception as e:
    print(f"Connection error: {e}")
