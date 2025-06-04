import time
import serial
import os
import sys
import asyncio
import serial

from roh_registers_v1 import *
from serial.tools import list_ports
from pymodbus import FramerType
from pymodbus.client import ModbusSerialClient
from pymodbus.exceptions import ModbusException

# Constants
MAX_PROTOCOL_DATA_SIZE = 64

# Protocol states
WAIT_ON_HEADER_0 = 0
WAIT_ON_HEADER_1 = 1
WAIT_ON_BYTE_COUNT = 2
WAIT_ON_DATA = 3
WAIT_ON_LRC = 4

# Protocol byte name
DATA_CNT_BYTE_NUM = 0
DATA_START_BYTE_NUM = 1

# ROHand configuration
NODE_ID = 2
NUM_FINGERS = 6

current_dir = os.path.dirname(os.path.realpath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

def clamp(n, smallest, largest):
    return max(smallest, min(n, largest))

def interpolate(n, from_min, from_max, to_min, to_max):
    return (n - from_min) / (from_max - from_min) * (to_max - to_min) + to_min

# OHand bus context
class OGlove:
    def __init__(self, serial, timeout):
        """
        Initialize OGlove.

        Parameters
        ----------
        serial : str
            Path to serial port
        timeout : int
            Timeout in in milliseconds
        """
        self.serial_port = serial
        self.timeout = timeout
        self.is_whole_packet = False
        self.decode_state = WAIT_ON_HEADER_0
        self.packet_data = bytearray(MAX_PROTOCOL_DATA_SIZE + 2)  # Including byte_cnt, data[], lrc
        self.send_buf = bytearray(MAX_PROTOCOL_DATA_SIZE + 4)  # Including header0, header1, nb_data, lrc
        self.byte_count = 0

    def calc_lrc(ctx, lrcBytes, lrcByteCount):
        """
        Calculate the LRC for a given sequence of bytes
        :param lrcBytes: sequence of bytes to calculate LRC over
        :param lrcByteCount: number of bytes in the sequence
        :return: calculated LRC value
        """
        lrc = 0
        for i in range(lrcByteCount):
            lrc ^= lrcBytes[i]
        return lrc

    def on_data(self, data):
        """
        Called when a new byte is received from the serial port. This function implements
        a state machine to decode the packet. If a whole packet is received, is_whole_packet
        is set to 1 and the packet is stored in packet_data.

        Args:
            data (int): The newly received byte

        Returns:
            None
        """
        if self is None:
            return

        if self.is_whole_packet:
            return  # Old packet is not processed, ignore

        # State machine implementation
        if self.decode_state == WAIT_ON_HEADER_0:
            if data == 0x55:
                self.decode_state = WAIT_ON_HEADER_1

        elif self.decode_state == WAIT_ON_HEADER_1:
            self.decode_state = WAIT_ON_BYTE_COUNT if data == 0xAA else WAIT_ON_HEADER_0

        elif self.decode_state == WAIT_ON_BYTE_COUNT:
            self.packet_data[DATA_CNT_BYTE_NUM] = data
            self.byte_count = data

            if self.byte_count > MAX_PROTOCOL_DATA_SIZE:
                self.decode_state = WAIT_ON_HEADER_0
            elif self.byte_count > 0:
                self.decode_state = WAIT_ON_DATA
            else:
                self.decode_state = WAIT_ON_LRC

        elif self.decode_state == WAIT_ON_DATA:
            self.packet_data[DATA_START_BYTE_NUM + self.packet_data[DATA_CNT_BYTE_NUM] - self.byte_count] = data
            self.byte_count -= 1

            if self.byte_count == 0:
                self.decode_state = WAIT_ON_LRC

        elif self.decode_state == WAIT_ON_LRC:
            self.packet_data[DATA_START_BYTE_NUM + self.packet_data[DATA_CNT_BYTE_NUM]] = data
            self.is_whole_packet = True
            self.decode_state = WAIT_ON_HEADER_0

        else:
            self.decode_state = WAIT_ON_HEADER_0

    def get_data(self, resp_bytes) -> bool:
        """
        Retrieve a complete packet from the serial port and validate it.

        Args:
            resp_bytes (bytearray): A bytearray to store the response data.

        Returns:
            bool: True if a valid packet is received, False otherwise.
        """
        # Check if self or self.serial_port is None
        if self is None or self.serial_port is None:
            return False

        # 记录开始等待的时间
        wait_start = time.time()
        # 计算等待超时时间
        wait_timeout = wait_start + self.timeout / 1000

        # 循环等待完整的数据包
        while not self.is_whole_packet:
            # time.sleep(0.001)
            # print(f"in_waiting: {self.serial_port.in_waiting}")

            # 如果串口有数据可读
            while self.serial_port.in_waiting > 0:
                # 读取串口数据
                data_bytes = self.serial_port.read(self.serial_port.in_waiting)
                # print("data_bytes: ", len(data_bytes))

                # 遍历读取到的数据
                for ch in data_bytes:
                    # print(f"data: {hex(ch)}")
                    # 处理数据
                    self.on_data(ch)
                # 如果已经读取到完整的数据包，跳出循环
                if self.is_whole_packet:
                    break

            # 如果还没有读取到完整的数据包，并且已经超时，跳出循环
            if (not self.is_whole_packet) and (wait_timeout < time.time()):
                # print(f"wait time out: {wait_timeout}, now: {time.time()}")
                # 重置解码状态
                self.decode_state = WAIT_ON_HEADER_0
                return False

        # Validate LRC
        lrc = self.calc_lrc(self.packet_data, self.packet_data[DATA_CNT_BYTE_NUM] + 1)
        if lrc != self.packet_data[DATA_START_BYTE_NUM + self.packet_data[DATA_CNT_BYTE_NUM]]:
            self.is_whole_packet = False
            return False

        # Copy response data
        if resp_bytes is not None:
            packet_byte_count = self.packet_data[DATA_CNT_BYTE_NUM]
            resp_bytes.clear()
            resp_data = self.packet_data[DATA_START_BYTE_NUM : DATA_START_BYTE_NUM + packet_byte_count]
            for v in resp_data:
                resp_bytes.append(v)

        self.is_whole_packet = False
        return True
    
    def do_calibration(self, cali_min, cali_max) -> bool:
        """
        Do calibration to obtain user-appropriate glove data.

        Args:
            cali_min: Minimum of calicration data.
            cali_min: Maximum of calicration data.

        Returns: 
            bool: True if calibration data is valid, False otherwise.
        """
        cali_min[:] = [2000 for _ in range(NUM_FINGERS)]
        cali_max[:] = [0 for _ in range(NUM_FINGERS)]

        glove_raw_data = bytearray()

        print("校正模式，请执行握拳和张开动作若干次\nCalibrating mode, please perform a fist and open action several times")

        for _ in range(512):
            self.get_data(glove_raw_data)
            glove_data = []

            for i in range(int(len(glove_raw_data) / 2)):
                glove_data.append((glove_raw_data[i * 2]) | (glove_raw_data[i * 2 + 1] << 8)) # 每两个字节为一个数据

                # 不断刷新最大最小值
                cali_max[i] = max(cali_max[i], glove_data[i])
                cali_min[i] = min(cali_min[i], glove_data[i])

        for i in range(NUM_FINGERS):
            print("MIN/MAX of finger {0}: {1}-{2}".format(i, cali_min[i], cali_max[i]))
            if (cali_min[i] >= cali_max[i]):
                print("无效数据，退出.\nInvalid data, exit.")
                return False  
                              
        return True


def find_comport(port_name):
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

def write_registers(client, address, values):
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

def read_registers(client, address, count):
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


async def main():
    # 配置串口参数（根据实际设备修改）
    glove_serial_port = serial.Serial(
        port=find_comport("STM" or "串行设备"),
        baudrate=115200,
        bytesize=serial.EIGHTBITS,
        parity=serial.PARITY_NONE,
        stopbits=serial.STOPBITS_ONE,
        timeout=0.1,
    )
    print(f"手套使用端口:{0}\nGlove using serial port: {0}".format(glove_serial_port.name))

    # 初始化数据
    prev_glove_data = [0 for _ in range(NUM_FINGERS)]
    finger_data = [0 for _ in range(NUM_FINGERS)] # 灵巧手手指位置

    # 连接到Modbus设备
    client = ModbusSerialClient(find_comport("CH340"), FramerType.RTU, 115200)
    if not client.connect():
        print("连接Modbus设备失败\nFailed to connect to Modbus device")
        exit(-1)
    
    # 初始化手套
    oglove = OGlove(serial=glove_serial_port, timeout=2000)

    # 开始校正
    cali_min = [0 for _ in range(NUM_FINGERS)]
    cali_max = [0 for _ in range(NUM_FINGERS)]
    if not (oglove.do_calibration(cali_min, cali_max)):
        exit(-1)
        
    try:
        glove_raw_data = bytearray() # 手套原始数据，单字节形式

        while True:
            # 读取串口数据
            if oglove.get_data(glove_raw_data):
                glove_data = [] # 手套完整数据，两个字节

                # 处理数据
                for i in range(int(len(glove_raw_data) / 2)):
                    glove_data.append(((glove_raw_data[i * 2]) | (glove_raw_data[i * 2 + 1] << 8))) # 每两个字节为一个数据
                    # glove_data[i] = round((prev_glove_data[i] * 7 + glove_data[i]) / 8)  # 数据平滑处理

                    # 减小发送频率，避免手指抖动
                    if abs(glove_data[i] - prev_glove_data[i]) < 50:
                        glove_data[i] = prev_glove_data[i] 
                    else:
                        prev_glove_data[i] = glove_data[i]  # 保存当前数据

                    # 映射到灵巧手位置
                    finger_data[i] = round(interpolate(glove_data[i], cali_min[i], cali_max[i], 65535, 0))
                    finger_data[i] = clamp(finger_data[i], 0, 65535) # 限制在最大最小范围内

                # print(glove_data)
                # print(finger_data)
                if not write_registers(client, ROH_FINGER_POS_TARGET0, finger_data):
                    print("控制指令发送失败\nFailed to send control command")
            
    except KeyboardInterrupt:
        print("用户终止程序\nUser terminated the program")
    finally:
        glove_serial_port.close()
        print("串口已关闭\nSerial port closed")


if __name__ == "__main__":
    asyncio.run(main())
