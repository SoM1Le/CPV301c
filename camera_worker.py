"""QThread chạy camera + MediaPipe + gesture, emit kết quả sang GUI."""
from __future__ import annotations

import sys
import time
from dataclasses import dataclass
from typing import Optional

import cv2
from PySide6.QtCore import QThread, Signal
from PySide6.QtGui import QImage

import config
from gesture_detector import GestureDetector
from hand_tracker import HandTracker
from overlay import FlashInfo, draw_overlay


@dataclass
class FrameStatus:
    """Trạng thái gửi sang GUI mỗi frame."""
    fps: float
    hand_tracked: bool
    hand_text: str
    state: str
    gesture: str                 # DOT / DASH / END / DELETE / CLEAR / NONE
    ratios: dict[str, float]     # normalized distance thumb -> từng ngón (cho debug)
    clear_progress: float


class CameraWorker(QThread):
    frame_ready = Signal(QImage)
    status_ready = Signal(object)        # FrameStatus
    gesture_triggered = Signal(str)      # Gesture.value, chỉ phát 1 lần mỗi lần trigger
    camera_error = Signal(str)

    def stop(self) -> None:
        """Yêu cầu dừng và đợi thread kết thúc (gọi từ closeEvent)."""
        self.requestInterruption()
        self.wait(5000)

    # ------------------------------------------------------------------
    def _open_camera(self) -> Optional[cv2.VideoCapture]:
        # DirectShow mở camera nhanh hơn trên Windows.
        backend = cv2.CAP_DSHOW if sys.platform.startswith("win") else cv2.CAP_ANY
        cap = cv2.VideoCapture(config.CAMERA_INDEX, backend)
        if not cap.isOpened():
            cap.release()
            self.camera_error.emit(
                f"Cannot open camera (index {config.CAMERA_INDEX}).\n"
                "Check that the webcam is connected, not used by another app, "
                "or change CAMERA_INDEX in config.py."
            )
            return None
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, config.FRAME_WIDTH)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, config.FRAME_HEIGHT)
        cap.set(cv2.CAP_PROP_FPS, config.CAMERA_FPS)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # giảm độ trễ (một số backend bỏ qua)
        return cap

    @staticmethod
    def _to_qimage(frame_bgr) -> QImage:
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        # .copy() bắt buộc: QImage chỉ mượn buffer numpy, sẽ bị ghi đè ở frame sau.
        return QImage(rgb.data, w, h, ch * w, QImage.Format.Format_RGB888).copy()

    # ------------------------------------------------------------------
    def run(self) -> None:
        cap = self._open_camera()
        if cap is None:
            return

        tracker: Optional[HandTracker] = None
        try:
            tracker = HandTracker()
            detector = GestureDetector()
            flash: Optional[FlashInfo] = None
            fps = 0.0
            prev_time = time.monotonic()
            last_ok = prev_time

            while not self.isInterruptionRequested():
                ok, frame = cap.read()
                now = time.monotonic()

                if not ok or frame is None:
                    if now - last_ok > config.CAMERA_READ_TIMEOUT:
                        self.camera_error.emit("Camera stopped delivering frames.")
                        break
                    continue
                last_ok = now

                if config.MIRROR_VIEW:
                    frame = cv2.flip(frame, 1)

                hand = tracker.process(frame)
                result = detector.update(hand, now)

                if result.event is not None:
                    self.gesture_triggered.emit(result.event.value)
                    if result.active_finger is not None:
                        flash = FlashInfo(result.event, result.active_finger, now)

                draw_overlay(frame, hand, result, flash, now)

                # FPS làm mượt (EMA)
                dt = now - prev_time
                prev_time = now
                if dt > 0:
                    instant = 1.0 / dt
                    fps = instant if fps == 0.0 else 0.9 * fps + 0.1 * instant

                if hand is not None:
                    hand_text = f"{hand.handedness} hand tracked"
                elif tracker.ignored_hand_label is not None:
                    hand_text = (f"{tracker.ignored_hand_label} hand ignored "
                                 f"- show {config.TARGET_HANDEDNESS.lower()} hand")
                else:
                    hand_text = "No hand detected"

                self.frame_ready.emit(self._to_qimage(frame))
                self.status_ready.emit(FrameStatus(
                    fps=fps,
                    hand_tracked=hand is not None,
                    hand_text=hand_text,
                    state=result.state.value,
                    gesture=result.current_gesture.value,
                    ratios=result.ratios,
                    clear_progress=result.clear_progress,
                ))
        except Exception as exc:  # noqa: BLE001 - báo lỗi lên UI thay vì chết im lặng
            self.camera_error.emit(f"Camera worker crashed: {exc!r}")
        finally:
            cap.release()
            if tracker is not None:
                tracker.close()
