# Projects-for-Python-Class
# Project Thanos

## Team Members
- Johanna-Mae Tolentino 
- Sabrina Hassain

## Project Overview
Control an LED (on/off and brightness) using clap/snap patterns. The ESP32 processes sound sensor input and communicates with Raspberry Pi via MQTT for monitoring and control.

## Components
- Raspberry Pi 
- ESP32 WeMos Lolin D32 
- KY-037 Sound Sensor
- LED
- Resistor 220Ω
- Breadboard and jumper wires

## Schematics

![Screenshot](image.png)

## System Analysis

Which applications will handle which tasks?
KY-037 Sound Sensor: Detects sounds and send an analog signal to ESP32.
ESP32 WeMos Lolin D32: Reads input from the KY-037 sound sensor, analyzes the signal to detect clap patterns, controls the LED and publishes status messages to an MQTT topic for monitoring and communication.
Raspberry Pi: Runs the MQTT broker, subscribes to MQTT topics to receive status updates from the ESP32, provides a monitoring or a control of the LED state.


## Which conditions will lead to which results?

| **Condition / Input**                              | **Processing (by ESP32)**                                | **Result / Output**                                                            |
| -------------------------------------------------- | -------------------------------------------------------- | ------------------------------------------------------------------------------ |
| **One clap detected**                              | Pattern recognized as “single clap.”                     | ESP32 sends `LED_ON` message via MQTT → LED turns **ON**.                      |
| **Two claps detected**                             | Pattern recognized as “double clap.”                     | ESP32 sends `LED_OFF` message via MQTT → LED turns **OFF**.                    |
| **Three claps detected**                           | Pattern recognized as “triple clap.”                     | ESP32 sends `BRIGHTNESS_UP` message via MQTT → LED brightness **increases**.   |
| **Four claps detected**                            | Pattern recognized as “quadruple clap.”                  | ESP32 sends `BRIGHTNESS_DOWN` message via MQTT → LED brightness **decreases**. |
| **No sound detected**                              | Idle state.                                              | LED maintains previous state (no change).                                      |
| **Command sent from Raspberry Pi**                 | Publishes override message.                              | ESP32 receives MQTT message and updates LED                                    |
