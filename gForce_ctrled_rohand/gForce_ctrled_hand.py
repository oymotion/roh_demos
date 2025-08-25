# Sample code to get glove data and controls ROHand via ModBus-RTU protocol

import asyncio
import os
import signal
import sys
import time

from pymodbus import FramerType
from pymodbus.client import ModbusSerialClient
from pymodbus.exceptions import ModbusException
from serial.tools import list_ports

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from common.roh_registers_v1 import *
from lib_gforce import gforce

# ROHand configuration
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

    def write_registers(self, client, address, values):
        """
        Write data to Modbus device.
        :param client: Modbus client instance
        :param address: Register address
        :param values: Data to be written
        :return: True if successful, False otherwise
        """
        try:
            resp = client.write_registers(address, values, NODE_ID)
            if resp.isError():
                print("client.write_registers() returned", resp)
                return False
            return True
        except ModbusException as e:
            print("ModbusException:{0}".format(e))
            return False

    def read_registers(self, client, address, count):
        """
        Read data from Modbus device.
        :param client: Modbus client instance
        :param address: Register address
        :param count: Register count to be read
        :return: List of registers if successful, None otherwise
        """
        try:
            resp = client.read_holding_registers(address, count, NODE_ID)
            if resp.isError():
                return None    
            return resp.registers
        except ModbusException as e:
            print("ModbusException:{0}".format(e))
            return None

    async def main(self):
        gforce_device = gforce.GForce(DEV_NAME_PREFIX, DEV_MIN_RSSI)

        client = ModbusSerialClient(self.find_comport("CH340"), FramerType.RTU, 115200)
        if not client.connect():
            print("连接Modbus设备失败\nFailed to connect to Modbus device")
            exit(-1)

        def gestures_control(gesture):
            if not self.write_registers(client, ROH_FINGER_POS_TARGET0, GESTURES["REST"]):
                print("控制指令发送失败\nFailed to send control command")
            time.sleep(0.5)
    
            # if not self.write_registers(client, ROH_FINGER_POS_TARGET5, gesture[NUM_FINGERS]):
            #     print("控制指令发送失败\nFailed to send control command")
            # time.sleep(1)

            if not self.write_registers(client, ROH_FINGER_POS_TARGET0, gesture):
                print("控制指令发送失败\nFailed to send control command")

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
