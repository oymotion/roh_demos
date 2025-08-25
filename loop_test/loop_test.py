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

# ROHand configuration
NODE_ID = [2] # Support multiple nodes
WITH_LODE = False # Choose with load or without load
TIME_DELAY = 1.5

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
        for i in range(len(NODE_ID)):
            try:
                resp = client.write_registers(address, values, NODE_ID[i])
                if resp.isError():
                    print("client.write_registers() returned", resp)
                    return False
            except ModbusException as e:
                print("ModbusException:{0}".format(e))
                return False
        return True

    def read_registers(self, client, address, count, node_id):
        """
        Read data from Modbus device.
        :param client: Modbus client instance
        :param address: Register address
        :param count: Register count to be read
        :return: List of registers if successful, None otherwise
        """
        try:
            resp = client.read_holding_registers(address, count, node_id)
            if resp.isError():
                return None    
            return resp.registers
        except ModbusException as e:
            print("ModbusException:{0}".format(e))
            return None
        
    def loop_without_load(self, client):
            #
            # Close thumb then spread
            if not self.write_registers(client, ROH_FINGER_POS_TARGET0, [65535]):
                return False
            time.sleep(TIME_DELAY)

            if not self.write_registers(client, ROH_FINGER_POS_TARGET0, [0]):
                return False
            time.sleep(TIME_DELAY)

            #
            # Rotate thumb root
            if not self.write_registers(client, ROH_FINGER_POS_TARGET5, [65535]):
                return False
            time.sleep(TIME_DELAY)

            if not self.write_registers(client, ROH_FINGER_POS_TARGET5, [0]):
                return False
            time.sleep(TIME_DELAY)

            #
            # Close other fingers then spread
            if not self.write_registers(client, ROH_FINGER_POS_TARGET1, [65535, 65535, 65535, 65535]):
                return False
            time.sleep(TIME_DELAY)

            if not self.write_registers(client, ROH_FINGER_POS_TARGET1, [0, 0, 0, 0]):
                return False
            time.sleep(TIME_DELAY)
      
            return True
    
    def loop_with_load(self, client):
        #
        # Close other fingers then spread
        if not self.write_registers(client, ROH_FINGER_POS_TARGET0, [65535, 65535, 65535, 65535, 65535]):
            return False
        time.sleep(TIME_DELAY)
            
        if not self.write_registers(client, ROH_FINGER_POS_TARGET0, [0, 0, 0, 0, 0]):
            return False
        time.sleep(TIME_DELAY)
        
        return True

    async def main(self):
        client = ModbusSerialClient(self.find_comport("CH340"), FramerType.RTU, 115200)
        if not client.connect():
            print("Failed to connect Modbus device")
            exit(-1)

        # Open all fingers
        self.write_registers(client, ROH_FINGER_POS_TARGET0, [0, 0, 0, 0, 0, 0])
        time.sleep(TIME_DELAY)

        if WITH_LODE:
            # Rotate thumb root to opposite
            self.write_registers(client, ROH_FINGER_POS_TARGET5, [65535])
            time.sleep(TIME_DELAY)

        loop_time = 0

        while not self.terminated:
            
            if WITH_LODE:
                if not self.loop_with_load(client):
                    break
            else:
                if not self.loop_without_load(client):
                    break

            loop_time += 1
            print("Loop executed:", loop_time)


if __name__ == "__main__":
    app = Application()
    asyncio.run(app.main())
