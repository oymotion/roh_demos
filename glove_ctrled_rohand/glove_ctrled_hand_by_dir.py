# Sample code to get glove data and controls ROHand via ModBus-RTU protocol
import asyncio
import os
import signal
import sys

from pymodbus import FramerType
from pymodbus.client import ModbusSerialClient
from pymodbus.exceptions import ModbusException
from serial.tools import list_ports

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

    def find_comport(self, port_name):
        """
        Find available serial port automatically
        :param port_name: Characterization of the port description, such as "CH340"
        :return: Comport of device if successful, None otherwise
        """
        ports = list_ports.comports()
        for port in ports:
            if port_name in port.description:
                return port.device
        return None

    async def main(self):
        gforce_device = gforce.GForce(DEV_NAME_PREFIX, DEV_MIN_RSSI)
        emg_data = [0 for _ in range(NUM_FINGERS)]
        emg_min = [65535 for _ in range(NUM_FINGERS)]
        emg_max = [0 for _ in range(NUM_FINGERS)]
        prev_finger_data = [65535 for _ in range(NUM_FINGERS)]
        finger_data = [0 for _ in range(NUM_FINGERS)]
        prev_dir = [0 for _ in range(NUM_FINGERS)]

        TOLERANCE = round(65536 / 32)  # 判断目标位置变化的阈值，位置控制模式时为整数，角度控制模式时为浮点数

        # 连接到Modbus设备
        client = ModbusSerialClient(self.find_comport("CH340"), FramerType.RTU, 115200)
        if not client.connect():
            print("连接Modbus设备失败\nFailed to connect to Modbus device")
            exit(-1)

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
            cfg = EmgRawDataConfig(fs=20, channel_mask=0xFF, batch_len=8, resolution=SampleResolution.BITS_12)
            await gforce_device.set_emg_raw_data_config(cfg)

        baterry_level = await gforce_device.get_battery_level()
        print("电池电量: {0}%\nDevice baterry level: {0}%".format(baterry_level))

        await gforce_device.set_subscription(gforce.DataSubscription.EMG_RAW)
        q = await gforce_device.start_streaming()

        print("校正模式，请执行握拳和张开动作若干次\nCalibrating mode, please perform a fist and open action several times")

        for _ in range(256):
            v = await q.get()
            # print(v)

            emg_sum = [0 for _ in range(NUM_FINGERS)]

            for j in range(len(v)):
                for i in range(NUM_FINGERS):
                    emg_sum[i] += v[j][INDEX_CHANNELS[i]]

            for i in range(NUM_FINGERS):
                temp = emg_sum[i] / len(v)
                emg_max[i] = max(emg_max[i], temp)
                emg_min[i] = min(emg_min[i], temp)

            # print(emg_min, emg_max)

        range_valid = True

        for i in range(NUM_FINGERS):
            print("MIN/MAX of finger {0}: {1}-{2}".format(i, emg_min[i], emg_max[i]))
            if emg_min[i] >= emg_max[i]:
                range_valid = False

        if not range_valid:
            print("无效的校正范围,退出\nInvalid range(s), exit.")
            self.terminated = True

        while not self.terminated:
            v = await q.get()
            # print(v)

            emg_sum = [0 for _ in range(NUM_FINGERS)]

            for j in range(len(v)):
                for i in range(NUM_FINGERS):
                    emg_sum[i] += v[j][INDEX_CHANNELS[i]]

            for i in range(NUM_FINGERS):
                emg_data[i] = emg_sum[i] / len(v)
                finger_data[i] = round(interpolate(emg_data[i], emg_min[i], emg_max[i], 65535, 0))
                finger_data[i] = clamp(finger_data[i], 0, 65535)

            # print(f"emg_data: {emg_data}, finger_data: {finger_data}, prev_finger_data: {prev_finger_data}")

            dir = [0 for _ in range(NUM_FINGERS)]
            pos = [0 for _ in range(NUM_FINGERS)]
            target_changed = False

            for i in range(NUM_FINGERS):
                if finger_data[i] > prev_finger_data[i] + TOLERANCE:
                    prev_finger_data[i] = finger_data[i]
                    dir[i] = 1
                elif finger_data[i] < prev_finger_data[i] - TOLERANCE:
                    prev_finger_data[i] = finger_data[i]
                    dir[i] = -1

                # 只在方向发生变化时发送目标位置/角度
                if dir[i] != prev_dir[i]:
                    prev_dir[i] = dir[i]
                    target_changed = True

                if dir[i] == -1:
                    pos[i] = 0
                elif dir[i] == 0:
                    pos[i] = finger_data[i]
                else:
                    pos[i] = 65535

            # print(f"target_changed: {target_changed}, dir: {dir}, pos: {pos}")

            # pos = finger_data
            # target_changed = True

            if target_changed:
                # Read current position
                curr_pos = [0 for _ in range(NUM_FINGERS)]
                try:
                    resp = client.read_holding_registers(ROH_FINGER_POS0, NUM_FINGERS, NODE_ID)
                    if resp.isError():
                        print("读取指令发送失败\nFailed to send read command")
                        print(f"client.read_holding_registers({ROH_FINGER_POS0 + i}, {NUM_FINGERS}, {NODE_ID}) returned {resp})")
                    curr_pos = resp.registers
                except ModbusException as e:
                    print("ModbusException:{0}".format(e))

                speed = [0 for _ in range(NUM_FINGERS)]

                for i in range(NUM_FINGERS):
                    temp = interpolate(abs(curr_pos[i] - finger_data[i]), 0, 4095, 0, 65535)
                    speed[i] = clamp(round(temp), 0, 65535)

                # Set speed
                try:
                    resp = client.write_registers(ROH_FINGER_SPEED0, speed, NODE_ID)
                    if resp.isError():
                        print("控制指令发送失败\nFailed to send control command")
                        print(f"client.write_registers({ROH_FINGER_SPEED0 + i}, {pos}, {NODE_ID}) returned {resp})")
                except ModbusException as e:
                    print("ModbusException:{0}".format(e))

                # Control the ROHand
                try:
                    resp = client.write_registers(ROH_FINGER_POS_TARGET0, pos, NODE_ID)
                    if resp.isError():
                        print("控制指令发送失败\nFailed to send control command")
                        print(f"client.write_registers({ROH_FINGER_POS_TARGET0 + i}, {pos}, {NODE_ID}) returned {resp})")
                except ModbusException as e:
                    print("ModbusException:{0}".format(e))

        await gforce_device.stop_streaming()
        await gforce_device.disconnect()


if __name__ == "__main__":
    app = Application()
    asyncio.run(app.main())
