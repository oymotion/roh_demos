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
COM_PORT = "COM8"
NODE_ID = 2

# Device filters
DEV_NAME_PREFIX = "gForceBLE"
DEV_MIN_RSSI = -64

NUM_FINGERS = 5


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
        emg_data = [0 for _ in range(NUM_FINGERS)]
        emg_min = [0 for _ in range(NUM_FINGERS)]
        emg_max = [0 for _ in range(NUM_FINGERS)]
        prev_finger_data = [65535 for _ in range(NUM_FINGERS)]
        finger_data = [0 for _ in range(NUM_FINGERS)]
        last_time = 0

        client = ModbusSerialClient(COM_PORT, FramerType.RTU, 115200)
        client.connect()

        # GForce.connect() may get exception, but we just ignore for gloves
        try:
            await gforce_device.connect()
        except Exception as e:
            print(e)

        if gforce_device.client == None or not gforce_device.client.is_connected:
            exit(-1)

        print("Connected to {0}".format(gforce_device.device_name))

        await gforce_device.set_subscription(gforce.DataSubscription.EMG_RAW)
        q = await gforce_device.start_streaming()

        print("Please spread your fingers")

        for _ in range(256):
            v = await q.get()
            # print(v)

            for i in range(len(v)):
                emg_max[0] = round((emg_max[0] + v[i][7]) / 2)  # 拇指
                emg_max[1] = round((emg_max[1] + v[i][6]) / 2)  # 食指
                emg_max[2] = round((emg_max[2] + v[i][0]) / 2)  # 中指
                emg_max[3] = round((emg_max[3] + v[i][3]) / 2)  # 无名指
                emg_max[4] = round((emg_max[4] + v[i][4]) / 2)  # 小指

            # print(emg_max)

        print("Please make a fist")

        for _ in range(256):
            v = await q.get()
            # print(v)

            for i in range(len(v)):
                emg_min[0] = round((emg_min[0] + v[i][7]) / 2)  # 拇指
                emg_min[1] = round((emg_min[1] + v[i][6]) / 2)  # 食指
                emg_min[2] = round((emg_min[2] + v[i][0]) / 2)  # 中指
                emg_min[3] = round((emg_min[3] + v[i][3]) / 2)  # 无名指
                emg_min[4] = round((emg_min[4] + v[i][4]) / 2)  # 小指

            # print(emg_min)

        for i in range(NUM_FINGERS):
            print("MIN/MAX of finger {0}: {1}-{2}".format(i, emg_min[i], emg_max[i]))

        while not self.terminated:
            if keyboard.is_pressed('1'):
                resp = client.write_registers(ROH_FINGER_POS_TARGET5, [0], NODE_ID)
                print("client.write_registers() returned", resp)
            elif keyboard.is_pressed('2'):
                resp = client.write_registers(ROH_FINGER_POS_TARGET5, [65535], NODE_ID)
                print("client.write_registers() returned", resp)

            v = await q.get()
            # print(v)

            for i in range(len(v)):
                emg_data[0] = round((emg_data[0] + v[i][7]) / 2)  # 拇指
                emg_data[1] = round((emg_data[1] + v[i][6]) / 2)  # 食指
                emg_data[2] = round((emg_data[2] + v[i][0]) / 2)  # 中指
                emg_data[3] = round((emg_data[3] + v[i][3]) / 2)  # 无名指
                emg_data[4] = round((emg_data[4] + v[i][4]) / 2)  # 小指

                finger_data[0] = round(interpolate(emg_data[0], emg_min[0], emg_max[0], 65535, 0))
                finger_data[1] = round(interpolate(emg_data[1], emg_min[1], emg_max[1], 65535, 0))
                finger_data[2] = round(interpolate(emg_data[2], emg_min[2], emg_max[2], 65535, 0))
                finger_data[3] = round(interpolate(emg_data[3], emg_min[3], emg_max[3], 65535, 0))
                finger_data[4] = round(interpolate(emg_data[4], emg_min[4], emg_max[4], 65535, 0))

                finger_data[0] = clamp(finger_data[0], 0, 45000)
                finger_data[1] = clamp(finger_data[1], 0, 65535)
                finger_data[2] = clamp(finger_data[2], 0, 65535)
                finger_data[3] = clamp(finger_data[3], 0, 65535)
                finger_data[4] = clamp(finger_data[4], 0, 65535)


            # are_equal = True

            # for i in range(len(finger_data)):
            #     if prev_finger_data[i] != finger_data[i]:
            #         are_equal = False
            #         break

            # if (are_equal == True):
            #     continue

            if (finger_data == prev_finger_data or time.time() - last_time < 0.05):
                continue

            print(finger_data)

            # Control the ROHand
            resp = client.write_registers(ROH_FINGER_POS_TARGET0, finger_data, NODE_ID)
            print("client.write_registers() returned", resp)

            last_time = time.time()

            # prev_finger_data = finger_data.copy()
            for i in range(len(finger_data)):
                prev_finger_data[i] = finger_data[i]

        await gforce_device.stop_streaming()
        await gforce_device.disconnect()


if __name__ == "__main__":
    app = Application()
    asyncio.run(app.main())
