import ctypes
import cv2
import mediapipe as mp
import pyautogui
import numpy as np
import math
import time
import sys

# ---------------------------------------------------
# Windows DPI awareness
# ---------------------------------------------------
def enable_dpi_awareness():
    if sys.platform.startswith("win"):
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            try:
                ctypes.windll.user32.SetProcessDPIAware()
            except Exception:
                pass

enable_dpi_awareness()

# ---------------------------------------------------
# PyAutoGUI
# ---------------------------------------------------
pyautogui.FAILSAFE = False
pyautogui.PAUSE = 0

SCREEN_W, SCREEN_H = pyautogui.size()

# ---------------------------------------------------
# Ayarlar
# ---------------------------------------------------
CAM_W = 1280
CAM_H = 720

FRAME_REDUCTION = 120
SMOOTHENING = 6
CLICK_COOLDOWN = 0.35
LEFT_CLICK_DISTANCE = 30
RIGHT_CLICK_DISTANCE = 35
SCROLL_DEADZONE = 10
SCROLL_STEP = 40

ACCENT = (255, 120, 0)
GREEN = (80, 220, 120)
RED = (80, 80, 255)
CYAN = (255, 255, 0)
WHITE = (255, 255, 255)
GRAY = (40, 40, 40)
DARK = (20, 20, 20)
YELLOW = (0, 255, 255)

# ---------------------------------------------------
# MediaPipe
# ---------------------------------------------------
mp_hands = mp.solutions.hands
mp_draw = mp.solutions.drawing_utils

hands = mp_hands.Hands(
    static_image_mode=False,
    max_num_hands=1,
    model_complexity=1,
    min_detection_confidence=0.7,
    min_tracking_confidence=0.7
)

# ---------------------------------------------------
# Kamera
# ---------------------------------------------------
cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAM_W)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAM_H)

if not cap.isOpened():
    cap = cv2.VideoCapture(0)

if not cap.isOpened():
    raise RuntimeError("Kamera acilamadi.")

prev_x, prev_y = 0, 0
curr_x, curr_y = 0, 0

last_left_click_time = 0
last_right_click_time = 0
scroll_anchor_y = None

prev_frame_time = time.time()

# ---------------------------------------------------
# Yardimci fonksiyonlar
# ---------------------------------------------------
def fingers_up(lm):
    index_up = lm[8].y < lm[6].y
    middle_up = lm[12].y < lm[10].y
    ring_up = lm[16].y < lm[14].y
    pinky_up = lm[20].y < lm[18].y
    return index_up, middle_up, ring_up, pinky_up

def distance_px(p1, p2):
    return int(math.hypot(p2[0] - p1[0], p2[1] - p1[1]))

def clamp(value, min_value, max_value):
    return max(min_value, min(value, max_value))

def draw_panel(img, x1, y1, x2, y2, color, alpha=0.35, radius=16):
    overlay = img.copy()
    cv2.rectangle(overlay, (x1, y1), (x2, y2), color, -1)
    cv2.addWeighted(overlay, alpha, img, 1 - alpha, 0, img)
    cv2.rectangle(img, (x1, y1), (x2, y2), color, 2)

def put_text(img, text, org, scale=0.7, color=WHITE, thickness=2):
    cv2.putText(img, text, org, cv2.FONT_HERSHEY_SIMPLEX, scale, color, thickness, cv2.LINE_AA)

