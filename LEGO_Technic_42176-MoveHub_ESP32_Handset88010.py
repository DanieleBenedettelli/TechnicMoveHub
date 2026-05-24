"""
LEGO Technic Move Hub ESP32 Bridge
Program version: 1.0.0

Hardware:
- TinyPICO ESP32
- LEGO Technic Move Hub, e.g. LEGO part 103479c01 / set 42176
- LEGO Powered Up Remote Control 88010

Firmware:
- MicroPython for UM_TINYPICO
- Tested with: MicroPython v1.28.0 on 2026-04-06; TinyPICO with ESP32-PICO-D4
- Required built-in modules from UM_TINYPICO firmware:
  - tinypico
  - dotstar
  - aioble
  - bluetooth

What this program does:
- Uses the TinyPICO as a BLE bridge.
- Connects to any compatible LEGO Powered Up remote control.
- Renames the connected remote to "pyb42176".
- Connects to the LEGO Technic Move Hub.
- Controls driving, steering, lights and speed levels without a smartphone.
- Uses the TinyPICO onboard DotStar RGB LED as a status indicator.
- Uses the LEGO hub lights to indicate the current speed level.
- Enters deep sleep when the green centre button on the LEGO remote is held.

Remote control mapping:
- Left plus/minus: drive forward/backward
- Right plus/minus: steering
- Left red button: toggle vehicle lights
- Right red button: toggle max speed level
- Green centre button, held for approx. 3 seconds: stop and deep sleep

TinyPICO onboard LED status:
- Blue, static briefly: program started
- Yellow, slow blinking: waiting for LEGO remote
- Magenta, slow blinking: waiting for Technic Move Hub
- Green, weak static: ready
- Red, fast blinking: going to deep sleep
- Red, strong static: fatal error
"""

from machine import SoftSPI, deepsleep
import uasyncio as asyncio
import aioble
import bluetooth
import tinypico
from dotstar import DotStar


# ---------------------------------------------------------------------------
# BLE configuration
# ---------------------------------------------------------------------------

SERVICE_UUID = bluetooth.UUID("00001623-1212-efde-1623-785feabcd123")
CHARACTERISTIC_UUID = bluetooth.UUID("00001624-1212-efde-1623-785feabcd123")

REMOTE_NEW_NAME = "pyb42176"
HUB_NAME = "Technic Move"


# ---------------------------------------------------------------------------
# LEGO protocol constants
# ---------------------------------------------------------------------------

LIGHTS_ON_ON = 0b000
LIGHTS_OFF_OFF = 0b100

ID_BTNS_A = 0x00
ID_BTNS_B = 0x01
ID_REMOTE_LED = 0x34

CMD_PORT_INPUT_FORMAT_SETUP_SINGLE = 0x41


# ---------------------------------------------------------------------------
# Global BLE state
# ---------------------------------------------------------------------------

hub_connection = None
hub_characteristic = None

remote_connection = None
remote_characteristic = None

buttons_pressed = set()


# ---------------------------------------------------------------------------
# TinyPICO onboard DotStar status LED
# ---------------------------------------------------------------------------

tinypico.set_dotstar_power(True)

spi = SoftSPI(
    sck=tinypico.DOTSTAR_CLK,
    mosi=tinypico.DOTSTAR_DATA,
    miso=18
)

status_led = DotStar(spi, 1, brightness=0.05)
status_blink_task = None

STATUS_START = (0, 0, 80)
STATUS_WAIT_REMOTE = (80, 60, 0)
STATUS_WAIT_HUB = (80, 0, 80)
STATUS_READY = (0, 80, 0)
STATUS_ERROR = (255, 0, 0)
STATUS_OFF = (0, 0, 0)


def status_set(rgb, brightness=0.05):
    status_led.brightness = brightness
    status_led[0] = rgb


def status_off():
    status_set(STATUS_OFF, 0.05)


async def status_blink(rgb, brightness=0.05, on_ms=600, off_ms=600):
    while True:
        status_set(rgb, brightness)
        await asyncio.sleep_ms(on_ms)
        status_off()
        await asyncio.sleep_ms(off_ms)


def status_start_blink(rgb, brightness=0.05, on_ms=600, off_ms=600):
    global status_blink_task

    if status_blink_task:
        status_blink_task.cancel()

    status_blink_task = asyncio.create_task(
        status_blink(rgb, brightness, on_ms, off_ms)
    )


def status_stop_blink():
    global status_blink_task

    if status_blink_task:
        status_blink_task.cancel()
        status_blink_task = None


