import asyncio
import sys
from bleak import BleakScanner, BleakClient
import time
from enum import IntEnum

start_time = 0

class Button(IntEnum):
    LEFT_MINUS = 1
    LEFT = 2
    LEFT_PLUS = 3
    RIGHT_MINUS = 4
    RIGHT = 5
    RIGHT_PLUS = 6

class LEGOHandset:
    def __init__(self, device_name):
        self.device_name = device_name
        self.service_uuid = "00001623-1212-EFDE-1623-785FEABCD123"
        self.char_uuid = "00001624-1212-EFDE-1623-785FEABCD123"
        self.client = None
        self.buttons_pressed = []
        
        self.ID_BTNS_A  = 0x00
        self.ID_BTNS_B  = 0x01
        self.ID_LED      = 0x34
        self.CMD_PORT_INPUT_FORMAT_SETUP_SINGLE = 0x41

    def run_discover(self):
        try:
            devices = BleakScanner.discover(timeout=20)
            return devices
        except Exception as e:
            print(f"Discovery failed with error: {e}")
            return None

    async def scan_and_connect(self):
        scanner = BleakScanner()
        print(f"searching for LEGO Handset")
        devices = await scanner.discover(timeout =5)

        for device in devices:
            if device.name is not None and self.device_name in device.name:
                print(f"Found device: {device.name} with address: {device.address}")
                self.client = BleakClient(device)

                
                await self.client.connect()
                if self.client.is_connected:
                    print(f"Connected to {self.device_name}")
                    
                    #paired = await self.client.pair()#protection_level = 2) # this is crucial!!!
                    #if not paired:
                    #    print(f"could not pair")

                    await self.setNotifications(self.ID_BTNS_A, True)
                    await self.setNotifications(self.ID_BTNS_B, True)
                    await self.client.start_notify(self.char_uuid, self.buttonsHandler)

                    return True
                else:
                    print(f"Failed to connect to {self.device_name}")
        print(f"Device {self.device_name} not found.")
        return False  

    async def setNotifications(self, port, enable=True):
        _MODE = 0x01
        await self.send_data(bytearray([0x0A, 0x00, self.CMD_PORT_INPUT_FORMAT_SETUP_SINGLE, port, _MODE, 1, 0, 0, 0, 1 if enable else 0]))

    async def buttonsHandler(self, sender, data):
        """
        Callback function to handle incoming notifications from the LEGO hub.
        `sender` is the characteristic that triggered the callback.
        `data` is the data received from the LEGO hub.
        """
        if len(data) == 5:
            port = data[3]
            button = data[4]
            
            if port == self.ID_BTNS_A:
                if button == 0xFF:
                    if Button.LEFT_MINUS not in self.buttons_pressed:
                        self.buttons_pressed.append(Button.LEFT_MINUS)
                elif button == 0x7F:
                    if Button.LEFT not in self.buttons_pressed:
                        self.buttons_pressed.append(Button.LEFT)
                elif button == 0x01:
                    if Button.LEFT_PLUS not in self.buttons_pressed:
                        self.buttons_pressed.append(Button.LEFT_PLUS)
                elif button == 0x00:
                    self.buttons_pressed = [btn for btn in self.buttons_pressed if btn not in [Button.LEFT_MINUS, Button.LEFT, Button.LEFT_PLUS]]

            elif port == self.ID_BTNS_B:
                if button == 0xFF:
                    if Button.RIGHT_MINUS not in self.buttons_pressed:
                        self.buttons_pressed.append(Button.RIGHT_MINUS)
                elif button == 0x7F:
                    if Button.RIGHT not in self.buttons_pressed:
                        self.buttons_pressed.append(Button.RIGHT)
                elif button == 0x01:
                    if Button.RIGHT_PLUS not in self.buttons_pressed:
                        self.buttons_pressed.append(Button.RIGHT_PLUS)
                elif button == 0x00:
                    self.buttons_pressed = [btn for btn in self.buttons_pressed if btn not in [Button.RIGHT_MINUS, Button.RIGHT, Button.RIGHT_PLUS]]

        #print(f"Current pressed buttons: {[btn.name for btn in self.pressed]}")

    def pressed(self):
        return set(self.buttons_pressed)
  

    async def send_data(self, data):
        global start_time
        if self.client is None:
            print("No BLE client connected.")
            return

        try:
            # Ensure service discovery
            #await self.discover_services()
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
            await self.setNotifications(self.ID_BTNS_A, False)
            await self.setNotifications(self.ID_BTNS_B, False)
            await self.client.stop_notify(self.char_uuid)
            await self.client.disconnect()
            print("Disconnected from the device")
    
    LED_MODE_COLOR = 0x00
    LED_MODE_RGB = 0x01

    async def change_led_color(self, colorID):
        if self.client and self.client.is_connected:
            await self.send_data(bytearray([0x08, 0x00, 0x81, self.ID_LED, 0x11, 0x51, self.LED_MODE_COLOR, colorID]))          

