"""Bảng Morse và bộ giải mã: tích luỹ dot/dash, ghép thành chữ."""
from __future__ import annotations

from typing import Optional

import config

# Thứ tự chèn dict = thứ tự hiển thị trong bảng chart (A-Z rồi 0-9).
MORSE_CODE: dict[str, str] = {
    "A": ".-",    "B": "-...",  "C": "-.-.",  "D": "-..",   "E": ".",
    "F": "..-.",  "G": "--.",   "H": "....",  "I": "..",    "J": ".---",
    "K": "-.-",   "L": ".-..",  "M": "--",    "N": "-.",    "O": "---",
    "P": ".--.",  "Q": "--.-",  "R": ".-.",   "S": "...",   "T": "-",
    "U": "..-",   "V": "...-",  "W": ".--",   "X": "-..-",  "Y": "-.--",
    "Z": "--..",
    "0": "-----", "1": ".----", "2": "..---", "3": "...--", "4": "....-",
    "5": ".....", "6": "-....", "7": "--...", "8": "---..", "9": "----.",
}

MORSE_TO_CHAR: dict[str, str] = {code: char for char, code in MORSE_CODE.items()}


class MorseDecoder:
    """Trạng thái: current_morse (chuỗi dot/dash đang gõ) và message (văn bản đã giải mã)."""

    def __init__(self) -> None:
        self.current_morse: str = ""
        self.message: str = ""
        # Được đặt sau finish_letter() nếu chuỗi Morse không hợp lệ, ngược lại là None.
        self.last_error: Optional[str] = None

    def add_dot(self) -> bool:
        return self._add(".")

    def add_dash(self) -> bool:
        return self._add("-")

    def _add(self, symbol: str) -> bool:
        if len(self.current_morse) >= config.MAX_MORSE_LENGTH:
            return False  # không có ký tự nào dài hơn -> bỏ qua
        self.current_morse += symbol
        return True

    def finish_letter(self) -> bool:
        """Giải mã current_morse thành chữ, thêm vào message.

        - current_morse rỗng: thêm 1 dấu cách (ngăn từ), không thêm ở đầu hoặc trùng lặp.
        - Morse sai: không crash, đặt last_error, bỏ chuỗi đó.
        Trả về True nếu message thay đổi.
        """
        self.last_error = None

        if not self.current_morse:
            if self.message and not self.message.endswith(" "):
                self.message += " "
                return True
            return False

        char = MORSE_TO_CHAR.get(self.current_morse)
        if char is None:
            self.last_error = f"Invalid Morse: {self.current_morse}"
            self.current_morse = ""
            return False

        self.message += char
        self.current_morse = ""
        return True

    def delete(self) -> None:
        """Có Morse đang gõ -> xoá dấu cuối; nếu không -> xoá chữ cuối của message."""
        if self.current_morse:
            self.current_morse = self.current_morse[:-1]
        else:
            self.message = self.message[:-1]

    def clear(self) -> None:
        self.current_morse = ""
        self.message = ""
        self.last_error = None
