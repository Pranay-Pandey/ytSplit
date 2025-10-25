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

- The app accepts an uploaded video file (mp4/mov/mkv), a direct URL pointing to a downloadable video file, or a YouTube URL. If you paste a YouTube URL, the app will use `yt-dlp` to download the source video locally.
- Enter time ranges, one per line. Examples:
  - `00:00:10-00:00:30`
  - `1:00-2:30`
  - `10-20`
- Click `Split`. The app will save the source file to a temporary directory, create clips using OpenCV, and show download buttons for each clip.

Limitations & notes:

- This version integrates `yt-dlp` for YouTube downloads and uses the `ffmpeg` system binary to cut clips. `ffmpeg` must be installed and on PATH.

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
