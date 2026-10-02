"""Cấu hình trung tâm của Morse Hand. Mọi ngưỡng/thời gian chỉnh ở đây."""
from __future__ import annotations

# ----------------------------- Camera -----------------------------
CAMERA_INDEX: int = 0
FRAME_WIDTH: int = 640
FRAME_HEIGHT: int = 480
CAMERA_FPS: int = 30
CAMERA_READ_TIMEOUT: float = 2.0   # giây: đọc frame lỗi liên tục quá lâu -> báo lỗi
MIRROR_VIEW: bool = True           # lật ngang như gương (dễ dùng hơn)

# ----------------------------- MediaPipe -----------------------------
MAX_NUM_HANDS: int = 1             # đặt 2 nếu muốn tìm tay phải khi có cả hai tay trong khung
MODEL_COMPLEXITY: int = 1          # 0 = nhanh hơn, 1 = chính xác hơn
MIN_DETECTION_CONFIDENCE: float = 0.6
MIN_TRACKING_CONFIDENCE: float = 0.5
TARGET_HANDEDNESS: str = "Right"   # "Right" hoặc "Left"
ONLY_TARGET_HANDEDNESS: bool = True

# ----------------------------- Landmarks -----------------------------
WRIST: int = 0
MIDDLE_MCP: int = 9
THUMB_TIP: int = 4
FINGER_TIP_IDS: dict[str, int] = {
    "index": 8,
    "middle": 12,
    "ring": 16,
    "pinky": 20,
}

# ----------------------------- Màu -----------------------------
FINGER_COLORS_HEX: dict[str, str] = {
    "thumb": "#ffffff",
    "index": "#22d3ee",   # cyan
    "middle": "#a855f7",  # purple
    "ring": "#facc15",    # yellow
    "pinky": "#f43f5e",   # pink/red
}


def _hex_to_bgr(value: str) -> tuple[int, int, int]:
    """'#rrggbb' -> (b, g, r) cho OpenCV."""
    value = value.lstrip("#")
    r, g, b = (int(value[i:i + 2], 16) for i in (0, 2, 4))
    return (b, g, r)


FINGER_COLORS_BGR: dict[str, tuple[int, int, int]] = {
    name: _hex_to_bgr(color) for name, color in FINGER_COLORS_HEX.items()
}

# ----------------------------- Touch detection -----------------------------
# touch_ratio = dist(thumb_tip, finger_tip) / dist(wrist, middle_mcp)
TOUCH_THRESHOLD: float = 0.30      # ratio < giá trị này  => đang chạm
RELEASE_THRESHOLD: float = 0.45    # ratio > giá trị này  => đã nhả (phải > TOUCH_THRESHOLD)
FINGER_SWITCH_MARGIN: float = 0.08 # ngón mới phải gần hơn ngón đang khóa ít nhất chừng này mới đổi
PROXIMITY_FAR_RATIO: float = 0.90  # ratio >= giá trị này => "xa" (proximity = 0) cho hiệu ứng vẽ

# ----------------------------- Thời gian (giây) -----------------------------
GESTURE_HOLD_TIME: float = 0.12    # chạm ổn định bao lâu thì mới trigger
CLEAR_HOLD_TIME: float = 1.5       # giữ thumb + pinky bao lâu thì CLEAR
HAND_LOST_GRACE: float = 0.25      # mất tay ngắn hơn giá trị này thì giữ nguyên state
FEEDBACK_DURATION: float = 0.35    # thời gian highlight sau khi trigger
INVALID_MORSE_DURATION: float = 1.5

# ----------------------------- Morse -----------------------------
MAX_MORSE_LENGTH: int = 5          # ký tự dài nhất (số 0-9) có 5 dấu

# ----------------------------- Debug -----------------------------
DEBUG_MODE: bool = True

assert RELEASE_THRESHOLD > TOUCH_THRESHOLD, "RELEASE_THRESHOLD phải lớn hơn TOUCH_THRESHOLD"
