import os
import cv2
import keyboard

from pymodbus import FramerType
from pymodbus.client import ModbusSerialClient
from pymodbus.exceptions import ModbusException
from serial.tools import list_ports

from HandTrackingModule import HandDetector
from roh_registers_v1 import *

# Hand configuration
NUM_FINGERS = 6
NODE_ID = 2

file_path = os.path.abspath(os.path.dirname(__file__))

video = cv2.VideoCapture(0)

# 获取摄像头的分辨率
width = int(video.get(cv2.CAP_PROP_FRAME_WIDTH))  # 摄像头帧宽度
height = int(video.get(cv2.CAP_PROP_FRAME_HEIGHT))  # 摄像头帧高度

detector = HandDetector(maxHands=1, detectionCon=0.8)

# 创建可调整大小的窗口
cv2.namedWindow("Video", cv2.WINDOW_NORMAL)

# 设置窗口大小为摄像头分辨率
cv2.resizeWindow("Video", width, height)

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

def main():
    client = ModbusSerialClient(find_comport("CH340"), FramerType.RTU, 115200)
    if not client.connect():
        print("连接Modbus设备失败\nFailed to connect to Modbus device")
        exit(-1)

    prev_gesture = [0, 0, 0, 0, 0, 0]

    while True:
        _, img = video.read()
        img = cv2.flip(img, 1)
        hand = detector.findHands(img, draw=True)
        gesture_pic = cv2.imread(file_path + "/gestures/unknown.png")
        gesture = [45000, 65535, 65535, 65535, 65535, 65535]

        if hand:
            lmlist = hand[0]

            if lmlist and lmlist[0]:
                try:
                    finger_up = detector.fingersUp(lmlist[0])
                    for i in range(len(finger_up)):
                        gesture[i] = int(gesture[i] * (1 - finger_up[i]))
                except Exception as e:
                    print(str(e))

                # print(gesture)

                if finger_up[:5] == [0, 0, 0, 0, 0]:
                    gesture_pic = cv2.imread(file_path + "/gestures/0.png")
                elif finger_up[:5] == [0, 1, 0, 0, 0]:
                    gesture_pic = cv2.imread(file_path + "/gestures/1.png")
                elif finger_up[:5] == [0, 1, 1, 0, 0]:
                    gesture_pic = cv2.imread(file_path + "/gestures/2.png")
                elif finger_up[:5] == [0, 1, 1, 1, 0]:
                    gesture_pic = cv2.imread(file_path + "/gestures/3.png")
                elif finger_up[:5] == [0, 1, 1, 1, 1]:
                    gesture_pic = cv2.imread(file_path + "/gestures/4.png")
                elif finger_up[:5] == [1, 1, 1, 1, 1]:
                    gesture_pic = cv2.imread(file_path + "/gestures/5.png")
            else:
                gesture = [0, 0, 0, 0, 0, 0]

        # print(gesture_pic)
        if gesture_pic.any():
            gesture_pic = cv2.resize(gesture_pic, (161, 203))
            img[0:203, 0:161] = gesture_pic
            cv2.putText(img, "Try with gestures", (16, 272), cv2.FONT_HERSHEY_SIMPLEX, 2, (0, 255, 0), 5)
            cv2.imshow("Video", img)


        if (prev_gesture != gesture):
            if not write_registers(client, ROH_FINGER_POS_TARGET0, gesture):
                print("写入目标位置失败\nFailed to write target position")
            prev_gesture = gesture

        if cv2.waitKey(1) & 0xFF == ord('q'):
                break

    video.release()
    cv2.destroyAllWindows()
    client.close()

if __name__ == "__main__":
    main()