# ---------------------------------------------------
# Ana dongu
# ---------------------------------------------------
while True:
    success, frame = cap.read()
    if not success:
        print("Kameradan goruntu okunamadi.")
        break

    frame = cv2.flip(frame, 1)
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    results = hands.process(rgb)

    h, w, _ = frame.shape
    mode_text = "NO HAND"
    status_color = RED

    # Aktif hareket alanı
    cv2.rectangle(
        frame,
        (FRAME_REDUCTION, FRAME_REDUCTION),
        (w - FRAME_REDUCTION, h - FRAME_REDUCTION),
        ACCENT,
        2
    )

    if results.multi_hand_landmarks:
        hand_landmarks = results.multi_hand_landmarks[0]
        mp_draw.draw_landmarks(
            frame,
            hand_landmarks,
            mp_hands.HAND_CONNECTIONS,
            mp_draw.DrawingSpec(color=CYAN, thickness=2, circle_radius=2),
            mp_draw.DrawingSpec(color=GREEN, thickness=2, circle_radius=2)
        )

        lm = hand_landmarks.landmark

        index_tip = (int(lm[8].x * w), int(lm[8].y * h))
        thumb_tip = (int(lm[4].x * w), int(lm[4].y * h))
        middle_tip = (int(lm[12].x * w), int(lm[12].y * h))

        index_up, middle_up, ring_up, pinky_up = fingers_up(lm)

        cv2.circle(frame, index_tip, 10, GREEN, cv2.FILLED)
        cv2.circle(frame, thumb_tip, 10, ACCENT, cv2.FILLED)
        cv2.circle(frame, middle_tip, 10, CYAN, cv2.FILLED)

        thumb_index_dist = distance_px(thumb_tip, index_tip)
        thumb_middle_dist = distance_px(thumb_tip, middle_tip)

        # MOVE
        if index_up and not middle_up and not ring_up and not pinky_up:
            mode_text = "MOVE"
            status_color = GREEN

            x = clamp(index_tip[0], FRAME_REDUCTION, w - FRAME_REDUCTION)
            y = clamp(index_tip[1], FRAME_REDUCTION, h - FRAME_REDUCTION)

            screen_x = np.interp(x, (FRAME_REDUCTION, w - FRAME_REDUCTION), (0, SCREEN_W - 1))
            screen_y = np.interp(y, (FRAME_REDUCTION, h - FRAME_REDUCTION), (0, SCREEN_H - 1))

            curr_x = prev_x + (screen_x - prev_x) / SMOOTHENING
            curr_y = prev_y + (screen_y - prev_y) / SMOOTHENING

            pyautogui.moveTo(int(curr_x), int(curr_y))

            prev_x, prev_y = curr_x, curr_y
            scroll_anchor_y = None

            cv2.circle(frame, (x, y), 14, YELLOW, 2)

        # SCROLL
        elif index_up and middle_up and not ring_up and not pinky_up:
            mode_text = "SCROLL"
            status_color = CYAN

            avg_y = (index_tip[1] + middle_tip[1]) // 2

            if scroll_anchor_y is None:
                scroll_anchor_y = avg_y
            else:
                delta_y = scroll_anchor_y - avg_y
                if abs(delta_y) > SCROLL_DEADZONE:
                    pyautogui.scroll(int(delta_y * (SCROLL_STEP / 10)))
                    scroll_anchor_y = avg_y

            cv2.line(frame, index_tip, middle_tip, CYAN, 3)

        else:
            scroll_anchor_y = None

        now = time.time()

        # LEFT CLICK
        if thumb_index_dist < LEFT_CLICK_DISTANCE:
            cv2.line(frame, thumb_tip, index_tip, YELLOW, 3)
            if now - last_left_click_time > CLICK_COOLDOWN:
                pyautogui.click()
                last_left_click_time = now
                mode_text = "LEFT CLICK"
                status_color = YELLOW

        # RIGHT CLICK
        if thumb_middle_dist < RIGHT_CLICK_DISTANCE:
            cv2.line(frame, thumb_tip, middle_tip, ACCENT, 3)
            if now - last_right_click_time > CLICK_COOLDOWN:
                pyautogui.click(button="right")
                last_right_click_time = now
                mode_text = "RIGHT CLICK"
                status_color = ACCENT

        draw_panel(frame, 15, 15, 300, 145, DARK, alpha=0.45)
        put_text(frame, f"Mode: {mode_text}", (30, 45), 0.8, status_color, 2)
        put_text(frame, f"Thumb-Index: {thumb_index_dist}", (30, 80), 0.65, WHITE, 2)
        put_text(frame, f"Thumb-Middle: {thumb_middle_dist}", (30, 110), 0.65, WHITE, 2)

    else:
        draw_panel(frame, 15, 15, 300, 100, DARK, alpha=0.45)
        put_text(frame, "Mode: NO HAND", (30, 50), 0.8, RED, 2)

    # FPS
    current_time = time.time()
    fps = 1 / (current_time - prev_frame_time) if current_time != prev_frame_time else 0
    prev_frame_time = current_time

    draw_panel(frame, w - 180, 15, w - 15, 70, DARK, alpha=0.45)
    put_text(frame, f"FPS: {int(fps)}", (w - 160, 50), 0.75, GREEN, 2)

    draw_panel(frame, 15, h - 75, 320, h - 15, DARK, alpha=0.45)
    put_text(frame, "ESC = Cikis", (30, h - 38), 0.7, WHITE, 2)

    cv2.imshow("Finger Follow Mouse Control", frame)

    key = cv2.waitKey(1) & 0xFF
    if key == 27:
        break

cap.release()
cv2.destroyAllWindows()