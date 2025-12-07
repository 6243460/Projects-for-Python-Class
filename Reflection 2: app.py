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

# Track if web initiated the command (to avoid slider bouncing)
last_web_command_time = 0
web_command_cooldown = 0.5  # 500ms cooldown

# MQTT Client Setup
mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, "RaspberryPi_Controller")

def on_connect(client, userdata, flags, rc, properties=None):
    print(f"Raspberry Pi connected to MQTT with code {rc}")
    # Subscribe to topics from ESP32
    client.subscribe("thanos/clap/detected")
    client.subscribe("thanos/esp32/heartbeat")
    client.subscribe("thanos/led/status")  # For LED status feedback from ESP32

def on_message(client, userdata, msg, properties=None):
    topic = msg.topic
    payload = msg.payload.decode()
    
    try:
        # ESP32 sends detected clap patterns
        if topic == "thanos/clap/detected":
            data = json.loads(payload)
            pattern = data.get("pattern", 0)
            mic_value = data.get("mic_value", 0)
            
            print(f"🎯 Clap pattern {pattern} detected from ESP32 (mic: {mic_value})")
            
            # Update system state
            system_state["clap_pattern"] = pattern
            system_state["last_clap_time"] = time.strftime("%H:%M:%S")
            system_state["mic_level"] = mic_value
            
            # Add to history
            system_state["clap_history"].insert(0, {
                "time": system_state["last_clap_time"],
                "pattern": pattern,
                "source": "esp32"
            })
            # Keep only last 10 events
            system_state["clap_history"] = system_state["clap_history"][:10]
            
            # Raspberry Pi decides what to do with the clap pattern
            handle_clap_pattern(pattern)
            
        # LED status feedback from ESP32 (CRITICAL FOR SLIDER SYNC)
        elif topic == "thanos/led/status":
            current_time = time.time()
            # Only update if not recently commanded by web (to avoid feedback loop)
            if current_time - last_web_command_time > web_command_cooldown:
                if payload == "ON":
                    system_state["led_status"] = "ON"
                    system_state["brightness"] = 100
                    print("ESP32 feedback: LED is ON (brightness: 100%)")
                elif payload == "OFF":
                    system_state["led_status"] = "OFF"
                    system_state["brightness"] = 0
                    print("ESP32 feedback: LED is OFF (brightness: 0%)")
                elif payload.startswith("BRIGHTNESS:"):
                    brightness = int(payload.split(":")[1])
                    # Convert 0-255 PWM to 0-100 percentage
                    system_state["brightness"] = int((brightness / 255) * 100)
                    system_state["led_status"] = "ON" if brightness > 0 else "OFF"
                    print(f"ESP32 feedback: Brightness {system_state['brightness']}%")
            
        # Heartbeat from ESP32
        elif topic == "thanos/esp32/heartbeat":
            system_state["esp32_connected"] = True
            system_state["last_esp32_heartbeat"] = datetime.now()
            print(f"💓 ESP32 heartbeat received")
                
    except Exception as e:
        print(f"Error processing MQTT message: {e}")

def handle_clap_pattern(pattern):
    """Raspberry Pi handles clap patterns and controls ESP32"""
    if pattern == 1:
        # Toggle LED
        if system_state["led_status"] == "ON":
            control_led("off", source="clap")
        else:
            control_led("on", source="clap")
            
    elif pattern == 2:
        # Decrease brightness by 25%
        new_brightness = max(0, system_state["brightness"] - 25)
        control_brightness(new_brightness, source="clap")
        
    elif pattern == 3:
        # Increase brightness by 25%
        new_brightness = min(100, system_state["brightness"] + 25)
        control_brightness(new_brightness, source="clap")
        
    elif pattern == 4:
        # Max brightness
        control_brightness(100, source="clap")

def control_led(command, source="web"):
    """Send LED control command to ESP32"""
    global last_web_command_time
    
    if source == "web":
        last_web_command_time = time.time()
        # Update state immediately for responsive UI
        if command == "on":
            system_state["led_status"] = "ON"
            system_state["brightness"] = 100
        elif command == "off":
            system_state["led_status"] = "OFF"
            system_state["brightness"] = 0
    
    if command == "on":
        mqtt_client.publish("thanos/led/command", "ON")
        print(f"Pi: LED ON command sent (source: {source})")
    elif command == "off":
        mqtt_client.publish("thanos/led/command", "OFF")
        print(f"Pi: LED OFF command sent (source: {source})")

def control_brightness(brightness, source="web"):
    """Send brightness command to ESP32"""
    global last_web_command_time
    
    if source == "web":
        last_web_command_time = time.time()
        # Update state immediately for responsive UI
        system_state["brightness"] = brightness
        system_state["led_status"] = "ON" if brightness > 0 else "OFF"
    
    pwm_value = int((brightness / 100) * 255)
    mqtt_client.publish("thanos/led/command", f"BRIGHTNESS:{pwm_value}")
    print(f"Pi: Brightness {brightness}% command sent (source: {source})")

def check_esp32_connection():
    """Check if ESP32 is still connected based on last heartbeat"""
    if system_state["last_esp32_heartbeat"] is None:
        return False
    
    time_since_heartbeat = datetime.now() - system_state["last_esp32_heartbeat"]
    if time_since_heartbeat > timedelta(seconds=10):
        system_state["esp32_connected"] = False
        return False
    
    return True

def connection_monitor():
    """Background thread to monitor ESP32 connection"""
    while True:
        check_esp32_connection()
        time.sleep(5)

def start_mqtt_client():
    mqtt_client.on_connect = on_connect
    mqtt_client.on_message = on_message
    mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
    mqtt_client.loop_start()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/status')
def get_status():
    system_state["esp32_connected"] = check_esp32_connection()
    return jsonify(system_state)

@app.route('/api/control', methods=['POST'])
def web_control_led():
    """Web interface controls LED through Raspberry Pi"""
    data = request.json
    command = data.get('command')
    brightness = data.get('brightness')
    
    if command == "on":
        control_led("on", source="web")
    elif command == "off":
        control_led("off", source="web")
    elif command == "brightness" and brightness is not None:
        control_brightness(int(brightness), source="web")
    
    return jsonify({"status": "success"})

@app.route('/api/clap_test', methods=['POST'])
def simulate_clap():
    """Web interface can simulate claps (handled by Pi)"""
    data = request.json
    pattern = data.get('pattern', 1)
    
    print(f"🎯 Web: Simulating clap pattern {pattern}")
    
    # Add to history
    system_state["clap_history"].insert(0, {
        "time": time.strftime("%H:%M:%S"),
        "pattern": pattern,
        "source": "web"
    })
    system_state["clap_history"] = system_state["clap_history"][:10]
    
    # Raspberry Pi handles the pattern
    handle_clap_pattern(pattern)
    
    return jsonify({"status": f"Simulated clap pattern {pattern}"})

if __name__ == '__main__':
    # Start MQTT client
    mqtt_thread = threading.Thread(target=start_mqtt_client)
    mqtt_thread.daemon = True
    mqtt_thread.start()
    
    # Start connection monitor
    monitor_thread = threading.Thread(target=connection_monitor)
    monitor_thread.daemon = True
    monitor_thread.start()
    
    print("=== RASPBERRY PI CONTROLLER ===")
    print("Central control system started")
    print("Web interface: http://0.0.0.0:5000")
    print("ESP32 sends claps -> Pi processes -> Pi controls ESP32")
    print("Sensor values are printed to ESP32 Serial Monitor")
    print("Slider now syncs properly with LED state")
    
    app.run(host='0.0.0.0', port=5000, debug=False)
