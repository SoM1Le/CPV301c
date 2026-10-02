"""Cửa sổ chính: top bar, panel điều khiển, video, bảng Morse, panel kết quả."""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, QTimer, Slot
from PySide6.QtGui import QCloseEvent, QImage, QPixmap
from PySide6.QtWidgets import (
    QFrame, QGridLayout, QHBoxLayout, QLabel, QMainWindow,
    QScrollArea, QSizePolicy, QVBoxLayout, QWidget,
)

import config
from camera_worker import CameraWorker, FrameStatus
from gesture_detector import Gesture
from morse_decoder import MORSE_CODE, MorseDecoder
from .styles import ACCENT, APP_STYLESHEET, DANGER, MUTED, OK

# Màu hiển thị của từng gesture ở panel dưới
GESTURE_COLORS: dict[str, str] = {
    "DOT": config.FINGER_COLORS_HEX["index"],
    "DASH": config.FINGER_COLORS_HEX["middle"],
    "END": config.FINGER_COLORS_HEX["ring"],
    "DELETE": config.FINGER_COLORS_HEX["pinky"],
    "CLEAR": config.FINGER_COLORS_HEX["pinky"],
    "NONE": MUTED,
}


def _make_panel() -> QFrame:
    frame = QFrame()
    frame.setObjectName("panel")
    return frame


def _make_label(text: str = "", object_name: str = "") -> QLabel:
    label = QLabel(text)
    if object_name:
        label.setObjectName(object_name)
    return label


