# LEGO Technic Move Hub 88019 Control Protocol

This document describes the communication protocol for controlling the LEGO Technic Move Hub 88019 included in the LEGO Technic set 42176 Porsche GT4 e-performance. The hub must be connected and paired using the specified UUIDs and in the security mode detailed below.

## Connection Details

### Hub Name
- **Technic Move**

### Service and Characteristic UUIDs
- **Service UUID**: `00001623-1212-EFDE-1623-785FEABCD123`
- **Characteristic UUID**: `00001624-1212-EFDE-1623-785FEABCD123`

### Security Mode
Your application must pair with the hub in security mode 1 level 2, which involves unauthenticated encrypted communication.

## Commands

### Calibrating the Steering
To calibrate the steering, send the following commands sequentially:

1. `0x0d, 0x00, 0x81, 0x36, 0x11, 0x51, 0x00, 0x03, 0x00, 0x00, 0x00, 0x10, 0x00`
2. `0x0d, 0x00, 0x81, 0x36, 0x11, 0x51, 0x00, 0x03, 0x00, 0x00, 0x00, 0x08, 0x00`

### Driving the Car
To drive the car, send the following command with the specified parameters:

`0x0d, 0x00, 0x81, 0x36, 0x11, 0x51, 0x00, 0x03, 0x00, speed, steering_angle, lights, 0x00`

- **speed**: The speed of the car.
- **steering_angle**: The steering angle of the car.
- **lights**: The state of the lights.

### Lights Parameter Values
- **Front and back lights on**: `0x00`
- **Front and back lights on braking**: `0x01`
- **Front and back lights off**: `0x04`
- **Front lights off, back lights on braking**: `0x05`

## Resources
For more details on the LEGO Wireless Protocol, refer to the [LEGO BLE Wireless Protocol documentation](https://lego.github.io/lego-ble-wireless-protocol-docs/).

---

This document serves as a quick reference guide for developers looking to integrate and control the LEGO Technic Move Hub 88019 in their applications. Ensure your application adheres to the specified security mode and correctly sequences the commands for optimal performance.
