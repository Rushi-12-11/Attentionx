"""
caption_adder.py — adds headline + karaoke word captions to a clip
"""
from __future__ import annotations
import textwrap
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from moviepy.editor import VideoFileClip, VideoClip


def _load_font(size: int) -> ImageFont.FreeTypeFont:
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "C:/Windows/Fonts/arialbd.ttf",
        "C:/Windows/Fonts/arial.ttf",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            pass
    print(f"[CaptionAdder] WARNING: No TTF font found — using PIL default (quality will be lower)")
    return ImageFont.load_default()


def add_captions(
    input_path: str,
    output_path: str,
    word_segments: list[dict],
    clip_start_sec: float,
    headline: str,
) -> None:
    print(f"[CaptionAdder] Adding captions to: {input_path}")

    clip_src = VideoFileClip(input_path)
    try:
        clip_dur     = clip_src.duration
        W, H         = clip_src.w, clip_src.h
        clip_end_sec = clip_start_sec + clip_dur

        # Remap global word timestamps to local clip time
        local_words = [
            {
                "start": max(0.0, w["start"] - clip_start_sec),
                "end":   min(clip_dur, w["end"] - clip_start_sec),
                "text":  w["text"],
            }
            for w in word_segments
            if w["start"] < clip_end_sec and w["end"] > clip_start_sec
        ]

        print(f"[CaptionAdder] {len(local_words)} words in this clip window.")

        font_caption  = _load_font(max(24, H // 22))
        font_headline = _load_font(max(28, H // 18))

        # Capture clip_src in closure while it is still open
        def render_frame(t: float):
            frame = clip_src.get_frame(t)
            img   = Image.fromarray(frame)
            draw  = ImageDraw.Draw(img, "RGBA")
            _draw_headline(draw, headline, W, H, font_headline)
            _draw_karaoke(draw, local_words, t, W, H, font_caption)
            return np.array(img.convert("RGB"))

        captioned = VideoClip(render_frame, duration=clip_dur).set_fps(clip_src.fps)
        if clip_src.audio:
            captioned = captioned.set_audio(clip_src.audio)

        captioned.write_videofile(
            output_path,
            codec="libx264",
            audio_codec="aac",
            logger=None,
            preset="ultrafast",
        )
        print(f"[CaptionAdder] Done: {output_path}")

    finally:
        clip_src.close()


def _draw_headline(draw, text, W, H, font):
    if not text:
        return
    lines  = textwrap.wrap(text.upper(), width=22)
    line_h = max(H // 16, 30)
    y      = int(H * 0.04)

    # Semi-transparent background bar
    draw.rectangle(
        [0, y - 6, W, y + len(lines) * line_h + 10],
        fill=(0, 0, 0, 160),
    )
    for line in lines:
        _draw_outlined_text(draw, line, W // 2, y, font, fill=(255, 215, 0), anchor="mm")
        y += line_h


def _draw_karaoke(draw, words, t, W, H, font):
    if not words:
        return

    # Show words that are current or upcoming in next 3 seconds
    window = [w for w in words if w["end"] >= t - 0.5 and w["start"] <= t + 3.0]
    if not window:
        return

    display = window[:8]
    parts   = [
        (
            w["text"] + " ",
            (255, 230, 0) if w["start"] <= t <= w["end"] else (255, 255, 255),
        )
        for w in display
    ]

    bar_y = int(H * 0.80)
    draw.rectangle([0, bar_y - 8, W, H], fill=(0, 0, 0, 180))

    # Measure total width safely
    try:
        total_w = draw.textlength("".join(p[0] for p in parts), font=font)
    except AttributeError:
        # PIL < 9.2 fallback
        total_w = sum(len(p[0]) for p in parts) * (H // 28)

    x = max(0, (W - int(total_w)) // 2)
    y = bar_y + 6

    for text, colour in parts:
        _draw_outlined_text(draw, text, x, y, font, fill=colour, anchor="la")
        try:
            x += int(draw.textlength(text, font=font))
        except AttributeError:
            x += len(text) * (H // 28)


def _draw_outlined_text(draw, text, x, y, font, fill, anchor="la", outline_width=2):
    """Draw text with a solid black outline for readability on any background."""
    for dx in range(-outline_width, outline_width + 1):
        for dy in range(-outline_width, outline_width + 1):
            if dx or dy:
                draw.text((x + dx, y + dy), text, font=font, fill=(0, 0, 0), anchor=anchor)
    draw.text((x, y), text, font=font, fill=fill, anchor=anchor)