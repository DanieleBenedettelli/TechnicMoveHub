# LEGO Technic Move Hub 88019 (released in LEGO Technic 42176)
# remote-control with XBOX controller
# Daniele Benedettelli @profbricks - 6 August 2024
# requires pygame and bleak
# INSTALLATION:
# pip intall pygame
# pip install bleak

import os, sys, platform
os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = '1'
# crucial! otherwise Bleak will raise exception
# see https://bleak.readthedocs.io/en/latest/troubleshooting.html#windows-bugs

if sys.platform == "win32":
    sys.coinit_flags = 0 

import pygame
import asyncio
from bleak import BleakScanner, BleakClient
import time

start_time = 0

class TechnicMoveHub:
    def __init__(self, device_name):
        self.device_name = device_name
        self.service_uuid = "00001623-1212-EFDE-1623-785FEABCD123"
        self.char_uuid = "00001624-1212-EFDE-1623-785FEABCD123"
        self.client = None
        
        self.LIGHTS_OFF_OFF =    0b100
        self.LIGHTS_OFF_ON =     0b101
        self.LIGHTS_ON_ON =      0b000

    def run_discover(self):
        try:
            devices = BleakScanner.discover(timeout=20)
            return devices
        except Exception as e:
            print(f"Discovery failed with error: {e}")
            return None

    async def scan_and_connect(self):
        scanner = BleakScanner()
        print(f"searching for Technic Move Hub...")
        devices = await scanner.discover(timeout =5)

        for device in devices:
            if device.name is not None and self.device_name in device.name:
                print(f"Found device: {device.name} with address: {device.address}")
                self.client = BleakClient(device)

                await self.client.connect()
                if self.client.is_connected:
                    print(f"Connected to {self.device_name}")

                    if platform.system() == "Darwin":
                        print(f"Skipping pairing on OS X")
                        return True

                    paired = await self.client.pair(protection_level = 2) # this is crucial!!!
                    if not paired:
                        print(f"could not pair")
                    return True
                else:
                    print(f"Failed to connect to {self.device_name}")
        print(f"Device {self.device_name} not found.")
        return False

    async def send_data(self, data):
        global start_time
        if self.client is None:
            print("No BLE client connected.")
            return

        try:
            # Write the data to the characteristic
            await self.client.write_gatt_char(self.char_uuid, data)
            #print(f"Data written to characteristic {self.char_uuid}: {data}")
       
            elapsed_time_ms = (time.time() - start_time) * 1000
            #print(f"Timestamp: {elapsed_time_ms:.2f} ms", end=" ")
            #print(' '.join(f'{byte:02x}' for byte in data))

        except Exception as e:
            print(f"Failed to write data: {e}")

    async def disconnect(self):
        if self.client and self.client.is_connected:
            await self.client.disconnect()
            print("Disconnected from the device")
    
    LED_MODE_COLOR = 0x00
    LED_MODE_RGB = 0x01

    async def change_led_color(self, colorID):
        if self.client and self.client.is_connected:
            await self.send_data(bytearray([0x08, 0x00, 0x81, self.ID_LED, self.IO_TYPE_RGB_LED, 0x51, self.LED_MODE_COLOR, colorID]))

    async def motor_start_power(self, motor, power):
        if self.client and self.client.is_connected:
            await self.send_data(bytearray([0x08, 0x00, 0x81, motor&0xFF, self.SC_BUFFER_NO_FEEDBACK, 0x51, self.MOTOR_MODE_POWER, 0xFF&power]))

    async def motor_stop(self, motor, brake=True):
        # motor can be 0x32, 0x33, 0x34
        if self.client and self.client.is_connected:
            await self.send_data(bytearray([0x08, 0x00, 0x81, motor&0xFF, self.SC_BUFFER_NO_FEEDBACK, 0x51, self.MOTOR_MODE_POWER, self.END_STATE_BRAKE if brake else 0x00]))

    async def calibrate_steering(self):
        await self.send_data(bytes.fromhex("0d008136115100030000001000"))
        #await asyncio.sleep(0.1)
        await self.send_data(bytes.fromhex("0d008136115100030000000800"))
        #await asyncio.sleep(0.1)

    async def drive(self, speed=0, angle=0, lights = 0x00):
        await self.send_data(bytearray([0x0d,0x00,0x81,0x36,0x11,0x51,0x00,0x03,0x00, speed&0xFF, angle&0xFF, lights&0xFF,0x00]))
        #await asyncio.sleep(0.1)


