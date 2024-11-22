# Sample code to get glove data and controls ROHand via ModBus-RTU protocol

import asyncio
import os
import signal
import sys
import time

from pymodbus import FramerType
from pymodbus.client import ModbusSerialClient

from roh_registers_v1 import *

# ROHand configuration
COM_PORT = "COM7"
NODE_ID = 2

# Device filters

NUM_FINGERS = 5


current_dir = os.path.dirname(os.path.realpath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)


class Application:

    def __init__(self):
        signal.signal(signal.SIGINT, lambda signal, frame: self._signal_handler())
        self.terminated = False

    def _signal_handler(self):
        print("You pressed ctrl-c, exit")
        self.terminated = True

    def write_registers(self, client, address, values, node_id):
        resp = client.write_registers(address, values, node_id)
        if resp.isError():
            print("client.write_registers() returned", resp)
            return False
        else :
            return True

    async def main(self):
        client = ModbusSerialClient(COM_PORT, FramerType.RTU, 115200)
        client.connect()

        # Set current limit
        self.write_registers(client, ROH_FINGER_CURRENT_LIMIT0, [200, 200, 200, 200, 200, 200], NODE_ID)
        time.sleep(1.5)

        print("Moving thumb root...")
        # Open all fingers
        self.write_registers(client, ROH_FINGER_POS_TARGET0, [0, 0, 0, 0, 0], NODE_ID)
        time.sleep(1.5)

        # Rotate thumb root to opposite
        self.write_registers(client, ROH_FINGER_POS_TARGET5, [65535], NODE_ID)
        time.sleep(1.5)

        loop_time = 0

        while not self.terminated:
            #
            # Close other fingers then spread
            if not self.write_registers(client, ROH_FINGER_POS_TARGET1, [65535, 65535, 65535, 65535], NODE_ID):
                break
            time.sleep(1.5)
            
            if not self.write_registers(client, ROH_FINGER_POS_TARGET1, [0, 0, 0, 0], NODE_ID):
                break
            time.sleep(1.5)

            loop_time += 1
            print("Loop executed:", loop_time)
            


if __name__ == "__main__":
    app = Application()
    asyncio.run(app.main())
