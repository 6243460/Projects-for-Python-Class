from flask import Flask, render_template, jsonify, request
import paho.mqtt.client as mqtt
import json
import threading
import time
from datetime import datetime, timedelta

app = Flask(__name__)

# MQTT Configuration
MQTT_BROKER = "localhost"
MQTT_PORT = 1883

# System state
system_state = {
    "led_status": "OFF",
    "brightness": 0,
    "clap_pattern": 0,
    "last_clap_time": "Never",
    "mic_level": 0,
    "esp32_connected": False,
    "clap_history": [],
    "last_esp32_heartbeat": None
}

# MQTT Client Setup
mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, "Web_Interface")

def on_connect(client, userdata, flags, rc, properties=None):
    print(f"Web Interface connected to MQTT with code {rc}")
    client.subscribe("thanos/clap")
    client.subscribe("thanos/led/status")
    client.subscribe("thanos/system/esp32")
    client.subscribe("thanos/heartbeat")  # Add heartbeat topic

def on_message(client, userdata, msg, properties=None):
    topic = msg.topic
    payload = msg.payload.decode()
    
    try:
        if topic == "thanos/clap":
            data = json.loads(payload)
            pattern = data.get("pattern", 0)
            system_state["clap_pattern"] = pattern
            system_state["last_clap_time"] = time.strftime("%H:%M:%S")
            
            # Add to history
            system_state["clap_history"].insert(0, {
                "time": system_state["last_clap_time"],
                "pattern": pattern
            })
            # Keep only last 10 events
            system_state["clap_history"] = system_state["clap_history"][:10]
            
            print(f"🎯 Clap pattern {pattern} detected at {system_state['last_clap_time']}")
            
        elif topic == "thanos/led/status":
            if payload == "ON":
                system_state["led_status"] = "ON"
                system_state["brightness"] = 100
            elif payload == "OFF":
                system_state["led_status"] = "OFF" 
                system_state["brightness"] = 0
            elif payload.startswith("BRIGHTNESS:"):
                brightness = int(payload.split(":")[1])
                system_state["brightness"] = int((brightness / 255) * 100)
                system_state["led_status"] = "ON" if brightness > 0 else "OFF"
                
        elif topic == "thanos/system/esp32":
            if payload == "online":
                system_state["esp32_connected"] = True
                system_state["last_esp32_heartbeat"] = datetime.now()
            elif payload == "offline":
                system_state["esp32_connected"] = False
                
        elif topic == "thanos/heartbeat":
            # ESP32 sends regular heartbeat to show it's alive
            system_state["esp32_connected"] = True
            system_state["last_esp32_heartbeat"] = datetime.now()
           print(f"💓 ESP32 heartbeat received")
                
    except Exception as e:
        print(f"Error processing MQTT message: {e}")

def check_esp32_connection():
    """Check if ESP32 is still connected based on last heartbeat"""
    if system_state["last_esp32_heartbeat"] is None:
        return False
    
    # If no heartbeat in last 10 seconds, consider ESP32 disconnected
    time_since_heartbeat = datetime.now() - system_state["last_esp32_heartbeat"]
    if time_since_heartbeat > timedelta(seconds=10):
        system_state["esp32_connected"] = False
        return False
    
    return True

def connection_monitor():
    """Background thread to monitor ESP32 connection"""
    while True:
        check_esp32_connection()
        time.sleep(5)  # Check every 5 seconds

def start_mqtt_client():
    mqtt_client.on_connect = on_connect
    mqtt_client.on_message = on_message
    mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
    mqtt_client.loop_start()

# Flask Routes
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/status')
def get_status():
    # Update connection status before sending response
    system_state["esp32_connected"] = check_esp32_connection()
    return jsonify(system_state)

@app.route('/api/control', methods=['POST'])
def control_led():
    data = request.json
    command = data.get('command')
    brightness = data.get('brightness')
    
    if command == "on":
        mqtt_client.publish("thanos/led/control", "ON")
        print("Web: LED ON")
    elif command == "off":
        mqtt_client.publish("thanos/led/control", "OFF")
        print("Web: LED OFF")
    elif command == "brightness" and brightness is not None:
        pwm_value = int((brightness / 100) * 255)
        mqtt_client.publish("thanos/led/control", f"BRIGHTNESS:{pwm_value}")
        print(f"Web: Brightness {brightness}%")
    
    return jsonify({"status": "success"})

@app.route('/api/clap_test', methods=['POST'])
def simulate_clap():
    data = request.json
    pattern = data.get('pattern', 1)
    
    print(f"🎯 Web: Simulating clap pattern {pattern}")
    
    # Forward the clap pattern to ESP32 via MQTT
    clap_message = json.dumps({"pattern": pattern, "source": "web"})
    mqtt_client.publish("thanos/clap", clap_message)
    
    # Also update the system state locally for immediate feedback
    system_state["clap_pattern"] = pattern
    system_state["last_clap_time"] = time.strftime("%H:%M:%S")
    
    # Add to history
    system_state["clap_history"].insert(0, {
        "time": system_state["last_clap_time"],
        "pattern": pattern
    })
    # Keep only last 10 events
    system_state["clap_history"] = system_state["clap_history"][:10]
    
    # Trigger LED actions based on clap pattern
    if pattern == 1:
        # Toggle LED
        if system_state["led_status"] == "ON":
            mqtt_client.publish("thanos/led/control", "OFF")
            system_state["led_status"] = "OFF"
            system_state["brightness"] = 0
        else:
            mqtt_client.publish("thanos/led/control", "ON")
            system_state["led_status"] = "ON"
            system_state["brightness"] = 100
            
    elif pattern == 2:
        # Decrease brightness
        new_brightness = max(0, system_state["brightness"] - 50)
        pwm_value = int((new_brightness / 100) * 255)
        mqtt_client.publish("thanos/led/control", f"BRIGHTNESS:{pwm_value}")
        system_state["brightness"] = new_brightness
        system_state["led_status"] = "ON" if new_brightness > 0 else "OFF"
        
    elif pattern == 3:
        # Increase brightness
        new_brightness = min(100, system_state["brightness"] + 50)
        pwm_value = int((new_brightness / 100) * 255)
        mqtt_client.publish("thanos/led/control", f"BRIGHTNESS:{pwm_value}")
        system_state["brightness"] = new_brightness
        system_state["led_status"] = "ON"
        
    elif pattern == 4:
        # Max brightness
        mqtt_client.publish("thanos/led/control", "BRIGHTNESS:255")
        system_state["brightness"] = 100
        system_state["led_status"] = "ON"
    
    return jsonify({"status": f"Simulated clap pattern {pattern}"})

if __name__ == '__main__':
    # Start MQTT client in background thread
    mqtt_thread = threading.Thread(target=start_mqtt_client)
    mqtt_thread.daemon = True
    mqtt_thread.start()
    
    # Start connection monitor thread
    monitor_thread = threading.Thread(target=connection_monitor)
    monitor_thread.daemon = True
    monitor_thread.start()
    
    print("=== PROJECT THANOS WEB INTERFACE ===")
    print("Starting web server on http://0.0.0.0:5000")
    print("Access from any device on your network!")
    
    app.run(host='0.0.0.0', port=5000, debug=False)