class TechnicMoveHub:
    def __init__(self, device_name):
        self.device_name = device_name
        self.service_uuid = "00001623-1212-EFDE-1623-785FEABCD123"
        self.char_uuid = "00001624-1212-EFDE-1623-785FEABCD123"
        self.client = None
        
        self.ID_MOTOR_A  = 0x32
        self.ID_MOTOR_B  = 0x33
        self.ID_MOTOR_C  = 0x34
        self.ID_LED      = 0x3F
        self.IO_TYPE_RGB_LED = 0x17
        self.IO_TYPE_RGB_LED = 0x17
        self.OUT_SUBCMD_SPEED_FOR_TIME = 0x09
        self.SC_BUFFER_NO_FEEDBACK = 0x00
        self.SC_BUFFER_AND_FEEDBACK = 0x01
        self.SC_IMMEDIATE_NO_FEEDBACK = 0x10
        self.SC_IMMEDIATE_AND_FEEDBACK = 0x11

        self.MOTOR_MODE_POWER =  0x00
        self.MOTOR_MODE_SPEED =  0x01
        self.MOTOR_MODE_POS =    0x02
        self.MOTOR_MODE_GOPOS =  0x03
        self.MOTOR_MODE_STATS =  0x04

        self.END_STATE_FLOAT = 0
        self.END_STATE_BRAKE = 127
        self.END_STATE_HOLD = 126

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
                    
                    paired = await self.client.pair(protection_level = 2) # this is crucial!!!
                    if not paired:
                        print(f"could not pair")
                    return True
                else:
                    print(f"Failed to connect to {self.device_name}")
        print(f"Device {self.device_name} not found.")
        return False

    async def discover_services(self):
        if self.client is None:
            print("No BLE client connected.")
            return []

        try:
            services = self.client.services
            for service in services:
                print(f"Service: {service.uuid}")
                for char in service.characteristics:
                    print(f"Characteristic: {char.uuid}")
            return services
        except Exception as e:
            print(f"Failed to discover services: {e}")
            return []

    async def send_data(self, data):
        global start_time
        if self.client is None:
            print("No BLE client connected.")
            return

        try:
            # Ensure service discovery
            #await self.discover_services()
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

    async def _motor_speed_for_time(self, motor, time_ms, speed_percent, max_power_percent, end_state = 0, use_acc_profile=0, use_dec_profile=0):
        profile_byte = use_acc_profile | use_dec_profile<<1
        if speed_percent > 100:
            speed_percent = 100
        if max_power_percent > 100:
            max_power_percent = 100

        if time_ms > 0xFFFF:
            time_ms = 0xFFFF

        time_lo = time_ms & 0xFF
        time_hi = (time_ms >> 8) & 0xFF

        
        if self.client and self.client.is_connected:
            await self.send_data(bytearray([12, 0x00, 0x81, motor&0xFF, 
                                            self.SC_BUFFER_NO_FEEDBACK, 
                                            self.OUT_SUBCMD_SPEED_FOR_TIME, 
                                            time_hi, time_lo, 
                                            speed_percent, max_power_percent, end_state, profile_byte]))


    async def some_sort_of_reset(self):
        await self.send_data(bytes.fromhex("0800813611510001"))

    async def calibrate_steering(self):
        await self.send_data(bytes.fromhex("0d008136115100030000001000"))
        #await asyncio.sleep(0.1)
        await self.send_data(bytes.fromhex("0d008136115100030000000800"))
        #await asyncio.sleep(0.1)

    async def drive(self, speed=0, angle=0, lights = 0x00):
        await self.send_data(bytearray([0x0d,0x00,0x81,0x36,0x11,0x51,0x00,0x03,0x00, speed&0xFF, angle&0xFF, lights&0xFF,0x00]))
        #await asyncio.sleep(0.1)


async def main():

    #device_name = "Handset"  # Replace with your BLE device's name
    remote = LEGOHandset("Handset")

    if not await remote.scan_and_connect():
        print("Handset not found!")
        return
    await remote.change_led_color(9) # red

    hub = TechnicMoveHub("Technic Move ")
    
    if not await hub.scan_and_connect():
        print("Technic Move Hub not found!")
        return    
    
    await hub.calibrate_steering()    
    await remote.change_led_color(3) # blue
    

    toggle_old = False
    throttle_old = 0
    steering_old = 0
    lights_old = 0
    brake = False
    was_brake = False
    steering = 0
    throttle = 0
    lights = hub.LIGHTS_ON_ON
    start_time = time.time()

    try:
        while True:
            buttons = remote.pressed()

            # driving 
            if Button.RIGHT_MINUS in buttons:
                throttle = -100
            elif Button.RIGHT_PLUS in buttons:
                throttle = 100
            else:
                throttle = 0

            # steering
            if Button.LEFT_MINUS in buttons:
                steering = -100
            elif Button.LEFT_PLUS in buttons:
                steering = 100 
            else:
                steering = 0

            if Button.RIGHT in buttons:
                brake = True
            else:
                brake = False

            if Button.LEFT in buttons:
                toggle = True
            else:
                toggle = False

            if toggle and not toggle_old:
                if lights == hub.LIGHTS_OFF_OFF :
                    print("lights on")
                    lights = hub.LIGHTS_ON_ON
                else:
                    print("lights off")
                    lights = hub.LIGHTS_OFF_OFF
            toggle_old = toggle                
            
            if brake and not was_brake:
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

            await asyncio.sleep(0.05)

    except KeyboardInterrupt:
        pass
    finally:
        await hub.disconnect()
        await remote.disconnect()

if __name__ == "__main__":
    asyncio.run(main())

