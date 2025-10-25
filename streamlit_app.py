import streamlit as st
import tempfile
import os
import urllib.request
import shutil
import re
from typing import List, Tuple
import subprocess
# import cv2
import math
 
def parse_time_to_seconds(t: str) -> float:
    """Parse timestamps like HH:MM:SS or MM:SS or S to seconds."""
    parts = t.strip().split(":")
    parts = [p for p in parts if p != ""]
    parts = [float(p) for p in parts]
    if len(parts) == 1:
        return parts[0]
    if len(parts) == 2:
        return parts[0] * 60 + parts[1]
    if len(parts) == 3:
        return parts[0] * 3600 + parts[1] * 60 + parts[2]
    raise ValueError(f"Can't parse time: {t}")


def parse_ranges(text: str) -> List[Tuple[float, float]]:
    """Parse multiline ranges. Accept formats like:
    00:00:10-00:00:30
    10-20
    1:00-2:30
    One range per line. Empty lines ignored.
    """
    ranges = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        # allow separators '-' or 'to'
        m = re.split(r"\s*-\s*|\s+to\s+", line)
        if len(m) != 2:
            raise ValueError(f"Invalid range line: {line}")
        start_s = parse_time_to_seconds(m[0])
        end_s = parse_time_to_seconds(m[1])
        if end_s <= start_s:
            raise ValueError(f"End must be greater than start in line: {line}")
        ranges.append((start_s, end_s))
    return ranges


def download_file_from_url(url: str, out_dir: str, filename: str = "source.mp4") -> str:
    out_path = os.path.join(out_dir, filename)
    # Basic direct-file download using urllib. This requires the URL to point directly to a downloadable file (not YouTube page).
    urllib.request.urlretrieve(url, out_path)
    return out_path


def download_youtube_with_exe(url: str, out_dir: str) -> str:
    """Download YouTube using an external `yt-dlp` executable (must be installed on the system PATH).

    This avoids adding yt-dlp as a Python package dependency. If the executable is not found,
    the function will raise FileNotFoundError.
    """
    outtmpl = os.path.join(out_dir, 'source.%(ext)s')
    cmd = [
        'yt-dlp',
        '-f', 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        '-o', outtmpl,
        '--merge-output-format', 'mp4',
        url,
    ]
    # Run yt-dlp; let errors bubble up to be reported to the user
    subprocess.run(cmd, check=True)

    # find the downloaded file in out_dir
    for f in os.listdir(out_dir):
        if f.startswith('source.'):
            return os.path.join(out_dir, f)
    raise FileNotFoundError('yt-dlp did not produce a file in the output directory')


def split_video_cv(source_path: str, ranges: List[Tuple[float, float]], out_dir: str) -> List[str]:
    """Split a video using OpenCV by frame copying.

    This keeps CPU-only Python dependencies minimal (only OpenCV is required).
    Note: audio is NOT preserved with this method because OpenCV handles frames only.
    If you need audio preserved, use ffmpeg-based splitting instead.
    """
    clips = []
    return clips
    cap = cv2.VideoCapture(source_path)
    if not cap.isOpened():
        cap.release()
        raise RuntimeError('Could not open video file for reading.')

    fps = cap.get(cv2.CAP_PROP_FPS)
    if fps <= 0 or math.isnan(fps):
        fps = 30.0
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    for idx, (start, end) in enumerate(ranges, start=1):
        start_frame = max(0, int(start * fps))
        end_frame = min(frame_count, int(end * fps))
        if start_frame >= frame_count:
            raise ValueError(f'Start {start} >= video duration ({frame_count/fps:.2f}s)')
        out_file = os.path.join(out_dir, f'clip_{idx:02d}.mp4')
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        writer = cv2.VideoWriter(out_file, fourcc, fps, (width, height))

        cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
        curr = start_frame
        while curr < end_frame:
            ret, frame = cap.read()
            if not ret:
                break
            writer.write(frame)
            curr += 1
        writer.release()
        clips.append(out_file)

    cap.release()
    return clips


