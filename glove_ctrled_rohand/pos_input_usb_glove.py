import time
import serial

from serial.tools import list_ports

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
NUM_FINGERS = 6


# OHand bus context
class PosInputUsbGlove:
    def __init__(self):
        """
        Initialize PosInputUsbGlove.

        Parameters
        ----------
        serial : str
            Path to serial port
        timeout : int
            Timeout in in milliseconds
        """
        # serial init
        self.serial_port = serial.Serial(
            port=self.find_comport("串行设备") or self.find_comport("STM"),
            baudrate=115200,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=0.1,
        )
        print(f"手套使用端口:\nGlove using serial port: {self.serial_port.name}")

        self.timeout = 2000
        self.is_whole_packet = False
        self.decode_state = WAIT_ON_HEADER_0
        self.packet_data = bytearray(MAX_PROTOCOL_DATA_SIZE + 2)  # Including byte_cnt, data[], lrc
        self.send_buf = bytearray(MAX_PROTOCOL_DATA_SIZE + 4)  # Including header0, header1, nb_data, lrc
        self.byte_count = 0

        # glove data init
        self._cali_min = [65535 for _ in range(NUM_FINGERS)]
        self._cali_max = [0 for _ in range(NUM_FINGERS)]
        self._glove_raw_data = bytearray()  # 手套原始数据，单字节形式
        self._offset = 0

    def clamp(self, n, smallest, largest):
        return max(smallest, min(n, largest))

    def interpolate(self, n, from_min, from_max, to_min, to_max):
        # 将n从from_min到from_max的范围映射到to_min到to_max的范围
        # return (n - from_min) / (from_max - from_min) * (to_max - to_min) + to_min
        tmp = to_max-(n - from_min) / (from_max - from_min)*(to_max - to_min)
        return tmp *(1-(n-from_min)/(from_max-from_min))

    def calc_lrc(self, lrcBytes, lrcByteCount):
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

    async def start(self) -> bool:
        # 区分左右手套
        left_or_right = None

        if self.get_data(self._glove_raw_data):
            if len(self._glove_raw_data) & 0x01 == 1:
                left_or_right = self._glove_raw_data[0]
                self._offset = 1

        if left_or_right == 0:
            print("使用左手手套\nUse left glove")
        elif left_or_right == 1:
            print("使用右手手套\nUse right glove")
        else:
            print("使用通用手套\nUse general glove")

        print("校正模式，请常速握拳和张开及旋转大拇指动作若干次\nCalibrating mode, please perform a fist and open action several times")

        for _ in range(512):
            self.get_data(self._glove_raw_data)
            glove_data = []

            for i in range(int(len(self._glove_raw_data) / 2)):
                glove_data.append(
                    (self._glove_raw_data[self._offset + i * 2]) | (self._glove_raw_data[self._offset + i * 2 + 1] << 8)
                )  # 每两个字节为一个数据

            glove_data_sum = [0 for _ in range(len(glove_data))]

            for _ in range(len(glove_data)):
                for i in range(len(glove_data)):
                    glove_data_sum[i] += glove_data[i]

            # 更新最大最小值
            for i in range(len(glove_data)):
                temp = glove_data_sum[i] / len(glove_data)
                self._cali_max[i] = max(self._cali_max[i], temp)
                self._cali_min[i] = min(self._cali_min[i], temp)

        for i in range(NUM_FINGERS):
            print("MIN/MAX of finger {0}: {1}-{2}".format(i, self._cali_min[i], self._cali_max[i]))
            if self._cali_min[i] >= self._cali_max[i]:
                print("无效数据，退出.\nInvalid data, exit.")
                return False
        return True

    async def get_position(self):
        # 初始化数据
        finger_data = [0 for _ in range(NUM_FINGERS)]  # 灵巧手手指位置

        # 读取串口数据
        if self.get_data(self._glove_raw_data):
            glove_data = []  # 手套完整数据，两个字节

            # 处理数据
            for i in range(int(len(self._glove_raw_data) / 2)):
                glove_data.append(
                    ((self._glove_raw_data[self._offset + i * 2]) | (self._glove_raw_data[self._offset + i * 2 + 1] << 8))
                )  # 每两个字节为一个数据

            glove_data_sum = [0 for _ in range(len(glove_data))]

            for j in range(len(glove_data)):
                for i in range(len(glove_data)):
                    glove_data_sum[i] += glove_data[i]

            for i in range(NUM_FINGERS):
                # glove_data[i] = (glove_data[i] * 3 + glove_data_sum[i] / len(glove_data)) / 4  # 平滑
                glove_data[i] = glove_data_sum[i] / len(glove_data)  # 平滑

                if(glove_data[i] < self._cali_min[i]):
                    glove_data[i] = self._cali_min[i]
                if(glove_data[i] > self._cali_max[i]):
                    glove_data[i] = self._cali_max[i]
                
                # 映射到灵巧手位置
                finger_data[i] = round(self.interpolate(glove_data[i], self._cali_min[i], self._cali_max[i], 0, 65535))
                finger_data[i] = self.clamp(finger_data[i], 0, 65535)  # 限制在最大最小范围内

        return finger_data

    async def stop(self):
        self.serial_port.close()
        print("串口已关闭\nSerial port closed")