def get_left_joystick(joystick):
    x = round(joystick.get_axis(0)*100)
    y = -round(joystick.get_axis(1)*100)
    return (x,y)

def get_right_joystick(joystick):
    x = round(joystick.get_axis(2)*100)
    y = -round(joystick.get_axis(3)*100)
    return (x,y)

def get_triggers(joystick):
    left = round((joystick.get_axis(4)+100)/2)
    right = round((joystick.get_axis(5)+100)/2)
    return (left, right)


def get_A_button(joystick):
    return joystick.get_button(0)

def get_B_button(joystick):
    return joystick.get_button(1)

def get_X_button(joystick):
    return joystick.get_button(2)

def get_Y_button(joystick):
    return joystick.get_button(3)

def get_left_bumper(joystick):
    return joystick.get_button(4)

def get_right_bumper(joystick):
    return joystick.get_button(5)


async def main():
    device_name = "Technic Move"  # Replace with your BLE device's name
    hub = TechnicMoveHub(device_name)
    if not await hub.scan_and_connect():
        print("Technic hub not found!")
        return
        
    # Initialize Pygame
    pygame.init()
    pygame.joystick.init()

    # Check for joystick
    if pygame.joystick.get_count() == 0:
        print("No joystick found")
        return

    # Initialize the first joystick
    joystick = pygame.joystick.Joystick(0)
    joystick.init()
    
    print(f"Joystick name: {joystick.get_name()}")

    await hub.calibrate_steering()
        
    lights = hub.LIGHTS_ON_ON
    toggle_old = False
    throttle_old = 0
    steering_old = 0
    lights_old = 0
    was_brake = False
    start_time = time.time()

    try:
        while True:
            # Pump Pygame event loop
            pygame.event.pump() # poll joystick

            # Print controller inputs
            throttle = get_right_joystick(joystick)[1]
            steering = get_left_joystick(joystick)[0]
            #steering = get_right_joystick(joystick)[0] # use only one joystick?
        
            if abs(throttle)<3:
                throttle = 0
            if abs(steering)< 3:
                steering = 0

            brake = get_right_bumper(joystick)
            # toggle lights
            toggle = get_Y_button(joystick)
            if toggle and not toggle_old:
                if lights == hub.LIGHTS_OFF_OFF :
                    print("lights on")
                    lights = hub.LIGHTS_ON_ON
                else:
                    print("lights off")
                    lights = hub.LIGHTS_OFF_OFF
            toggle_old = toggle

       
            if brake and not was_brake:
                joystick.rumble(0.0, 0.3, 300)                    
                await hub.drive(0, steering, hub.LIGHTS_OFF_ON)
                await asyncio.sleep(0.4)
                throttle = 0
                throttle_old = 0
            
            if not brake and was_brake:
                await hub.drive(throttle, steering, lights)

            was_brake = brake
            
            if steering != steering_old or throttle != throttle_old or lights != lights_old and not brake:
                print("throttle", throttle, "steering", steering)
                await hub.drive(throttle, steering, lights)
            
            throttle_old = throttle
            steering_old = steering
            lights_old = lights

            # Flush the output
            sys.stdout.flush()

            asyncio.sleep(0.05)

    except KeyboardInterrupt:
        pass
    finally:
        pygame.quit()

if __name__ == "__main__":
    asyncio.run(main())

