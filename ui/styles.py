"""Màu sắc và stylesheet dark theme."""
from __future__ import annotations

BG = "#0f1117"
PANEL = "#171a23"
PANEL_BORDER = "#252a37"
TEXT = "#e5e7eb"
MUTED = "#8b93a7"
ACCENT = "#22d3ee"
OK = "#22c55e"
DANGER = "#f43f5e"

APP_STYLESHEET = f"""
QWidget#root {{ background: {BG}; }}
QLabel {{ color: {TEXT}; }}
QFrame#panel {{
    background: {PANEL};
    border: 1px solid {PANEL_BORDER};
    border-radius: 12px;
}}
QLabel#title {{ font-size: 20px; font-weight: 800; color: {ACCENT}; }}
QLabel#sectionTitle {{ font-size: 11px; font-weight: 700; color: {MUTED}; }}
QLabel#morse {{
    font-family: Consolas, 'Courier New', monospace;
    font-size: 34px; font-weight: 700; color: {ACCENT};
}}
QLabel#message {{ font-size: 28px; font-weight: 600; }}
QLabel#mono {{ font-family: Consolas, 'Courier New', monospace; font-size: 12px; }}
QLabel#video {{ background: #000000; color: {MUTED}; border-radius: 12px; }}
QScrollArea {{ border: none; background: transparent; }}
QScrollArea > QWidget > QWidget {{ background: transparent; }}
"""