class VideoWidget(QLabel):
    """Hiển thị frame, tự co giãn nhưng giữ đúng aspect ratio."""

    def __init__(self) -> None:
        super().__init__("Starting camera...")
        self.setObjectName("video")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumSize(320, 240)
        # Ignored: cho phép cửa sổ thu nhỏ dù pixmap đang lớn
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
        self._pixmap: Optional[QPixmap] = None

    def set_frame(self, image: QImage) -> None:
        self._pixmap = QPixmap.fromImage(image)
        self._refresh()

    def show_message(self, text: str) -> None:
        self._pixmap = None
        self.clear()
        self.setText(text)

    def resizeEvent(self, event) -> None:  # noqa: N802 (tên do Qt quy định)
        super().resizeEvent(event)
        self._refresh()

    def _refresh(self) -> None:
        if self._pixmap is not None:
            self.setPixmap(self._pixmap.scaled(
                self.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            ))


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Morse Hand")
        self.setMinimumSize(980, 620)

        self._decoder = MorseDecoder()
        self._last_tracked: Optional[bool] = None
        self._last_gesture: Optional[str] = None

        self._invalid_timer = QTimer(self)
        self._invalid_timer.setSingleShot(True)
        self._invalid_timer.timeout.connect(self._clear_invalid)

        self._build_ui()
        self.setStyleSheet(APP_STYLESHEET)
        self._refresh_text()

        # Worker: camera + MediaPipe chạy nền; kết quả về GUI qua signal (queued).
        self._worker = CameraWorker(self)
        self._worker.frame_ready.connect(self._on_frame)
        self._worker.status_ready.connect(self._on_status)
        self._worker.gesture_triggered.connect(self._on_gesture)
        self._worker.camera_error.connect(self._on_camera_error)
        self._worker.start()

    # ------------------------------------------------------------------ UI build
    def _build_ui(self) -> None:
        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)

        outer = QVBoxLayout(root)
        outer.setContentsMargins(14, 14, 14, 14)
        outer.setSpacing(12)

        outer.addWidget(self._build_top_bar())

        middle = QHBoxLayout()
        middle.setSpacing(12)
        middle.addWidget(self._build_left_panel(), 0)
        self._video = VideoWidget()
        middle.addWidget(self._video, 1)
        middle.addWidget(self._build_right_panel(), 0)
        outer.addLayout(middle, 1)

        outer.addWidget(self._build_bottom_panel())

    def _build_top_bar(self) -> QFrame:
        bar = _make_panel()
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(18, 10, 18, 10)

        self._hand_label = _make_label("No hand detected")
        self._set_hand_style(False)
        self._fps_label = _make_label("FPS 0.0")
        self._fps_label.setStyleSheet(f"color: {MUTED}; font-weight: 600;")

        layout.addWidget(_make_label("MORSE HAND", "title"))
        layout.addStretch(1)
        layout.addWidget(self._hand_label)
        layout.addSpacing(24)
        layout.addWidget(self._fps_label)
        return bar

    def _build_left_panel(self) -> QFrame:
        panel = _make_panel()
        panel.setFixedWidth(250)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(16, 14, 16, 14)

        layout.addWidget(_make_label("CONTROLS", "sectionTitle"))

        rows = [
            ("Index", "DOT", ".", "index"),
            ("Middle", "DASH", "-", "middle"),
            ("Ring", "END", "OK", "ring"),
            ("Pinky", "DELETE", "DEL", "pinky"),
            ("Pinky Hold", "CLEAR", f"{config.CLEAR_HOLD_TIME:g}s", "pinky"),
        ]
        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        for r, (finger, action, symbol, key) in enumerate(rows):
            color = config.FINGER_COLORS_HEX[key]
            for c, text in enumerate((finger, action, symbol)):
                cell = QLabel(text)
                cell.setStyleSheet(f"color: {color}; font-weight: 600;")
                grid.addWidget(cell, r, c)
        layout.addLayout(grid)

        hint = _make_label("Thumb touches a finger.\nRing with empty Morse = SPACE.")
        hint.setStyleSheet(f"color: {MUTED}; font-size: 11px;")
        hint.setWordWrap(True)
        layout.addSpacing(8)
        layout.addWidget(hint)

        self._debug_label: Optional[QLabel] = None
        if config.DEBUG_MODE:
            layout.addSpacing(14)
            layout.addWidget(_make_label("DEBUG (normalized distance)", "sectionTitle"))
            self._debug_label = _make_label("(no hand)", "mono")
            layout.addWidget(self._debug_label)

        layout.addStretch(1)
        return panel

    def _build_right_panel(self) -> QFrame:
        panel = _make_panel()
        panel.setFixedWidth(230)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.addWidget(_make_label("MORSE CHART", "sectionTitle"))

        chart = QLabel(self._build_chart_html())
        chart.setTextFormat(Qt.TextFormat.RichText)
        chart.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(chart)
        layout.addWidget(scroll, 1)
        return panel

    @staticmethod
    def _build_chart_html() -> str:
        items = list(MORSE_CODE.items())
        rows = []
        for i in range(0, len(items), 2):  # 2 cột: (A,B) ... (Y,Z), (0,1) ... (8,9)
            cells = ""
            for char, code in items[i:i + 2]:
                cells += (
                    f"<td style='padding:2px 8px 2px 0;'>"
                    f"<b style='color:{ACCENT}'>{char}</b></td>"
                    f"<td style='padding:2px 20px 2px 0;'>{code}</td>"
                )
            rows.append(f"<tr>{cells}</tr>")
        return ("<table style=\"font-family:Consolas,'Courier New',monospace; font-size:14px;\">"
                + "".join(rows) + "</table>")

    def _build_bottom_panel(self) -> QFrame:
        panel = _make_panel()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(18, 12, 18, 12)

        header = QHBoxLayout()
        header.addWidget(_make_label("CURRENT MORSE", "sectionTitle"))
        header.addStretch(1)
        self._invalid_label = _make_label("")
        self._invalid_label.setStyleSheet(f"color: {DANGER}; font-weight: 700;")
        header.addWidget(self._invalid_label)
        header.addSpacing(20)
        self._gesture_label = _make_label("Current Gesture: NONE")
        header.addWidget(self._gesture_label)
        layout.addLayout(header)

        self._morse_label = _make_label("", "morse")
        self._morse_label.setMinimumHeight(48)
        layout.addWidget(self._morse_label)

        layout.addWidget(_make_label("MESSAGE", "sectionTitle"))
        self._message_label = _make_label("", "message")
        self._message_label.setWordWrap(True)
        self._message_label.setMinimumHeight(44)
        layout.addWidget(self._message_label)
        return panel

    # ------------------------------------------------------------------ helpers
    def _set_hand_style(self, tracked: bool) -> None:
        color = OK if tracked else DANGER
        self._hand_label.setStyleSheet(f"color: {color}; font-weight: 700;")

    def _refresh_text(self) -> None:
        self._morse_label.setText(self._decoder.current_morse or " ")
        self._message_label.setText(self._decoder.message or " ")

    def _show_invalid(self, text: str) -> None:
        self._invalid_label.setText(text)
        self._invalid_timer.start(int(config.INVALID_MORSE_DURATION * 1000))

    def _clear_invalid(self) -> None:
        self._invalid_label.setText("")

    # ------------------------------------------------------------------ slots
    @Slot(QImage)
    def _on_frame(self, image: QImage) -> None:
        self._video.set_frame(image)

    @Slot(object)
    def _on_status(self, status: FrameStatus) -> None:
        self._fps_label.setText(f"FPS {status.fps:4.1f}")
        self._hand_label.setText(status.hand_text)

        if status.hand_tracked != self._last_tracked:
            self._last_tracked = status.hand_tracked
            self._set_hand_style(status.hand_tracked)

        if status.gesture != self._last_gesture:
            self._last_gesture = status.gesture
            color = GESTURE_COLORS.get(status.gesture, MUTED)
            self._gesture_label.setText(f"Current Gesture: {status.gesture}")
            self._gesture_label.setStyleSheet(f"color: {color}; font-weight: 700;")

        if self._debug_label is not None:
            if status.ratios:
                lines = [f"{name.capitalize():<7}{status.ratios[name]:.2f}"
                         for name in config.FINGER_TIP_IDS if name in status.ratios]
            else:
                lines = ["(no hand)"]
            lines += [
                "",
                f"touch   < {config.TOUCH_THRESHOLD:.2f}",
                f"release > {config.RELEASE_THRESHOLD:.2f}",
                f"state: {status.state}",
            ]
            self._debug_label.setText("\n".join(lines))

    @Slot(str)
    def _on_gesture(self, name: str) -> None:
        gesture = Gesture(name)
        if gesture is Gesture.DOT:
            self._decoder.add_dot()
        elif gesture is Gesture.DASH:
            self._decoder.add_dash()
        elif gesture is Gesture.END:
            self._decoder.finish_letter()
            if self._decoder.last_error:
                self._show_invalid(self._decoder.last_error)
        elif gesture is Gesture.DELETE:
            self._decoder.delete()
        elif gesture is Gesture.CLEAR:
            self._decoder.clear()
        self._refresh_text()

    @Slot(str)
    def _on_camera_error(self, message: str) -> None:
        self._video.show_message(message)
        self._hand_label.setText("Camera error")
        self._set_hand_style(False)

    # ------------------------------------------------------------------ lifecycle
    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        # Dừng worker sạch sẽ: thoát vòng lặp -> finally: cap.release(), tracker.close()
        self._worker.stop()
        event.accept()
