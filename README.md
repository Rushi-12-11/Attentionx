# ⚡ AttentionX — AI-Powered Video Content Repurposing Engine

## 🌐 Live Demo → [attentionx-production.up.railway.app](https://attentionx-production.up.railway.app)

> Built for the AttentionX AI Hackathon by UnsaidTalks

AttentionX automatically transforms long-form videos into viral short clips — complete with smart 9:16 cropping, face tracking, and karaoke-style captions — powered by Gemini AI and Whisper.

---

## 🚀 Demo

Upload any video → Get viral short clips in minutes.

![AttentionX Demo](frontend/demo.png)

---

## ✨ Features

- 🎯 **AI Clip Selection** — Gemini 1.5 Flash identifies the most impactful moments
- 🗣 **Speech Transcription** — faster-whisper transcribes with word-level timestamps
- 📱 **Smart 9:16 Crop** — OpenCV face detection keeps the speaker centered
- 💬 **Karaoke Captions** — animated word-by-word captions synced to speech
- 🔊 **Audio Energy Peaks** — finds high-energy moments even without transcription
- ⚡ **Fast Processing** — ultrafast preset, isolated subprocess for audio analysis

---

## 🛠 Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | FastAPI + Uvicorn |
| AI Clip Selection | Google Gemini 1.5 Flash |
| Transcription | faster-whisper (OpenAI Whisper) |
| Video Processing | MoviePy + OpenCV |
| Captions | Pillow (PIL) |
| Audio Analysis | NumPy + FFmpeg |
| Frontend | Vanilla HTML/CSS/JS |

---

## 📦 Setup & Installation

### Prerequisites
- Python 3.10+
- FFmpeg installed and on PATH

### 1. Clone the repo
```bash
git clone https://github.com/YOUR_USERNAME/attentionx.git
cd attentionx
```

### 2. Create virtual environment
```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Mac/Linux
source venv/bin/activate
```

### 3. Install dependencies
```bash
pip install -r backend/requirements.txt
```

### 4. Set up environment variables
```bash
cp backend/.env.example backend/.env
# Edit backend/.env and add your GEMINI_API_KEY
```

Get a free Gemini API key at: https://aistudio.google.com

### 5. Run the server
```bash
cd backend
uvicorn main:app --host 0.0.0.0 --port 8000
```

### 6. Open the app
Visit `http://127.0.0.1:8000` in your browser.

---

## 📁 Project Structure

```
attentionx/
├── backend/
│   ├── main.py              # FastAPI app & pipeline orchestrator
│   ├── requirements.txt     # Python dependencies
│   ├── .env.example         # Environment variable template
│   └── pipeline/
│       ├── audio_analyzer.py   # FFmpeg audio energy peak detection
│       ├── transcriber.py      # Whisper speech-to-text
│       ├── clip_selector.py    # Gemini AI clip selection
│       ├── video_processor.py  # 9:16 crop with face tracking
│       └── caption_adder.py    # Karaoke caption rendering
└── frontend/
    └── index.html           # Single-page UI
```

---

## 🔑 Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `GEMINI_API_KEY` | Google Gemini API key | Required |
| `WHISPER_MODEL` | Whisper model size (`tiny`, `base`, `small`) | `base` |

---

## 🏆 Built at AttentionX AI Hackathon

Built with ⚡ by **UnsaidTalks** · Powered by Gemini 1.5 Flash · Whisper · MoviePy · OpenCV