def main():
    st.set_page_config(page_title="YouTube Splitter", layout="centered")
    st.title("YouTube Video Splitter")

    st.markdown("Provide a direct video file (upload or a direct file URL). YouTube page URLs are NOT supported here unless you download the video yourself with a downloader (e.g. `yt-dlp`) and then upload the file. Example range formats: `00:00:10-00:00:30`, `1:00-2:30`, or `10-20`.")

    upload = st.file_uploader("Upload a video file (mp4/mov/mkv)", type=["mp4", "mov", "mkv"], accept_multiple_files=False)
    url = st.text_input("Or provide a direct video file URL (must point to a downloadable file)")
    ranges_text = st.text_area("Time ranges (one per line)", height=200, placeholder="00:00:10-00:00:30\n1:00-2:30")

    col1, col2 = st.columns([1, 1])
    with col1:
        split_btn = st.button("Split")
    with col2:
        clear_btn = st.button("Clear temp files")

    if 'clips' not in st.session_state:
        st.session_state.clips = []
    if 'tempdir' not in st.session_state:
        st.session_state.tempdir = None

    if clear_btn:
        td = st.session_state.get('tempdir')
        if td and os.path.exists(td):
            shutil.rmtree(td)
        st.session_state.clips = []
        st.session_state.tempdir = None
        st.success("Temporary files cleared.")

    if split_btn:
        # determine source: upload preferred
        if not upload and not url:
            st.error("Please upload a video file or provide a direct video URL.")
            return

        try:
            ranges = parse_ranges(ranges_text)
        except Exception as e:
            st.error(f"Could not parse ranges: {e}")
            return

        tmp = tempfile.mkdtemp(prefix="yt_split_")
        st.session_state.tempdir = tmp
        status = st.empty()
        try:
            # save uploaded file if present
            if upload:
                status.info("Saving uploaded file...")
                source_path = os.path.join(tmp, upload.name)
                with open(source_path, 'wb') as f:
                    f.write(upload.getbuffer())
            else:
                # detect YouTube-like URLs; if so try to call yt-dlp executable
                if any(d in url.lower() for d in ['youtube.com', 'youtu.be']):
                    status.info("Detected YouTube URL — attempting to download with local yt-dlp executable...")
                    try:
                        source_path = download_youtube_with_exe(url, tmp)
                    except FileNotFoundError:
                        raise RuntimeError('yt-dlp executable not found on PATH. Please install yt-dlp or upload the file manually.')
                else:
                    status.info("Downloading file from URL... (must be a direct file link)")
                    source_path = download_file_from_url(url, tmp, filename='source.mp4')

            status.info("File ready. Splitting clips (OpenCV - frames only, audio will NOT be preserved)...")
            clips = split_video_cv(source_path, ranges, tmp)
            st.session_state.clips = clips
            status.success(f"Created {len(clips)} clip(s). Scroll below to download.")
        except Exception as e:
            status.error(f"Error: {e}")
            # cleanup on failure
            if os.path.exists(tmp):
                try:
                    shutil.rmtree(tmp)
                except Exception:
                    pass
            st.session_state.tempdir = None

    # Show available clips with download buttons
    if st.session_state.clips:
        st.header("Clips")
        for i, clip_path in enumerate(st.session_state.clips, start=1):
            fname = os.path.basename(clip_path)
            cols = st.columns([4, 1])
            cols[0].text(f"{i}. {fname} ({os.path.getsize(clip_path)//1024} KB)")
            with open(clip_path, 'rb') as f:
                data = f.read()
            cols[1].download_button(label="Download", data=data, file_name=fname, mime='video/mp4')

    st.markdown("---")
    st.markdown("Notes: This app uses pytube to download YouTube and moviepy/FFmpeg to split. On Windows you must have FFmpeg installed and available on PATH.")


if __name__ == '__main__':
    main()
