"""Vẽ overlay OpenCV lên frame: skeleton, fingertip, đường thumb–finger, hiệu ứng."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import cv2
import numpy as np

import config
from gesture_detector import Gesture, GestureResult, GestureState
from hand_tracker import HAND_CONNECTIONS, HandData

SKELETON_COLOR = (200, 200, 200)
LANDMARK_COLOR = (120, 120, 120)


@dataclass
class FlashInfo:
    """Thông tin lần trigger gần nhất để vẽ highlight ngắn."""
    gesture: Gesture
    finger: str
    started_at: float


def _pt(p: tuple[float, float]) -> tuple[int, int]:
    return int(p[0]), int(p[1])


def _put_text(frame: np.ndarray, text: str, org: tuple[int, int],
              color: tuple[int, int, int], scale: float = 0.7, thickness: int = 2) -> None:
    # Vẽ viền đen trước để chữ đọc được trên mọi nền.
    cv2.putText(frame, text, org, cv2.FONT_HERSHEY_SIMPLEX, scale, (0, 0, 0),
                thickness + 3, cv2.LINE_AA)
    cv2.putText(frame, text, org, cv2.FONT_HERSHEY_SIMPLEX, scale, color,
                thickness, cv2.LINE_AA)


def draw_overlay(frame: np.ndarray, hand: Optional[HandData], result: GestureResult,
                 flash: Optional[FlashInfo], now: float) -> None:
    """Vẽ trực tiếp lên frame (in-place)."""
    if hand is None:
        return

    pts = hand.points_px
    colors = config.FINGER_COLORS_BGR

    # 1) Skeleton + 21 landmark
    for a, b in HAND_CONNECTIONS:
        cv2.line(frame, _pt(pts[a]), _pt(pts[b]), SKELETON_COLOR, 2, cv2.LINE_AA)
    for p in pts:
        cv2.circle(frame, _pt(p), 3, LANDMARK_COLOR, -1, cv2.LINE_AA)

    thumb = _pt(pts[config.THUMB_TIP])

    # 2) Đường nối thumb -> fingertip: càng gần càng dày (far -> near -> touching)
    for name, tip_id in config.FINGER_TIP_IDS.items():
        proximity = result.proximity.get(name, 0.0)
        if proximity <= 0.2:
            continue
        thickness = 1 + int(round(3 * proximity))
        cv2.line(frame, thumb, _pt(pts[tip_id]), colors[name], thickness, cv2.LINE_AA)

    # 3) Fingertip tô màu riêng
    cv2.circle(frame, thumb, 9, colors["thumb"], -1, cv2.LINE_AA)
    cv2.circle(frame, thumb, 9, (0, 0, 0), 1, cv2.LINE_AA)
    for name, tip_id in config.FINGER_TIP_IDS.items():
        tip = _pt(pts[tip_id])
        cv2.circle(frame, tip, 9, colors[name], -1, cv2.LINE_AA)
        cv2.circle(frame, tip, 9, (0, 0, 0), 1, cv2.LINE_AA)

    # 4) Vòng highlight quanh ngón đang active (candidate / đã trigger / chờ nhả)
    finger = result.active_finger
    if finger is not None and result.state is not GestureState.IDLE:
        tip = _pt(pts[config.FINGER_TIP_IDS[finger]])
        cv2.circle(frame, tip, 16, colors[finger], 2, cv2.LINE_AA)
        cv2.circle(frame, thumb, 16, colors[finger], 2, cv2.LINE_AA)

    # 5) Cung tròn tiến độ CLEAR quanh pinky
    if result.clear_progress > 0.0 and finger == "pinky":
        tip = _pt(pts[config.FINGER_TIP_IDS["pinky"]])
        end_angle = -90 + int(360 * result.clear_progress)
        cv2.ellipse(frame, tip, (26, 26), 0, -90, end_angle, colors["pinky"], 3, cv2.LINE_AA)

    # 6) Flash + nhãn ngay sau khi trigger thành công
    if flash is not None:
        age = now - flash.started_at
        if 0.0 <= age < config.FEEDBACK_DURATION:
            t = age / config.FEEDBACK_DURATION
            tip = _pt(pts[config.FINGER_TIP_IDS[flash.finger]])
            cv2.circle(frame, tip, int(16 + 22 * t), colors[flash.finger], 3, cv2.LINE_AA)
            _put_text(frame, flash.gesture.value, (tip[0] + 14, tip[1] - 14),
                      colors[flash.finger])
