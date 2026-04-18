from __future__ import annotations
import json, os, subprocess, sys, tempfile


# The worker script runs in a SEPARATE Python process to avoid moviepy
# monkey-patching numpy before audio processing happens.
_WORKER = """
import sys, os, wave, json, subprocess, tempfile

def main():
    video_path     = sys.argv[1]
    top_n          = int(sys.argv[2])
    min_gap_sec    = float(sys.argv[3])
    frame_duration = float(sys.argv[4])
    ffmpeg_path    = sys.argv[5]

    try:
        import numpy as np
    except ImportError:
        print(json.dumps([]))
        sys.stderr.write("[AudioWorker] numpy not available\\n")
        return

    tmp_fd, tmp_path = tempfile.mkstemp(suffix=".wav")
    os.close(tmp_fd)
    try:
        result = subprocess.run(
            [ffmpeg_path, "-y", "-i", video_path,
             "-ac", "1", "-ar", "22050", "-vn", tmp_path],
            capture_output=True,
        )
        if result.returncode != 0:
            sys.stderr.write(f"[AudioWorker] ffmpeg failed: {result.stderr.decode(errors='replace')}\\n")
            print(json.dumps([]))
            return

        with wave.open(tmp_path, "rb") as wf:
            raw_bytes = wf.readframes(wf.getnframes())
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

    if not raw_bytes:
        sys.stderr.write("[AudioWorker] Empty audio extracted\\n")
        print(json.dumps([]))
        return

    audio = np.frombuffer(raw_bytes, dtype=np.int16).astype(np.float32) / 32768.0
    hop   = int(22050 * frame_duration)
    n     = len(audio) // hop

    if n == 0:
        print(json.dumps([]))
        return

    rms   = [float(np.sqrt(np.mean(audio[i*hop:(i+1)*hop]**2))) for i in range(n)]
    times = [float(i * frame_duration) for i in range(n)]
    maxr  = max(rms) + 1e-8
    norm  = [v / maxr for v in rms]

    order = sorted(range(n), key=lambda i: norm[i], reverse=True)
    peaks, used = [], []

    for idx in order:
        t = times[idx]
        if all(abs(t - u) >= min_gap_sec for u in used):
            peaks.append({"time": t, "energy": norm[idx]})
            used.append(t)
        if len(peaks) >= top_n:
            break

    peaks.sort(key=lambda p: p["energy"], reverse=True)
    print(json.dumps(peaks[:top_n]))

main()
"""


def _get_ffmpeg() -> str:
    """Return ffmpeg path — prefer imageio_ffmpeg, fall back to system ffmpeg."""
    try:
        from imageio_ffmpeg import get_ffmpeg_exe
        path = get_ffmpeg_exe()
        print(f"[AudioAnalyzer] Using imageio ffmpeg: {path}")
        return path
    except Exception:
        print("[AudioAnalyzer] imageio_ffmpeg not found — using system ffmpeg")
        return "ffmpeg"


def find_energy_peaks(video_path, top_n=10, min_gap_sec=15.0, frame_duration=1.0):
    print(f"[AudioAnalyzer] Extracting audio peaks from: {video_path}")
    ffmpeg_path = _get_ffmpeg()

    fd, script_path = tempfile.mkstemp(suffix=".py")
    try:
        with os.fdopen(fd, "w") as f:
            f.write(_WORKER)

        result = subprocess.run(
            [
                sys.executable, script_path,
                video_path,
                str(top_n),
                str(min_gap_sec),
                str(frame_duration),
                ffmpeg_path,
            ],
            capture_output=True,
            text=True,
        )

        if result.stderr.strip():
            print(f"[AudioAnalyzer] Worker stderr:\n{result.stderr.strip()}")

        if result.returncode != 0:
            print(f"[AudioAnalyzer] Worker exited with code {result.returncode}")
            return []

        output = result.stdout.strip()
        if not output:
            print("[AudioAnalyzer] Worker produced no output.")
            return []

        peaks = json.loads(output)
        print(f"[AudioAnalyzer] Found {len(peaks)} peaks.")
        return peaks

    except json.JSONDecodeError as je:
        print(f"[AudioAnalyzer] JSON decode error: {je}. stdout was: {result.stdout[:200]}")
        return []
    except Exception as e:
        print(f"[AudioAnalyzer] Unexpected error: {e}")
        return []
    finally:
        if os.path.exists(script_path):
            os.remove(script_path)