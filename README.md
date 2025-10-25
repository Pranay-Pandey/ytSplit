# Video Splitter (Streamlit + OpenCV)

This Streamlit app splits a provided video into clips based on user-provided time ranges and offers download buttons for each clip.

Files:

- `streamlit_app.py` — the Streamlit application
- `requirements.txt` — Python dependencies

Quick start (Windows):

1. Create a virtual environment and activate it (PowerShell):

   ```powershell
   python -m venv .venv; .\.venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   ```

2. Run the app:

   ```powershell
   streamlit run streamlit_app.py
   ```

Usage notes:

- The app accepts an uploaded video file (mp4/mov/mkv), a direct URL pointing to a downloadable video file, or a YouTube URL. If you paste a YouTube URL, the app will use `pytubefix` (the Python package) to download the source video locally. If the downloader fails for a particular video it will present the error and you can upload the file manually.
- Enter time ranges, one per line. Examples:
  - `00:00:10-00:00:30`
  - `1:00-2:30`
  - `10-20`
- Click `Split`. The app will save the source file to a temporary directory, create clips using OpenCV, and show download buttons for each clip.

Limitations & notes:

- This version uses `pytubefix` for YouTube downloads and OpenCV to trim video frames. Note: OpenCV trimming does NOT preserve audio. If you need audio-preserving splits, install `ffmpeg` and ask to switch trimming to ffmpeg (subprocess) behavior.
- This version uses `pytubefix` for YouTube downloads and prefers `ffmpeg` (system binary) to create audio-preserving clips. If `ffmpeg` is not found on PATH the app will fall back to OpenCV frame-based trimming (which does NOT preserve audio). To keep audio, install `ffmpeg`.

Installing FFmpeg on Windows:

1. Download a static build (e.g., from https://www.gyan.dev/ffmpeg/builds/ or https://www.ffmpeg.org/download.html).
2. Unzip and add the `bin` folder (containing `ffmpeg.exe`) to your PATH environment variable.
3. Restart your terminal/PowerShell and re-run the app.

Fixing the Numpy / MINGW warning you saw:

- That warning comes from a NumPy build that was compiled with MINGW and can be unstable on Windows in some combinations. The easiest fix is to remove the packages that pulled that NumPy wheel and reinstall clean wheels. Run these steps in your activated virtualenv:

```powershell
pip uninstall -y opencv-python numpy
pip install --upgrade pip
pip install numpy --prefer-binary
pip install -r requirements.txt
```

If the opencv wheel still pulls a MINGW-built numpy, you can avoid installing `opencv-python` entirely (this repo no longer requires it) or use `opencv-python-headless` from a different wheel source. The steps above should result in a stable NumPy wheel.

If you'd like me to switch to a different approach (e.g., integrate `yt-dlp` to download YouTube automatically, or use `moviepy`), tell me which direction you prefer.
