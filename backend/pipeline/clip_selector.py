from __future__ import annotations
import os, json, re
from pathlib import Path
from dotenv import load_dotenv

# Load .env from the same folder as this file — works in Jupyter and scripts
load_dotenv(Path(__file__).parent / ".env")

# FIX: correct model name for google-generativeai SDK
_MODEL_NAME = "gemini-1.5-flash"


def select_clips(transcript, peaks, video_path, max_clips=5, min_clip_sec=20.0, max_clip_sec=90.0):
    import google.generativeai as genai

    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        print("[ClipSelector] WARNING: No GEMINI_API_KEY found in environment.")
        print("[ClipSelector] Falling back to audio-peak based selection.")
        return _fallback_from_peaks(peaks, min_clip_sec, max_clip_sec, max_clips)

    genai.configure(api_key=api_key)

    if not transcript.strip():
        print("[ClipSelector] Empty transcript — falling back to peaks.")
        return _fallback_from_peaks(peaks, min_clip_sec, max_clip_sec, max_clips)

    peak_summary = (
        ", ".join(
            f"{p['time']:.1f}s (energy {p['energy']:.2f})"
            for p in sorted(peaks, key=lambda x: x["time"])[:15]
        )
        if peaks
        else "No peaks detected"
    )

    prompt = (
        f"You are a viral content strategist. Identify the {max_clips} most IMPACTFUL moments "
        f"as standalone {int(min_clip_sec)}-{int(max_clip_sec)} second clips.\n"
        f"AUDIO ENERGY PEAKS: {peak_summary}\n"
        f"TRANSCRIPT:\n{transcript[:12000]}\n\n"
        f"Rules:\n"
        f"- Each clip must be {int(min_clip_sec)}-{int(max_clip_sec)} seconds long\n"
        f"- Headline in ALL CAPS, max 8 words\n"
        f"- Return ONLY valid JSON, no markdown, no explanation\n"
        f'FORMAT: {{"clips": [{{"start": 45.0, "end": 90.0, "headline": "HOOK HERE", "reason": "why"}}]}}'
    )

    try:
        print(f"[ClipSelector] Calling Gemini model: {_MODEL_NAME}")
        model    = genai.GenerativeModel(_MODEL_NAME)
        response = model.generate_content(prompt)
        raw      = response.text.strip()

        # Strip markdown code fences if present
        raw = re.sub(r"```(?:json)?", "", raw).strip().rstrip("`").strip()
        print(f"[ClipSelector] Gemini raw response: {raw[:300]}")

        data   = json.loads(raw)
        clips  = data.get("clips", [])
        valid  = []

        for c in clips:
            s = float(c.get("start", 0))
            e = float(c.get("end", 0))
            dur = e - s
            if dur < min_clip_sec:
                print(f"[ClipSelector] Skipping clip {s}-{e}s: too short ({dur:.1f}s)")
                continue
            # Cap duration
            e = min(e, s + max_clip_sec)
            valid.append({
                "start":    s,
                "end":      e,
                "headline": c.get("headline", "WATCH THIS"),
                "reason":   c.get("reason", ""),
            })

        print(f"[ClipSelector] Valid clips from Gemini: {len(valid)}")

        if valid:
            return valid[:max_clips]

        print("[ClipSelector] Gemini returned no valid clips — falling back to peaks.")
        return _fallback_from_peaks(peaks, min_clip_sec, max_clip_sec, max_clips)

    except json.JSONDecodeError as je:
        print(f"[ClipSelector] JSON parse error: {je}. Raw: {raw[:200]}")
        return _fallback_from_peaks(peaks, min_clip_sec, max_clip_sec, max_clips)
    except Exception as exc:
        print(f"[ClipSelector] Gemini error: {exc}")
        return _fallback_from_peaks(peaks, min_clip_sec, max_clip_sec, max_clips)


def _fallback_from_peaks(peaks, min_clip_sec, max_clip_sec, max_clips):
    print(f"[ClipSelector] Fallback: {len(peaks)} peaks available, min={min_clip_sec}s, max={max_clip_sec}s")

    if not peaks:
        print("[ClipSelector] WARNING: No peaks — returning empty list. Emergency fallback will handle this in main.py.")
        return []

    clips  = []
    half   = min_clip_sec / 2
    used   = []  # list of (start, end) tuples

    for peak in sorted(peaks, key=lambda p: p["energy"], reverse=True):
        t     = peak["time"]
        start = max(0.0, t - half)
        end   = start + min_clip_sec

        # FIX: check for overlap correctly
        overlaps = any(
            not (end <= us or start >= ue)   # i.e. they DO overlap
            for us, ue in used
        )
        if overlaps:
            continue

        clips.append({
            "start":    round(start, 2),
            "end":      round(end, 2),
            "headline": "HIGH ENERGY MOMENT",
            "reason":   f"Peak energy at {t:.1f}s (score: {peak['energy']:.2f})",
        })
        used.append((start, end))

        if len(clips) >= max_clips:
            break

    print(f"[ClipSelector] Fallback produced {len(clips)} clips")
    return clips