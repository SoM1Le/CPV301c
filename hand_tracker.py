"""Bọc MediaPipe Hands: nhận frame BGR, trả về landmark (pixel) của tay được chọn."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import cv2
import mediapipe as mp
import numpy as np

import config

_mp_hands = mp.solutions.hands
HAND_CONNECTIONS = _mp_hands.HAND_CONNECTIONS  # tập các cặp (i, j) để vẽ skeleton


@dataclass
class HandData:
    """Dữ liệu 1 bàn tay đã được chọn."""
    points_px: list[tuple[float, float]]  # 21 landmark, toạ độ pixel (x, y)
    handedness: str                       # "Left" / "Right" (theo góc nhìn người dùng)
    score: float                          # độ tin cậy của handedness


class HandTracker:
    def __init__(self) -> None:
        self._hands = _mp_hands.Hands(
            static_image_mode=False,
            max_num_hands=config.MAX_NUM_HANDS,
            model_complexity=config.MODEL_COMPLEXITY,
            min_detection_confidence=config.MIN_DETECTION_CONFIDENCE,
            min_tracking_confidence=config.MIN_TRACKING_CONFIDENCE,
        )
        # Nhãn của tay bị bỏ qua ở frame gần nhất (để UI báo "Left hand ignored")
        self.ignored_hand_label: Optional[str] = None

    @staticmethod
    def _fix_label(label: str) -> str:
        """MediaPipe giả định ảnh đầu vào đã được lật gương (selfie).
        Nếu ta KHÔNG lật ảnh thì phải đảo nhãn."""
        if config.MIRROR_VIEW:
            return label
        return "Left" if label == "Right" else "Right"

    def process(self, frame_bgr: np.ndarray) -> Optional[HandData]:
        """Trả về HandData của tay mục tiêu, hoặc None nếu không có."""
        height, width = frame_bgr.shape[:2]
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        rgb.flags.writeable = False  # gợi ý cho MediaPipe: không copy ảnh
        results = self._hands.process(rgb)

        self.ignored_hand_label = None
        if not results.multi_hand_landmarks or not results.multi_handedness:
            return None

        selected: Optional[HandData] = None
        for landmarks, handedness in zip(results.multi_hand_landmarks,
                                         results.multi_handedness):
            classification = handedness.classification[0]
            label = self._fix_label(classification.label)

            if config.ONLY_TARGET_HANDEDNESS and label != config.TARGET_HANDEDNESS:
                self.ignored_hand_label = label
                continue

            candidate = HandData(
                # x, y của MediaPipe là toạ độ chuẩn hoá [0,1] -> đổi sang pixel
                # để khoảng cách không bị méo theo tỉ lệ khung hình.
                points_px=[(p.x * width, p.y * height) for p in landmarks.landmark],
                handedness=label,
                score=float(classification.score),
            )
            if selected is None or candidate.score > selected.score:
                selected = candidate
        return selected

    def close(self) -> None:
        self._hands.close()
