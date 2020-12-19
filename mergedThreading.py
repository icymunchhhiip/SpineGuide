import cv2
import dlib
from math import hypot
import time
import datetime
import pygame
import asyncio

import picamera
import RPi.GPIO as GPIO
from PIL import Image
import requests
import os
import numpy as np
from matplotlib import pyplot as plt
from matplotlib import image as mpimg
from pycocotools.coco import COCO

# blink
def midpoint(p1, p2):
    return int((p1.x + p2.x)/2), int((p1.y + p2.y)/2)

def get_blinking_ratio(image, eye_points, facial_landmarks):
    left_point = (facial_landmarks.part(
        eye_points[0]).x, facial_landmarks.part(eye_points[0]).y)
    right_point = (facial_landmarks.part(
        eye_points[3]).x, facial_landmarks.part(eye_points[3]).y)
    center_top = midpoint(facial_landmarks.part(
        eye_points[1]), facial_landmarks.part(eye_points[2]))
    center_bottom = midpoint(facial_landmarks.part(
        eye_points[5]), facial_landmarks.part(eye_points[4]))

    hor_line = cv2.line(image, left_point, right_point, (0, 255, 0), 2)
    ver_line = cv2.line(image, center_top, center_bottom, (0, 255, 0), 2)

    hor_line_lenght = hypot(
        (left_point[0] - right_point[0]), (left_point[1] - right_point[1]))
    ver_line_lenght = hypot(
        (center_top[0] - center_bottom[0]), (center_top[1] - center_bottom[1]))

    ratio = hor_line_lenght / ver_line_lenght
    return ratio

# pose
def inference(filename):
    with open(filename, 'rb') as f:
        response = session.post('https://cv-api.kakaobrain.com/pose', files=[('file', f)])
        return response.json()

def visualori(filename, annotations, threshold=0.2):
    for annotation in annotations:
        keypoints = np.asarray(annotation['keypoints']).reshape(-1, 3)
        low_confidence = keypoints[:, -1] < threshold
        keypoints[low_confidence, :] = [0, 0, 0]
        annotation['keypoints'] = keypoints.reshape(-1).tolist()

    # COCO API를 활용한 시각화
    plt.cla()
    plt.clf()
    plt.imshow(mpimg.imread(filename))
    plt.axis('off')

    coco = COCO()
    coco.dataset = {}
    coco.dataset = {
        "categories": [
            {
                "supercategory": "person",
                "id": 1,
                "name": "person",
                "keypoints": ["nose", "left_eye", "right_eye", "left_ear", "right_ear", "left_shoulder",
                              "right_shoulder", "left_elbow", "right_elbow", "left_wrist", "right_wrist",
                              "left_hip",
                              "right_hip", "left_knee", "right_knee", "left_ankle", "right_ankle"],
                "skeleton": [[1, 2], [1, 3], [2, 3], [2, 4], [3, 5], [4, 6], [5, 7], [6, 7], [6, 8], [6, 12],
                             [7, 9],
                             [7, 13], [8, 10], [9, 11], [12, 13], [14, 12], [15, 13], [16, 14], [17, 15]]
            }
        ]
    }
    coco.createIndex()
    coco.showAnns(annotations)
    plt.savefig('test.jpg')

    img = cv2.imread('test.jpg', cv2.IMREAD_UNCHANGED)
    cv2.waitKey(1)
    return img

def addpic(img, img2):
    newimg = np.hstack((img, img2))
    cv2.imshow('Result', newimg)
    cv2.waitKey(5000)
    cv2.destroyAllWindows()

