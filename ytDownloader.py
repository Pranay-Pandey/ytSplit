"""Utility module to download YouTube videos and fetch basic metadata.

This module provides simple functions without web framework dependencies so it can be
used from the Streamlit app or called as a CLI tool.

Functions:
- is_valid_youtube_url(url) -> bool
- get_video_info(url) -> (dict, None) or (None, error_str)
- download_video(url, resolution=None, output_path=None) -> (True, filepath) or (False, error_str)

Requires: pytubefix (pip install pytubefix)
"""

from pytubefix import YouTube
import re
import json
import os
import argparse
import sys
from typing import Optional, Tuple, Dict


def is_valid_youtube_url(url: str) -> bool:
    """Return True if URL looks like a YouTube watch or youtu.be link.

    This is a permissive check — yt-dlp/pytube will perform the authoritative validation.
    """
    if not isinstance(url, str) or not url:
        return False
    pattern = r"^(https?://)?(www\.)?(youtube\.com|youtu\.be)/"
    return re.match(pattern, url) is not None


def get_video_info(url: str) -> Tuple[Optional[Dict], Optional[str]]:
    """Return basic metadata for a YouTube video.

    Returns (info_dict, None) on success or (None, error_message) on failure.
    """
    try:
        yt = YouTube(url)
        info = {
            "title": yt.title,
            "author": yt.author,
            "length": yt.length,  # seconds
            "views": yt.views,
            "description": yt.description,
            "publish_date": str(yt.publish_date),
        }
        return info, None
    except Exception as e:
        return None, str(e)


def download_video(url: str, resolution: Optional[str] = None, output_path: Optional[str] = None) -> Tuple[bool, Optional[str]]:
    """Download a YouTube video.

    - resolution: optional string like '720p' to choose a progressive stream at that resolution.
    - output_path: optional directory or full file path. If directory provided, the stream's default filename is used.

    Returns (True, saved_filepath) on success, or (False, error_message) on failure.
    """
    try:
        yt = YouTube(url)
        # pick a progressive mp4 stream (contains audio)
        stream = None
        if resolution:
            stream = yt.streams.filter(progressive=True, file_extension='mp4', res=resolution).first()
        if stream is None:
            # fallback to highest progressive mp4
            stream = yt.streams.get_highest_resolution()
        if stream is None:
            return False, 'No suitable progressive MP4 stream found for this video.'

        # Determine output path
        if output_path:
            # if a directory, use stream.default_filename inside it
            if os.path.isdir(output_path) or output_path.endswith(os.sep):
                target_dir = output_path
                filename = stream.default_filename
                out_file = os.path.join(target_dir, filename)
            else:
                # treat as full path
                out_file = output_path
                target_dir = os.path.dirname(out_file) or os.getcwd()
        else:
            target_dir = os.getcwd()
            out_file = None

        # ensure target dir exists
        os.makedirs(target_dir, exist_ok=True)

        if out_file:
            # pytube's download can accept output_path and filename separately
            stream.download(output_path=target_dir, filename=os.path.basename(out_file))
            return True, out_file
        else:
            saved = stream.download(output_path=target_dir)
            return True, saved
    except Exception as e:
        return False, str(e)


def _cli():
    parser = argparse.ArgumentParser(description='Download YouTube videos or show metadata using pytube')
    parser.add_argument('url', help='YouTube video URL')
    parser.add_argument('--info', action='store_true', help='Print video info as JSON and exit')
    parser.add_argument('--resolution', '-r', help='Preferred resolution (e.g. 720p)')
    parser.add_argument('--output', '-o', help='Output directory or filename')

    args = parser.parse_args()
    url = args.url
    if not is_valid_youtube_url(url):
        print(json.dumps({'error': 'Invalid YouTube URL'}))
        sys.exit(2)

    if args.info:
        info, err = get_video_info(url)
        if err:
            print(json.dumps({'error': err}))
            sys.exit(1)
        print(json.dumps(info, indent=2))
        return

    success, result = download_video(url, resolution=args.resolution, output_path=args.output)
    if success:
        print(json.dumps({'message': 'Downloaded', 'path': result}))
    else:
        print(json.dumps({'error': result}))
        sys.exit(1)


if __name__ == '__main__':
    _cli()