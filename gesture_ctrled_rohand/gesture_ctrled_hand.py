import os
import cv2
from roh_registers_v1 import *
from cvzone.HandTrackingModule import HandDetector
from pymodbus import FramerType
from pymodbus.client import ModbusSerialClient


COM_PORT = "COM4"
NODE_ID = 2

file_path = os.path.abspath(os.path.dirname(__file__))

video = cv2.VideoCapture(0) 

# # 获取摄像头的分辨率
# width = int(video.get(cv2.CAP_PROP_FRAME_WIDTH))  # 摄像头帧宽度
# height = int(video.get(cv2.CAP_PROP_FRAME_HEIGHT))  # 摄像头帧高度

# # 创建可调整大小的窗口
# cv2.namedWindow("window", cv2.WINDOW_NORMAL)

# # 设置窗口大小为摄像头分辨率
# cv2.resizeWindow("window", width, height)

cv2.namedWindow("window", cv2.WND_PROP_FULLSCREEN)
cv2.setWindowProperty("window", cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)

detector = HandDetector(maxHands=5, detectionCon=0.8)

client = ModbusSerialClient(COM_PORT, FramerType.RTU, 115200)
client.connect()

GESTURE_CLOSE = [45000, 65535, 65535, 65535, 65535, 0]
prev_gesture = GESTURE_CLOSE.copy()
gesture = GESTURE_CLOSE.copy()

while True:
    _, img = video.read()
    img = cv2.flip(img, 1)
    hands = detector.findHands(img, draw=True)
    # print(hands)
    gesture_pic = cv2.imread(file_path + "/gestures/unknown.png")
    selected_hand = None
    cy_min = 65535

    if len(hands) > 0:
        for idx in range(len(hands)):
            # print(hands[idx])
            for idx2 in range(len(hands[idx])): 
                hand = hands[idx][idx2]
                # print(f"hands[{idx}]: {hand}, type: {type(hand)}")

                if (hand is not None) and (type(hand) == dict):
                    print(f"hands[{idx}][{[idx2]}]: {hand}")
                    lmlist = hand['lmList']
                    cx, cy = hand['center']
                    
                    if cy_min > cy:
                        cy_min = cy
                        selected_hand = hand
                    # endif
                # end if
            # end if
        # end for
    # end if

    gesture = [0, 0, 0, 0, 0]

    if selected_hand is not None:
        lmlist = selected_hand['lmList']
        bbox = selected_hand['bbox']

        cv2.rectangle(img, (bbox[0] - 20, bbox[1] - 20), (bbox[0] + bbox[2] + 20, bbox[1] + bbox[3] + 20), (0, 255, 0), 2)

        finger_up = detector.fingersUp(selected_hand)

        for i in range(5):
            gesture[i] = GESTURE_CLOSE[i] * (1 - finger_up[i])

        # print(gesture)

        if finger_up == [0, 0, 0, 0, 0]:
            gesture_pic = cv2.imread(file_path + "/gestures/0.png")
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
    # end if

    # print(gesture_pic)
    if gesture_pic.any():
        gesture_pic = cv2.resize(gesture_pic, (161, 203))
        img[0:203, 0:161] = gesture_pic
        cv2.putText(img, "Try with gestures", (16, 272), cv2.FONT_HERSHEY_SIMPLEX, 2, (0, 255, 0), 5)
        cv2.imshow("window", img)

    if prev_gesture != gesture:
        resp = client.write_registers(ROH_FINGER_POS_TARGET0, gesture, NODE_ID)
        print("client.write_registers() returned", resp)
        prev_gesture = gesture

    if cv2.waitKey(1) & 0xFF == ord("q"):
        break

video.release()
cv2.destroyAllWindows()
client.close()
