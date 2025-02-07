# Sample code to get glove data and controls ROHand via ModBus-RTU protocol

import asyncio
import os
import signal
import sys
import time

from pymodbus import FramerType
from pymodbus.client import ModbusSerialClient

from lib_gforce.gforce import DataSubscription, GForce, EmgRawDataConfig, SampleResolution
from roh_registers_v1 import *

# ROHand configuration
COM_PORT = "COM8"
NODE_ID = 2

# Degree of freedom settings, modify EXTRA_FINGERS to distinguish between 5 DOF and 6 DOFgloves.
NUM_FINGERS = 5
EXTRA_FINGERS = 1

# Device filters
DEV_NAME_PREFIX = "gForceBLE"
DEV_MIN_RSSI = -64

NUM_CHANNELS = NUM_FINGERS + EXTRA_FINGERS
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
        gforce_device = GForce(DEV_NAME_PREFIX, DEV_MIN_RSSI)
        emg_data = [0 for _ in range(NUM_CHANNELS)]
        emg_min = [0 for _ in range(NUM_CHANNELS)]
        emg_max = [0 for _ in range(NUM_CHANNELS)]
        prev_finger_data = [65535 for _ in range(NUM_CHANNELS)]
        finger_data = [0 for _ in range(NUM_CHANNELS)]
        # speed = [0 for _ in range(NUM_CHANNELS)]
        last_time = 0

        client = ModbusSerialClient(COM_PORT, FramerType.RTU, 115200)
        if not client.connect():
            exit(-1)

        # GForce.connect() may get exception, but we just ignore for gloves
        try:
            await gforce_device.connect()
        except Exception as e:
            print(e)

        if gforce_device.client == None or not gforce_device.client.is_connected:
            exit(-1)

        print("Connected to {0}".format(gforce_device.device_name))

        baterry_level = await gforce_device.get_battery_level()
        print("Device baterry level: {0}%".format(baterry_level))
        
        cfg = EmgRawDataConfig(fs=100, channel_mask=0xff, batch_len=16, resolution=SampleResolution.BITS_12)
        await gforce_device.set_emg_raw_data_config(cfg)

        await gforce_device.set_subscription(DataSubscription.EMG_RAW)
        q = await gforce_device.start_streaming()

        print("Please spread your fingers")

        for _ in range(256):
            v = await q.get()
            # print(v, '#')

            for i in range(len(v)):
                for j in range(NUM_CHANNELS):
                    emg_max[j] = round((emg_max[j] + v[i][INDEX_CHANNELS[j]]) / 2)

        # print(emg_max)

        print("Please make a fist")

        for _ in range(256):
            v = await q.get()
            # print(v)

            for i in range(len(v)):
                for j in range(NUM_CHANNELS):
                    emg_min[j] = round((emg_max[j] + v[i][INDEX_CHANNELS[j]]) / 2)
        
        # For extra fingers
        if NUM_CHANNELS > NUM_FINGERS:
            print("Please spread your fingers, then rotate thumb")

            for _ in range(256):
                v = await q.get()
                for i in range(len(v)):
                    emg_min[5] = round((emg_min[5] + v[i][INDEX_CHANNELS[5]]) / 2)
  
        # print(emg_min)

        range_valid = True

        for i in range(NUM_CHANNELS):
            print("MIN/MAX of finger {0}: {1}-{2}".format(i, emg_min[i], emg_max[i]))
            if (emg_min[i] >= emg_max[i]):
                range_valid = False

        if not range_valid:
            print("Invalid range(s), exit.")
            exit(-1)
        
        print("Open your fingers")
        time.sleep(1)

        while not self.terminated:

            v = await q.get()
            # print(v)

            for i in range(len(v)):
                for j in range(NUM_CHANNELS):
                    emg_data[j] = round((emg_data[j] + v[i][INDEX_CHANNELS[j]]) / 2)
                    finger_data[j] = round(interpolate(emg_data[j], emg_min[j], emg_max[j], 65535, 0))
                    finger_data[j] = clamp(finger_data[j], 0, 65535)

            are_equal = True

            for i in range(len(finger_data)):
                if abs(prev_finger_data[i] - finger_data[i]) > 512:
                    are_equal = False
                    break

            if (are_equal or time.time() - last_time < 0.05):
                continue

            # if (finger_data == prev_finger_data or time.time() - last_time < 0.05):
            #     continue
            
            # Calculate speed
            
            # for i in range(len(finger_data)):
            #     speed[i] = int(abs(prev_finger_data[i] - finger_data[i]) / (time.time() - last_time) * 0.5)
            #     speed[i] = clamp(speed[i], 0, 65535)
            
            # prev_finger_data = finger_data.copy()
            for i in range(len(finger_data)):
                prev_finger_data[i] = finger_data[i]

            last_time = time.time()

            # print("finger data:", finger_data, "speed:", speed)
            # print("finger data:", finger_data)

            # Control the ROHand
            # resp = client.write_registers(ROH_FINGER_SPEED0, speed, NODE_ID)
            resp = client.write_registers(ROH_FINGER_POS_TARGET0, finger_data, NODE_ID)
            print("client.write_registers() returned", resp)

        await gforce_device.stop_streaming()
        await gforce_device.disconnect()


if __name__ == "__main__":
    app = Application()
    asyncio.run(app.main())
