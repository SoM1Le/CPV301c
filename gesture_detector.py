"""Tính touch ratio và state machine nhận diện gesture (thumb chạm ngón khác)."""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

import config
from hand_tracker import HandData


class Gesture(str, Enum):
    NONE = "NONE"
    DOT = "DOT"
    DASH = "DASH"
    END = "END"
    DELETE = "DELETE"
    CLEAR = "CLEAR"


class GestureState(str, Enum):
    IDLE = "IDLE"
    TOUCH_CANDIDATE = "TOUCH_CANDIDATE"
    ACTIVE = "ACTIVE"
    WAIT_RELEASE = "WAIT_RELEASE"


FINGER_TO_GESTURE: dict[str, Gesture] = {
    "index": Gesture.DOT,
    "middle": Gesture.DASH,
    "ring": Gesture.END,
    "pinky": Gesture.DELETE,
}


@dataclass
class GestureResult:
    """Kết quả xử lý 1 frame."""
    state: GestureState = GestureState.IDLE
    event: Optional[Gesture] = None          # gesture VỪA được trigger ở frame này (chỉ 1 frame)
    active_finger: Optional[str] = None      # ngón đang là candidate / đang bị khóa
    current_gesture: Gesture = Gesture.NONE  # gesture hiển thị trên UI
    ratios: dict[str, float] = field(default_factory=dict)     # normalized distance
    proximity: dict[str, float] = field(default_factory=dict)  # 0 (xa) .. 1 (đang chạm)
    clear_progress: float = 0.0              # 0..1 tiến độ giữ pinky để CLEAR


def _distance(a: tuple[float, float], b: tuple[float, float]) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def compute_touch_ratios(points: list[tuple[float, float]]) -> dict[str, float]:
    """touch_ratio = dist(thumb_tip, finger_tip) / hand_size.

    hand_size = dist(wrist, middle_mcp): gần như không đổi khi các ngón cử động,
    nên tỉ số này không phụ thuộc khoảng cách từ tay tới camera.
    Trả về dict rỗng nếu hand_size quá nhỏ (dữ liệu hỏng).
    """
    hand_size = _distance(points[config.WRIST], points[config.MIDDLE_MCP])
    if hand_size < 1e-6:
        return {}
    thumb = points[config.THUMB_TIP]
    return {
        name: _distance(thumb, points[tip_id]) / hand_size
        for name, tip_id in config.FINGER_TIP_IDS.items()
    }