# main
async def blinkmain():
    # blink
    detector = dlib.get_frontal_face_detector()
    faceCascade = cv2.CascadeClassifier('haarcascade_frontalface_default.xml')
    predictor = dlib.shape_predictor("shape_predictor_68_face_landmarks.dat")
    font = cv2.FONT_HERSHEY_SIMPLEX

    JAWLINE_POINTS = list(range(0, 17))
    RIGHT_EYEBROW_POINTS = list(range(17, 22))
    LEFT_EYEBROW_POINTS = list(range(22, 27))
    NOSE_POINTS = list(range(27, 36))
    LEFT_EYE_POINTS = list(range(36, 42))
    RIGHT_EYE_POINTS = list(range(42, 48))
    MOUTH_OUTLINE_POINTS = list(range(48, 61))
    MOUTH_INNER_POINTS = list(range(61, 68))

    capture = cv2.VideoCapture(0)
    capture.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    BLINK_CYCLE_SEC = 5

    pygame.mixer.init()
    blink_sound = pygame.mixer.Sound("please_blink.wav")
    SOUND_LENTH = 2
    sound_time = SOUND_LENTH
    last_time_blink = time.time()

    while True:
        _, image = capture.read()

        # convert frame to gray
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        faces = detector(gray)

        for face in faces:
            landmarks = predictor(gray, face)

            left_eye_ratio = get_blinking_ratio(image,
                LEFT_EYE_POINTS, landmarks)
            right_eye_ratio = get_blinking_ratio(image,
                RIGHT_EYE_POINTS, landmarks)
            blinking_ratio = (left_eye_ratio + right_eye_ratio) / 2
            if blinking_ratio >= 4.3:
                last_time_blink = time.time()
                cv2.putText(image, "blinking", (50, 50), font, 2, (255, 0, 0))
                print("blinking")
            elif (time.time() - last_time_blink) >= BLINK_CYCLE_SEC:
                cv2.putText(image, "please blink", (50, 50), font, 2, (0, 255, 0))
                print("please blink")
                if (time.time() - sound_time) >= SOUND_LENTH:
                    sound_time = time.time()
                    blink_sound.play()

        # show the frame
        cv2.imshow("Frame", image)
        key = cv2.waitKey(1) & 0xFF

        # if the `q` key was pressed, break from the loop
        if key == ord("q"):
            break
        print("sleep blink")
        await asyncio.sleep(5)
        print("awake blink")

async def posemain():
    # pose
    pygame.mixer.init()
    bang = pygame.mixer.Sound("please_correct.wav")
    quitm = pygame.mixer.Sound("quit.wav")
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(17, GPIO.IN, GPIO.PUD_UP)

    APP_KEY = '61438e2034d5616b9ecaf5ab8ccf7bf7'

    session = requests.Session()
    session.headers.update({'Authorization': 'KakaoAK ' + APP_KEY})

    ORIGIN_PATH = '/home/pi/HumanIron/origin.jpg'
    NEW_PATH = '/home/pi/HumanIron/new.jpg'

    with picamera.PiCamera() as camera:
        camera.start_preview()
        frame = 1
        GPIO.wait_for_edge(17, GPIO.FALLING)

        camera.capture(ORIGIN_PATH)
        orgimg = Image.open(ORIGIN_PATH)
        orgimg.save(ORIGIN_PATH, quality=86)

        origin = inference(ORIGIN_PATH)
        img = visualori(ORIGIN_PATH, origin)

        while True:
            start = time.time()
            camera.capture(NEW_PATH)
            newimg = Image.open(NEW_PATH)
            newimg.save(NEW_PATH, quality=86)
            newdata = inference(NEW_PATH)
            img2 = visualori(NEW_PATH, newdata)

            try:
                # 캡쳐 이미자
                # 파일로 이미지 입력시
                oleft_shoulder = origin[0]["keypoints"][6]
                oright_shoulder = origin[0]["keypoints"][7]
                onose = origin[0]["keypoints"][0]
                # t분에 한번씩 이미지 저장
                sleft_shoulder = newdata[0]["keypoints"][6]
                sright_shoulder = newdata[0]["keypoints"][7]
                snose = newdata[0]["keypoints"][0]

                lsd = oleft_shoulder - sleft_shoulder
                rsd = oright_shoulder - sright_shoulder
                nd = onose - snose

                if abs(lsd) > 30 or abs(rsd) > 30 or abs(nd) > 30:
                    print(" alarm")
                    bang.play()
                    addpic(img, img2)

                else:
                    print(abs(lsd))
                    print(abs(rsd))
                    print(abs(nd))
                    camera.stop_preview()
                    await asyncio.sleep(
                        int(5) - (time.time() - start)
                    )
                print("sleep pose")
                await asyncio.sleep(30)
                print("awake pose")
            except:
                quitm.play()
                break

async def process_async():
    start = time.time()
    await asyncio.wait([
        blinkmain(),
        posemain()
    ])
    end = time.time()
    print(f'>>> 비동기 처리 총 소요 시간: {end - start}')

if __name__ == '__main__':
    asyncio.run(process_async())
