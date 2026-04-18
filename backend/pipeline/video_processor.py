"""
video_processor.py — smart 9:16 crop with OpenCV face detection
"""
from __future__ import annotations
import cv2
import numpy as np
from moviepy.editor import VideoFileClip, VideoClip

TARGET_RATIO = 9 / 16
SAMPLE_EVERY = 5        # sample every N frames for face detection
SMOOTH_ALPHA = 0.15     # exponential smoothing for crop center

# OpenCV built-in face detector — no mediapipe needed
_face_cascade = cv2.CascadeClassifier(
    cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
)


def process_clip(video_path: str, output_path: str, start_sec: float, end_sec: float) -> None:
    print(f"[VideoProcessor] Cutting {start_sec:.1f}s -> {end_sec:.1f}s  →  {output_path}")

    src = VideoFileClip(video_path)
    try:
        duration  = src.duration
        start_sec = max(0.0, min(start_sec, duration - 1))
        end_sec   = min(end_sec, duration)

        if end_sec <= start_sec:
            end_sec = min(start_sec + 30.0, duration)

        clip   = src.subclip(start_sec, end_sec)
        W, H   = clip.w, clip.h
        crop_w = int(H * TARGET_RATIO)

        # If the video is already narrow enough, just write it as-is
        if crop_w >= W:
            print(f"[VideoProcessor] Video already ≤9:16 ratio — no crop needed.")
            clip.write_videofile(
                output_path, codec="libx264", audio_codec="aac",
                logger=None, preset="ultrafast"
            )
            return

        crop_centers = _compute_crop_centers(clip, W, H, crop_w)

        def make_frame(t: float):
            frame_idx = min(int(t * clip.fps), len(crop_centers) - 1)
            cx = crop_centers[frame_idx]
            x1 = max(0, cx - crop_w // 2)
            x2 = x1 + crop_w
            if x2 > W:
                x2 = W
                x1 = W - crop_w
            return clip.get_frame(t)[:, x1:x2]

        cropped = VideoClip(make_frame, duration=clip.duration).set_fps(clip.fps)
        if clip.audio:
            cropped = cropped.set_audio(clip.audio)

        cropped.write_videofile(
            output_path, codec="libx264", audio_codec="aac",
            logger=None, preset="ultrafast"
        )
        print(f"[VideoProcessor] Saved: {output_path}")

    finally:
        src.close()


def _compute_crop_centers(clip, W: int, H: int, crop_w: int) -> list[int]:
    total_frames = int(clip.duration * clip.fps) + 1
    sampled: dict[int, int] = {}

    for fi in range(0, total_frames, SAMPLE_EVERY):
        t     = fi / clip.fps
        frame = clip.get_frame(t)
        sampled[fi] = _detect_face_center(frame, W)

    # Linear interpolation between sampled frames
    centers = [W // 2] * total_frames
    keys    = sorted(sampled.keys())

    for i, k in enumerate(keys):
        centers[k] = sampled[k]
        if i + 1 < len(keys):
            k2 = keys[i + 1]
            for f in range(k + 1, k2):
                a          = (f - k) / (k2 - k)
                centers[f] = int(sampled[k] * (1 - a) + sampled[k2] * a)

    # Exponential smoothing to avoid jitter
    smoothed = [centers[0]]
    for v in centers[1:]:
        smoothed.append(int(SMOOTH_ALPHA * v + (1 - SMOOTH_ALPHA) * smoothed[-1]))

    # Clamp so we never go out of frame
    half = crop_w // 2
    return [max(half, min(W - half, c)) for c in smoothed]


def _detect_face_center(frame_rgb: np.ndarray, W: int) -> int:
    """Return the horizontal center of the largest detected face, or W//2."""
    gray  = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2GRAY)
    faces = _face_cascade.detectMultiScale(
        gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30)
    )
    if len(faces) == 0:
        return W // 2
    x, y, w, h = max(faces, key=lambda f: f[2] * f[3])
    return int(x + w // 2)