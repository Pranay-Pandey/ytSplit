import streamlit as st
import tempfile
import os
import urllib.request
import shutil
import re
from typing import List, Tuple
import subprocess
import cv2
import math
from ytDownloader import is_valid_youtube_url, get_video_info, download_video
 
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


# NOTE: yt-dlp executable removed per user request. All YouTube downloads use pytube via ytDownloader.download_video


def split_video_cv(source_path: str, ranges: List[Tuple[float, float]], out_dir: str) -> List[str]:
    """Split a video using OpenCV by frame copying.

    This keeps CPU-only Python dependencies minimal (only OpenCV is required).
    Note: audio is NOT preserved with this method because OpenCV handles frames only.
    If you need audio preserved, use ffmpeg-based splitting instead.
    """
    clips = []
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


def split_video_ffmpeg(source_path: str, ranges: List[Tuple[float, float]], out_dir: str) -> List[str]:
    """Split using ffmpeg subprocess. Preserves audio when possible. Requires ffmpeg binary on PATH."""
    clips = []
    for idx, (start, end) in enumerate(ranges, start=1):
        out_file = os.path.join(out_dir, f"clip_{idx:02d}.mp4")
        # Try stream copy first (fast)
        cmd_copy = [
            'ffmpeg', '-y', '-ss', str(start), '-to', str(end), '-i', source_path,
            '-c', 'copy', out_file
        ]
        try:
            subprocess.run(cmd_copy, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        except subprocess.CalledProcessError:
            # Fallback: re-encode for frame-accurate and compatibility
            cmd_reencode = [
                'ffmpeg', '-y', '-ss', str(start), '-to', str(end), '-i', source_path,
                '-c:v', 'libx264', '-preset', 'fast', '-crf', '23', '-c:a', 'aac', '-b:a', '128k', out_file
            ]
            subprocess.run(cmd_reencode, check=True)
        clips.append(out_file)
    return clips


def main():
    st.set_page_config(page_title="YouTube Splitter", layout="centered")
    st.title("YouTube Video Splitter")

    st.markdown("Provide a direct video file (upload or a direct file URL), or paste a YouTube URL. The app will try to download YouTube videos using `pytube` (Python package). Example range formats: `00:00:10-00:00:30`, `1:00-2:30`, or `10-20`.")

    upload = st.file_uploader("Upload a video file (mp4/mov/mkv)", type=["mp4", "mov", "mkv"], accept_multiple_files=False)
    url = st.text_input("Or provide a direct video file or YouTube URL")

    # Mobile-friendly dynamic range inputs
    if 'num_ranges' not in st.session_state:
        st.session_state.num_ranges = 1

    st.markdown("#### Time ranges")
    st.markdown("Use HH:MM:SS, MM:SS or seconds. Add or remove ranges as needed.")

    remove_index = None
    for i in range(st.session_state.num_ranges):
        cols = st.columns([4, 4, 1])
        start_key = f"start_{i}"
        end_key = f"end_{i}"
        start_val = st.session_state.get(start_key, "")
        end_val = st.session_state.get(end_key, "")
        cols[0].text_input("Start", key=start_key, value=start_val, placeholder="00:00:00")
        cols[1].text_input("End", key=end_key, value=end_val, placeholder="00:00:10")
        if cols[2].button("Remove", key=f"remove_{i}"):
            remove_index = i

    cols_add = st.columns([1, 1])
    if cols_add[0].button("Add range"):
        # create next keys with empty values
        idx = st.session_state.num_ranges
        st.session_state[f"start_{idx}"] = ""
        st.session_state[f"end_{idx}"] = ""
        st.session_state.num_ranges += 1

    if remove_index is not None:
        # rebuild keys excluding the removed index
        new_pairs = []
        for j in range(st.session_state.num_ranges):
            if j == remove_index:
                continue
            new_pairs.append((st.session_state.get(f"start_{j}", ""), st.session_state.get(f"end_{j}", "")))
        # clear old keys
        for j in range(st.session_state.num_ranges):
            st.session_state.pop(f"start_{j}", None)
            st.session_state.pop(f"end_{j}", None)
        # write back
        for j, (s, e) in enumerate(new_pairs):
            st.session_state[f"start_{j}"] = s
            st.session_state[f"end_{j}"] = e
        st.session_state.num_ranges = len(new_pairs) if new_pairs else 1

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

        # Read ranges from dynamic inputs and validate each individually.
        invalid_inputs = []
        parsed_ranges: List[Tuple[float, float]] = []
        for i in range(st.session_state.num_ranges):
            s = st.session_state.get(f"start_{i}", "").strip()
            e = st.session_state.get(f"end_{i}", "").strip()
            if not s and not e:
                continue
            if not s or not e:
                invalid_inputs.append((i + 1, s, e, 'start or end missing'))
                continue
            try:
                start_s = parse_time_to_seconds(s)
                end_s = parse_time_to_seconds(e)
                if end_s <= start_s:
                    invalid_inputs.append((i + 1, s, e, 'end must be greater than start'))
                    continue
                parsed_ranges.append((start_s, end_s))
            except Exception as ex:
                invalid_inputs.append((i + 1, s, e, str(ex)))

        if not parsed_ranges and invalid_inputs:
            st.error(f"No valid ranges provided. First error: {invalid_inputs[0]}")
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
                    status.info("Detected YouTube URL — attempting to download with pytube first...")
                    # Use the included Python downloader (pytube) via ytDownloader
                    try:
                        success, result = download_video(url, output_path=tmp)
                        if success:
                            source_path = result
                            status.info("Downloaded via pytube.")
                        else:
                            # pytube reported an error; surface it
                            raise RuntimeError(f"pytube failed: {result}")
                    except Exception as ex:
                        # unexpected error from pytube usage
                        raise RuntimeError(f'pytube download failed: {ex}. Please ensure pytube is working or upload the video file manually.')
                else:
                    status.info("Downloading file from URL... (must be a direct file link)")
                    source_path = download_file_from_url(url, tmp, filename='source.mp4')

            status.info("File ready. Validating ranges against video duration...")

            # get duration using OpenCV
            cap_info = cv2.VideoCapture(source_path)
            if not cap_info.isOpened():
                # try to transcode with ffmpeg (if available) into an mp4 OpenCV can read
                if shutil.which('ffmpeg'):
                    status.info('Downloaded file not directly readable by OpenCV — attempting to transcode with ffmpeg...')
                    # To avoid issues with special characters or long paths in the original filename,
                    # copy the source to a safe temporary filename and run ffmpeg on that.
                    safe_input = os.path.join(tmp, 'source_input.mp4')
                    try:
                        shutil.copy2(source_path, safe_input)
                    except Exception:
                        # fallback to using original path if copy fails
                        safe_input = source_path
                    converted = os.path.join(tmp, 'source_converted.mp4')
                    cmd = ['ffmpeg', '-y', '-i', safe_input, '-c:v', 'libx264', '-c:a', 'aac', converted]
                    try:
                        proc = subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                        source_path = converted
                        cap_info = cv2.VideoCapture(source_path)
                    except subprocess.CalledProcessError as cpe:
                        stderr = cpe.stderr.decode('utf-8', errors='ignore') if cpe.stderr else str(cpe)
                        raise RuntimeError(f'ffmpeg failed to transcode file: {stderr}')
                else:
                    cap_info.release()
                    raise RuntimeError('Could not open downloaded video for duration check. The file may be in an unsupported container; install ffmpeg or upload the file manually.')
            fps = cap_info.get(cv2.CAP_PROP_FPS)
            if fps <= 0 or math.isnan(fps):
                fps = 30.0
            frame_count = int(cap_info.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
            duration = frame_count / fps if fps > 0 else 0
            cap_info.release()

            accepted_ranges: List[Tuple[float, float]] = []
            skipped_ranges: List[Tuple[float, float]] = []
            for (start_s, end_s) in parsed_ranges:
                if start_s >= duration:
                    skipped_ranges.append((start_s, end_s))
                else:
                    accepted_ranges.append((start_s, min(end_s, duration)))

            clips: List[str] = []
            if accepted_ranges:
                # prefer ffmpeg (preserves audio) if available, otherwise fall back to OpenCV
                if shutil.which('ffmpeg'):
                    status.info("ffmpeg found — performing audio-preserving splits...")
                    clips = split_video_ffmpeg(source_path, accepted_ranges, tmp)
                else:
                    status.warning("ffmpeg not found on PATH — falling back to OpenCV (audio will be dropped). Install ffmpeg to keep audio.")
                    clips = split_video_cv(source_path, accepted_ranges, tmp)
                st.session_state.clips = clips
                status.success(f"Created {len(clips)} clip(s). Scroll below to download.")
            else:
                status.info("No ranges to split after validating against video duration.")

            # Report invalid or skipped ranges to user
            if invalid_inputs:
                st.warning("Some range inputs were invalid and skipped:")
                for idx, s, e, reason in invalid_inputs:
                    st.text(f"Range #{idx}: '{s}' - '{e}'  => {reason}")
            if skipped_ranges:
                st.warning("Some ranges started after video end and were skipped:")
                for s, e in skipped_ranges:
                    st.text(f"{s} - {e} (video duration {duration:.2f}s)")
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
    st.markdown("Notes: This app uses `pytube` (Python package) to download YouTube links and OpenCV to trim video frames. OpenCV trimming will NOT preserve audio. If you need audio-preserving splits, install `ffmpeg` and ask me to switch trimming to use it.")


if __name__ == '__main__':
    main()
