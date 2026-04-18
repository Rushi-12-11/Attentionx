import os
import sys
import uuid
import shutil
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from dotenv import load_dotenv

# FIX: ensure backend dir is on path and load .env
BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

load_dotenv(BASE_DIR / ".env", override=True)

app = FastAPI(title="AttentionX – AI Content Repurposing Engine", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Directories ───────────────────────────────────────────────────────────────
UPLOAD_DIR = BASE_DIR / "uploads"
OUTPUT_DIR = BASE_DIR / "outputs"
STATIC_DIR = BASE_DIR.parent / "frontend"

for d in [UPLOAD_DIR, OUTPUT_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# ── In-memory job store ───────────────────────────────────────────────────────
jobs: dict = {}


def _update(job_id, step_msg, status="processing"):
    jobs[job_id]["step"] = step_msg
    jobs[job_id]["status"] = status
    print(f"[Pipeline] [{status}] {step_msg}")


def _run_pipeline(job_id: str, video_path: str):
    try:
        out_dir = OUTPUT_DIR / job_id
        out_dir.mkdir(parents=True, exist_ok=True)

        # ── Step 1: Audio peaks ──────────────────────────────────────────────
        # Import audio_analyzer BEFORE any moviepy to avoid numpy conflict
        _update(job_id, "Analyzing audio for emotional peaks…", "analyzing_audio")
        from pipeline.audio_analyzer import find_energy_peaks
        peaks = find_energy_peaks(video_path)
        print(f"[Pipeline] Audio peaks found: {len(peaks)}")

        # ── Step 2: Transcription ────────────────────────────────────────────
        _update(job_id, "Transcribing with Whisper…", "transcribing")
        from pipeline.transcriber import transcribe
        transcript, word_segments = transcribe(video_path)
        print(f"[Pipeline] Transcript length: {len(transcript)} chars, words: {len(word_segments)}")

        # ── Step 3: AI clip selection ─────────────────────────────────────────
        _update(job_id, "Asking Gemini to pick viral moments…", "selecting_clips")
        from pipeline.clip_selector import select_clips
        clips = select_clips(transcript, peaks, video_path)
        print(f"[Pipeline] DEBUG peaks={len(peaks)} clips={len(clips)} clips_data={clips}")

        # FIX: if clips is still empty, force a minimum fallback so user gets output
        if not clips:
            print("[Pipeline] WARNING: No clips selected — using emergency fallback (first 60s)")
            import subprocess, json as _json
            try:
                r = subprocess.run(
                    ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", video_path],
                    capture_output=True, text=True
                )
                duration = float(_json.loads(r.stdout)["format"]["duration"])
            except Exception:
                duration = 120.0

            step = min(60.0, duration / 3)
            clips = []
            t = 0.0
            i = 1
            while t + 20 <= duration and len(clips) < 5:
                clips.append({
                    "start": round(t, 2),
                    "end": round(min(t + step, duration), 2),
                    "headline": f"HIGHLIGHT MOMENT {i}",
                    "reason": "Auto-selected segment"
                })
                t += step
                i += 1
            print(f"[Pipeline] Emergency fallback produced {len(clips)} clips")

        # ── Step 4: Per-clip crop + captions ─────────────────────────────────
        from pipeline.video_processor import process_clip
        from pipeline.caption_adder import add_captions

        ready_clips = []
        for i, clip in enumerate(clips):
            _update(job_id, f"Processing clip {i+1}/{len(clips)}: cropping & captioning…", "processing_clips")

            raw_path   = out_dir / f"clip_{i+1}_raw.mp4"
            final_path = out_dir / f"clip_{i+1}_final.mp4"

            try:
                process_clip(video_path, str(raw_path), clip["start"], clip["end"])
                add_captions(
                    str(raw_path),
                    str(final_path),
                    word_segments,
                    clip["start"],
                    clip.get("headline", ""),
                )
            except Exception as clip_err:
                print(f"[Pipeline] Clip {i+1} failed: {clip_err} — skipping")
                continue
            finally:
                try:
                    raw_path.unlink()
                except Exception:
                    pass

            if final_path.exists():
                ready_clips.append({
                    "name":     final_path.name,
                    "headline": clip.get("headline", f"Clip {i+1}"),
                    "reason":   clip.get("reason", ""),
                    "start":    clip["start"],
                    "end":      clip["end"],
                    "duration": round(clip["end"] - clip["start"], 1),
                })

        jobs[job_id].update({
            "status": "done",
            "step":   "Done",
            "clips":  ready_clips,
        })
        print(f"[Pipeline] Completed. {len(ready_clips)} clips ready.")

    except Exception as exc:
        import traceback
        tb = traceback.format_exc()
        print(f"[Pipeline] FATAL ERROR: {exc}\n{tb}")
        jobs[job_id].update({
            "status": "failed",
            "step":   "Error",
            "error":  str(exc),
            "trace":  tb,
        })


# ── Routes ────────────────────────────────────────────────────────────────────

@app.post("/api/upload")
async def upload_video(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    if not file.filename.lower().endswith((".mp4", ".mov", ".avi", ".mkv", ".webm")):
        raise HTTPException(400, "Only video files are accepted.")

    job_id     = str(uuid.uuid4())
    video_path = UPLOAD_DIR / f"{job_id}_{file.filename}"

    with open(video_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    jobs[job_id] = {"status": "queued", "step": "Uploaded – queued for processing", "clips": [], "error": None}
    background_tasks.add_task(_run_pipeline, job_id, str(video_path))

    return {"job_id": job_id}


@app.get("/api/status/{job_id}")
async def get_status(job_id: str):
    if job_id not in jobs:
        raise HTTPException(404, "Job not found")
    return jobs[job_id]


@app.get("/api/download/{job_id}/{clip_name}")
async def download_clip(job_id: str, clip_name: str):
    clip_path = OUTPUT_DIR / job_id / clip_name
    if not clip_path.exists():
        raise HTTPException(404, "Clip not found")
    return FileResponse(str(clip_path), media_type="video/mp4", filename=clip_name)


@app.get("/api/preview/{job_id}/{clip_name}")
async def preview_clip(job_id: str, clip_name: str):
    clip_path = OUTPUT_DIR / job_id / clip_name
    if not clip_path.exists():
        raise HTTPException(404, "Clip not found")
    return FileResponse(str(clip_path), media_type="video/mp4")


@app.get("/health")
async def health():
    return {"status": "ok"}


# ── Serve frontend ────────────────────────────────────────────────────────────
if STATIC_DIR.exists():
    app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")