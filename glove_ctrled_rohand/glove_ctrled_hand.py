# Sample code to get glove data and controls ROHand via ModBus-RTU protocol

import asyncio
import os
import signal
import sys
import serial.tools.list_ports

from pymodbus import FramerType
from pymodbus.client import ModbusSerialClient

from lib_gforce import gforce
from lib_gforce.gforce import EmgRawDataConfig, SampleResolution

from roh_registers_v1 import *

# ROHand configuration
NODE_ID = 2

NUM_FINGERS = 6

# Device filters
DEV_NAME_PREFIX = "gForceBLE"
DEV_MIN_RSSI = -128

# sample resolution:BITS_8 or BITS_12
SAMPLE_RESOLUTION = 8

# Channel0: thumb, Channel1: index, Channel2: middle, Channel3: ring, Channel4: pinky, Channel5: thumb root
INDEX_CHANNELS = [7, 6, 0, 3, 4, 5]

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
        ports = []

        for port in serial.tools.list_ports.comports():
            if port.description.startswith("USB-SERIAL"):
                print(f"port: {port.name}-{port.description}")
                ports.append(port.name)

        if len(ports) == 0:
            print("No ROHand found, exit.")
            exit(-1)

        gforce_device = gforce.GForce(DEV_NAME_PREFIX, DEV_MIN_RSSI)
        emg_data = [0 for _ in range(NUM_FINGERS)]
        emg_min = [0 for _ in range(NUM_FINGERS)]
        emg_max = [0 for _ in range(NUM_FINGERS)]
        prev_finger_data = [0 for _ in range(NUM_FINGERS)]
        finger_data = [0 for _ in range(NUM_FINGERS)]
        prev_dir = [0 for _ in range(NUM_FINGERS)]

        client = ModbusSerialClient(ports[0], FramerType.RTU, 115200)
        client.connect()

        # GForce.connect() may get exception, but we just ignore for gloves
        try:
            await gforce_device.connect()
        except Exception as e:
            print(e)

        if gforce_device.client == None or not gforce_device.client.is_connected:
            exit(-1)

        print("Connected to {0}".format(gforce_device.device_name))

        # Set the EMG raw data configuration, default configuration is 8 bits, 16 batch_len
        if SAMPLE_RESOLUTION == 12:
            cfg = EmgRawDataConfig(fs=100, channel_mask=0xff, batch_len = 48, resolution = SampleResolution.BITS_12)
            await gforce_device.set_emg_raw_data_config(cfg)

        baterry_level = await gforce_device.get_battery_level()
        print("Device baterry level: {0}%".format(baterry_level))

        await gforce_device.set_subscription(gforce.DataSubscription.EMG_RAW)
        q = await gforce_device.start_streaming()

        print("Please spread your fingers")

        for _ in range(256):
            v = await q.get()
            # print(v)

            for i in range(len(v)):
                for j in range(NUM_FINGERS):
                    emg_max[j] = round((emg_max[j] + v[i][INDEX_CHANNELS[j]]) / 2)

        # print(emg_max)

        print("Please rotate your thumb to maximum angle")

        for _ in range(256):
            v = await q.get()
            for i in range(len(v)):
                emg_min[5] = round((emg_min[5] + v[i][INDEX_CHANNELS[5]]) / 2)

        print("Please make a fist")

        for _ in range(256):
            v = await q.get()
            # print(v)

            for i in range(len(v)):
                for j in range(NUM_FINGERS - 1):
                    emg_min[j] = round((emg_max[j] + v[i][INDEX_CHANNELS[j]]) / 2)

            # print(emg_min)

        range_valid = True

        for i in range(NUM_FINGERS):
            print("MIN/MAX of finger {0}: {1}-{2}".format(i, emg_min[i], emg_max[i]))
            if (emg_min[i] >= emg_max[i]):
                range_valid = False

        if not range_valid:
            print("Invalid range(s), exit.")
            exit(-1)

        while not self.terminated:
            v = await q.get()

            # print(v)

            for i in range(len(v)):
                for j in range(NUM_FINGERS):
                    emg_data[j] = round((emg_data[j] + v[i][INDEX_CHANNELS[j]]) / 2)
                    finger_data[j] = round(interpolate(emg_data[j], emg_min[j], emg_max[j], 65535, 0))
                    finger_data[j] = clamp(finger_data[j], 0, 65535)
            # print(finger_data)

            dir = [0 for _ in range(NUM_FINGERS)]

            for i in range(NUM_FINGERS):
                if finger_data[i] > prev_finger_data[i]:
                    dir[i] = 1
                elif finger_data[i] < prev_finger_data[i]:
                    dir[i] = -1

                if dir[i] != prev_dir[i]:
                    if dir[i] == -1:
                        pos = 0
                    elif dir[i] == 0:
                        pos = finger_data[i]
                    else:
                        pos = 65535

                    # Control the ROHand
                    resp = client.write_register(ROH_FINGER_POS_TARGET0 + i, pos, NODE_ID)
                    print(f"client.write_register({ROH_FINGER_POS_TARGET0 + i}, {pos}, {NODE_ID}) returned", resp)

                    prev_dir[i] = dir[i]

                prev_finger_data[i] = finger_data[i]

        await gforce_device.stop_streaming()
        await gforce_device.disconnect()


if __name__ == "__main__":
    app = Application()
    asyncio.run(app.main())
