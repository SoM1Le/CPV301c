# Morse Hand

Ứng dụng desktop chạy hoàn toàn local: dùng webcam phát hiện **một bàn tay phải**, người dùng
dùng **ngón cái chạm các ngón còn lại** để nhập mã Morse. Không dùng cloud API, không train model.

## Kiến trúc

```
main.py ─► ui/main_window.py (GUI thread)
                ▲  Qt signals
                │
          camera_worker.py (QThread)
                ├─ hand_tracker.py     MediaPipe Hands -> 21 landmarks
                ├─ gesture_detector.py touch ratio + state machine
                ├─ overlay.py          vẽ skeleton / fingertip / hiệu ứng
                └─ config.py           mọi ngưỡng và thời gian
morse_decoder.py: bảng Morse + MorseDecoder (chạy trong GUI thread)
```

## Computer Vision pipeline

1. Đọc frame BGR từ `cv2.VideoCapture`, lật gương.
2. MediaPipe Hands trả về 21 landmark + handedness.
3. Chọn tay phải, đổi toạ độ chuẩn hoá sang pixel.
4. Tính khoảng cách chuẩn hoá thumb–từng ngón.
5. State machine + hysteresis quyết định có trigger gesture hay không.
6. Vẽ overlay, chuyển thành `QImage`, gửi sang GUI cùng trạng thái.

## MediaPipe hand landmarks

MediaPipe Hands gồm hai model: *palm detector* tìm lòng bàn tay, sau đó *hand landmark model*
hồi quy 21 điểm 3D trên bàn tay. Các điểm dùng trong project:

| ID | Landmark |
|----|----------|
| 0 | WRIST |
| 4 | THUMB_TIP |
| 8 | INDEX_FINGER_TIP |
| 9 | MIDDLE_FINGER_MCP |
| 12 | MIDDLE_FINGER_TIP |
| 16 | RING_FINGER_TIP |
| 20 | PINKY_TIP |

Toạ độ x, y được chuẩn hoá theo [0, 1]. Project đổi sang pixel để khoảng cách không bị méo
theo tỉ lệ khung hình. MediaPipe giả định ảnh đã lật gương (selfie), nên project lật frame
trước khi xử lý để nhãn handedness "Right" tương ứng với tay phải thật của người dùng.

## Normalized fingertip distance

```
hand_size   = dist(wrist, middle_mcp)
touch_ratio = dist(thumb_tip, finger_tip) / hand_size
```

`hand_size` gần như cố định khi các ngón cử động, và co giãn theo khoảng cách tay–camera,
nên tỉ số này không phụ thuộc tay ở gần hay xa camera. Ngón có `touch_ratio` nhỏ nhất
là ngón duy nhất được xét.

## Gesture mapping

| Gesture | Hành động |
|---|---|
| Thumb + Index | DOT `.` |
| Thumb + Middle | DASH `-` |
| Thumb + Ring | END: giải mã chữ (nếu Morse rỗng: thêm dấu cách) |
| Thumb + Pinky | DELETE: xoá dấu Morse cuối, hoặc chữ cuối nếu Morse rỗng |
| Thumb + Pinky giữ 1.5s | CLEAR: xoá toàn bộ |

## State machine

```
IDLE ──(ratio < TOUCH)──► TOUCH_CANDIDATE ──(ổn định ≥ GESTURE_HOLD_TIME)──► ACTIVE
  ▲                              │ ratio > RELEASE (nhiễu)                     │ 1 frame, phát event
  │◄─────────────────────────────┘                                             ▼
  └────────────────(ratio ngón đã chọn > RELEASE)──────────────────── WAIT_RELEASE
```

- Hysteresis: chạm khi `ratio < TOUCH_THRESHOLD`, chỉ nhả khi `ratio > RELEASE_THRESHOLD`.
- Mỗi lần chạm chỉ phát đúng 1 event, phải nhả rồi mới trigger lại.
- Không dùng `time.sleep()`; thời gian đo bằng `time.monotonic()`.
- Nếu ngón khác gần hơn rõ rệt (`FINGER_SWITCH_MARGIN`) thì coi như chuyển ngón.

## Cài đặt và chạy

```
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements.txt
python main.py
```

Dùng Python 3.10 hoặc 3.11. Không cài thêm `opencv-python` cùng `opencv-contrib-python`.

## Calibration TOUCH_THRESHOLD

1. Giữ `DEBUG_MODE = True` trong `config.py`.
2. Chạm thumb vào từng ngón, ghi lại giá trị ở panel DEBUG (thường 0.10 – 0.28).
3. Xoè tay bình thường, ghi lại giá trị khi không chạm (thường > 0.6).
4. Đặt `TOUCH_THRESHOLD` cao hơn một chút so với giá trị chạm lớn nhất.
5. Đặt `RELEASE_THRESHOLD` cao hơn `TOUCH_THRESHOLD` khoảng 0.10 – 0.15,
   và thấp hơn giá trị lúc xoè tay.
6. Nếu bị trigger nhầm khi tay chuyển động: tăng `GESTURE_HOLD_TIME`.
   Nếu thấy chậm: giảm xuống (tối thiểu ~0.08).

## Limitations

- Khoảng cách tính theo 2D; khi xoay lòng bàn tay nghiêng về camera, `hand_size` co lại và tỉ số bị lệch.
- Các đầu ngón kề nhau nên khi gõ nhanh cần tách nhẹ các ngón.
- Nhãn handedness của MediaPipe đôi khi sai khi bàn tay bị che một phần.
- Ánh sáng yếu hoặc nền phức tạp làm giảm độ ổn định của landmark.
- Chỉ hỗ trợ A–Z và 0–9, không có dấu câu.

## Ideas for future improvement

- Dùng cả toạ độ z hoặc hand_size 3D để chống nghiêng tay.
- Lọc landmark (One-Euro filter) để giảm jitter.
- Wizard calibration tự đo ngưỡng cho từng người dùng.
- Thêm dấu câu, âm thanh phản hồi, xuất/copy message.
- Hỗ trợ tay trái, lưu cấu hình vào file JSON.
