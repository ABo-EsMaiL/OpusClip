"""
B-roll blurred background generator.
"""

import cv2
import numpy as np

# B-roll rendering constants
_BLUR_KERNEL_SIZE = (71, 71)
_BLUR_INTENSITY = 0.28
_BORDER_WIDTH = 5
_BORDER_COLOR = (245, 245, 245)
_FG_HEIGHT_RATIO = 0.95


def make_broll_frame(frame_bgr: np.ndarray, tgt_w: int, tgt_h: int) -> np.ndarray:
    """
    Creates a blurred background with the original frame centered on top.
    Used for shots where no active speakers are detected (B-roll).
    """
    src_h, src_w = frame_bgr.shape[:2]
    # Blurred + darkened background
    bg = cv2.resize(frame_bgr, (tgt_w, tgt_h), interpolation=cv2.INTER_LINEAR)
    bg = cv2.GaussianBlur(bg, _BLUR_KERNEL_SIZE, 0)
    bg = (bg.astype(np.float32) * _BLUR_INTENSITY).clip(0, 255).astype(np.uint8)

    # Clean letterboxed panel
    fg_w = tgt_w
    fg_h = int(fg_w * src_h / src_w)
    if fg_h > int(tgt_h * _FG_HEIGHT_RATIO):
        fg_h = int(tgt_h * _FG_HEIGHT_RATIO)
        fg_w = int(fg_h * src_w / src_h)
        if fg_w % 2:
            fg_w -= 1

    fg = cv2.resize(frame_bgr, (fg_w, fg_h), interpolation=cv2.INTER_LANCZOS4)
    bd = _BORDER_WIDTH
    fg = cv2.copyMakeBorder(fg, bd, bd, bd, bd, cv2.BORDER_CONSTANT, value=_BORDER_COLOR)
    fg_h, fg_w = fg.shape[:2]

    result = bg.copy()
    y0 = max(0, (tgt_h - fg_h) // 2)
    y1 = min(tgt_h, y0 + fg_h)
    x0 = max(0, (tgt_w - fg_w) // 2)
    x1 = min(tgt_w, x0 + fg_w)

    result[y0:y1, x0:x1] = fg[: y1 - y0, : x1 - x0]
    return result
