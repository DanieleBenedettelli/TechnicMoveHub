# LEGO Technic Move Hub ESP32 Bridge

A standalone ESP32 BLE bridge for controlling modern LEGO® Technic Powered Up vehicles without a smartphone.

Tested with LEGO® Technic set 42176 and the new USB-C Technic Move Hub (`103479c01`), which is currently not supported by Pybricks.

This project uses a TinyPICO ESP32 running MicroPython to connect a LEGO Powered Up Remote Control (`88010`) directly to the LEGO Technic Move Hub via BLE.

---

# Features

- Smartphone-free operation
- Works with modern USB-C LEGO Technic Move Hubs
- Uses original LEGO hardware only
- Automatic BLE pairing
- Automatic remote renaming
- 3 selectable driving speed levels
- Steering calibration on startup
- Vehicle light control
- Deep sleep power-off mode
- TinyPICO RGB status LED support
- LEGO hub light feedback for speed levels

---

# Tested Hardware

## ESP32 Board

- TinyPICO ESP32

## LEGO Components

- LEGO Powered Up Remote Control 88010
- LEGO Technic Move Hub (`103479c01`)
- LEGO Technic 42176 Porsche GT4 e-Performance

---

# Firmware Requirements

## ESP32 Firmware

This project requires the dedicated TinyPICO MicroPython firmware:

- `UM_TINYPICO`

Download:

https://micropython.org/download/UM_TINYPICO/

Tested with:

```text
MicroPython v1.28.0 on 2026-04-06
TinyPICO with ESP32-PICO-D4