async def status_deep_sleep_animation():
    status_stop_blink()

    for _ in range(5):
        status_set(STATUS_ERROR, 0.5)
        await asyncio.sleep_ms(150)
        status_off()
        await asyncio.sleep_ms(150)

    status_off()


# ---------------------------------------------------------------------------
# LEGO Technic Move Hub functions
# ---------------------------------------------------------------------------

async def connect_hub():
    global hub_connection
    global hub_characteristic

    print("Waiting for Technic Move Hub...")

    while True:
        async with aioble.scan(
            duration_ms=5000,
            interval_us=30000,
            window_us=30000,
            active=True
        ) as scanner:
            async for result in scanner:
                name = result.name()

                if name and HUB_NAME in name:
                    print("Found hub:", name)

                    try:
                        hub_connection = await result.device.connect(
                            timeout_ms=3000
                        )

                        await hub_connection.pair(
                            bond=True,
                            le_secure=True
                        )

                        service = await hub_connection.service(SERVICE_UUID)
                        hub_characteristic = await service.characteristic(
                            CHARACTERISTIC_UUID
                        )

                        print("Hub connected")
                        return

                    except Exception as e:
                        print("Hub connection failed:", e)

        print("Hub not found yet, retrying...")
        await asyncio.sleep_ms(500)


async def send_hub_command(data):
    try:
        if hub_characteristic:
            await hub_characteristic.write(bytearray(data), False)

    except Exception as e:
        # Send errors are ignored here on purpose.
        # Some BLE writes may fail transiently although control continues to work.
        print("Hub send ignored:", e)


async def drive_car(speed=0, steer_angle=0, lights=0):
    await send_hub_command([
        0x0d, 0x00, 0x81, 0x36,
        0x11, 0x51,
        0x00, 0x03, 0x00,
        int(speed) & 0xFF,
        int(steer_angle) & 0xFF,
        int(lights) & 0xFF,
        0x00
    ])


async def calibrate_steering():
    print("Calibrating steering")

    await send_hub_command(bytes.fromhex("0d008136115100030000001000"))
    await asyncio.sleep_ms(100)

    await send_hub_command(bytes.fromhex("0d008136115100030000000800"))
    await asyncio.sleep_ms(100)


async def blink_hub_lights(times, current_lights):
    for _ in range(times):
        await drive_car(0, 0, LIGHTS_OFF_OFF)
        await asyncio.sleep_ms(120)

        await drive_car(0, 0, LIGHTS_ON_ON)
        await asyncio.sleep_ms(120)

    await drive_car(0, 0, current_lights)


# ---------------------------------------------------------------------------
# LEGO Powered Up remote functions
# ---------------------------------------------------------------------------

async def connect_any_remote():
    global remote_connection
    global remote_characteristic

    print("Waiting for LEGO Powered Up remote...")

    while True:
        async with aioble.scan(
            duration_ms=5000,
            interval_us=30000,
            window_us=30000,
            active=True
        ) as scanner:
            async for result in scanner:
                name = result.name()

                if name:
                    print("Found:", name)

                if name and HUB_NAME in name:
                    continue

                try:
                    test_connection = await result.device.connect(
                        timeout_ms=3000
                    )

                    service = await test_connection.service(SERVICE_UUID)
                    test_characteristic = await service.characteristic(
                        CHARACTERISTIC_UUID
                    )

                    remote_connection = test_connection
                    remote_characteristic = test_characteristic

                    print("Remote connected:", name)
                    return

                except Exception:
                    try:
                        await test_connection.disconnect()
                    except Exception:
                        pass

        print("Remote not found yet, retrying...")
        await asyncio.sleep_ms(500)


async def send_remote_command(data):
    await remote_characteristic.write(bytearray(data), False)


async def rename_remote(new_name):
    name_bytes = new_name.encode()

    command = bytearray([
        5 + len(name_bytes),
        0x00,
        0x01,
        0x01,
        0x01
    ])

    command.extend(name_bytes)

    print("Renaming remote to:", new_name)

    await send_remote_command(command)
    await asyncio.sleep_ms(500)


async def set_remote_notifications(port, enable=True):
    await send_remote_command([
        0x0A, 0x00,
        CMD_PORT_INPUT_FORMAT_SETUP_SINGLE,
        port,
        0x01,
        1, 0, 0, 0,
        1 if enable else 0
    ])


async def set_remote_led_color(color_id):
    await send_remote_command([
        0x08, 0x00, 0x81,
        ID_REMOTE_LED,
        0x11, 0x51,
        0x00,
        color_id & 0xFF
    ])


