import ctypes
import math
import sys
import time

import cv2
import mediapipe as mp
import numpy as np
import pyautogui


# Enables Windows DPI awareness
def enable_dpi_awareness():
    if sys.platform.startswith("win"):
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            try:
                ctypes.windll.user32.SetProcessDPIAware()
            except Exception:
                pass


# Returns hand finger states
def get_finger_states(landmarks):
    index_up  = landmarks[8].y < landmarks[6].y
    middle_up = landmarks[12].y < landmarks[10].y
    ring_up   = landmarks[16].y < landmarks[14].y
    pinky_up  = landmarks[20].y < landmarks[18].y
    return index_up, middle_up, ring_up, pinky_up


# Returns distance between two points
def distance_pixels(point1, point2):
    return int(math.hypot(point2[0] - point1[0], point2[1] - point1[1]))


# Keeps value inside range
def clamp(value, min_value, max_value):
    return max(min_value, min(value, max_value))


# Draws a simple panel
def draw_panel(image, x1, y1, x2, y2, color, alpha=0.35):
    overlay = image.copy()
    cv2.rectangle(overlay, (x1, y1), (x2, y2), color, -1)
    cv2.addWeighted(overlay, alpha, image, 1 - alpha, 0, image)
    cv2.rectangle(image, (x1, y1), (x2, y2), color, 2)


# Draws text on image
def draw_text(image, text, position, scale=0.7, color=(255, 255, 255), thickness=2):
    cv2.putText(
        image,
        text,
        position,
        cv2.FONT_HERSHEY_SIMPLEX,
        scale,
        color,
        thickness,
        cv2.LINE_AA
    )


# Creates MediaPipe hand tracker
def create_hand_tracker():
    mp_hands = mp.solutions.hands
    hand_tracker = mp_hands.Hands(
        static_image_mode=False,
        max_num_hands=1,
        model_complexity=1,
        min_detection_confidence=0.7,
        min_tracking_confidence=0.7
    )
    return mp_hands, mp.solutions.drawing_utils, hand_tracker


# Opens the main camera
def open_camera(camera_width, camera_height):
    camera = cv2.VideoCapture(0, cv2.CAP_DSHOW)
    camera.set(cv2.CAP_PROP_FRAME_WIDTH, camera_width)
    camera.set(cv2.CAP_PROP_FRAME_HEIGHT, camera_height)

    if not camera.isOpened():
        camera = cv2.VideoCapture(0)

    if not camera.isOpened():
        raise RuntimeError("Camera could not be opened.")

    return camera


# Moves mouse with smoothing
def move_mouse(index_tip, frame_width, frame_height, previous_x, previous_y, screen_width, screen_height):
    x = clamp(index_tip[0], FrameReduction, frame_width - FrameReduction)
    y = clamp(index_tip[1], FrameReduction, frame_height - FrameReduction)

    screen_x = np.interp(x, (FrameReduction, frame_width - FrameReduction), (0, screen_width - 1))
    screen_y = np.interp(y, (FrameReduction, frame_height - FrameReduction), (0, screen_height - 1))

    current_x = previous_x + (screen_x - previous_x) / Smoothing
    current_y = previous_y + (screen_y - previous_y) / Smoothing

    pyautogui.moveTo(int(current_x), int(current_y))
    return current_x, current_y, x, y


# Handles scroll mode
def handle_scroll(index_tip, middle_tip, scroll_anchor_y):
    average_y = (index_tip[1] + middle_tip[1]) // 2

    if scroll_anchor_y is None:
        return average_y

    delta_y = scroll_anchor_y - average_y
    if abs(delta_y) > ScrollDeadzone:
        pyautogui.scroll(int(delta_y * (ScrollStep / 10)))
        return average_y

    return scroll_anchor_y


# Draws status panels
def draw_status(frame, frame_width, frame_height, mode_text, status_color, thumb_index_distance, thumb_middle_distance, fps):
    draw_panel(frame, 15, 15, 240, 115, Dark, alpha=0.45)
    draw_text(frame, f"Mode: {mode_text}", (30, 45), 0.8, status_color, 2)
    draw_text(frame, f"Thumb-Index: {thumb_index_distance}", (30, 80), 0.65, White, 2) # baş parmak - işaret p. arası mesafe
    draw_text(frame, f"Thumb-Middle: {thumb_middle_distance}", (30, 110), 0.65, White, 2) # baş p. - orta p arası mesafe

    draw_panel(frame, frame_width - 180, 15, frame_width - 15, 70, Dark, alpha=0.45)
    draw_text(frame, f"FPS: {int(fps)}", (frame_width - 160, 50), 0.75, Green, 2)

    draw_panel(frame, 15, frame_height - 75, 320, frame_height - 15, Dark, alpha=0.45)
    draw_text(frame, "ESC = Exit", (30, frame_height - 38), 0.7, White, 2)