class GestureDetector:
    """State machine: IDLE -> TOUCH_CANDIDATE -> ACTIVE -> WAIT_RELEASE -> IDLE.

    - IDLE:            chờ 1 ngón có ratio < TOUCH_THRESHOLD.
    - TOUCH_CANDIDATE: đang đếm thời gian ổn định (GESTURE_HOLD_TIME).
    - ACTIVE:          frame duy nhất mà event được phát ra.
    - WAIT_RELEASE:    đã trigger; im lặng cho tới khi ngón đó ratio > RELEASE_THRESHOLD.
    """

    def __init__(self) -> None:
        self._state = GestureState.IDLE
        self._finger: Optional[str] = None
        self._touch_start = 0.0
        self._last_seen = 0.0
        self._clear_fired = False

    # ------------------------------------------------------------------ public
    def update(self, hand: Optional[HandData], now: float) -> GestureResult:
        ratios = compute_touch_ratios(hand.points_px) if hand is not None else {}
        if not ratios:
            return self._handle_no_hand(now)

        self._last_seen = now
        nearest, nearest_d = min(ratios.items(), key=lambda kv: kv[1])
        event: Optional[Gesture] = None

        # ACTIVE chỉ tồn tại đúng 1 frame rồi chuyển sang WAIT_RELEASE.
        if self._state is GestureState.ACTIVE:
            self._state = GestureState.WAIT_RELEASE

        if self._state is GestureState.IDLE:
            if nearest_d < config.TOUCH_THRESHOLD:
                self._start_candidate(nearest, now)

        elif self._state is GestureState.TOUCH_CANDIDATE:
            assert self._finger is not None
            if ratios[self._finger] > config.RELEASE_THRESHOLD:
                self._reset()  # chỉ là nhiễu thoáng qua
            elif self._should_switch(ratios, nearest, nearest_d):
                self._start_candidate(nearest, now)  # ngón khác gần hơn rõ rệt
            elif now - self._touch_start >= config.GESTURE_HOLD_TIME:
                event = FINGER_TO_GESTURE[self._finger]
                self._state = GestureState.ACTIVE

        elif self._state is GestureState.WAIT_RELEASE:
            assert self._finger is not None
            if ratios[self._finger] > config.RELEASE_THRESHOLD:
                self._reset()  # đã nhả -> được phép trigger lần sau
            elif self._should_switch(ratios, nearest, nearest_d):
                # Người dùng chuyển thẳng sang ngón khác mà chưa nhả hẳn
                # (các đầu ngón kề nhau nên ngón cũ vẫn < RELEASE).
                # Coi như nhả ngón cũ và bắt đầu candidate mới ngay.
                self._start_candidate(nearest, now)
            elif (self._finger == "pinky"
                  and not self._clear_fired
                  and now - self._touch_start >= config.CLEAR_HOLD_TIME):
                event = Gesture.CLEAR
                self._clear_fired = True

        return self._build_result(ratios, event, now)

    def reset(self) -> None:
        self._reset()

    # ------------------------------------------------------------------ internals
    def _should_switch(self, ratios: dict[str, float], nearest: str, nearest_d: float) -> bool:
        """Ngón gần nhất có phải là 1 ngón KHÁC, đang touching và gần hơn ngón hiện tại rõ rệt?"""
        assert self._finger is not None
        return (nearest != self._finger
                and nearest_d < config.TOUCH_THRESHOLD
                and ratios[self._finger] - nearest_d > config.FINGER_SWITCH_MARGIN)

    def _start_candidate(self, finger: str, now: float) -> None:
        self._state = GestureState.TOUCH_CANDIDATE
        self._finger = finger
        self._touch_start = now
        self._clear_fired = False

    def _reset(self) -> None:
        self._state = GestureState.IDLE
        self._finger = None
        self._clear_fired = False

    def _handle_no_hand(self, now: float) -> GestureResult:
        if self._state is GestureState.TOUCH_CANDIDATE:
            self._reset()  # chưa trigger -> bỏ ngay
        elif self._state is not GestureState.IDLE:
            # Đã trigger: chịu mất tay ngắn để tránh trigger trùng khi MediaPipe chớp tắt.
            if now - self._last_seen > config.HAND_LOST_GRACE:
                self._reset()
        return GestureResult(
            state=self._state,
            active_finger=self._finger if self._state is not GestureState.IDLE else None,
            current_gesture=self._current_gesture(),
        )

    def _current_gesture(self) -> Gesture:
        if self._state is GestureState.IDLE or self._finger is None:
            return Gesture.NONE
        if self._clear_fired:
            return Gesture.CLEAR
        return FINGER_TO_GESTURE[self._finger]

    @staticmethod
    def _proximity(ratio: float) -> float:
        span = config.PROXIMITY_FAR_RATIO - config.TOUCH_THRESHOLD
        return max(0.0, min(1.0, (config.PROXIMITY_FAR_RATIO - ratio) / span))

    def _clear_progress(self, now: float) -> float:
        if self._finger != "pinky" or self._state not in (
                GestureState.ACTIVE, GestureState.WAIT_RELEASE):
            return 0.0
        if self._clear_fired:
            return 1.0
        return min((now - self._touch_start) / config.CLEAR_HOLD_TIME, 1.0)

    def _build_result(self, ratios: dict[str, float],
                      event: Optional[Gesture], now: float) -> GestureResult:
        return GestureResult(
            state=self._state,
            event=event,
            active_finger=self._finger if self._state is not GestureState.IDLE else None,
            current_gesture=self._current_gesture(),
            ratios=ratios,
            proximity={name: self._proximity(r) for name, r in ratios.items()},
            clear_progress=self._clear_progress(now),
        )