async def remote_listener():
    global buttons_pressed

    await set_remote_notifications(ID_BTNS_A, True)
    await set_remote_notifications(ID_BTNS_B, True)

    await remote_characteristic.subscribe(notify=True)

    while True:
        data = await remote_characteristic.notified()

        # Green centre button pressed
        if data == b"\x05\x00\x08\x02\x01":
            buttons_pressed.add("CENTER")
            continue

        # Green centre button released
        if data == b"\x04\x00\x08\x03":
            buttons_pressed.discard("CENTER")
            continue

        if len(data) == 5:
            port = data[3]
            value = data[4]

            if port == ID_BTNS_A:
                buttons_pressed.difference_update([
                    "LEFT_MINUS",
                    "LEFT",
                    "LEFT_PLUS"
                ])

                if value == 0xFF:
                    buttons_pressed.add("LEFT_MINUS")
                elif value == 0x7F:
                    buttons_pressed.add("LEFT")
                elif value == 0x01:
                    buttons_pressed.add("LEFT_PLUS")

            elif port == ID_BTNS_B:
                buttons_pressed.difference_update([
                    "RIGHT_MINUS",
                    "RIGHT",
                    "RIGHT_PLUS"
                ])

                if value == 0xFF:
                    buttons_pressed.add("RIGHT_MINUS")
                elif value == 0x7F:
                    buttons_pressed.add("RIGHT")
                elif value == 0x01:
                    buttons_pressed.add("RIGHT_PLUS")


# ---------------------------------------------------------------------------
# Main program
# ---------------------------------------------------------------------------

async def main():
    status_set(STATUS_START, 0.08)
    await asyncio.sleep_ms(1000)

    status_start_blink(STATUS_WAIT_REMOTE, 0.05)
    await connect_any_remote()

    status_stop_blink()
    await rename_remote(REMOTE_NEW_NAME)

    # Remote red LED means: remote connected, waiting for hub.
    await set_remote_led_color(9)

    asyncio.create_task(remote_listener())

    status_start_blink(STATUS_WAIT_HUB, 0.05)
    await connect_hub()

    await calibrate_steering()
    await asyncio.sleep_ms(1000)

    status_stop_blink()
    status_set(STATUS_READY, 0.08)

    # Remote blue LED means: vehicle ready.
    await set_remote_led_color(3)

    headlights = LIGHTS_ON_ON
    light_toggle_old = False

    speed_levels = [40, 70, 100]
    speed_level_index = 0
    speed_toggle_old = False

    center_hold_count = 0

    await blink_hub_lights(1, headlights)

    while True:
        buttons = buttons_pressed
        max_speed = speed_levels[speed_level_index]

        # Hold green centre button for approx. 3 seconds to enter deep sleep.
        if "CENTER" in buttons:
            center_hold_count += 1
        else:
            center_hold_count = 0

        if center_hold_count >= 60:
            print("Power off requested. Going to deep sleep.")

            await drive_car(0, 0, LIGHTS_OFF_OFF)
            await asyncio.sleep_ms(300)

            await status_deep_sleep_animation()
            deepsleep()

        # Left control: drive forward/backward.
        if "LEFT_PLUS" in buttons:
            drive = max_speed
        elif "LEFT_MINUS" in buttons:
            drive = -max_speed
        else:
            drive = 0

        # Right control: steering.
        if "RIGHT_PLUS" in buttons:
            steer = 100
        elif "RIGHT_MINUS" in buttons:
            steer = -100
        else:
            steer = 0

        # Left red button: toggle vehicle lights.
        light_toggle = "LEFT" in buttons

        if light_toggle and not light_toggle_old:
            if headlights == LIGHTS_ON_ON:
                headlights = LIGHTS_OFF_OFF
                print("Vehicle lights off")
            else:
                headlights = LIGHTS_ON_ON
                print("Vehicle lights on")

        light_toggle_old = light_toggle

        # Right red button: toggle max speed level.
        speed_toggle = "RIGHT" in buttons

        if speed_toggle and not speed_toggle_old:
            speed_level_index = (speed_level_index + 1) % len(speed_levels)

            print("Max speed:", speed_levels[speed_level_index])

            await blink_hub_lights(
                speed_level_index + 1,
                headlights
            )

        speed_toggle_old = speed_toggle

        await drive_car(drive, steer, headlights)
        await asyncio.sleep_ms(50)


try:
    asyncio.run(main())

except Exception as e:
    print("Fatal error:", e)

    status_stop_blink()
    status_set(STATUS_ERROR, 0.5)