import os
import cv2
from roh_registers_v1 import *
from cvzone.HandTrackingModule import HandDetector
from pymodbus import FramerType
from pymodbus.client import ModbusSerialClient


COM_PORT = "COM8"
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

client = ModbusSerialClient(COM_PORT, FramerType.RTU, 115200)
client.connect()

prev_gesture = [0, 0, 0, 0, 0, 0]

while True:
    _, img = video.read()
    img = cv2.flip(img, 1)
    hand = detector.findHands(img, draw=False)
    gesture_pic = cv2.imread(file_path + "/gestures/0.png")
    gesture = [45000, 65535, 65535, 65535, 65535, 0]

    if hand:
        lmlist = hand[0]

        if lmlist and lmlist[0]:
            finger_up = detector.fingersUp(lmlist[0])

            for i in range(5):
                gesture[i] = gesture[i] * (1 - finger_up[i])

            # print(gesture)

            if finger_up == [0, 1, 0, 0, 0]:
                gesture_pic = cv2.imread(file_path + "/gestures/1.png")
            elif finger_up == [0, 1, 1, 0, 0]:
                gesture_pic = cv2.imread(file_path + "/gestures/2.png")
            elif finger_up == [0, 1, 1, 1, 0]:
                gesture_pic = cv2.imread(file_path + "/gestures/3.png")
            elif finger_up == [0, 1, 1, 1, 1]:
                gesture_pic = cv2.imread(file_path + "/gestures/4.png")
            elif finger_up == [1, 1, 1, 1, 1]:
                gesture_pic = cv2.imread(file_path + "/gestures/5.png")

    # print(gesture_pic)
    if gesture_pic.any():
        gesture_pic = cv2.resize(gesture_pic, (161, 203))
        img[0:203, 0:161] = gesture_pic
        cv2.imshow("Video", img)

    if (prev_gesture != gesture):
        resp = client.write_registers(ROH_FINGER_POS_TARGET0, gesture, NODE_ID)
        print("client.write_registers() returned", resp)
        prev_gesture = gesture

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

video.release()
cv2.destroyAllWindows()
client.close()