enable_dpi_awareness()

pyautogui.FAILSAFE = False
pyautogui.PAUSE    = 0

ScreenWidth, ScreenHeight = pyautogui.size()

CameraWidth      = 1280
CameraHeight     = 720
FrameReduction   = 120
Smoothing        = 6
ClickCooldown    = 0.35
LeftClickDistance  = 30
RightClickDistance = 35
ScrollDeadzone   = 10
ScrollStep       = 40

Accent = (255, 120, 0)
Green  = (80, 220, 120)
Red    = (80, 80, 255)
Cyan   = (255, 255, 0)
White  = (255, 255, 255)
Dark   = (20, 20, 20)
Yellow = (0, 255, 255)

MpHands, MpDraw, Hands = create_hand_tracker()
Camera = open_camera(CameraWidth, CameraHeight)

PreviousX = 0
PreviousY = 0

LastLeftClickTime  = 0
LastRightClickTime = 0
ScrollAnchorY      = None
PreviousFrameTime  = time.time()

while True:
    success, frame = Camera.read()
    if not success:
        print("Could not read frame from camera.")
        break

    frame   = cv2.flip(frame, 1)
    rgb     = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    results = Hands.process(rgb)

    frame_height, frame_width, _ = frame.shape
    mode_text    = "NO HAND"
    status_color = Red

    cv2.rectangle(
        frame,
        (FrameReduction, FrameReduction),
        (frame_width - FrameReduction, frame_height - FrameReduction),
        Accent,
        2
    )

    thumb_index_distance  = 0
    thumb_middle_distance = 0

    if results.multi_hand_landmarks:
        hand_landmarks = results.multi_hand_landmarks[0]

        MpDraw.draw_landmarks(
            frame,
            hand_landmarks,
            MpHands.HAND_CONNECTIONS,
            MpDraw.DrawingSpec(color=Cyan, thickness=2, circle_radius=2),
            MpDraw.DrawingSpec(color=Green, thickness=2, circle_radius=2)
        )

        landmarks = hand_landmarks.landmark

        index_tip  = (int(landmarks[8].x * frame_width), int(landmarks[8].y * frame_height))
        thumb_tip  = (int(landmarks[4].x * frame_width), int(landmarks[4].y * frame_height))
        middle_tip = (int(landmarks[12].x * frame_width), int(landmarks[12].y * frame_height))

        index_up, middle_up, ring_up, pinky_up = get_finger_states(landmarks)

        cv2.circle(frame, index_tip, 10, Green, cv2.FILLED)
        cv2.circle(frame, thumb_tip, 10, Accent, cv2.FILLED)
        cv2.circle(frame, middle_tip, 10, Cyan, cv2.FILLED)

        thumb_index_distance  = distance_pixels(thumb_tip, index_tip)
        thumb_middle_distance = distance_pixels(thumb_tip, middle_tip)

        if index_up and not middle_up and not ring_up and not pinky_up:
            mode_text    = "MOVE"
            status_color = Green

            PreviousX, PreviousY, x, y = move_mouse(
                index_tip,
                frame_width,
                frame_height,
                PreviousX,
                PreviousY,
                ScreenWidth,
                ScreenHeight
            )

            ScrollAnchorY = None
            cv2.circle(frame, (x, y), 14, Yellow, 2)

        elif index_up and middle_up and not ring_up and not pinky_up:
            mode_text    = "SCROLL"
            status_color = Cyan
            ScrollAnchorY = handle_scroll(index_tip, middle_tip, ScrollAnchorY)
            cv2.line(frame, index_tip, middle_tip, Cyan, 3)

        else:
            ScrollAnchorY = None

        now = time.time()

        if thumb_index_distance < LeftClickDistance:
            cv2.line(frame, thumb_tip, index_tip, Yellow, 3)
            if now - LastLeftClickTime > ClickCooldown:
                pyautogui.click()
                LastLeftClickTime = now
                mode_text         = "LEFT CLICK"
                status_color      = Yellow

        if thumb_middle_distance < RightClickDistance:
            cv2.line(frame, thumb_tip, middle_tip, Accent, 3)
            if now - LastRightClickTime > ClickCooldown:
                pyautogui.click(button="right")
                LastRightClickTime = now
                mode_text          = "RIGHT CLICK"
                status_color       = Accent

    current_time = time.time()
    fps = 1 / (current_time - PreviousFrameTime) if current_time != PreviousFrameTime else 0
    PreviousFrameTime = current_time

    draw_status(
        frame,
        frame_width,
        frame_height,
        mode_text,
        status_color,
        thumb_index_distance,
        thumb_middle_distance,
        fps
    )

    cv2.imshow("Finger Follow Mouse Control", frame)

    key = cv2.waitKey(1) & 0xFF
    if key == 27:
        break

Camera.release()
cv2.destroyAllWindows()
