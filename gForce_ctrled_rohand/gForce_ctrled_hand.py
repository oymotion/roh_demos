# Sample code to get glove data and controls ROHand via ModBus-RTU protocol

import asyncio
import os
import signal
import sys
import time
import keyboard

from pymodbus import FramerType
from pymodbus.client import ModbusSerialClient

from lib_gforce import gforce

from roh_registers_v1 import *

# ROHand configuration
COM_PORT = "COM7"
NODE_ID = 2

# Device filters
DEV_NAME_PREFIX = "gForce"
DEV_MIN_RSSI = -64

NUM_FINGERS = 5

THUMB_ROOT = {
    "ZERO":    0, 
    "HALF":32767, 
    "FULL":65535
}

GESTURES = {
   "REST":     [20000, 10000, 10000, 10000, 10000,     0],
   "FIST":     [45000, 65535, 65535, 65535, 65535,     0],
   "POINT":    [45000,     0, 65535, 65535, 65535,     0],
   "VICTORY":  [45000,     0,     0, 65535, 65535,     0],
   "SPREAD":   [    0,     0,     0,     0,     0,     0],
   "ROCK":     [    0,     0, 65535, 65535,     0,     0],
   "PINCH":    [45000, 45000, 45000, 45000, 45000,     0],
   "SHOOT":    [    0,     0, 65535, 65535, 65535,     0],
   "ITC":      [30000, 30000,     0,     0,     0, 65535],
   "SIX":      [    0, 65535, 65535, 65535,     0,     0],
   "TRIGGER":  [38000, 30000, 32000, 65535, 65535, 65535],
   "THUMBUP":  [    0, 65535, 65535, 65535, 65535,     0],
   "GRASP":    [27525, 29491, 32768, 27525, 24903, 65535]
}

current_dir = os.path.dirname(os.path.realpath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)


def clamp(n, smallest, largest):
    return max(smallest, min(n, largest))


def interpolate(n, from_min, from_max, to_min, to_max):
    return (n - from_min) / (from_max - from_min) * (to_max - to_min) + to_min


class Application:

    def __init__(self):
        signal.signal(signal.SIGINT, lambda signal, frame: self._signal_handler())
        self.terminated = False

    def _signal_handler(self):
        print("You pressed ctrl-c, exit")
        self.terminated = True

    async def main(self):
        gforce_device = gforce.GForce(DEV_NAME_PREFIX, DEV_MIN_RSSI)

        client = ModbusSerialClient(COM_PORT, FramerType.RTU, 115200)
        client.connect()

        def gestures_control(gesture):
            resp = client.write_registers(ROH_FINGER_POS_TARGET0, GESTURES["REST"], NODE_ID)
            time.sleep(0.5)
    
            # resp = client.write_registers(ROH_FINGER_POS_TARGET5, gesture[NUM_FINGERS], NODE_ID)
            # time.sleep(1)

            resp = client.write_registers(ROH_FINGER_POS_TARGET0, gesture, NODE_ID)
            print("client.write_registers() returned", resp)

        try:
            await gforce_device.connect()
        except Exception as e:
            print(e)

        if gforce_device.client == None or not gforce_device.client.is_connected:
            exit(-1)

        print("Connected to {0}".format(gforce_device.device_name))

        await gforce_device.set_subscription(gforce.DataSubscription.EMG_GESTURE)
        q = await gforce_device.start_streaming()

        prev_pos = 0
        while not self.terminated:
                gesture = await q.get()
                print("gesture ID:", gesture)
                if (gesture != prev_pos):
                    match(gesture):
                        case 0: continue 
                        case 1: gestures_control(GESTURES["SPREAD"])
                        case 2: gestures_control(GESTURES["FIST"])
                        case 3: gestures_control(GESTURES["VICTORY"])
                        case 4: gestures_control(GESTURES["SIX"])
                        case 5: continue

                    prev_pos = gesture
                else:
                    continue

        await gforce_device.stop_streaming()
        await gforce_device.disconnect()


if __name__ == "__main__":
    app = Application()
    asyncio.run(app.main())
